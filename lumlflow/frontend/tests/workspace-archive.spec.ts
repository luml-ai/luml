import { Blob as NodeBlob } from 'node:buffer'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Table, tableFromArrays, tableToIPC } from 'apache-arrow'
import { Form } from '@primevue/forms'
import { ProgressBar } from 'primevue'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { ArchiveInspection } from '@/api/slices/workspace/workspace.interface'
import { apiService } from '@/api/api.service'
import { api } from '@/api/client'
import CollectionField from '@/components/upload/CollectionField.vue'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import WorkspaceFileViewer from '@/components/workspace/WorkspaceFileViewer.vue'
import { ROUTE_NAMES } from '@/router/router.const'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia } from 'pinia'
import ToastService from 'primevue/toastservice'

const file = {
  path: '/work/run #1.luml',
  name: 'run #1.luml',
  size: 500_000_000,
  modified_at: '2026-01-01T00:00:00Z',
  is_symlink: false,
}
const manifest = { name: 'Test artifact', payload: { labels: ['validation'] } }
const files = [{ name: 'attachments.index.json', size: 13 }]
let wrapper: VueWrapper

async function open(inspection?: ArchiveInspection) {
  if (inspection) vi.spyOn(workspaceApi, 'inspectFile').mockResolvedValue(inspection)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      {
        name: ROUTE_NAMES.WORKSPACE_EXPERIMENT,
        path: '/workspaces/experiment',
        component: { template: '<div />' },
      },
    ],
  })
  await router.push('/')
  wrapper = mount(WorkspaceFileViewer, {
    props: { file, gone: false, refreshKey: 0 },
    global: { plugins: [router, createPinia(), ToastService], stubs: { teleport: true } },
  })
  await flushPromises()
}
beforeEach(() => {
  vi.stubGlobal('Blob', NodeBlob)
  localStorage.setItem('lumlflow.flow.token', 'fixture')
})
afterEach(() => {
  wrapper?.unmount()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('Workspace archives', () => {
  it.each(['experiment', 'model'] as const)(
    'shows the %s actions, YAML and member previews',
    async (kind) => {
      vi.spyOn(api, 'post').mockResolvedValue({ data: { signature: 'scoped', expires: 1234 } })
      const fetch = vi.fn().mockResolvedValue(new Response('{"score":123}'))
      vi.stubGlobal('fetch', fetch)
      await open({ kind, files, manifest })
      expect(workspaceApi.inspectFile).toHaveBeenCalledWith(file.path)
      expect(wrapper.getComponent(UiCodeEditor).props()).toMatchObject({
        language: 'yaml',
        readonly: true,
        modelValue: expect.stringContaining('name: Test artifact'),
      })
      expect(wrapper.text()).toContain(`Upload ${kind} to LUML`)
      const link = wrapper.find('a[href*="workspaces/experiment"]')
      expect(link.exists()).toBe(kind === 'experiment')
      if (link.exists())
        expect(new URL(link.attributes('href')!, location.origin).searchParams.get('file')).toEqual(
          file.path,
        )
      expect(fetch).not.toHaveBeenCalled()
      await wrapper.get('.contents-row').trigger('click')
      await vi.waitFor(() => expect(wrapper.get('[role="dialog"]').text()).toMatch(/"score": 123/))
      const url = new URL(fetch.mock.calls[0]![0], location.origin)
      expect(url.pathname).toBe('/api/flow/file/entry')
      expect(Object.fromEntries(url.searchParams)).toEqual({
        path: file.path,
        name: files[0]!.name,
        signature: 'scoped',
        expires: '1234',
      })
    },
  )

  it('displays exact integer literals from the inspection response in the YAML manifest', async () => {
    const adapter = api.defaults.adapter
    api.defaults.adapter = async (config) => ({
      config,
      status: 200,
      statusText: 'OK',
      headers: {},
      data: '{"result":{"kind":"model","manifest":{"payload":{"seed":9223372036854775807}},"files":[]}}',
    })
    try {
      await open()
      expect(wrapper.getComponent(UiCodeEditor).props('modelValue')).toContain(
        'seed: 9223372036854775807',
      )
    } finally {
      api.defaults.adapter = adapter
    }
  })

  it('keeps only the file header and no-preview state for an unknown archive', async () => {
    await open({ kind: 'unknown', manifest, files })
    expect(wrapper.text()).toContain(file.path)
    expect(wrapper.text()).toContain('No preview for this file type')
    expect(wrapper.text()).not.toMatch(/Upload|Manifest|Contents|Edit/)
  })

  it.each([
    ['hf', 'arrow'],
    ['tabular', 'parquet'],
  ] as const)(
    'reads the first chunk of each %s split',
    { timeout: 20000 },
    async (variant, format) => {
      const bytes = readFileSync(
        resolve(
          import.meta.dirname,
          '../../../extras/js/packages/attachments/src/components/preview/__tests__/fixtures',
          `samples.${format}`,
        ),
      )
      vi.spyOn(api, 'post').mockResolvedValue({ data: { signature: 'scoped', expires: 1234 } })
      const splits = ['train', 'test'].map((name, i) => ({
        name,
        subset: 'default',
        num_rows: i ? null : 5400,
        format,
        files: [`default/${name}/first.${format}`, `default/${name}/next.${format}`],
      }))
      const reads: string[] = []
      vi.stubGlobal('fetch', async (url: string, options: RequestInit) => {
        reads.push(new URL(url, location.origin).searchParams.get('name')!)
        if (format === 'arrow') return new Response(bytes)
        const range = new Headers(options.headers).get('Range')!
        const [start, end] = range.slice(6).split('-').map(Number) as [number, number]
        return new Response(bytes.subarray(start, end + 1), {
          status: 206,
          headers: { 'Content-Range': `bytes ${start}-${end}/${bytes.length}` },
        })
      })
      await open({
        kind: 'dataset',
        manifest,
        variant,
        splits,
        files: splits.flatMap((s) => s.files.map((name) => ({ name, size: bytes.length }))),
      })
      await vi.waitFor(
        () => expect(wrapper.text()).toContain('Showing first 1,000 of 5,400 rows'),
        {
          timeout: 10000,
        },
      )
      expect(wrapper.findAll('.contents-name').map((row) => row.text())).toEqual([
        'default/',
        ...splits.flatMap((split) => split.files),
      ])
      expect(wrapper.findAll('.contents button')).toHaveLength(4)
      expect(new Set(reads)).toEqual(new Set([splits[0]!.files[0]]))
      expect(wrapper.get('[role="tablist"]').attributes('style')).toContain('border-top:')
      expect(wrapper.findAll('[role="tab"].split-tab')).toHaveLength(2)
      await wrapper.get('[role="tablist"]').findAll('[role="tab"]')[1]!.trigger('click')
      await vi.waitFor(() => expect(wrapper.text()).toContain('Showing first 1,000 rows'))
      expect(new Set(reads)).toEqual(new Set(splits.map((s) => s.files[0])))
    },
  )

  it.each(['csv', 'arrow'] as const)(
    'previews 1,000 rows from a split with a large %s chunk',
    { timeout: 20000 },
    async (format) => {
      const name = `data/default/train/first.${format}`
      vi.spyOn(api, 'post').mockResolvedValue({ data: { signature: 'scoped', expires: 1234 } })
      const body =
        format === 'csv'
          ? 'id,label\n' + '42,example\n'.repeat(1000) + '43,' + 'x'.repeat(11 * 1024 ** 2)
          : // As `datasets` writes a shard: a stream of 1,000-row record batches, 12 MB in all.
            new Uint8Array(
              tableToIPC(
                new Table(
                  Array.from(
                    { length: 3 * 1024 },
                    () => tableFromArrays({ id: new Int32Array(1000).fill(42) }).batches[0]!,
                  ),
                ),
              ),
            )
      const fetch = vi.fn(async () => new Response(body))
      vi.stubGlobal('fetch', fetch)
      await open({
        kind: 'dataset',
        manifest,
        splits: [{ subset: 'default', name: 'train', format, files: [name], num_rows: 5000000 }],
        files: [{ name, size: body.length }],
      })
      await vi.waitFor(
        () => expect(wrapper.text()).toContain('Showing first 1,000 of 5,000,000 rows'),
        { timeout: 10000 },
      )
      expect(wrapper.get('table').text()).toContain('42')
      // Only the start of the chunk is asked for, not the whole file.
      const read = (fetch.mock.calls as unknown as [string, RequestInit][]).find(([url]) =>
        url.includes('first.'),
      )!
      expect(new Headers(read[1].headers).get('Range')).toBe(`bytes=0-${10 * 1024 ** 2}`)
    },
  )

  it('publishes the selected file and follows the job returned by the daemon', async () => {
    vi.spyOn(apiService, 'checkAuth').mockResolvedValue({ has_key: true })
    vi.spyOn(apiService, 'getLumlOrganizations').mockResolvedValue([])
    vi.spyOn(apiService, 'getLumlOrbits').mockResolvedValue([])
    const collection = {
      id: 'collection',
      name: 'Datasets',
      orbit_id: 'orbit',
      description: '',
      type: 'dataset',
      tags: [],
      total_artifacts: 0,
      created_at: '',
      updated_at: null,
    }
    vi.spyOn(apiService, 'getLumlCollections').mockImplementation(async ({ cursor }) =>
      cursor === 'page-two'
        ? { items: [collection], cursor: null }
        : {
            items: Array.from({ length: 20 }, (_, i) => ({
              ...collection,
              id: String(i),
              name: `Models ${i}`,
              type: 'model',
            })),
            cursor: 'page-two',
          },
    )
    const publish = vi.spyOn(api, 'post').mockResolvedValue({
      status: 200,
      data: { result: { job_id: 'dataset-job' } },
    })
    let progress!: ReadableStreamDefaultController<Uint8Array>
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        progress = controller
      },
    })
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: stream })
    await open({ kind: 'dataset', manifest, files, splits: [] })
    vi.mocked(workspaceApi.inspectFile).mockResolvedValue({
      kind: 'dataset',
      manifest: { ...manifest, name: 'Refreshed dataset' },
      files,
      splits: [],
    })
    await wrapper.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(apiService.checkAuth).not.toHaveBeenCalled()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Upload dataset to LUML')!
      .trigger('click')
    await flushPromises()
    const form = wrapper.getComponent(Form)
    expect((wrapper.get('input#name').element as HTMLInputElement).value).toBe('Refreshed dataset')
    expect(wrapper.getComponent(CollectionField).props('requiredKinds')).toEqual(['dataset'])
    const fields = wrapper.getComponent(CollectionField).props('formRef')!
    fields.setFieldValue('organization', 'org')
    await flushPromises()
    fields.setFieldValue('orbit', 'orbit')
    await flushPromises()
    await wrapper.getComponent(CollectionField).get('[role="combobox"]').trigger('click')
    const option = wrapper.findAll('[role="option"]').find((item) => item.text() === 'Datasets')
    expect(option).toBeDefined()
    await option!.trigger('mousedown')
    await wrapper.get('input#name').setValue('Uploaded dataset')
    await wrapper.setProps({ refreshKey: 2 })
    await flushPromises()
    expect((wrapper.get('input#name').element as HTMLInputElement).value).toBe('Uploaded dataset')
    expect(workspaceApi.inspectFile).toHaveBeenCalledTimes(3)
    expect(publish).not.toHaveBeenCalled()
    await wrapper.get('textarea#description').setValue('Test description')
    fields.setFieldValue('tags', ['example'])
    await form.trigger('submit')
    await flushPromises()
    expect(publish).toHaveBeenCalledWith(
      'flow/rpc',
      {
        method: 'file.publish',
        params: {
          path: file.path,
          organization_id: 'org',
          orbit_id: 'orbit',
          collection_id: 'collection',
          artifact: {
            name: 'Uploaded dataset',
            description: 'Test description',
            tags: ['example'],
          },
        },
      },
      expect.objectContaining({ headers: { 'x-lumlflow-token': 'fixture' } }),
    )
    expect(get).toHaveBeenCalledWith('/luml/artifact/dataset-job/progress', expect.anything())
    await wrapper.setProps({ refreshKey: 3 })
    await flushPromises()
    progress.enqueue(new TextEncoder().encode('data: {"type":"progress","percent":45}\n\n'))
    await vi.waitFor(() => expect(wrapper.getComponent(ProgressBar).props('value')).toBe(45))
    progress.enqueue(new TextEncoder().encode('data: {"type":"complete"}\n\n'))
    await vi.waitFor(() => expect(wrapper.findComponent(Form).exists()).toBe(false))
  })
})
