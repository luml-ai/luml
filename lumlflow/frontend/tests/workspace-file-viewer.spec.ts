import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { FilePreview } from '@luml/attachments'
import { syntaxTree } from '@codemirror/language'
import { workspaceApi, WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import type { WorkspaceFile, WorkspaceFileLock } from '@/api/slices/workspace/workspace.interface'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import WorkspaceFileViewer from '@/components/workspace/WorkspaceFileViewer.vue'
import { settle } from './fakes'

const toast = vi.hoisted(() => ({ add: vi.fn() }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => toast,
}))
vi.mock('@/store/flow', () => ({
  AGENT_COLORS: ['var(--p-blue-500)'],
  useFlowStore: () => ({ pairedAgents: [{ actor: 'ada', color: 'var(--p-orange-500)' }] }),
}))

const file = (name = 'Makefile', size: number | null = 15): WorkspaceFile => ({
  name,
  path: '/work/' + name,
  size,
  modified_at: '2026-01-01T00:00:00Z',
  is_symlink: size === null,
})
const lock: WorkspaceFileLock = { actor: 'ada', label: 'Ada', path: file().path, last: 300 }
const original = { text: 'test: lint', mtime_ns: '1234567890123456789', revision: 'original' }
const changed = { text: 'test: coverage', mtime_ns: original.mtime_ns, revision: 'replacement' }

function mountViewer(entry: WorkspaceFile, realPreview = false) {
  return mount(WorkspaceFileViewer, {
    props: { file: entry, gone: false, refreshKey: 0 },
    global: { stubs: { FilePreview: !realPreview } },
  })
}
let viewer: ReturnType<typeof mountViewer>
async function open(entry = file(), realPreview = false) {
  viewer = mountViewer(entry, realPreview)
  await settle()
}
const button = (name: string) => viewer.findAll('button').find((b) => b.text() === name)
async function click(name: string) {
  const found = button(name)
  if (!found) throw new Error('Missing button ' + name)
  await found.trigger('click')
  await settle()
}
const editor = () => viewer.getComponent(UiCodeEditor)
async function edit() {
  await click('Edit')
  editor().vm.$emit('update:modelValue', 'my draft')
  await settle()
}

