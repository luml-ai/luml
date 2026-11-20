import { Blob as NodeBlob } from 'node:buffer'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAnnotationsStore } from '@luml/experiments'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { api } from '@/api/client'
import ArchiveExperimentPage from '@/pages/workspaces/ArchiveExperimentPage.vue'

// Run the worker's database provider in-process in jsdom, using the installed wasm.
vi.mock('@luml/experiments', async (original) => {
  const lib = await original<typeof import('@luml/experiments')>()
  return {
    ...lib,
    ExperimentSnapshotWorkerProxy: class extends lib.ExperimentSnapshotDatabaseProvider {
      async init(
        data:
          | Parameters<InstanceType<typeof lib.ExperimentSnapshotDatabaseProvider>['init']>[0]
          | { modelId: string; buffer: ArrayBuffer }[],
      ) {
        const modelsInfo = Array.isArray(data) ? data : data.modelsInfo
        return super.init({
          modelsInfo,
          wasmUrl: createRequire(import.meta.url).resolve('sql.js/dist/sql-wasm.wasm'),
        })
      }
      terminate() {}
    },
  }
})

const path = String.raw`/work/run\42.luml`
const fixture = resolve(import.meta.dirname, 'fixtures/run.luml')
const members = new Map(
  ['manifest.json', 'exp.db.zip', 'attachments.index.json', 'attachments.tar'].map(
    (name) => [name, new Uint8Array(execFileSync('tar', ['-xOf', fixture, name]))] as const,
  ),
)
const files = [...members].map(([name, bytes]) => ({ name, size: bytes.length }))
const manifest = JSON.parse(new TextDecoder().decode(members.get('manifest.json')))
let page: VueWrapper
beforeEach(() => {
  vi.spyOn(api, 'post').mockResolvedValue({ data: { signature: 'scoped', expires: 1234 } })
  vi.stubGlobal('Worker', class {})
  vi.stubGlobal('Blob', NodeBlob)
  localStorage.setItem('lumlflow.flow.token', 'fixture')
  vi.spyOn(workspaceApi, 'inspectFile').mockResolvedValue({ kind: 'experiment', manifest, files })
})
afterEach(() => {
  page?.unmount()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})
function open() {
  page = mount(ArchiveExperimentPage, {
    props: { path },
    global: {
      plugins: [createPinia(), ToastService, ConfirmationService],
      stubs: { RouterLink: RouterLinkStub, DynamicMetrics: true },
    },
  })
}
async function tab(label: string) {
  await page
    .findAll('[role="tab"]')
    .find((t) => t.text() === label)!
    .trigger('click')
  await flushPromises()
}

describe('archived experiment details', () => {
  it(
    'renders the SDK archive read-only and reads only the selected attachment range',
    { timeout: 20000 },
    async () => {
      const post = vi.spyOn(api, 'post')
      const get = vi.spyOn(api, 'get')
      const reads: { name: string; range: string | null }[] = []
      vi.stubGlobal('fetch', async (url: string, opts: RequestInit) => {
        const member = new URL(url, location.origin)
        expect(member.pathname).toBe('/api/flow/file/entry')
        expect(member.searchParams.get('path')).toBe(path)
        const name = member.searchParams.get('name')!
        const bytes = members.get(name)!
        const range = new Headers(opts.headers).get('Range')
        reads.push({ name, range })
        if (!range) return new Response(bytes)
        const [start, end] = range.slice(6).split('-').map(Number) as [number, number]
        return new Response(bytes.slice(start, end + 1), {
          status: 206,
          headers: { 'Content-Range': `bytes ${start}-${end}/${bytes.length}` },
        })
      })
      open()
      await vi.waitFor(() => expect(page.text()).toContain('learning_rate'), { timeout: 10000 })
      expect(page.text()).toContain('0.001')
      expect(page.text()).toContain(String.raw`Read-only experiment from run\42.luml`)
      expect(page.getComponent(RouterLinkStub).props('to')).toMatchObject({
        query: { directory: '/work', file: path },
      })
      expect(page.findAll('tr').map((row) => row.text())).toContain('modelId9223372036854775807')
      expect(page.text()).toContain('Archive run')
      expect(page.text()).not.toMatch(/Rename|Delete|Upload|Edit tags/)
      expect(useAnnotationsStore().isEditAvailable).toBe(false)
      expect(reads).toEqual([{ name: 'exp.db.zip', range: null }])
      await tab('Metrics')
      expect(page.findComponent({ name: 'DynamicMetrics' }).props('metricsNames')).toEqual(['loss'])
      await tab('Traces')
      await vi.waitFor(() => expect(page.text()).toContain('trace-1'))
      await tab('Evals')
      await vi.waitFor(() => expect(page.text()).toContain('validation'))
      await tab('Attachments')
      const attachment = page.findAll('span').find((span) => span.text() === 'notes.txt')
      expect(attachment).toBeDefined()
      await attachment!.trigger('click')
      await vi.waitFor(() => expect(page.text()).toContain('Recorded in the archive'))
      const index = JSON.parse(new TextDecoder().decode(members.get('attachments.index.json')))
      const [start, size] = index['attachments/notes.txt']
      expect(reads.filter((read) => read.name === 'attachments.tar')).toEqual([
        { name: 'attachments.tar', range: `bytes=${start}-${start + size - 1}` },
      ])
      expect(post.mock.calls.every(([url]) => url === 'flow/file')).toBe(true)
      expect(get).not.toHaveBeenCalled()
    },
  )

  it('rejects a non-experiment direct link before requesting any bytes', async () => {
    vi.mocked(workspaceApi.inspectFile).mockResolvedValue({ kind: 'model', manifest, files })
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    open()
    await flushPromises()
    expect(page.get('[role="alert"]').text()).toContain('not an experiment archive')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('reports a missing database without displaying stale details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 404 })))
    open()
    await flushPromises()
    expect(page.get('[role="alert"]').text()).toContain(
      'Could not read the experiment database (404)',
    )
    expect(page.find('[role="tab"]').exists()).toBe(false)
  })
})
