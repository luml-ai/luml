import { getCurrentInstance, inject, type InjectionKey } from 'vue'
import type { EditedCell, FlowMethods } from '@/flow/api/client'
import type {
  CellContextPayload,
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
  checkpoint: (intent: string, branch: string, step: number) => Result<'checkpoint'>
  adopt: (
    slug: string,
    from: string,
    options: { branch: string; force?: boolean },
  ) => Result<'adopt'>
  archive: (branch: string) => Result<'archive'>
  copyContext: (slug: string, branch: string) => Promise<CellContextPayload>
  saveSettings: (settings: Partial<FlowSettingsReport>) => Result<'settings.set'>
  restartKernel: () => Result<'kernel.restart'>
}

export type MoveGuard = (branch: string) => Promise<string | null>

export const MOVE_GUARD: InjectionKey<MoveGuard> = Symbol('lumlflow.move-guard')

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
  const guard = options.guard ?? (getCurrentInstance() ? inject(MOVE_GUARD, null) : null)

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

    saveSettings: (settings) => session.request('settings.set', { flow: flow(), ...settings }),

    restartKernel: () => session.request('kernel.restart', { flow: flow() }),
  }
}

function intentFor(options: { slug?: string; after?: string; source?: string }): string {
  if (options.source) return `duplicated a cell as ${options.slug ?? 'a new cell'}`
  if (options.after) return `added a cell downstream of ${options.after}`
  return 'added a cell'
}
