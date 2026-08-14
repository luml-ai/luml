/**
 * Every mutating gesture the workbench makes, and the intent it makes it under.
 *
 * `intent` is the journal's mandatory field, so it is required here too rather
 * than defaulted: a transaction the timeline cannot describe is one nobody can
 * rewind to on purpose. The wordings below are the UI's auto-intents, the
 * counterpart of the `-m` an agent passes on the CLI.
 *
 * Optimistic only where the store is. An edit carries the `definition_hash` it
 * started from and renders pending until its transaction lands; a run is never
 * optimistic, because what it will do is a preflight the daemon computes and
 * what it did is a materialization it records.
 */

import type { EditedCell, FlowMethods } from '@/flow/api/client'
import type {
  ConnectPrompt,
  EvalResult,
  FlowSettingsReport,
  HandoffGesture,
  HandoffPayload,
  Preflight,
  RunOutcome,
} from '@/flow/api/types'
import type { FlowSessionHandle } from './useFlowSession'

type Result<M extends keyof FlowMethods> = Promise<FlowMethods[M]['result']>

export interface FlowOps {
  preflight: (targets: string | string[], branch: string) => Promise<Preflight>
  run: (target: string, options: { branch: string; force?: boolean }) => Promise<RunOutcome>
  cancel: (branch: string) => Result<'cancel'>
  edit: (
    slug: string,
    source: string,
    options: { branch: string; base?: string; force?: boolean },
  ) => Promise<EditedCell>
  addCell: (options: {
    branch: string
    slug?: string
    after?: string
    source?: string
  }) => Promise<EditedCell>
  deleteCell: (slug: string, options: { branch: string; force?: boolean }) => Result<'cells.delete'>
  setEager: (slug: string, on: boolean, branch: string) => Result<'cells.eager'>
  rename: (
    slug: string,
    to: string,
    options: { branch: string; force?: boolean },
  ) => Result<'rename'>
  fork: (name: string, from: string) => Result<'fork'>
  checkout: (branch: string, options?: { force?: boolean }) => Result<'switch'>
  rewind: (toStep: number, options: { branch: string; force?: boolean }) => Result<'rewind'>
  /** The one op whose intent is the user's own words rather than an auto-intent. */
  checkpoint: (intent: string, branch: string) => Result<'checkpoint'>
  adopt: (
    slug: string,
    from: string,
    options: { branch: string; force?: boolean },
  ) => Result<'adopt'>
  archive: (branch: string) => Result<'archive'>
  promote: (target: string, branch: string) => Result<'promote'>
  /** Reads, not mutations — they carry no intent because they journal nothing. */
  handoff: (
    gesture: HandoffGesture,
    options: { branch: string; slug?: string; branches?: string[] },
  ) => Promise<HandoffPayload>
  /** Flow-scoped: an agent connects to the workspace, not to a branch. */
  connect: () => Promise<ConnectPrompt>
  evaluate: (code: string, branch: string) => Promise<EvalResult>
  saveSettings: (settings: Partial<FlowSettingsReport>) => Result<'settings.set'>
  addPackages: (packages: string[]) => Result<'env.add'>
  removePackages: (packages: string[]) => Result<'env.remove'>
  restartKernel: () => Result<'kernel.restart'>
}

