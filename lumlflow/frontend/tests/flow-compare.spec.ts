/**
 * Comparing 2–5 branches, on the daemon's own diff.
 *
 * Three things carry this suite. The **collapse** is the point of the screen: a
 * definition edit renders once as the branching point, and everything below it
 * — same code, different inputs — is one row per asset with a chip per branch,
 * never a fan of identical-code nodes. **Comparability is checked**, so where
 * pin-at-fork stopped holding the warning renders before the numbers do. And
 * **adopt is pick-a-side**: a conflict writes nothing and hands the choice
 * back, rather than quietly taking one branch's version over another's.
 */

import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import { FlowApiError } from '@/flow/api/client'
import type { BranchDiff, BranchRecord } from '@/flow/api/types'
import LiveCompare from '@/flow/workbench/pages/LiveCompare.vue'
import { attach, flowStatus, FLOW, settle, storedPreview } from './fakes'
import type { Attached, Handlers } from './fakes'

const SWEEP = ['main', 'exp/lr-3e4', 'exp/lr-1e3', 'exp/lr-3e3', 'exp/lr-1e2']

/**
 * The sweep as the daemon reports it: one cell edited (in two versions across
 * five branches), three assets below it whose results merely moved, one note
 * only trunk carries — and a pin the trunk has moved past.
 */
function sweepDiff(overrides: Partial<BranchDiff> = {}): BranchDiff {
  return {
    flow: 'churn',
    branches: SWEEP,
    definition: [
      {
        slug: 'train_model',
        versions: SWEEP.map((branch, index) => ({
          branch,
          // Five branches, two versions: main and the first fork are still on
          // what they forked at, the other three took the same edit.
          slug: 'train_model',
          author: index === 0 ? 'user' : 'claude-1',
          step: index < 2 ? 12 : 14,
          flags: [],
          params: { lr: index < 2 ? 3e-4 : 1e-3, epochs: 24 },
          state: 'synced' as const,
          cost_seconds: 61,
          outputs: [
            {
              name: 'run',
              kind: 'experiment',
              kind_source: 'declared' as const,
              declared: 'experiment' as const,
              size: 2048,
              persisted: true,
              uploaded: index !== 4,
            },
            {
              name: 'model',
              kind: 'note',
              kind_source: 'matcher' as const,
              declared: 'model' as const,
              size: 8192,
              persisted: true,
              uploaded: false,
            },
          ],
        })),
      },
    ],
    materialization: ['holdout_eval', 'roc_curve', 'error_analysis'].map((slug) => ({
      slug,
      results: SWEEP.map((branch, index) => ({
        branch,
        state: index === 0 ? ('unsynced' as const) : ('synced' as const),
        cost_seconds: 0.4,
        outputs: [
          {
            name: 'scores',
            kind: 'metric',
            kind_source: 'matcher' as const,
            declared: 'asset' as const,
            size: 32,
            persisted: true,
            uploaded: false,
          },
        ],
      })),
    })),
    shapeless: [
      {
        slug: 'summary',
        branches: Object.fromEntries(
          SWEEP.map((branch) => [branch, branch === 'main' ? 'summary' : null]),
        ),
      },
    ],
    integrity: [
      {
        kind: 'divergent-pin',
        slug: 'sweep_config',
        branches: SWEEP.slice(1),
        message:
          '`sweep_config` is pinned where these branches forked and `main` has ' +
          'edited it since — their results were not computed against the same `sweep_config`',
      },
    ],
    ...overrides,
  }
}

function branchRecords(): BranchRecord[] {
  return SWEEP.map((branch, index) => ({
    branch,
    branch_id: `branch-${index}`,
    parent: index === 0 ? null : 'main',
    forked_at_step: index === 0 ? 0 : 12,
    archived: false,
    checked_out: index === 0,
    cells: 5,
    states: { synced: 5 },
    checkpoint: 20,
    last_intent: {
      step: 20 + index,
      ts: '2026-08-13T09:20:00Z',
      actor: 'claude-1',
      intent: 'swept the learning rate',
      offline: false,
      settled: index > 0,
    },
    agent: null,
  }))
}

