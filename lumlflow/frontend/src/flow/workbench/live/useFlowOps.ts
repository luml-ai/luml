/**
 * Every mutating gesture the workbench makes, and the intent it makes it under.
 *
 * `intent` is the journal's mandatory field, so it is required here too rather
 * than defaulted: a transaction the timeline cannot describe is one nobody can
 * rewind to on purpose. The wordings below are the UI's auto-intents, the
 * counterpart of the `-m` an agent passes on the CLI.
 *
 * An edit carries the `definition_hash` it started from; a run is never
 * optimistic, because what it will do is a preflight the daemon computes and
 * what it did is a materialization it records.
 */

import { getCurrentInstance, inject, type InjectionKey } from 'vue'
import type { EditedCell, FlowMethods } from '@/flow/api/client'
import type {
  CellContextPayload,
  EvalResult,
  FlowBrief,
  FlowSettingsReport,
  Preflight,
  RunOutcome,
} from '@/flow/api/types'
import type { FlowSessionHandle } from './useFlowSession'

type Result<M extends keyof FlowMethods> = Promise<FlowMethods[M]['result']>

export interface FlowOps {
  preflight: (targets: string | string[], branch: string) => Promise<Preflight>
  run: (
    target: string | undefined,
    options: { branch: string; force?: boolean },
  ) => Promise<RunOutcome>
  cancel: (branch: string) => Result<'cancel'>
  edit: (
    slug: string,
    source: string,
    options: { branch: string; base: string; force?: boolean },
  ) => Promise<EditedCell>
  addCell: (options: {
    branch: string
    slug?: string
    after?: string
    anchor?: string
    source?: string
  }) => Promise<EditedCell>
  reorder: (
    slug: string,
    options: { branch: string; before?: string; after?: string },
  ) => Result<'cells.reorder'>
  deleteCell: (slug: string, options: { branch: string }) => Result<'cells.delete'>
  setEager: (slug: string, on: boolean, branch: string) => Result<'cells.eager'>
  rename: (slug: string, to: string, options: { branch: string }) => Result<'rename'>
  fork: (name: string, from: string) => Result<'fork'>
  checkout: (branch: string) => Result<'switch'>
  rewind: (toStep: number, options: { branch: string }) => Result<'rewind'>
  /**
   * The one op whose intent is the user's own words rather than an auto-intent.
   * The words attach to `step` — the one the timeline showed as current — and
   * add no step of their own.
   */
  checkpoint: (intent: string, branch: string, step: number) => Result<'checkpoint'>
  adopt: (
    slug: string,
    from: string,
    options: { branch: string; force?: boolean },
  ) => Result<'adopt'>
  archive: (branch: string) => Result<'archive'>
  /** A read copied from one card; it carries no intent because it journals nothing. */
  copyContext: (slug: string, branch: string) => Promise<CellContextPayload>
  evaluate: (code: string, branch: string) => Promise<EvalResult>
  saveSettings: (settings: Partial<FlowSettingsReport>) => Result<'settings.set'>
  restartKernel: () => Result<'kernel.restart'>
}

/**
 * Asked before any op that moves a branch. It answers with the branch the op
 * should land on — the same one, or a lane just started from where it stands —
 * or `null` when the reader stepped back from the gesture.
 *
 * A branch that was rewound stands behind its newest step, and a change made
 * there moves it on from that step. The page owning the dialog provides this
 * so every card and page asks the same question the same way.
 */
export type MoveGuard = (branch: string) => Promise<string | null>

export const MOVE_GUARD: InjectionKey<MoveGuard> = Symbol('lumlflow.move-guard')

/** The reader stepped back from a gesture the guard asked about. Not a refusal. */
export class MoveCancelled extends Error {
  constructor() {
    super('stayed where the lane stands')
    this.name = 'MoveCancelled'
  }
}

