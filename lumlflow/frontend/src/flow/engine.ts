/**
 * Derived views over a FlowSession.
 *
 * Everything here is computed, never hand-authored in a fixture — so a concept
 * that renders divergence, staleness, cost or integrity warnings is rendering
 * the same numbers as every other concept.
 */

import type {
  AssetDivergence,
  AssetId,
  AssetVersion,
  BranchId,
  DivergenceKind,
  FlowSession,
  IntegrityWarning,
  PreflightCost,
  Transaction,
  UnsyncedCause,
  VersionId,
} from './types'

export function versionsOf(session: FlowSession, assetId: AssetId): AssetVersion[] {
  return session.assets[assetId] ?? []
}

export function versionById(session: FlowSession, versionId: VersionId): AssetVersion | null {
  for (const versions of Object.values(session.assets)) {
    const hit = versions.find((v) => v.versionId === versionId)
    if (hit) return hit
  }
  return null
}

/** The assets present in a branch, with the version that branch selected. */
export function resolveSlice(
  session: FlowSession,
  branchId: BranchId,
): Record<AssetId, AssetVersion> {
  const branch = session.branches[branchId]
  if (!branch) return {}
  const slice: Record<AssetId, AssetVersion> = {}
  for (const [assetId, versionId] of Object.entries(branch.selection)) {
    const version = versionsOf(session, assetId).find((v) => v.versionId === versionId)
    if (version) slice[assetId] = version
  }
  return slice
}

/** Dependency order, so a slice can be rendered or read top to bottom. */
export function topoOrder(session: FlowSession, branchId: BranchId): AssetId[] {
  const slice = resolveSlice(session, branchId)
  const visited = new Set<AssetId>()
  const order: AssetId[] = []

  const visit = (assetId: AssetId): void => {
    if (visited.has(assetId)) return
    visited.add(assetId)
    for (const dep of slice[assetId]?.definition.deps ?? []) {
      if (slice[dep]) visit(dep)
    }
    order.push(assetId)
  }

  Object.keys(slice).forEach(visit)
  return order
}

export function downstreamOf(
  session: FlowSession,
  branchId: BranchId,
  assetId: AssetId,
): AssetId[] {
  const slice = resolveSlice(session, branchId)
  const out: AssetId[] = []
  const queue = [assetId]
  const seen = new Set<AssetId>([assetId])
  while (queue.length) {
    const current = queue.shift() as AssetId
    for (const [candidateId, version] of Object.entries(slice)) {
      if (version.definition.deps.includes(current) && !seen.has(candidateId)) {
        seen.add(candidateId)
        out.push(candidateId)
        queue.push(candidateId)
      }
    }
  }
  return out
}

/**
 * Why an asset reads as unsynced in this branch, or null if it is in sync.
 *
 * Non-transitive on purpose: an asset does not go unsynced because an *ancestor*
 * is unsynced, only when its own definition changed, its deps were rewired, or a
 * direct parent actually rematerialized with a different content hash. Without
 * this the whole canvas lights up on one edit.
 */
export function unsyncedCause(
  session: FlowSession,
  branchId: BranchId,
  assetId: AssetId,
): UnsyncedCause | null {
  const slice = resolveSlice(session, branchId)
  const version = slice[assetId]
  if (!version) return null

  const materialization = session.materializations[version.versionId]
  if (!materialization || materialization.state === 'never') return null
  if (materialization.state === 'failed') return null

  // Staleness is derived per branch rather than stored, because it is a property
  // of (branch, asset): the same version is in sync in the branch that authored
  // it and stale in a branch that pins a different upstream. Measured against
  // the branch's own baseline — its parent branch — so `main` reads clean.
  const parentBranchId = session.branches[branchId]?.parentBranchId
  if (parentBranchId) {
    const baseline = resolveSlice(session, parentBranchId)[assetId]
    if (baseline && baseline.versionId !== version.versionId) {
      if (baseline.definition.deps.join() !== version.definition.deps.join()) return 'deps-rewired'
      if (baseline.definitionHash !== version.definitionHash) return 'definition-changed'
    }
  }

  // A direct parent this branch selects is not the one this materialization
  // actually consumed — the cached value is real, but no longer current here.
  const consumed = new Set(materialization.inputVersionIds)
  if (consumed.size) {
    for (const depId of version.definition.deps) {
      const selectedParent = slice[depId]
      if (selectedParent && !consumed.has(selectedParent.versionId)) {
        return 'parent-rematerialized'
      }
    }
  }

  return null
}