const Empty = defineComponent({ template: '<div />' })

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/flow', component: Empty },
      { path: '/flow/:flowId', component: Empty },
      { path: '/flow/:flowId/compare', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

interface Bench {
  wrapper: VueWrapper
  live: Attached
  router: Router
}

async function compare(
  options: { handlers?: Handlers; compared?: string[]; at?: string } = {},
): Promise<Bench> {
  const compared = options.compared ?? SWEEP
  const live = await attach({
    status: flowStatus(),
    handlers: {
      diff: () => sweepDiff(),
      tree: () => ({ flow: 'churn', branch: 'main', branches: branchRecords() }),
      'asset.preview': (params) => ({
        flow: 'churn',
        branch: String(params.branch),
        slug: String(params.target),
        output: 'scores',
        state: 'synced',
        kind: 'metric',
        size: 32,
        persisted: true,
        preview: storedPreview('metric', [
          { block: 'kv', entries: { auc: 0.84 + SWEEP.indexOf(String(params.branch)) / 100 } },
        ]),
      }),
      set_focus: (params) => ({
        flow: 'churn',
        branch: String(params.branch ?? 'main'),
        asset: (params.asset as string | null) ?? null,
        compare: (params.compare as string[]) ?? [],
      }),
      ...options.handlers,
    },
  })
  const router = testRouter()
  await router.push(options.at ?? `/flow/${FLOW}/compare?branch=main&compare=${compared.join(',')}`)
  await router.isReady()
  const wrapper = mount(LiveCompare, {
    props: { session: live.session },
    global: { plugins: [router, ToastService] },
  })
  await settle()
  return { wrapper, live, router }
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

describe('the comparison collapses a wide sweep', () => {
  it('renders the edit once and everything below it one row per asset', async () => {
    const { wrapper, live } = await compare()

    // The selection is the graph's; this route asks for exactly those branches.
    expect(asked(live, 'diff')[0].branches).toEqual(SWEEP)

    const text = wrapper.text()
    // One branching point, whatever the branch count — and one side per
    // distinct version rather than per branch: five branches holding two
    // versions are two sides, and the params that differ are what they differ by.
    expect(text.match(/definition divergence/g)).toHaveLength(1)
    expect(text.match(/step 1\d/g)).toEqual(['step 12', 'step 14'])
    expect(text).toContain('0.0003')
    expect(text).toContain('0.001')
    // Same code, different inputs: one row per asset with a chip per branch.
    expect(text).toContain('same code, different inputs')
    for (const slug of ['holdout_eval', 'roc_curve', 'error_analysis']) {
      expect(text.match(new RegExp(slug, 'g'))).toHaveLength(1)
    }
    // The chips are the branches' own verdicts, in the runtime's words.
    expect(text).toContain('materialized')
    expect(text).toContain('stale')

    wrapper.unmount()
  })

  it('leads with the daemon’s first divergence and reports the focus', async () => {
    const { wrapper, live } = await compare()

    expect(wrapper.text()).toContain('Results · train_model')
    // Columns are one per compared branch, read off each one's stored preview.
    for (const branch of SWEEP) expect(wrapper.text()).toContain(branch)
    expect(asked(live, 'asset.preview').map((params) => params.branch)).toEqual(SWEEP)
    expect(wrapper.text()).toContain('0.84')

    // What the user is looking at is reported, so an agent's brief can say so.
    const focus = asked(live, 'set_focus').at(-1)
    expect(focus?.compare).toEqual(SWEEP)

    wrapper.unmount()
  })

  it('reads an experiment’s metrics as its results and its params as neither', async () => {
    const { wrapper } = await compare({
      handlers: {
        'asset.preview': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          slug: String(params.target),
          output: 'run',
          state: 'synced',
          kind: 'experiment',
          size: 2048,
          persisted: true,
          preview: storedPreview('experiment', [
            { block: 'markdown', text: '**params**' },
            { block: 'kv', entries: { lr: 0.0003, epochs: 24 } },
            { block: 'markdown', text: '**metrics**' },
            { block: 'kv', entries: { auc: 0.86 } },
          ]),
        }),
      },
    })

    // A setting listed under "final results" reads as an outcome nobody measured.
    const results = wrapper.text().slice(0, wrapper.text().indexOf('divergence'))
    expect(results).toContain('auc')
    expect(results).not.toContain('epochs')

    wrapper.unmount()
  })

  it('reads an experiment that never got to its metrics as holding no results', async () => {
    const { wrapper } = await compare({
      handlers: {
        'asset.preview': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          slug: String(params.target),
          output: 'run',
          state: 'synced',
          kind: 'experiment',
          size: 2048,
          persisted: true,
          preview: storedPreview('experiment', [
            { block: 'markdown', text: '**params**' },
            { block: 'kv', entries: { lr: 0.0003, epochs: 24 } },
          ]),
        }),
      },
    })

    // The run recorded what it was told to do and no number it got. Reading its
    // `lr` as the result would report a setting as an outcome nobody measured.
    const results = wrapper.text().slice(0, wrapper.text().indexOf('divergence'))
    expect(results).not.toContain('epochs')
    expect(results).toContain('no numbers to compare')

    wrapper.unmount()
  })

  it('says an output holds no numbers rather than that nothing materialized', async () => {
    const { wrapper } = await compare({
      handlers: {
        // Most kinds record no numbers at all — a frame previews as head rows.
        'asset.preview': (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          slug: String(params.target),
          output: 'features',
          state: 'synced',
          kind: 'frame',
          size: 4096,
          persisted: true,
          preview: storedPreview('frame', [
            {
              block: 'table',
              columns: ['id', 'churn'],
              dtypes: ['int64', 'bool'],
              rows: [[1, true]],
              total_rows: 4096,
            },
          ]),
        }),
      },
    })

    expect(wrapper.text()).toContain('frame · no numbers to compare')
    expect(wrapper.text()).not.toContain('nothing materialized here')

    wrapper.unmount()
  })

  it('says nothing materialized on a branch that stored no preview at all', async () => {
    const { wrapper } = await compare({
      handlers: {
        'asset.preview': () => {
          throw new FlowApiError('train_model has never run here', {
            kind: 'UnknownAsset',
            status: 404,
          })
        },
      },
    })

    expect(wrapper.text()).toContain('nothing materialized here')
    expect(wrapper.text()).not.toContain('no numbers to compare')

    wrapper.unmount()
  })

  it('lists what neither divergence shape covers, and what left the flow', async () => {
    const { wrapper } = await compare()

    // Absences and renames are exhaustive but secondary — behind a disclosure,
    // and not rendered at all until it is opened.
    expect(wrapper.text()).not.toContain('not on exp/lr-3e4')
    await wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text().startsWith('all differences'))!
      .trigger('click')
    await settle()
    expect(wrapper.text()).toContain('summary')
    expect(wrapper.text()).toContain('not on exp/lr-3e4')

    // Artifacts are the focused cell's outputs that leave the flow, in the word
    // each was declared under — a `metric` the flow keeps inline is not one —
    // with each branch's upload state, and no link where no screen answers.
    // Links are a follow-up action, so the section starts folded.
    await wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((header) => header.text().startsWith('Links'))!
      .trigger('click')
    await settle()
    const artifacts = wrapper.text().slice(wrapper.text().indexOf('Links'))
    expect(artifacts).toContain('run · experiment')
    expect(artifacts).toContain('model · model')
    expect(artifacts).not.toContain('scores')
    expect(artifacts).toContain('uploaded')
    expect(artifacts).toContain('not uploaded')
    expect(wrapper.find('a[href="/experiments"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('marks no column best, because no output declares which way it reads', async () => {
    const { wrapper } = await compare()

    // The green best-dot the fixture comparison draws is a claim the runtime
    // never recorded; a live comparison shows the numbers and ranks nothing.
    expect(wrapper.find('.text-emerald-600').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('higher is better')

    wrapper.unmount()
  })

  it('says the branches are the same rather than drawing an empty comparison', async () => {
    const { wrapper } = await compare({
      handlers: {
        diff: () =>
          sweepDiff({ definition: [], materialization: [], shapeless: [], integrity: [] }),
      },
    })

    expect(wrapper.text()).toContain('these lanes hold the same cells and the same results')
    expect(wrapper.text()).not.toContain('Final results')

    wrapper.unmount()
  })

  it('sends nobody to a comparison of one branch', async () => {
    const { wrapper, live } = await compare({ at: `/flow/${FLOW}/compare?branch=main` })

    expect(wrapper.text()).toContain('Pick 2–5 lanes there')
    expect(asked(live, 'diff')).toEqual([])

    wrapper.unmount()
  })
})