export function useFlowOps(
  session: FlowSessionHandle,
  options: { guard?: MoveGuard } = {},
): FlowOps {
  const flow = () => session.brief.value?.path
  // The page that owns the dialog hands its guard in directly — a component
  // cannot inject what it provides itself — and everything under it injects.
  const guard = options.guard ?? (getCurrentInstance() ? inject(MOVE_GUARD, null) : null)

  /** The branch a moving op lands on, once the guard — when one is provided — has answered. */
  async function onto(branch: string): Promise<string> {
    if (guard === null) return branch
    const target = await guard(branch)
    if (target === null) throw new MoveCancelled()
    return target
  }

  function applyBrief(next: FlowBrief): void {
    const current = session.brief.value
    if (current === null) return
    session.brief.value = {
      ...current,
      flow: next.flow,
      path: next.path,
      branch: next.branch,
      checked_out: next.checked_out,
      agent: next.agent,
      kernel: next.kernel,
      settings: next.settings,
    }
  }

  return {
    // One target or several: rerunning a branch to its leaves is one closure,
    // so a parent two leaves share is costed the once it will run.
    preflight: (targets, branch) =>
      session.request('preflight', {
        flow: flow(),
        branch,
        ...(Array.isArray(targets) ? { targets } : { target: targets }),
      }),

    run: async (target, { branch: asked, force }) => {
      const branch = await onto(asked)
      return session.request('run', {
        flow: flow(),
        branch,
        ...(target ? { target } : {}),
        force,
        intent: `${force ? 'force rerun' : target ? 'run' : 'rerun'} ${target ?? branch}`,
      })
    },

    // Named for what it is: leaving a run, which only stops it when no other
    // branch is still awaiting the result.
    cancel: (branch) => session.request('cancel', { flow: flow(), branch }),

    edit: async (slug, source, { branch: asked, base, force }) => {
      const branch = await onto(asked)
      return session.request('cells.edit', {
        flow: flow(),
        branch,
        slug,
        source,
        base,
        force,
        intent: force ? `overwrote ${slug}` : `edited ${slug}`,
      })
    },

    addCell: async ({ branch: asked, slug, after, anchor, source }) => {
      const branch = await onto(asked)
      return session.request('cells.new', {
        flow: flow(),
        branch,
        slug,
        after,
        anchor,
        source,
        intent: intentFor({ slug, after, source }),
      })
    },

    reorder: async (slug, { branch: asked, before, after }) => {
      const branch = await onto(asked)
      return session.request('cells.reorder', {
        flow: flow(),
        branch,
        slug,
        before,
        after,
      })
    },

    deleteCell: async (slug, { branch: asked }) => {
      const branch = await onto(asked)
      return session.request('cells.delete', {
        flow: flow(),
        branch,
        slug,
        intent: `deleted ${slug} from ${branch}`,
      })
    },

    // Reactivity, not a run: this decides whether the cell rematerializes
    // without being asked, so it carries no intent and journals nothing.
    setEager: (slug, on, branch) =>
      session.request('cells.eager', { flow: flow(), branch, slug, eager: on }),

    rename: async (slug, to, { branch: asked }) => {
      const branch = await onto(asked)
      return session.request('rename', {
        flow: flow(),
        branch,
        slug,
        to,
        intent: `renamed ${slug} to ${to}`,
      })
    },

    fork: (name, from) =>
      session.request('fork', {
        flow: flow(),
        branch: from,
        name,
        from_branch: from,
        intent: `started ${name} from ${from}`,
      }),

    checkout: async (branch) => {
      const switched = await session.request('switch', {
        flow: flow(),
        branch,
        intent: `put ${branch} on disk`,
      })
      applyBrief(switched)
      return switched
    },

    rewind: async (toStep, { branch }) => {
      const rewound = await session.request('rewind', {
        flow: flow(),
        branch,
        to_step: toStep,
        intent: `rewound ${branch}`,
      })
      applyBrief(rewound)
      return rewound
    },

    // The intent is not written here. Every other verb above carries an
    // auto-intent because the gesture says what happened; a checkpoint's whole
    // content is what the user meant by it, so there is nothing to default to.
    checkpoint: (intent, branch, step) =>
      session.request('checkpoint', { flow: flow(), branch, step, intent }),

    adopt: async (slug, from, { branch: asked, force }) => {
      const branch = await onto(asked)
      return session.request('adopt', {
        flow: flow(),
        branch,
        slug,
        from_branch: from,
        force,
        intent: `adopted ${slug} from ${from}`,
      })
    },

    archive: (branch) =>
      session.request('archive', { flow: flow(), branch, intent: `archived ${branch}` }),

    copyContext: (slug, branch) => session.request('agent.payload', { flow: flow(), branch, slug }),

    // A read of what the branch already observed. The names hydrate as copies,
    // so this writes no version, no materialization and no journal line.
    evaluate: (code, branch) => session.request('eval', { flow: flow(), branch, code }),

    // Config rather than history — which is why it carries no intent and lands
    // in `flow.yaml` instead of the journal.
    saveSettings: (settings) => session.request('settings.set', { flow: flow(), ...settings }),

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