/**
 * How two or more branches differ, per asset.
 *
 * `definition` means someone edited the asset; `materialization` means the code
 * is identical and only the inputs differ. The distinction is the difference
 * between a readable comparison and a wall of fans: definition divergence is
 * rare and structural, materialization divergence is transitively closed and so
 * covers most of the graph below any edit.
 */
export function divergence(session: FlowSession, branchIds: BranchId[]): AssetDivergence[] {
  const slices = branchIds.map((id) => resolveSlice(session, id))
  const allAssetIds = new Set<AssetId>()
  slices.forEach((slice) => Object.keys(slice).forEach((id) => allAssetIds.add(id)))

  const result: AssetDivergence[] = []
  for (const assetId of allAssetIds) {
    const byBranch: Record<BranchId, VersionId | null> = {}
    const definitionHashes = new Set<string>()
    const versionIds = new Set<string>()
    let missingSomewhere = false

    branchIds.forEach((branchId, index) => {
      const version = slices[index][assetId]
      byBranch[branchId] = version?.versionId ?? null
      if (!version) {
        missingSomewhere = true
        return
      }
      definitionHashes.add(version.definitionHash)
      versionIds.add(version.versionId)
    })

    let kind: DivergenceKind = 'none'
    if (definitionHashes.size > 1 || missingSomewhere) kind = 'definition'
    else if (versionIds.size > 1) kind = 'materialization'

    result.push({ assetId, kind, byBranch })
  }
  return result
}

/**
 * Cost of moving to a branch or checkpoint, split into what comes from cache and
 * what actually recomputes. Shown before the click, not after — the difference
 * between "instant" and "two hours" is the whole reactive-kernel promise.
 */
export function preflightCost(session: FlowSession, branchId: BranchId): PreflightCost {
  const slice = resolveSlice(session, branchId)
  const cachedAssetIds: AssetId[] = []
  const recomputeAssetIds: AssetId[] = []
  let totalSeconds = 0

  for (const [assetId, version] of Object.entries(slice)) {
    const materialization = session.materializations[version.versionId]
    if (materialization?.cached && materialization.state === 'materialized') {
      cachedAssetIds.push(assetId)
    } else {
      recomputeAssetIds.push(assetId)
      totalSeconds += materialization?.costSeconds ?? 0
    }
  }
  return { cachedAssetIds, recomputeAssetIds, totalSeconds }
}

/**
 * Upstream versions this branch pinned away from, filtered to those that would
 * actually change something it consumes.
 *
 * A bare "N updates available" count is permanently nonzero on an active trunk
 * and goes blind within a day. Running early cutoff hypothetically means we only
 * raise the notice when a content hash the branch reads would actually move.
 */
export function upstreamUpdates(
  session: FlowSession,
  branchId: BranchId,
): { assetId: AssetId; latestVersionId: VersionId; affects: AssetId[] }[] {
  const branch = session.branches[branchId]
  if (!branch) return []
  const updates: { assetId: AssetId; latestVersionId: VersionId; affects: AssetId[] }[] = []

  for (const [assetId, pinnedVersionId] of Object.entries(branch.pins)) {
    const versions = versionsOf(session, assetId)
    const latest = versions[versions.length - 1]
    if (!latest || latest.versionId === pinnedVersionId) continue

    const pinned = versions.find((v) => v.versionId === pinnedVersionId)
    const pinnedHashes = (pinned?.definition.outputs ?? []).map((o) => o.contentHash).join()
    const latestHashes = latest.definition.outputs.map((o) => o.contentHash).join()
    if (pinnedHashes === latestHashes) continue // early cutoff: nothing downstream moves

    updates.push({
      assetId,
      latestVersionId: latest.versionId,
      affects: downstreamOf(session, branchId, assetId),
    })
  }
  return updates
}