describe('comparability is checked, not assumed', () => {
  it('renders the daemon’s integrity warning above the results it qualifies', async () => {
    const { wrapper } = await compare()
    const text = wrapper.text()

    expect(text).toContain('divergent pin')
    expect(text).toContain('sweep_config')
    expect(text).toContain('were not computed against the same')
    // Above the numbers it qualifies: a side-by-side of two results computed
    // under different code is worse read than not read.
    expect(text.indexOf('divergent pin')).toBeLessThan(text.indexOf('divergence'))
    // The branches it affects are named — the trunk that moved on is not among
    // them, since it holds the version the others never picked up.
    const affects = wrapper.findAll('div').find((node) => node.text().startsWith('affects'))
    expect(affects?.text()).toContain('exp/lr-3e4')
    expect(affects?.text()).not.toContain('main')

    wrapper.unmount()
  })

  it('keeps quiet when the daemon reports nothing to warn about', async () => {
    const { wrapper } = await compare({
      handlers: { diff: () => sweepDiff({ integrity: [] }) },
    })

    expect(wrapper.text()).not.toContain('divergent pin')

    wrapper.unmount()
  })
})

describe('adopt is pick-a-side', () => {
  it('cherry-picks the chosen branch’s version onto the one compared from', async () => {
    const adopts: Record<string, unknown>[] = []
    const { wrapper, live } = await compare({
      handlers: {
        adopt: (params) => {
          adopts.push(params)
          return { slug: 'train_model', branch: 'main', rebound: [], projected: null }
        },
      },
    })

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Adopt'))!
      .trigger('click')
    await settle()

    expect(adopts).toHaveLength(1)
    expect(adopts[0]).toMatchObject({
      slug: 'train_model',
      from_branch: 'exp/lr-3e4',
      branch: 'main',
    })
    // Every mutating call carries the intent the journal will read back.
    expect(String(adopts[0].intent)).toContain('adopted train_model')
    // The comparison re-reads: the target branch now selects another version.
    expect(asked(live, 'diff').length).toBeGreaterThan(1)

    wrapper.unmount()
  })

  it('hands a three-way conflict back unwritten and takes the side the reader picks', async () => {
    const adopts: Record<string, unknown>[] = []
    const { wrapper } = await compare({
      handlers: {
        adopt: (params) => {
          adopts.push(params)
          if (!params.force) {
            throw new FlowApiError(
              'train_model was edited on both main and exp/lr-3e4 since they forked — pick a side',
              { kind: 'AdoptConflict', status: 409 },
            )
          }
          return { slug: 'train_model', branch: 'main', rebound: [], projected: null }
        },
      },
    })

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Adopt'))!
      .trigger('click')
    await settle()

    // Nothing was written, and the daemon's own sentence is what is shown.
    expect(wrapper.text()).toContain('edited on both main and exp/lr-3e4')
    expect(wrapper.text()).toContain('nothing changed.')
    expect(adopts.every((call) => !call.force)).toBe(true)

    const take = wrapper.findAll('button').find((button) => button.text().includes('take'))
    expect(take).toBeDefined()
    expect(wrapper.findAll('button').some((button) => button.text().includes('keep main'))).toBe(
      true,
    )

    await take!.trigger('click')
    await settle()

    expect(adopts.at(-1)?.force).toBe(true)
    expect(wrapper.text()).not.toContain('nothing changed.')

    wrapper.unmount()
  })

  it('exports the chosen slice as a file, not an upload', async () => {
    const created = vi.fn(() => 'blob:churn')
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() })
    const { wrapper, live } = await compare({
      handlers: {
        export: (params) => ({
          flow: 'churn',
          branch: String(params.branch),
          cells: ['features', 'train_model'],
          source: '# churn\n',
        }),
      },
    })

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Export'))!
      .trigger('click')
    await settle()

    expect(asked(live, 'export')[0].branch).toBe('exp/lr-3e4')
    expect(created).toHaveBeenCalled()

    wrapper.unmount()
  })
})

describe('no internals reach the comparison', () => {
  it('addresses cells by slug and branches by name, and prints no key', async () => {
    const { wrapper } = await compare()
    const text = wrapper.text()

    expect(text).not.toMatch(/\buid\b/i)
    expect(text).not.toMatch(/memo key/i)
    expect(text).not.toMatch(/content hash/i)
    expect(text).not.toMatch(/\b[0-9a-f]{16,}\b/i)

    wrapper.unmount()
  })
})
