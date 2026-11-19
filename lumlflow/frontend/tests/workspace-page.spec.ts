import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { workspaceApi, WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import type { WorkspaceFile } from '@/api/slices/workspace/workspace.interface'
import WorkspacesPage from '@/pages/workspaces/WorkspacesPage.vue'

const { ask, toast } = vi.hoisted(() => ({ ask: vi.fn(), toast: vi.fn() }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useConfirm: () => ({ require: ask }),
  useToast: () => ({ add: toast }),
}))

class Socket {
  static latest: Socket
  onopen?: () => void
  onmessage?: (event: { data: string }) => void
  close = vi.fn()
  send = vi.fn()
  constructor() {
    Socket.latest = this
  }
  receive(frame: object) {
    this.onmessage?.({ data: JSON.stringify(frame) })
  }
}

const file: WorkspaceFile = {
  name: 'notes.md',
  path: '/project/notes.md',
  size: 17,
  modified_at: '2026-10-01T00:00:00Z',
  is_symlink: false,
}
let files: WorkspaceFile[]
let wrapper: VueWrapper
const viewerStub = defineComponent({
  name: 'WorkspaceFileViewer',
  props: ['file', 'locks', 'gone', 'refreshKey'],
  emits: ['dirty', 'close', 'saved'],
  template: '<aside>{{ file.name }}</aside>',
  methods: {
    discard() {
      this.$emit('dirty', false)
    },
  },
})
const folderStub = {
  name: 'WorkspaceFolder',
  props: ['items', 'selectedPath', 'beforeOperation'],
  emits: ['open-file', 'navigate', 'created-file'],
  template: '<section>{{ items.map(row => row.name).join(" ") }}</section>',
}

async function render(query: Record<string, string> = {}, real = false) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: WorkspacesPage }],
  })
  await router.push({ path: '/', query })
  wrapper = mount(RouterView, {
    global: {
      plugins: [router, createPinia()],
      stubs: {
        ...(real
          ? { CreateNewFlow: true }
          : { WorkspaceFolder: folderStub, WorkspaceFileViewer: viewerStub }),
        OpenFlowsSummary: true,
      },
    },
  })
  await flushPromises()
  return router
}
function folder() {
  return wrapper.getComponent({ name: 'WorkspaceFolder' })
}
function viewer() {
  return wrapper.getComponent({ name: 'WorkspaceFileViewer' })
}