beforeEach(() => {
  vi.spyOn(workspaceApi, 'readText').mockResolvedValue(original)
  vi.spyOn(workspaceApi, 'writeText').mockResolvedValue({ mtime_ns: '999', revision: 'saved' })
  vi.spyOn(workspaceApi, 'fileUrl').mockImplementation(
    (path) => '/api/flow/file?path=' + encodeURIComponent(path),
  )
  toast.add.mockReset()
})
afterEach(() => {
  viewer?.unmount()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('workspace file previews', () => {
  it('shows the size limit for large table and unknown files without requesting their contents', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await open(file('big.csv', 50 * 1024 * 1024), true)
    expect(viewer.text()).toContain('File is too large for preview')
    await viewer.setProps({ file: file('big.unknown', 50 * 1024 * 1024) })
    expect(viewer.text()).toContain('File is too large for preview')
    expect(fetch).not.toHaveBeenCalled()
    expect(workspaceApi.readText).not.toHaveBeenCalled()
  })

  it('streams a large video through the shared preview without probing the text endpoint', async () => {
    await open(file('run.mp4', 300 * 1024 * 1024), true)
    expect(viewer.get('video').attributes('src')).toBe('/api/flow/file?path=%2Fwork%2Frun.mp4')
    expect(viewer.text()).toContain('/work/run.mp4')
    expect(viewer.text()).toContain('Modified')
    expect(workspaceApi.readText).not.toHaveBeenCalled()
    expect(button('Edit')).toBeUndefined()
  })

  it('refreshes the shared preview when the watcher signals a change', async () => {
    await open(file('results.csv'))
    const before = viewer.getComponent(FilePreview)
    expect(before.props()).toMatchObject({ fileName: 'results.csv', fileSize: 15 })
    await viewer.setProps({ refreshKey: 1 })
    expect(viewer.getComponent(FilePreview).vm).not.toBe(before.vm)
  })

  it('waits for UTF-8 validation before showing Edit and escapes unknown text', async () => {
    let finish!: (data: typeof original) => void
    vi.mocked(workspaceApi.readText).mockImplementationOnce(
      () =>
        new Promise((r) => {
          finish = r
        }),
    )
    await open()
    expect(button('Edit')).toBeUndefined()
    finish({ ...original, text: '<em>all</em>' })
    await settle()
    expect(viewer.get('pre').text()).toBe('<em>all</em>')
    expect(viewer.find('em').exists()).toBe(false)
    expect(button('Edit')).toBeDefined()
  })

  it('keeps empty text files editable', async () => {
    vi.mocked(workspaceApi.readText).mockResolvedValue({ ...original, text: '' })
    await open(file('notes.md', 0))
    expect(viewer.text()).toContain('File is empty')
    await edit()
    await click('Save')
    expect(workspaceApi.writeText).toHaveBeenCalledWith(
      '/work/notes.md',
      'my draft',
      original.mtime_ns,
      original.revision,
      false,
    )
  })

  it('shows the no-preview card for binary data and never fetches a broken link', async () => {
    vi.mocked(workspaceApi.readText).mockRejectedValueOnce(
      new WorkspaceRefusedError('Contains NUL', 'NotText'),
    )
    await open(file('model.pkl'))
    expect(viewer.text()).toContain('No preview for this file type')
    expect(button('Edit')).toBeUndefined()
    await viewer.setProps({ file: file('linked.png', null) })
    expect(viewer.findComponent(FilePreview).exists()).toBe(false)
    expect(viewer.text()).toContain('Unknown size')
    expect(viewer.text()).toContain('No preview for this file type')
    expect(workspaceApi.readText).toHaveBeenCalledTimes(1)
  })

  it('ignores an old read that completes after switching files', async () => {
    let finish!: (data: typeof original) => void
    vi.mocked(workspaceApi.readText).mockImplementationOnce(
      () =>
        new Promise((r) => {
          finish = r
        }),
    )
    await open()
    await viewer.setProps({ file: file('training.mp4') })
    finish(original)
    await settle()
    expect(button('Edit')).toBeUndefined()
    expect(viewer.getComponent(FilePreview).props('fileName')).toBe('training.mp4')
  })
})

describe('workspace text editing', () => {
  it('saves the draft with its original revision and clears dirty status', async () => {
    await open()
    await edit()
    expect(viewer.emitted('dirty')).toEqual([[true]])
    await click('Save')
    expect(workspaceApi.writeText).toHaveBeenCalledWith(
      '/work/Makefile',
      'my draft',
      original.mtime_ns,
      original.revision,
      false,
    )
    expect(viewer.get('pre').text()).toBe('my draft')
    expect(viewer.emitted('saved')).toHaveLength(1)
    expect(viewer.emitted('dirty')).toEqual([[true], [false]])
  })

  it('uses the shared language map for the editable CodeMirror document', async () => {
    vi.mocked(workspaceApi.readText).mockResolvedValue({ ...original, text: '{"nested": true}' })
    await open(file('config.json'))
    await click('Edit')
    await vi.waitFor(() => {
      const handle = editor().vm.editor
      expect(handle && syntaxTree(handle.view.state).topNode.name).toBe('JsonText')
    })
  })

  it('compares revisions on refresh and overwrites only after explicit confirmation', async () => {
    await open()
    await edit()
    await viewer.setProps({ refreshKey: 1 })
    await settle()
    expect(button('Overwrite')).toBeUndefined()
    vi.mocked(workspaceApi.readText).mockResolvedValue(changed)
    await viewer.setProps({ refreshKey: 2 })
    await settle()
    expect(viewer.text()).toContain('This file changed on disk after you started to edit it.')
    expect(editor().props('modelValue')).toBe('my draft')
    await click('Overwrite')
    expect(workspaceApi.writeText).toHaveBeenCalledWith(
      '/work/Makefile',
      'my draft',
      original.mtime_ns,
      original.revision,
      true,
    )
  })

  it('offers Reload on an RPC conflict, keeping the draft until the fresh read succeeds', async () => {
    await open()
    await edit()
    vi.mocked(workspaceApi.writeText).mockRejectedValueOnce(
      new WorkspaceRefusedError('Concurrent write', 'FileConflict'),
    )
    await click('Save')
    vi.mocked(workspaceApi.readText).mockRejectedValueOnce(new Error('Read failed'))
    await click('Reload')
    expect(editor().props('modelValue')).toBe('my draft')
    vi.mocked(workspaceApi.readText).mockResolvedValue(changed)
    await click('Reload')
    expect(viewer.get('pre').text()).toBe(changed.text)
    expect(viewer.emitted('dirty')).toEqual([[true], [false]])
  })

  it.each(['NotText', 'TooLarge'])(
    'reloads the disk preview after a %s replacement',
    async (kind) => {
      await open()
      await edit()
      vi.mocked(workspaceApi.readText).mockRejectedValue(
        new WorkspaceRefusedError('Replacement', kind),
      )
      await viewer.setProps({ refreshKey: 1 })
      await settle()
      expect(editor().props('modelValue')).toBe('my draft')
      await click('Reload')
      expect(viewer.findComponent(UiCodeEditor).exists()).toBe(false)
      expect(viewer.text()).toContain('No preview for this file type')
      expect(viewer.emitted('dirty')).toEqual([[true], [false]])
    },
  )

  it('makes a refused save read-only until the next lock snapshot releases it', async () => {
    await open()
    await edit()
    vi.mocked(workspaceApi.writeText).mockRejectedValueOnce(
      new WorkspaceRefusedError('locked', 'FileLocked', { label: 'Ada' }),
    )
    await click('Save')
    expect(viewer.text()).toContain('Ada is working on this file')
    expect(editor().props('readonly')).toBe(true)
    expect(editor().props('modelValue')).toBe('my draft')
    expect(button('Save')?.element.disabled).toBe(true)
    await viewer.setProps({ locks: [] })
    expect(editor().props('readonly')).toBe(false)
    expect(button('Overwrite')).toBeDefined()
  })

  it.each(['one\r\ntwo\r\n', 'one\r\ntwo\nthree\r'])(
    'keeps the untouched line endings on Save',
    async (text) => {
      vi.mocked(workspaceApi.readText).mockResolvedValue({ ...original, text })
      await open()
      await click('Edit')
      await vi.waitFor(() => expect(editor().vm.editor).toBeTruthy())
      editor().vm.editor!.view.dispatch({ changes: { from: 1, to: 2, insert: 'N' } })
      await click('Save')
      expect(workspaceApi.writeText).toHaveBeenCalledWith(
        file().path,
        text.replace('one', 'oNe'),
        original.mtime_ns,
        original.revision,
        false,
      )
    },
  )

  it('locks a live draft, identifies the agent, and permits resolving the conflict after release', async () => {
    await open()
    await edit()
    await viewer.setProps({ locks: [lock] })
    expect(viewer.text()).toContain('Ada is working on this file')
    expect(viewer.attributes('style')).toContain('var(--p-orange-500)')
    expect(editor().props('readonly')).toBe(true)
    expect(editor().props('modelValue')).toBe('my draft')
    expect(button('Save')?.element.disabled).toBe(true)
    expect(button('Overwrite')).toBeUndefined()
    await viewer.setProps({ locks: [] })
    expect(editor().props('readonly')).toBe(false)
    expect(button('Overwrite')).toBeDefined()
    expect(button('Reload')).toBeDefined()
  })

  it('disables editing for an unowned lock and uses its neutral strip', async () => {
    await open()
    await viewer.setProps({ locks: [{ ...lock, actor: null, label: 'an agent' }] })
    expect(viewer.text()).toContain('An agent is working on this file')
    expect(button('Edit')?.element.disabled).toBe(true)
    expect(viewer.attributes('style')).toContain('var(--p-text-muted-color)')
  })

  it('keeps the header and draft available to copy when the file is gone', async () => {
    await open()
    await edit()
    await viewer.setProps({ gone: true })
    expect(viewer.text()).toContain('/work/Makefile')
    expect(viewer.text()).toContain('This file was moved or deleted')
    expect(editor().props('readonly')).toBe(true)
    expect(editor().props('modelValue')).toBe('my draft')
    expect(button('Save')?.element.disabled).toBe(true)
    await viewer.get('[aria-label="Close preview"]').trigger('click')
    expect(viewer.emitted('close')).toHaveLength(1)
    viewer.vm.discard()
    await flushPromises()
    expect(viewer.text()).toContain('This file was moved or deleted')
    expect(viewer.findComponent(UiCodeEditor).exists()).toBe(false)
  })
})