export function useFlowOps(session: FlowSessionHandle): FlowOps {
  const flow = () => session.brief.value?.path

  return {
    // One target or several: rerunning a branch to its leaves is one closure,
    // so a parent two leaves share is costed the once it will run.
    preflight: (targets, branch) =>
      session.request('preflight', {
        flow: flow(),
        branch,
        ...(Array.isArray(targets) ? { targets } : { target: targets }),
      }),

    run: (target, { branch, force }) =>
      session.request('run', {
        flow: flow(),
        branch,
        target,
        force,
        intent: force ? `force rerun ${target}` : `run ${target}`,
      }),

    // Named for what it is: leaving a run, which only stops it when no other
    // branch is still awaiting the result.
    cancel: (branch) => session.request('cancel', { flow: flow(), branch }),

    edit: (slug, source, { branch, base, force }) =>
      session.request('cells.edit', {
        flow: flow(),
        branch,
        slug,
        source,
        base,
        force,
        intent: force ? `overwrote ${slug}` : `edited ${slug}`,
      }),

    addCell: ({ branch, slug, after, source }) =>
      session.request('cells.new', {
        flow: flow(),
        branch,
        slug,
        after,
        source,
        intent: intentFor({ slug, after, source }),
      }),

    deleteCell: (slug, { branch, force }) =>
      session.request('cells.delete', {
        flow: flow(),
        branch,
        slug,
        force,
        intent: `deleted ${slug} from ${branch}`,
      }),

    // Reactivity, not a run: this decides whether the cell rematerializes
    // without being asked, so it carries no intent and journals nothing.
    setEager: (slug, on, branch) =>
      session.request('cells.eager', { flow: flow(), branch, slug, eager: on }),

    rename: (slug, to, { branch, force }) =>
      session.request('rename', {
        flow: flow(),
        branch,
        slug,
        to,
        force,
        intent: `renamed ${slug} to ${to}`,
      }),

    fork: (name, from) =>
      session.request('fork', {
        flow: flow(),
        branch: from,
        name,
        from_branch: from,
        intent: `started ${name} from ${from}`,
      }),

    checkout: (branch, options) =>
      session.request('switch', {
        flow: flow(),
        branch,
        force: options?.force,
        intent: `put ${branch} on disk`,
      }),

    rewind: (toStep, { branch, force }) =>
      session.request('rewind', {
        flow: flow(),
        branch,
        to_step: toStep,
        force,
        intent: `rewound ${branch}`,
      }),

    // The intent is not written here. Every other verb above carries an
    // auto-intent because the gesture says what happened; a checkpoint's whole
    // content is what the user meant by it, so there is nothing to default to.
    checkpoint: (intent, branch) =>
      session.request('checkpoint', { flow: flow(), branch, intent }),

    adopt: (slug, from, { branch, force }) =>
      session.request('adopt', {
        flow: flow(),
        branch,
        slug,
        from_branch: from,
        force,
        intent: `adopted ${slug} from ${from}`,
      }),

    archive: (branch) =>
      session.request('archive', { flow: flow(), branch, intent: `archived ${branch}` }),

    promote: (target, branch) =>
      session.request('promote', {
        flow: flow(),
        branch,
        target,
        intent: `promoted ${target}`,
      }),

    // The gesture is the whole request: what a handoff carries is the daemon's
    // to decide, so no surface gets to assemble a thinner version of it.
    handoff: (gesture, { branch, slug, branches }) =>
      session.request('agent.payload', { flow: flow(), branch, gesture, slug, branches }),

    // The prompt names the branch the files are on, which is the workspace's
    // fact and not this screen's — so the viewed branch is deliberately absent.
    connect: () => session.request('agent.connect', { flow: flow() }),

    // A read of what the branch already observed. The names hydrate as copies,
    // so this writes no version, no materialization and no journal line.
    evaluate: (code, branch) => session.request('eval', { flow: flow(), branch, code }),

    // Config rather than history — which is why it carries no intent and lands
    // in `flow.yaml` instead of the journal.
    saveSettings: (settings) => session.request('settings.set', { flow: flow(), ...settings }),

    addPackages: (packages) =>
      session.request('env.add', {
        flow: flow(),
        packages,
        intent: `added ${packages.join(', ')} to the workspace env`,
      }),

    removePackages: (packages) =>
      session.request('env.remove', {
        flow: flow(),
        packages,
        intent: `removed ${packages.join(', ')} from the workspace env`,
      }),

    restartKernel: () => session.request('kernel.restart', { flow: flow() }),
  }
}

/**
 * A new cell arrives three ways and the timeline has to tell them apart: added
 * blank, added downstream of something, or duplicated from a cell whose source
 * came along with it.
 */
function intentFor(options: { slug?: string; after?: string; source?: string }): string {
  if (options.source) return `duplicated a cell as ${options.slug ?? 'a new cell'}`
  if (options.after) return `added a cell downstream of ${options.after}`
  return 'added a cell'
}