beforeEach(() => {
  vi.stubGlobal('WebSocket', Socket)
  localStorage.setItem('lumlflow.flow.token', 'test')
  files = [file]
  vi.spyOn(workspaceApi, 'fileInfo').mockImplementation(async (path) => ({
    file: files.find((entry) => entry.path === path) ?? null,
  }))
  vi.spyOn(workspaceApi, 'openFlows').mockResolvedValue({
    directory: '/project',
    flows: [],
    totals: { open_flows: 0, running_kernels: 0, active_runs: 0, leased_sessions: 0 },
  })
  vi.spyOn(workspaceApi, 'listFlows').mockImplementation(async (path = '/project') => ({
    directory: path,
    flows: [],
    folders: [],
    files: path === '/project' ? [...files] : [],
    next_offset: null,
    total: path === '/project' ? files.length : 0,
  }))
})
afterEach(() => {
  wrapper?.unmount()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('Workspace file selection', () => {
  it('opens files from the listing, restores the selection on Back and follows folder navigation', async () => {
    const router = await render()
    expect(router.currentRoute.value.query.directory).toBe('/project')
    folder().vm.$emit('open-file', file.path)
    await flushPromises()
    expect(router.currentRoute.value.query.file).toBe(file.path)
    expect(folder().props('selectedPath')).toBe(file.path)
    expect(viewer().props('file')).toEqual(file)
    expect(wrapper.find('.content-split').exists()).toBe(true)
    viewer().vm.$emit('close')
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    router.back()
    await flushPromises()
    expect(viewer().text()).toBe(file.name)
    folder().vm.$emit('navigate', '/other')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ directory: '/other' })
    expect(wrapper.find('.content-split').exists()).toBe(false)
    const root = wrapper.get('nav a')
    expect(root.text()).toBe('/')
    await root.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.directory).toBe('/')
  })

  it('opens a PNG from the listing with its bytes, header and bookmark', async () => {
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4LyAAAAMxASBWi9TBAAAAAElFTkSuQmCC',
      'base64',
    )
    const plot = {
      ...file,
      path: '/project/plot.png',
      name: 'plot.png',
      size: png.length,
      modified_at: new Date(2026, 10, 4, 16, 42, 11).toISOString(),
    }
    files = [plot]
    const fetch = vi
      .fn<(url: string) => Promise<Response>>()
      .mockResolvedValue(new Response(png, { headers: { 'Content-Type': 'image/png' } }))
    vi.stubGlobal('fetch', fetch)
    const blobUrl = vi.fn(() => 'blob:plot')
    vi.stubGlobal(
      'URL',
      class extends URL {
        static createObjectURL = blobUrl
        static revokeObjectURL = vi.fn()
      },
    )
    const router = await render({ directory: '/project', log: 'launch-only' }, true)
    await wrapper.get('button.row-link').trigger('click')
    await vi.waitFor(() =>
      expect(wrapper.get('.content-split img').attributes('src')).toBe('blob:plot'),
    )
    expect(router.currentRoute.value.query).toEqual({ directory: '/project', file: plot.path })
    expect(wrapper.get('img').attributes('alt')).toBe(plot.name)
    const header = wrapper.get('.viewer header').text()
    expect(header).toContain(plot.name)
    expect(header).toContain(plot.path)
    expect(header).toContain(png.length + ' B · Modified 2026-11-04 16:42')
    const endpoint = new URL(fetch.mock.calls[0]![0], location.href)
    expect(endpoint.pathname).toBe('/api/flow/file')
    expect(endpoint.searchParams.get('path')).toBe(plot.path)
    expect(blobUrl).toHaveBeenCalledWith(
      expect.objectContaining({ size: png.length, type: 'image/png' }),
    )
  })

  it('pages through the first thousand Workspace Parquet rows using partial transfers', async () => {
    const bytes = readFileSync(
      resolve(
        import.meta.dirname,
        '../../../extras/js/packages/attachments/src/components/preview/__tests__/fixtures/samples.parquet',
      ),
    )
    const size = 400 * 1024 ** 2
    const dataEnd = bytes.length - 8 - bytes.readUInt32LE(bytes.length - 8)
    const footerStart = size - (bytes.length - dataEnd)
    const entry = { ...file, path: '/project/train.parquet', name: 'train.parquet', size }
    files = [entry]
    let transferred = 0
    // Insert empty space before the footer. All column offsets stay valid.
    vi.stubGlobal('fetch', async (url: string, options: RequestInit) => {
      const endpoint = new URL(url, location.href)
      expect(endpoint.pathname).toBe('/api/flow/file')
      expect(endpoint.searchParams.get('path')).toBe(entry.path)
      const range = /^bytes=(\d+)-(\d+)$/.exec(new Headers(options.headers).get('range') ?? '')
      if (!range) throw new Error('Expected a byte range')
      const start = Number(range[1]),
        end = Number(range[2]) + 1
      const length = end - start
      expect(length).toBeLessThan(size)
      const chunk = new Uint8Array(length)
      if (start < dataEnd) chunk.set(bytes.subarray(start, Math.min(end, dataEnd)))
      if (end > footerStart) {
        const offset = Math.max(start, footerStart)
        chunk.set(
          bytes.subarray(dataEnd + offset - footerStart, dataEnd + end - footerStart),
          offset - start,
        )
      }
      transferred += length
      return new Response(chunk, {
        status: 206,
        headers: { 'Content-Range': `bytes ${start}-${end - 1}/${size}` },
      })
    })
    await render({ directory: '/project' }, true)
    await wrapper.get('button.row-link').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Showing first 1,000 of 1,024 rows'))
    expect(wrapper.findAll('thead th').map((cell) => cell.text())).toEqual(['sample.id', 'score'])
    expect(wrapper.get('tbody td').text()).toBe('0')
    await wrapper.get('[aria-label="Last Page"]').trigger('click')
    expect(wrapper.get('tbody tr:last-child td').text()).toBe('999')
    expect(transferred).toBeGreaterThan(0)
    expect(transferred).toBeLessThan(size)
  })

  it('keeps the route, breadcrumb and rows when the destination is unreadable', async () => {
    const router = await render({ directory: '/project', file: file.path })
    vi.mocked(workspaceApi.listFlows).mockRejectedValueOnce(
      new WorkspaceRefusedError('Permission denied', 'OsError'),
    )
    folder().vm.$emit('navigate', '/project/private')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ directory: '/project', file: file.path })
    expect(wrapper.get('nav').text()).toContain('project')
    expect(folder().text()).toBe(file.name)
  })

  it('keeps the displayed directory when a file selection supersedes slow navigation', async () => {
    const router = await render({ directory: '/project' })
    const list = vi.mocked(workspaceApi.listFlows)
    const initial = await list.mock.results[0]!.value
    let finish!: (page: typeof initial) => void
    list.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    folder().vm.$emit('navigate', '/slow')
    await flushPromises()
    folder().vm.$emit('open-file', file.path)
    await flushPromises()
    finish({ ...initial, directory: '/slow', files: [] })
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ directory: '/project', file: file.path })
    expect(folder().text()).toBe(file.name)
    expect(wrapper.get('nav').text()).toContain('project')
  })

  it('preserves the open draft when its entire directory disappears', async () => {
    vi.spyOn(workspaceApi, 'readText').mockResolvedValue({
      text: 'original',
      revision: 'a',
      mtime_ns: '1',
    })
    files = [{ ...file, name: 'Makefile', path: '/project/Makefile' }]
    await render({ directory: '/project', file: files[0]!.path }, true)
    const edit = wrapper.findAll('button').find((button) => button.text() === 'Edit')!
    await edit.trigger('click')
    const editor = wrapper.getComponent({ name: 'UiCodeEditor' })
    editor.vm.$emit('update:modelValue', 'keep my draft')
    files = []
    vi.mocked(workspaceApi.listFlows).mockRejectedValue(
      new WorkspaceRefusedError('there is no directory `/project`', 'FlowError'),
    )
    Socket.latest.receive({
      channel: 'files',
      type: 'changed',
      directory: '/project',
      path: '/project',
    })
    await vi.waitFor(() => expect(wrapper.text()).toContain('This file was moved or deleted'))
    expect(editor.props('modelValue')).toBe('keep my draft')
    expect(editor.props('readonly')).toBe(true)
  })

  it('guards both the symlink and its resolved editing destination', async () => {
    files = [{ ...file, is_symlink: true, name: 'alias', path: '/project/alias' }]
    vi.spyOn(workspaceApi, 'readText').mockResolvedValue({
      text: 'original',
      target: '/data/notes.md',
      revision: 'a',
      mtime_ns: '1',
    })
    await render({ directory: '/project', file: '/project/alias' }, true)
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Edit')!
      .trigger('click')
    wrapper.getComponent({ name: 'UiCodeEditor' }).vm.$emit('update:modelValue', 'draft')
    await flushPromises()
    const guard = folder().props('beforeOperation')
    expect(await guard('/data/notes')).toBe(true)
    for (const path of ['/project/alias', '/project', '/data/notes.md', '/data']) {
      const prompt = guard(path)
      expect(ask.mock.lastCall![0].message).toContain('unsaved changes in alias')
      ask.mock.lastCall![0].reject()
      expect(await prompt).toBe(false)
    }
  })

  it('continues watching the folder when the optional file is refused', async () => {
    await render({ directory: '/project', file: '/missing/bookmark' })
    const socket = Socket.latest
    socket.onopen?.()
    socket.receive({ type: 'error', message: 'there is no directory' })
    expect(JSON.parse(socket.send.mock.lastCall![0])).toEqual({
      subscribe: 'files',
      directory: '/project',
    })
    files.push({ ...file, name: 'new.txt', path: '/project/new.txt' })
    socket.receive({
      channel: 'files',
      type: 'changed',
      directory: '/project',
      path: '/project/new.txt',
    })
    await vi.waitFor(() => expect(folder().text()).toContain('new.txt'))
  })

  it('restores a bookmarked selection beyond the visible pages without expanding the listing', async () => {
    vi.mocked(workspaceApi.listFlows).mockImplementation(async (directory = '/project') => ({
      directory,
      flows: [],
      folders: [],
      files: [],
      next_offset: 2000,
      total: 100000,
    }))
    await render({ directory: '/project', file: file.path })
    expect(viewer().props('file')).toEqual(file)
    expect(folder().props('items')).toEqual([])
    expect(workspaceApi.listFlows).toHaveBeenCalledTimes(1)
    expect(workspaceApi.fileInfo).toHaveBeenCalledWith(file.path)
  })

  it('finishes a slow listing and coalesces changes into a single follow-up', async () => {
    await render({ directory: '/project' })
    const list = vi.mocked(workspaceApi.listFlows)
    const first = await list.mock.results[0]!.value
    let finish!: (page: typeof first) => void
    let followUp!: (page: typeof first) => void
    list.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    list.mockReturnValueOnce(
      new Promise((resolve) => {
        followUp = resolve
      }),
    )
    const notify = () =>
      Socket.latest.receive({
        channel: 'files',
        type: 'changed',
        directory: '/project',
        path: file.path,
      })
    vi.useFakeTimers()
    try {
      notify()
      await vi.advanceTimersByTimeAsync(60)
      for (let i = 0; i < 3; i++) {
        notify()
        await vi.advanceTimersByTimeAsync(100)
      }
      expect(list).toHaveBeenCalledTimes(2)
      finish({ ...first, files: [{ ...file, name: 'first.txt' }] })
      await vi.advanceTimersByTimeAsync(60)
      expect(folder().text()).toBe('first.txt')
      expect(list).toHaveBeenCalledTimes(3)
      followUp({ ...first, files: [{ ...file, name: 'latest.txt' }] })
      await vi.advanceTimersByTimeAsync(100)
      expect(folder().text()).toBe('latest.txt')
      expect(list).toHaveBeenCalledTimes(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('updates the listing, lock and viewer on file frames and keeps a deleted file’s header', async () => {
    await render({ directory: '/project', file: file.path })
    const socket = Socket.latest
    socket.onopen?.()
    expect(JSON.parse(socket.send.mock.calls[0]![0])).toEqual({
      subscribe: 'files',
      directory: '/project',
      file: file.path,
    })
    const lock = { path: file.path, actor: 'agent-1', label: 'Agent One', last: 100 }
    socket.receive({ channel: 'files', type: 'locks', locks: [lock], idle_after_s: 180 })
    await flushPromises()
    expect(viewer().props('locks')).toEqual([lock])
    files = [{ ...file, name: 'new.md', path: '/project/new.md' }]
    socket.receive({ channel: 'files', type: 'changed', directory: '/project', path: file.path })
    socket.receive({ channel: 'files', type: 'locks', locks: [], idle_after_s: 180 })
    await vi.waitFor(() => expect(viewer().props('gone')).toBe(true))
    expect(viewer().props('locks')).toEqual([])
    expect(viewer().props('file')).toEqual(file)
    expect(folder().text()).toBe('new.md')
    wrapper.unmount()
    expect(socket.close).toHaveBeenCalled()
  })

  it('protects a dirty file and its ancestor and lets unrelated operations proceed', async () => {
    const router = await render({ directory: '/project', file: file.path })
    viewer().vm.$emit('dirty', true)
    await flushPromises()
    const guard = folder().props('beforeOperation')
    expect(await guard('/pro')).toBe(true)
    expect(ask).not.toHaveBeenCalled()
    const pending = guard('/project')
    expect(ask.mock.calls[0]![0].message).toBe(
      'You have unsaved changes in notes.md. Discard them and continue?',
    )
    ask.mock.calls[0]![0].reject()
    expect(await pending).toBe(false)
    const leaving = router.push({ query: { directory: '/elsewhere' } })
    await flushPromises()
    ask.mock.lastCall![0].reject()
    await leaving
    expect(router.currentRoute.value.query.file).toBe(file.path)
    const discard = guard(file.path)
    ask.mock.lastCall![0].accept()
    expect(await discard).toBe(true)
    expect(await guard(file.path)).toBe(true)
  })
})
