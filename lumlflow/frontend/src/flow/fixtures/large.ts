/**
 * Stress fixture: ~150 assets, 20 branches.
 *
 * Generated rather than hand-authored, but shaped like real work: a wide EDA
 * fringe hanging off the raw frame, a narrow trunk through cleaning and feature
 * building, then a fan into model families and a sweep underneath each.
 *
 * The point of this fixture is that divergence is *mid-graph*. Branches differ
 * at `Features` or at the model, which means every asset below the split is a
 * different version in every branch — materialization divergence, transitively
 * closed. A concept that draws one node per branch-version here will render
 * roughly 900 nodes and be unusable. That is the finding, not a bug in the data.
 */

import type { AssetVersion, Branch, FlowSession, Materialization, Transaction } from '../types'
import { curve, makeMaterialization, makeVersion, seeded } from './helpers'

const rand = seeded(20260809)
const versions: AssetVersion[] = []
const materializations: Record<string, Materialization> = {}

const agents = ['human', 'agent-1', 'agent-2', 'agent-3', 'agent-4']

const add = (
  assetId: string,
  name: string,
  kind: AssetVersion['definition']['kind'],
  deps: string[],
  tag: string,
  step: number,
  intent: string,
  params: Record<string, number | string> = {},
): AssetVersion => {
  const version = makeVersion({
    assetId,
    name,
    kind,
    deps,
    params,
    source: `class ${name}(Asset):\n    """${intent}"""\n${deps
      .map((dep, index) => `    dep_${index}: ${dep}`)
      .join('\n')}\n\n    def materialize(self) -> ${kind[0].toUpperCase()}${kind.slice(1)}:\n        ...`,
    doc: intent,
    outputs: [{ name: 'value', kind, content: `${assetId}-${tag}` }],
    step,
    author: agents[Math.floor(rand() * agents.length)],
    intent,
    tag,
  })
  versions.push(version)
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: deps.map((dep) => `${dep}@${tag}`),
    costSeconds: kind === 'experiment' ? 120 + Math.round(rand() * 2400) : Math.round(rand() * 30),
    cached: rand() > 0.25,
    values:
      kind === 'experiment'
        ? {
            value: {
              type: 'experiment',
              runName: `${assetId}-${tag}`,
              config: params,
              curves: [{ name: 'auc', points: curve(30, 0.6, 0.8 + rand() * 0.08, 0.01, step) }],
              finalMetrics: { auc: Number((0.78 + rand() * 0.09).toFixed(4)) },
              checkpointRef: `ckpt/${assetId}-${tag}`,
            },
          }
        : { value: { type: 'note', markdown: intent } },
    metrics: kind === 'experiment' ? { auc: Number((0.78 + rand() * 0.09).toFixed(4)) } : undefined,
  })
  return version
}

// Trunk
add('l_raw', 'RawEvents', 'source', [], 'v1', 1, 'Nightly event export')
const edaAssets: string[] = []
for (let i = 0; i < 18; i++) {
  const id = `l_eda_${i}`
  add(id, `Explore${i}`, i % 3 === 0 ? 'note' : 'plot', ['l_raw'], 'v1', 2 + i, `Explore slice ${i} of the raw events`)
  edaAssets.push(id)
}
add('l_clean', 'CleanEvents', 'frame', ['l_raw'], 'v1', 22, 'Drop malformed rows and coerce types')
for (let i = 0; i < 6; i++) {
  add(`l_qc_${i}`, `QualityCheck${i}`, 'plot', ['l_clean'], 'v1', 24 + i, `Quality check ${i} after cleaning`)
}

// Feature layer: three definition variants, the only real fan
const featureTags = ['v1', 'v2', 'v3']
for (const [index, tag] of featureTags.entries()) {
  const version = makeVersion({
    assetId: 'l_features',
    name: 'Features',
    kind: 'frame',
    deps: ['l_clean'],
    params: { window_days: 7 * (index + 1) },
    source: `class Features(Asset):\n    """Rolling aggregates over a ${7 * (index + 1)}-day window."""\n    clean: CleanEvents\n    window_days: int = ${7 * (index + 1)}\n\n    def materialize(self) -> Frame:\n        return rolling(self.clean, self.window_days)`,
    doc: `Rolling aggregates over a ${7 * (index + 1)}-day window.`,
    outputs: [{ name: 'value', kind: 'frame', content: `features-${tag}` }],
    step: 30 + index,
    author: 'agent-1',
    intent: `Try a ${7 * (index + 1)}-day feature window`,
    tag,
  })
  versions.push(version)
  materializations[version.versionId] = makeMaterialization(version, {
    inputVersionIds: ['l_clean@v1'],
    costSeconds: 45,
    values: { value: { type: 'note', markdown: version.definition.doc } },
  })
}

add('l_split', 'Split', 'frame', ['l_features'], 'v1', 34, 'Time-ordered train/validation split')

const modelFamilies = ['GBM', 'RandomForest', 'MLP', 'Linear']
const modelAssets: string[] = []
for (const [index, family] of modelFamilies.entries()) {
  const id = `l_model_${family.toLowerCase()}`
  modelAssets.push(id)
  add(id, `Train${family}`, 'experiment', ['l_split'], 'v1', 36 + index, `Train a ${family} baseline`, {
    seed: 42,
  })
  add(`l_eval_${family.toLowerCase()}`, `Eval${family}`, 'eval', [id, 'l_split'], 'v1', 40 + index, `Score ${family} on validation`)
  for (let s = 0; s < 4; s++) {
    add(
      `l_sweep_${family.toLowerCase()}_${s}`,
      `Sweep${family}${s}`,
      'experiment',
      ['l_split'],
      'v1',
      44 + index * 4 + s,
      `Sweep ${family} configuration ${s}`,
      { config: s },
    )
  }
}

