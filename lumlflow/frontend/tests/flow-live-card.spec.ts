/**
 * The card, on a live session.
 *
 * Four rules are load-bearing here. A cell with several outputs **opens on the
 * one the daemon named**, because which output a reader came for is a verdict
 * the runtime computes and not an order the browser invents. Browsing is
 * **kernel-free**: everything on the card face comes out of stored previews,
 * and the one gesture that needs a process announces itself first. Logs belong
 * to **the run this branch observed**, so a branch that moved back shows that
 * run's output rather than the newest. And the payload is a **versioned
 * envelope**: one this build is behind renders as the kv fallback saying so,
 * never as a guess.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { FlowApiError } from '@/flow/api/client'
import type { CellDetail, CellSummary, StoredPreview } from '@/flow/api/types'
import LiveCellCard from '@/flow/workbench/components/card/LiveCellCard.vue'
import { NEWER_FORMAT_NOTE, previewFrom } from '@/flow/workbench/live/preview'
import type { BlocksPreview, KvPreview } from '@/flow/workbench/model/types'
import {
  attach,
  cellDetail,
  cellSummary,
  clickMenuItem,
  flowStatus,
  FLOW,
  openCardMenu,
  settle,
  settleJournal,
  storedPreview,
  transaction,
} from './fakes'
import type { Attached, Handlers } from './fakes'

// A training cell: four outputs, and the one worth opening on is not the first
// key nor the biggest artifact.
const TRAINED = ['model', 'run', 'checkpoint', 'curves']

const PREVIEWS: Record<string, StoredPreview> = {
  run: storedPreview('experiment', [
    { block: 'markdown', text: '**metrics**' },
    { block: 'kv', entries: { auc: 0.91 } },
  ]),
  model: storedPreview('checkpoint', [{ block: 'kv', entries: { flavor: 'xgboost' } }]),
  checkpoint: storedPreview('file', [
    { block: 'file', name: 'epoch3.pt', size: 2048, content_type: 'application/octet-stream' },
  ]),
  curves: storedPreview('plot', [
    {
      block: 'series',
      name: 'loss',
      points: [
        [0, 1.2],
        [1, 0.7],
      ],
      total_points: 2,
    },
  ]),
}

function trainer(over: Partial<CellSummary> = {}): CellSummary {
  return cellSummary('train_model', { outputs: TRAINED, primary: 'run', ...over })
}

function trainerDetail(over: Partial<CellDetail> = {}): CellDetail {
  return cellDetail('train_model', {
    ...trainer(),
    doc: 'Train the churn model on engineered features.',
    produces: Object.fromEntries(
      TRAINED.map((name) => [name, { type: 'asset' as const, kind: null, persist: true }]),
    ),
    materialized: TRAINED.map((name) => ({
      name,
      kind: PREVIEWS[name].kind,
      kind_source: 'matcher' as const,
      declared: 'asset' as const,
      size: 128,
      persisted: true,
      uploaded: false,
    })),
    ...over,
  })
}

interface Card {
  wrapper: VueWrapper
  live: Attached
}

async function card(
  options: {
    summary?: CellSummary
    detail?: CellDetail
    handlers?: Handlers
    kernel?: 'running' | 'stopped'
    density?: 'canvas' | 'notebook'
  } = {},
): Promise<Card> {
  const summary = options.summary ?? trainer()
  const live = await attach({
    status: flowStatus({
      kernel: {
        state: options.kernel ?? 'running',
        restart_required: false,
        behind: [],
        sandbox: 'none',
      },
    }),
    handlers: {
      'cells.show': () => options.detail ?? trainerDetail(),
      'asset.preview': (params) => {
        const output = String(params.target).split('.')[1]
        return {
          flow: 'churn',
          branch: String(params.branch ?? 'main'),
          slug: 'train_model',
          output,
          state: 'synced',
          kind: PREVIEWS[output]?.kind ?? null,
          size: 128,
          persisted: true,
          preview: PREVIEWS[output] ?? null,
        }
      },
      ...options.handlers,
    },
  })
  const wrapper = mount(LiveCellCard, {
    props: {
      session: live.session,
      stream: live.stream,
      branch: 'main',
      summary,
      density: options.density ?? 'canvas',
    },
  })
  await settle()
  return { wrapper, live }
}

function asked(live: Attached, method: string): Record<string, unknown>[] {
  return live.daemon.calls.filter((call) => call.method === method).map((call) => call.params)
}

function tabs(wrapper: VueWrapper): string[] {
  return wrapper.findAll('[role="tab"]').map((tab) => tab.text())
}

function openTab(wrapper: VueWrapper): string | undefined {
  return wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.attributes('aria-selected') === 'true')
    ?.text()
}

async function clickTab(wrapper: VueWrapper, label: string): Promise<void> {
  await wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === label)
    ?.trigger('click')
  await settle()
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('a cell with four outputs is one card', () => {
  it('opens on the output the daemon named, not on whichever key came first', async () => {
    const { wrapper, live } = await card()

    expect(tabs(wrapper)).toEqual([...TRAINED, 'code', 'logs'])
    expect(openTab(wrapper)).toBe('run')
    // The experiment's own blocks are drawn — the metric it recorded, not a
    // config dump from the first output declared.
    expect(wrapper.text()).toContain('metrics')
    expect(wrapper.text()).toContain('0.91')

    // And exactly one preview was pulled: the card's face. Twenty cards each
    // fetching four payloads is what a canvas cannot afford.
    expect(asked(live, 'asset.preview').map((params) => params.target)).toEqual(['train_model.run'])
    wrapper.unmount()
  })

  it('pulls a payload when the reader moves to its tab, and only then', async () => {
    const { wrapper, live } = await card()

    await clickTab(wrapper, 'checkpoint')

    expect(asked(live, 'asset.preview').map((params) => params.target)).toEqual([
      'train_model.run',
      'train_model.checkpoint',
    ])
    expect(wrapper.text()).toContain('epoch3.pt')
    wrapper.unmount()
  })

  it('renders a note cell as the prose it is, with nothing to run', async () => {
    const { wrapper, live } = await card({
      summary: cellSummary('summary', { note: true, outputs: [], primary: null }),
      detail: cellDetail('summary', {
        note: true,
        outputs: [],
        primary: null,
        produces: {},
        materialized: [],
        doc: 'The sweep so far.\n\n`lr=3e-4` won by a nose.',
      }),
    })

    // A note declares no outputs and runs never: its docstring is the content,
    // and it is markdown on the card rather than a line of source.
    expect(wrapper.text()).toContain('The sweep so far.')
    expect(wrapper.text()).toContain('won by a nose')
    expect(tabs(wrapper)).toEqual(['note', 'code'])
    expect(asked(live, 'asset.preview')).toEqual([])
    wrapper.unmount()
  })

  it('shows the source behind the code tab, and never the hash that locks it', async () => {
    const { wrapper } = await card()

    await clickTab(wrapper, 'code')

    expect(wrapper.text()).toContain('class train_model')
    expect(wrapper.text()).not.toContain('def-hash')
    wrapper.unmount()
  })
})

describe('the run in flight', () => {
  async function running(): Promise<Card> {
    const made = await card()
    made.live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'started',
      step: 12,
      run_id: 'run-7',
      slug: 'train_model',
    })
    await settle()
    return made
  }

  it('takes focus with a live console and streams what the run prints', async () => {
    const { wrapper, live } = await running()

    expect(openTab(wrapper)).toContain('console')
    live.socket.deliver({
      channel: 'logs',
      flow: FLOW,
      run_id: 'run-7',
      seq: 1,
      stream: 'stdout',
      text: 'epoch 1 · auc 0.88\n',
    })
    live.socket.deliver({
      channel: 'logs',
      flow: FLOW,
      run_id: 'run-7',
      seq: 2,
      stream: 'stderr',
      text: 'epoch 2 · auc 0.91\n',
    })
    await settle()

    expect(wrapper.text()).toContain('epoch 1 · auc 0.88')
    // One monotonic sequence across both streams: the interleaving is the
    // daemon's order, not a guess made per stream here.
    expect(wrapper.text()).toContain('epoch 2 · auc 0.91')
    wrapper.unmount()
  })

  it('demotes the console to logs when the run ends, and moves to the fresh output', async () => {
    const { wrapper, live } = await running()

    live.socket.deliver({
      channel: 'journal',
      type: 'kernel',
      flow: FLOW,
      event: 'materialized',
      step: 13,
      run_id: 'run-7',
      slug: 'train_model',
    })
    await settle()

    expect(tabs(wrapper)).not.toContain('console')
    expect(openTab(wrapper)).toBe('run')
    wrapper.unmount()
  })
})

describe('logs belong to the materialization, not to the newest run', () => {
  it('asks for the run this branch observed, and asks again once it moves', async () => {
    let captured = 'epoch 1\nepoch 2\n'
    const { wrapper, live } = await card({
      handlers: {
        'cells.logs': () => ({
          flow: 'churn',
          branch: 'main',
          slug: 'train_model',
          state: 'succeeded',
          logs: captured,
        }),
      },
    })

    await clickTab(wrapper, 'logs')
    expect(wrapper.text()).toContain('epoch 2')

    // A rewind lands as a transaction like any other; what the branch observes
    // afterwards is the earlier run, and its artifact is a different one.
    captured = 'first run only\n'
    live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 20,
      transaction: transaction(20, { intent: 'rewound main' }),
    })
    await settleJournal()

    expect(asked(live, 'cells.logs')).toHaveLength(2)
    expect(wrapper.text()).toContain('first run only')
    expect(wrapper.text()).not.toContain('epoch 2')
    wrapper.unmount()
  })

  it('says a materialization left nothing rather than showing an empty box', async () => {
    const { wrapper } = await card({
      handlers: {
        'cells.logs': () => ({
          flow: 'churn',
          branch: 'main',
          slug: 'train_model',
          state: 'succeeded',
          logs: null,
        }),
      },
    })

    await clickTab(wrapper, 'logs')

    expect(wrapper.text()).toContain('no logs')
    wrapper.unmount()
  })
})

describe('the header states what was recorded', () => {
  it('names the cause in words and badges a reused result under an older env', async () => {
    const { wrapper } = await card({
      summary: trainer({
        state: 'unsynced',
        causes: ['`helpers.py` changed'],
        reused: true,
        older_env: true,
      }),
    })

    expect(wrapper.text()).toContain('stale')
    expect(wrapper.text()).toContain('helpers.py')
    // A hit is not a 0-second run, and a result from an older lock is not a
    // stale one — both are facts the store recorded, badged rather than folded
    // into the status.
    expect(wrapper.text()).toContain('cached')
    expect(wrapper.text()).toContain('older env')
    wrapper.unmount()
  })

  it('carries downstream staleness as stale, naming what above it is not current', async () => {
    const { wrapper } = await card({
      // A transitive verdict is `synced` with cells named above it: current on
      // its own facts, and carrying no cause of its own because none is its own.
      summary: trainer({ state: 'synced', transitive: true, upstream: ['features'] }),
    })

    // Which of the two views shows it is the page's filter; dropping it here
    // would make it unfindable in either.
    expect(wrapper.text()).toContain('stale · downstream')
    expect(wrapper.text()).toContain('upstream features is not current')
    expect(wrapper.find('code').text()).toBe('features')
    wrapper.unmount()
  })

  it('keeps unmaterialized its own state, with nothing to preview', async () => {
    const { wrapper, live } = await card({
      summary: trainer({ state: 'unmaterialized', cost_seconds: null }),
    })

    expect(wrapper.text()).toContain('unmaterialized')
    expect(wrapper.text()).not.toContain('stale')
    expect(wrapper.text()).toContain('not materialized on this lane')
    // Nothing to ask for: no run of this cell was ever observed here.
    expect(asked(live, 'asset.preview')).toEqual([])
    wrapper.unmount()
  })

  it('flags a mixed editing window instead of naming an author confidently', async () => {
    const { wrapper } = await card({
      detail: trainerDetail({
        author: 'claude-1',
        provenance: {
          created_by: 'user',
          created_step: 3,
          last_edited_by: 'claude-1',
          step: 11,
          intent: 'tuned the learning rate',
          attribution_uncertain: true,
        },
      }),
    })

    expect(wrapper.text()).toContain('claude-1')
    expect(wrapper.text()).toContain('uncertain')
    expect(wrapper.text()).toContain('tuned the learning rate')
    wrapper.unmount()
  })

  it('reads a failure by who wrote the version that broke, not by who typed last', async () => {
    const { wrapper } = await card({
      summary: trainer({ state: 'failed', causes: ['the last run failed'] }),
      detail: trainerDetail({
        error: 'Traceback (most recent call last):\nValueError: it did not converge',
        failed_by: 'claude-1',
        provenance: {
          created_by: 'user',
          created_step: 3,
          last_edited_by: 'user',
          step: 14,
          intent: 'put it back',
          attribution_uncertain: false,
        },
      }),
    })

    // The agent's broken version is what failed, so the card demotes: no red
    // wash and no handoff, even though a person edited afterwards.
    expect(wrapper.text()).toContain('failed')
    expect(wrapper.text()).not.toContain('Fix this')

    await clickTab(wrapper, 'logs')
    expect(wrapper.text()).toContain('ValueError: it did not converge')
    wrapper.unmount()
  })

  it('leaks no uid, content hash or memo key anywhere on the card', async () => {
    const { wrapper } = await card({
      summary: trainer({ state: 'unsynced', causes: ['`features` rematerialized'] }),
      detail: trainerDetail({ definition_hash: '9f2c1b7ae4d05c3188aa77e1bd6f0c42' }),
    })

    const text = wrapper.text()
    expect(text).not.toMatch(/\buid\b/i)
    expect(text).not.toMatch(/memo key/i)
    expect(text).not.toMatch(/\b[0-9a-f]{16,}\b/i)
    wrapper.unmount()
  })
})

describe('browsing needs no kernel; expand says when one starts', () => {
  async function expand(made: Card): Promise<void> {
    await openCardMenu(made.wrapper)
    await clickMenuItem('expand')
  }

  it('draws every card from stored previews and reads no value to do it', async () => {
    const { wrapper, live } = await card({ kernel: 'stopped' })

    expect(wrapper.text()).toContain('0.91')
    expect(asked(live, 'asset.page')).toEqual([])
    wrapper.unmount()
  })

  it('announces the kernel before expanding, then pages through the daemon', async () => {
    const rows = [
      ['a', 1],
      ['b', 2],
    ]
    const made = await card({
      kernel: 'stopped',
      summary: trainer({ outputs: ['rows'], primary: 'rows' }),
      detail: trainerDetail({
        outputs: ['rows'],
        primary: 'rows',
        produces: { rows: { type: 'asset', kind: 'frame', persist: true } },
        materialized: [
          {
            name: 'rows',
            kind: 'frame',
            kind_source: 'matcher',
            declared: 'asset',
            size: 4096,
            persisted: true,
            uploaded: false,
          },
        ],
      }),
      handlers: {
        'asset.preview': () => ({
          flow: 'churn',
          branch: 'main',
          slug: 'train_model',
          output: 'rows',
          state: 'synced',
          kind: 'frame',
          size: 4096,
          persisted: true,
          preview: storedPreview('frame', [
            {
              block: 'table',
              columns: ['name', 'n'],
              dtypes: ['object', 'int64'],
              rows,
              total_rows: 500,
              total_columns: 2,
            },
          ]),
        }),
        'asset.page': (params) => ({
          slug: 'train_model',
          output: 'rows',
          kind: 'frame',
          page: {
            columns: ['name', 'n'],
            dtypes: ['object', 'int64'],
            rows: [['zz', 51]],
            offset: Number((params.query as { offset: number }).offset),
            total_rows: 500,
          },
        }),
      },
    })

    await expand(made)
    // The drawer is not open yet: the reader is told what expanding costs
    // before it costs it.
    expect(document.body.textContent).toContain('this starts the kernel')
    expect(asked(made.live, 'asset.page')).toEqual([])

    const accept = [...document.body.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('start the kernel'),
    )
    accept?.click()
    await settle()

    // Now the value itself is being read: the preview held twenty rows of five
    // hundred, and the drawer is where the rest of them come from.
    expect(asked(made.live, 'asset.page')[0].query).toEqual({ offset: 0, limit: 50 })

    const next = [...document.body.querySelectorAll('button')].find(
      (button) => button.getAttribute('aria-label') === 'next page',
    )
    next?.click()
    await settle()

    expect(asked(made.live, 'asset.page')).toHaveLength(2)
    expect(asked(made.live, 'asset.page')[1].query).toEqual({ offset: 50, limit: 50 })
    // The window the kernel served is what the drawer now shows — the browser
    // receives pages, never the frame.
    expect(document.body.textContent).toContain('zz')
    expect(document.body.textContent).toContain('of 500')
    made.wrapper.unmount()
  })

  it('replays the run of the value it opened, without waiting to be asked twice', async () => {
    const made = await card({
      handlers: {
        'cells.logs': () => ({
          flow: 'churn',
          branch: 'main',
          slug: 'train_model',
          state: 'succeeded',
          logs: 'epoch 3 · auc 0.91\n',
        }),
      },
    })

    await expand(made)

    // The drawer shows the artifact beside the value; saying "no logs recorded"
    // because nobody clicked the card's logs tab would be a false report.
    expect(document.body.textContent).toContain('epoch 3 · auc 0.91')
    made.wrapper.unmount()
  })

  it('never carries one output’s window under another output’s tab', async () => {
    const table = (total: number) => ({
      block: 'table',
      columns: ['n'],
      dtypes: ['int64'],
      rows: [[0], [1]],
      total_rows: total,
      total_columns: 1,
    })
    const frames = { first: 500, second: 90 }
    const made = await card({
      summary: trainer({ outputs: ['first', 'second'], primary: 'first' }),
      detail: trainerDetail({
        outputs: ['first', 'second'],
        primary: 'first',
        produces: {
          first: { type: 'asset', kind: 'frame', persist: true },
          second: { type: 'asset', kind: 'frame', persist: true },
        },
        materialized: (['first', 'second'] as const).map((name) => ({
          name,
          kind: 'frame',
          kind_source: 'matcher' as const,
          declared: 'asset' as const,
          size: 4096,
          persisted: true,
          uploaded: false,
        })),
      }),
      handlers: {
        'asset.preview': (params) => {
          const output = String(params.target).split('.')[1] as keyof typeof frames
          return {
            flow: 'churn',
            branch: 'main',
            slug: 'train_model',
            output,
            state: 'synced',
            kind: 'frame',
            size: 4096,
            persisted: true,
            preview: storedPreview('frame', [table(frames[output])]),
          }
        },
        'asset.page': (params) => {
          const output = String(params.target).split('.')[1] as keyof typeof frames
          return {
            slug: 'train_model',
            output,
            kind: 'frame',
            page: {
              columns: ['n'],
              dtypes: ['int64'],
              rows: [[`${output}-paged`]],
              offset: 0,
              total_rows: frames[output],
            },
          }
        },
      },
    })

    await expand(made)
    expect(document.body.textContent).toContain('first-paged')

    const secondTab = [...document.body.querySelectorAll('[role="tab"]')].find(
      (tab) => tab.textContent?.trim() === 'second',
    ) as HTMLElement | undefined
    secondTab?.click()
    await settle()

    // A window belongs to the value it was read out of. Keeping it would show
    // one output's rows — and one output's row count — under another's name.
    const pages = asked(made.live, 'asset.page').map((params) => params.target)
    expect(pages).toEqual(['train_model.first', 'train_model.second'])
    expect(document.body.textContent).toContain('second-paged')
    expect(document.body.textContent).not.toContain('first-paged')
    expect(document.body.textContent).toContain('of 90')
    made.wrapper.unmount()
  })

  it('downloads a stored value and says where it landed', async () => {
    const made = await card({
      handlers: {
        'asset.download': () => ({
          slug: 'train_model',
          output: 'run',
          kind: 'experiment',
          size: 128,
          path: '/home/dana/project/train_model.run',
        }),
      },
    })

    await expand(made)
    const download = [...document.body.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('download'),
    )
    download?.click()
    await settle()

    expect(asked(made.live, 'asset.download')[0].target).toBe('train_model.run')
    expect(document.body.textContent).toContain('saved to /home/dana/project/train_model.run')
    made.wrapper.unmount()
  })

  it('materializes first when this branch holds nothing, and repeats a refusal verbatim', async () => {
    const made = await card({
      summary: trainer({ state: 'unmaterialized', outputs: ['run'], primary: 'run' }),
      detail: trainerDetail({ outputs: ['run'], primary: 'run', materialized: [] }),
      handlers: {
        run: () => ({
          branch: 'main',
          target: 'train_model',
          executed: ['train_model'],
          cached: [],
          pruned: [],
          failed: null,
          abandoned: false,
        }),
        'asset.download': () => {
          throw new FlowApiError('nothing is stored for `train_model.run` yet — run it first', {
            status: 409,
          })
        },
      },
    })

    await expand(made)
    const download = [...document.body.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('materialize and download'),
    )
    expect(download).toBeTruthy()
    download?.click()
    await settle()

    // The run is real and journaled, and it carries the intent every mutating
    // verb owes the timeline.
    expect(asked(made.live, 'run')[0]).toMatchObject({
      target: 'train_model',
      intent: 'run train_model',
    })
    expect(document.body.textContent).toContain('nothing is stored for')
    made.wrapper.unmount()
  })

  it('offers no download for a value the cell declares it never keeps', async () => {
    const made = await card({
      summary: trainer({ outputs: ['run'], primary: 'run' }),
      detail: trainerDetail({
        outputs: ['run'],
        primary: 'run',
        produces: { run: { type: 'asset', kind: null, persist: false } },
        materialized: [
          {
            name: 'run',
            kind: 'experiment',
            kind_source: 'matcher',
            declared: 'asset',
            size: 0,
            persisted: false,
            uploaded: false,
          },
        ],
      }),
    })

    await expand(made)

    const text = document.body.textContent ?? ''
    expect(text).toContain('declared not to persist')
    // A button that must refuse is worse than the sentence explaining why:
    // rerunning this cell stores nothing either.
    expect(
      [...document.body.querySelectorAll('button')].some((button) =>
        button.textContent?.includes('download'),
      ),
    ).toBe(false)
    made.wrapper.unmount()
  })
})

describe('what the card holds keeps up with the journal', () => {
  it('drops an answer the journal moved past, and re-reads what it cleared', async () => {
    let release: (detail: CellDetail) => void = () => {}
    let shows = 0
    const made = await card({
      density: 'notebook',
      handlers: {
        'cells.show': () => {
          shows += 1
          if (shows > 1) return trainerDetail({ source: 'source = "after the run"' })
          return new Promise<CellDetail>((resolve) => {
            release = resolve
          })
        },
      },
    })

    // A transaction lands while the first read is still out. Everything pulled
    // describes the cell as it was a step ago.
    made.live.socket.deliver({
      channel: 'journal',
      type: 'transaction',
      flow: FLOW,
      step: 30,
      transaction: transaction(30, { intent: 'ran train_model' }),
    })
    await settleJournal()
    release(trainerDetail({ source: 'source = "before the run"' }))
    await settle()

    // The late answer is discarded rather than written into the cleared cache,
    // where it would both show the old picture and convince the reload there
    // was nothing left to fetch.
    expect(shows).toBe(2)
    expect(made.wrapper.text()).toContain('after the run')
    expect(made.wrapper.text()).not.toContain('before the run')
    made.wrapper.unmount()
  })

  it('pulls the preview a cell gains when its verdict stops being unmaterialized', async () => {
    const made = await card({
      summary: trainer({ state: 'unmaterialized', cost_seconds: null }),
    })
    expect(asked(made.live, 'asset.preview')).toEqual([])

    // The slice is re-read after the run's transaction, and this card's verdict
    // changes with it — which is when there is finally something to preview.
    await made.wrapper.setProps({ summary: trainer() })
    await settle()

    expect(asked(made.live, 'asset.preview').map((params) => params.target)).toEqual([
      'train_model.run',
    ])
    expect(made.wrapper.text()).toContain('0.91')
    made.wrapper.unmount()
  })
})

// --- the preview envelope ----------------------------------------------------

describe('the stored preview is a versioned contract', () => {
  it('reads the blocks a kind composed, as the primitives they are', () => {
    const preview = previewFrom(
      storedPreview('eval', [
        {
          block: 'table',
          columns: ['case', 'score'],
          dtypes: ['', ''],
          rows: [['a', true]],
          total_rows: 40,
          total_columns: 2,
        },
        { block: 'kv', entries: { score: 0.75 } },
      ]),
    ) as BlocksPreview

    expect(preview.type).toBe('blocks')
    expect(preview.kind).toBe('eval')
    expect(preview.blocks.map((block) => block.block)).toEqual(['table', 'kv'])
    expect(preview.blocks[0]).toMatchObject({ totalRows: 40, rows: [['a', true]] })
  })

  it('drops a block it has never heard of and keeps the ones beside it', () => {
    const preview = previewFrom(
      storedPreview('plot', [
        { block: 'hologram', frames: 12 },
        { block: 'markdown', text: 'still readable' },
      ]),
    ) as BlocksPreview

    expect(preview.blocks).toEqual([{ block: 'markdown', text: 'still readable' }])
  })

  it('falls back to the kv grid, saying so, when the payload is newer than this build', () => {
    const preview = previewFrom(
      storedPreview('frame', [{ block: 'kv', entries: { rows: 500 } }], 2),
    ) as KvPreview

    expect(preview.type).toBe('kv')
    expect(preview.newerFormatNote).toBe(NEWER_FORMAT_NOTE)
    // What a kv block means cannot have been re-cut under it, so those entries
    // are still worth showing; nothing else in the payload is trusted.
    expect(preview.entries).toEqual({ rows: 500 })
  })

  it('renders a payload with no blocks as empty rather than as a broken card', () => {
    const preview = previewFrom(null) as BlocksPreview

    expect(preview).toMatchObject({ type: 'blocks', kind: 'unknown', blocks: [] })
  })
})

beforeEach(() => {
  document.body.innerHTML = ''
})
