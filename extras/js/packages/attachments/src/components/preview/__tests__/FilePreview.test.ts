import { Blob as NodeBlob } from 'node:buffer'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ModelAttachments from '../../../ModelAttachments.vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TarAttachmentsProvider } from '../../../models/TarAttachmentsProvider'
import FilePreview from '../../FilePreview.vue'
import { urlPreviewBytes } from '../../../utils/previewBytes'

beforeEach(() => vi.stubGlobal('Blob', NodeBlob))
afterEach(() => vi.unstubAllGlobals())

describe('standalone preview', () => {
  it.each([
    ['data.csv', 50 * 1024 ** 2, 'File is too large for preview'],
    ['data.arrow', 11 * 1024 ** 2, 'File is too large for preview'],
    ['empty.txt', 0, 'File is empty'],
    ['model.pkl', 20 * 1024 ** 2, 'not supported for preview'],
  ] as const)('shows the state of %s without requesting content', (fileName, fileSize, message) => {
    const source = vi.fn()
    const wrapper = mount(FilePreview, { props: { fileName, fileSize, source } })
    expect(wrapper.text()).toContain(message)
    expect(source).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([
    ['run.mp4', 'video'],
    ['music.mp3', 'audio'],
    ['report.pdf', 'iframe'],
  ])('passes the URL of a large %s directly to its native viewer', (name, element) => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    const wrapper = mount(FilePreview, {
      props: { fileName: name!, fileSize: 300 * 1024 ** 2, source: '/api/content' },
    })
    expect(wrapper.get(element!).attributes('src')).toBe('/api/content')
    expect(fetch).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('refuses a large TAR video before calling a full-content downloader', async () => {
    const size = 300 * 1024 ** 2
    const getFileFromBucket = vi.fn()
    const provider = new TarAttachmentsProvider({
      downloader: { getFileFromBucket },
      fileIndex: { tar: [0, size] },
      attachmentsIndex: { 'run.mp4': [0, size] },
      findAttachmentsTarPath: () => 'tar',
      findAttachmentsIndexPath: () => 'index',
    })
    await provider.init()
    const wrapper = mount(ModelAttachments, {
      props: { provider },
      global: {
        plugins: [PrimeVue, ToastService],
        directives: { tooltip: {} },
      },
    })
    try {
      await wrapper.get('.node').trigger('click')
      expect(wrapper.text()).toContain('File is too large for preview')
      expect(getFileFromBucket).not.toHaveBeenCalled()
    } finally {
      wrapper.unmount()
    }
  })

  it.each([
    ['html', 'iframe'],
    ['xml', '.table-preview'],
  ])('preserves the default %s view and offers highlighted source', async (extension, selector) => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }))
    vi.stubGlobal(
      'URL',
      class extends URL {
        static createObjectURL() {
          return 'blob:report'
        }
        static revokeObjectURL() {}
      },
    )
    const raw = '<row><title>Report</title></row>'
    const wrapper = mount(FilePreview, {
      props: { fileName: `report.${extension}`, source: new Blob([raw]) },
      global: { plugins: [PrimeVue] },
    })
    try {
      await flushPromises()
      expect(wrapper.find(selector!).exists()).toBe(true)
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Raw')!
        .trigger('click')
      expect(wrapper.get('.cm-content').text()).toBe(raw)
      expect(wrapper.find('.cm-line span').exists()).toBe(true)
    } finally {
      wrapper.unmount()
    }
  })

  it('keeps the new selection when an older load finishes later', async () => {
    let finish!: (blob: Blob) => void
    const pending = new Promise<Blob>((resolve) => {
      finish = resolve
    })
    const wrapper = mount(FilePreview, {
      props: { fileName: 'first.txt', source: () => pending },
    })
    await wrapper.setProps({ fileName: 'second.log', source: new Blob(['second']) })
    await flushPromises()
    finish(new Blob(['first']))
    await flushPromises()
    expect(wrapper.get('pre').text()).toBe('second')
    wrapper.unmount()
  })

  it('renders the HTTP failure message when the file cannot be read', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 404 })))
    const wrapper = mount(FilePreview, { props: { fileName: 'gone.txt', source: '/missing' } })
    await flushPromises()
    expect(wrapper.text()).toContain('404')
    wrapper.unmount()
  })

  it('reads a Parquet URL from the attachment tree using only the requested ranges', async () => {
    const fixture = readFileSync(resolve(import.meta.dirname, 'fixtures/samples.parquet'))
    const node = {
      name: 'samples.parquet',
      path: 'train/samples.parquet',
      size: fixture.length,
      type: 'file' as const,
    }
    const provider = {
      isEmpty: () => false,
      getTree: () => [node],
      getPreviewSource: vi.fn(() => '/archive/member'),
      getAttachmentContent: vi.fn(),
    }
    let transferred = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url, options) => {
        expect(url).toBe('/archive/member')
        const range = /^bytes=(\d+)-(\d+)$/.exec(options.headers.get('Range'))!
        const start = Number(range[1]),
          end = Number(range[2])
        const bytes = fixture.subarray(start, end + 1)
        transferred += bytes.length
        return new Response(new Uint8Array(bytes), {
          status: 206,
          headers: {
            'Content-Range': `bytes ${start}-${end}/${fixture.length}`,
          },
        })
      }),
    )
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }))
    const wrapper = mount(ModelAttachments, {
      props: { provider },
      global: {
        plugins: [[PrimeVue, { unstyled: true }], ToastService],
        directives: { tooltip: {} },
      },
    })
    try {
      await wrapper.get('.node').trigger('click')
      await vi.waitFor(() => expect(wrapper.text()).toContain('Showing first 1,000 of 1,024 rows'))
      expect(provider.getPreviewSource).toHaveBeenCalledWith(node.path, node.size)
      expect(provider.getAttachmentContent).not.toHaveBeenCalled()
      expect(transferred).toBeGreaterThan(0)
      expect(transferred).toBeLessThan(fixture.length)
    } finally {
      wrapper.unmount()
    }
  })

  it('reads only the start of a large dataset CSV split for its first rows', async () => {
    const row = `${'x'.repeat(100)}\n`
    const chunk = new TextEncoder().encode(row.repeat(10 * 1024))
    let sent = 0
    const cancel = vi.fn()
    const fetch = vi.fn<(url: string, options: RequestInit) => Promise<Response>>(
      async () =>
        new Response(
          new ReadableStream({
            // The server ignores Range: 100 MB would follow if the reader kept going.
            pull(controller) {
              if (sent >= 100 * 1024 ** 2) return controller.close()
              sent += chunk.byteLength
              controller.enqueue(chunk)
            },
            cancel,
          }),
        ),
    )
    vi.stubGlobal('fetch', fetch)
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }))
    const wrapper = mount(FilePreview, {
      props: {
        fileName: 'data.csv',
        fileSize: 100 * 1024 ** 2,
        supportsPartialPreview: true,
        datasetSplit: true,
        totalRows: 1_000_000,
        source: '/split',
      },
      global: { plugins: [[PrimeVue, { unstyled: true }]] },
    })
    try {
      await vi.waitFor(() =>
        expect(wrapper.text()).toContain('Showing first 1,000 of 1,000,000 rows'),
      )
      expect(new Headers(fetch.mock.calls[0]![1].headers).get('Range')).toBe(
        `bytes=0-${10 * 1024 ** 2}`,
      )
      expect(cancel).toHaveBeenCalled()
      expect(sent).toBeLessThan(12 * 1024 ** 2)
    } finally {
      wrapper.unmount()
    }
  })

  it('cancels a full response when the Parquet server ignores Range', async () => {
    const cancel = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new ReadableStream({ cancel }))))
    const file = await urlPreviewBytes('/data.parquet', 400 * 1024 ** 2)
    await expect(file.slice(0, 8)).rejects.toThrow('file range')
    expect(cancel).toHaveBeenCalled()
  })
})