add('l_leaderboard', 'Leaderboard', 'frame', modelAssets, 'v1', 70, 'Rank every model family by validation AUC')
add('l_report', 'Report', 'note', ['l_leaderboard'], 'v1', 71, 'Weekly write-up')

for (let i = 0; i < 40; i++) {
  add(`l_diag_${i}`, `Diagnostic${i}`, i % 2 === 0 ? 'plot' : 'metric', ['l_leaderboard'], 'v1', 72 + i, `Diagnostic ${i} over the leaderboard`)
}

const assets: Record<string, AssetVersion[]> = {}
for (const version of versions) {
  assets[version.assetId] = assets[version.assetId] ?? []
  assets[version.assetId].push(version)
}

const baseSelection: Record<string, string> = {}
for (const [assetId, list] of Object.entries(assets)) {
  baseSelection[assetId] = list[0].versionId
}

const branches: Record<string, Branch> = {
  main: {
    branchId: 'main',
    name: 'main',
    parentBranchId: null,
    forkedAtStep: 0,
    selection: baseSelection,
    pins: {},
    color: '#64748b',
    archived: false,
  },
}

const palette = ['#2563eb', '#7c3aed', '#0d9488', '#d97706', '#dc2626', '#db2777', '#0891b2', '#65a30d']
for (let i = 0; i < 19; i++) {
  const featureTag = featureTags[i % featureTags.length]
  const family = modelFamilies[i % modelFamilies.length].toLowerCase()
  branches[`exp-${i}`] = {
    branchId: `exp-${i}`,
    name: `exp/${family}-w${featureTag}`,
    parentBranchId: 'main',
    forkedAtStep: 30 + i,
    selection: { ...baseSelection, l_features: `l_features@${featureTag}` },
    pins: i % 4 === 0 ? { l_clean: 'l_clean@v1' } : {},
    color: palette[i % palette.length],
    archived: i > 14,
    sweepGroup: i >= 8 ? 'family-sweep' : undefined,
  }
}

/**
 * Model and sweep work lands on the fork that asked for it; the trunk keeps the
 * shared pipeline. Putting every transaction on `main` leaves a rail with
 * nineteen empty lanes and no history at any fork point.
 */
function buildTransactions(): Transaction[] {
  const expBranches = Object.values(branches).filter((branch) => branch.branchId !== 'main')
  const forked = new Set<string>()

  // Every fork is an event in its own right, so a lane that never went on to
  // produce an asset is still a line with a beginning rather than a bare stripe.
  const transactions: Transaction[] = expBranches.map((branch) => {
    forked.add(branch.branchId)
    return {
      txId: `ltx-fork-${branch.branchId}`,
      step: branch.forkedAtStep,
      branchId: branch.branchId,
      author: 'agent-1',
      intent: `Start ${branch.name}`,
      ops: [
        { op: 'fork-branch', branchId: branch.branchId, fromBranchId: 'main', name: branch.name },
      ],
      settled: true,
    }
  })

  const onFork = (assetId: string): boolean =>
    assetId.startsWith('l_model_') || assetId.startsWith('l_sweep_') || assetId.startsWith('l_eval_')

  versions.forEach((version, index) => {
    const step = version.createdAtStep
    const candidates = expBranches.filter((branch) => branch.forkedAtStep <= step)
    const branch =
      onFork(version.assetId) && candidates.length
        ? candidates[index % candidates.length]
        : branches.main

    const ops: Transaction['ops'] = []
    if (branch.branchId !== 'main' && !forked.has(branch.branchId)) {
      forked.add(branch.branchId)
      ops.push({
        op: 'fork-branch',
        branchId: branch.branchId,
        fromBranchId: 'main',
        name: branch.name,
      })
    }
    ops.push({ op: 'create-asset', assetId: version.assetId, version })

    transactions.push({
      txId: `ltx-${index}`,
      step,
      branchId: branch.branchId,
      author: version.authoredBy,
      intent: version.intent,
      ops,
      settled: index % 5 === 4,
    })
  })

  return transactions
}

export const largeSession: FlowSession = {
  sessionId: 'session-large',
  name: 'events model bake-off',
  projectName: 'events-platform',
  scenario: 'churn',
  createdAt: '2026-07-30T08:00:00Z',
  assets,
  materializations,
  branches,
  agents: {
    human: { agentId: 'human', label: 'You', color: '#0f172a', activeBranchId: 'main', activeAssetId: null },
    'agent-1': { agentId: 'agent-1', label: 'claude-1', color: '#2563eb', activeBranchId: 'exp-0', activeAssetId: 'l_features' },
    'agent-2': { agentId: 'agent-2', label: 'claude-2', color: '#0d9488', activeBranchId: 'exp-3', activeAssetId: 'l_model_mlp' },
    'agent-3': { agentId: 'agent-3', label: 'codex-1', color: '#d97706', activeBranchId: 'exp-7', activeAssetId: 'l_sweep_gbm_2' },
    'agent-4': { agentId: 'agent-4', label: 'gemini-1', color: '#db2777', activeBranchId: 'exp-11', activeAssetId: 'l_leaderboard' },
  },
  transactions: buildTransactions(),
  headBranchId: 'main',
}