/**
 * Reasons a comparison across these branches may not be apples to apples.
 *
 * The flagship case is divergent pins: branches 1–8 accepted an upstream data
 * fix and 9–20 did not, so their metrics are not comparable — and nothing else
 * in the UI would say so. Content addressing lets us detect this exactly rather
 * than guess at it.
 */
export function integrityWarnings(
  session: FlowSession,
  branchIds: BranchId[],
): IntegrityWarning[] {
  const warnings: IntegrityWarning[] = []
  const slices = branchIds.map((id) => resolveSlice(session, id))

  const sharedAssetIds = Object.keys(slices[0] ?? {}).filter((assetId) =>
    slices.every((slice) => slice[assetId]),
  )

  for (const assetId of sharedAssetIds) {
    const versions = slices.map((slice) => slice[assetId])
    const isUpstream = versions[0].definition.deps.length === 0
    const hashes = new Set(versions.map((v) => v.definitionHash))
    if (isUpstream && hashes.size > 1) {
      warnings.push({
        kind: 'divergent-pin',
        message: `Lanes pin different versions of shared upstream \`${versions[0].definition.name}\`. Metrics below are not directly comparable.`,
        assetId,
        affectedBranchIds: branchIds,
      })
    }
  }

  for (const [index, slice] of slices.entries()) {
    const volatile = Object.values(slice).filter(
      (v) => v.definition.volatility === 'nondeterministic',
    )
    if (volatile.length) {
      warnings.push({
        kind: 'nondeterministic-input',
        message: `\`${volatile[0].definition.name}\` is non-deterministic; repeated materializations of the same version may differ.`,
        assetId: volatile[0].assetId,
        affectedBranchIds: [branchIds[index]],
      })
    }
  }

  const evalDatasets = slices.map(
    (slice) =>
      Object.values(slice).find((v) => v.definition.kind === 'eval')?.definition.params.dataset,
  )
  if (new Set(evalDatasets.filter(Boolean)).size > 1) {
    warnings.push({
      kind: 'dataset-mismatch',
      message: 'Evaluations ran on different datasets; results are limited to the intersection.',
      affectedBranchIds: branchIds,
    })
  }

  return warnings
}

/** Assets a run would skip because their materialization is already cached.
 *  Broadcast before the run so a mostly-cached replay does not look dead. */
export function cacheSkipSet(session: FlowSession, branchId: BranchId): AssetId[] {
  return preflightCost(session, branchId).cachedAssetIds
}

/** Transactions that left the branch settled — the states worth returning to. */
export function checkpoints(session: FlowSession, branchId?: BranchId): Transaction[] {
  return session.transactions.filter(
    (tx) => tx.settled && (!branchId || tx.branchId === branchId),
  )
}

export function branchLineage(session: FlowSession, branchId: BranchId): BranchId[] {
  const lineage: BranchId[] = []
  let current: BranchId | null = branchId
  while (current) {
    lineage.unshift(current)
    current = session.branches[current]?.parentBranchId ?? null
  }
  return lineage
}

/** Nearest common ancestor branch — the anchor for a smartlog-style history view. */
export function mergeBase(
  session: FlowSession,
  a: BranchId,
  b: BranchId,
): BranchId | null {
  const lineageA = branchLineage(session, a)
  const lineageB = new Set(branchLineage(session, b))
  for (let i = lineageA.length - 1; i >= 0; i--) {
    if (lineageB.has(lineageA[i])) return lineageA[i]
  }
  return null
}

export function formatCost(seconds: number): string {
  if (seconds < 1) return 'instant'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}
