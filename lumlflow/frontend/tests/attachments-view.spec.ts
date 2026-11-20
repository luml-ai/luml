import { Blob as NodeBlob } from 'node:buffer'
import { mount } from '@vue/test-utils'
import ToastService from 'primevue/toastservice'
import { afterEach, expect, it, vi } from 'vitest'
import { routeLocationKey } from 'vue-router'
import { apiService } from '@/api/api.service'
import AttachmentsView from '@/pages/details/AttachmentsView.vue'
import {
  checkAttachmentSelection,
  largeParquet,
  pythonSource,
} from '../../../extras/js/tests/attachmentSelection'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it(
  'opens a range-backed table and highlighted Python from the Flow attachment tree',
  { timeout: 20000 },
  async () => {
    const file = largeParquet()
    vi.stubGlobal('Blob', NodeBlob)
    vi.spyOn(apiService, 'getAttachments').mockResolvedValue([
      { name: 'train.parquet', type: 'file', path: 'train.parquet', size: file.size },
      { name: 'train.py', type: 'file', path: 'train.py', size: pythonSource.length },
    ])
    vi.spyOn(apiService, 'getAttachmentContent').mockImplementation(async (id, params) => {
      expect([id, params.file_path]).toEqual(['run', 'train.py'])
      return new Blob([pythonSource])
    })
    vi.stubGlobal('fetch', async (url: string, options: RequestInit) => {
      const request = new URL(url, location.origin)
      expect(request.pathname).toBe('/api/experiments/run/attachments/content')
      expect(request.searchParams.get('file_path')).toBe('train.parquet')
      const range = /^bytes=(\d+)-(\d+)$/.exec(new Headers(options.headers).get('range') ?? '')!
      const start = Number(range[1]),
        last = Number(range[2])
      return new Response(file.slice(start, last + 1), {
        status: 206,
        headers: { 'Content-Range': `bytes ${start}-${last}/${file.size}` },
      })
    })
    const tab = mount(AttachmentsView, {
      global: {
        plugins: [ToastService],
        provide: {
          [routeLocationKey as symbol]: { params: { experimentId: 'run' } },
        },
      },
    })
    try {
      await checkAttachmentSelection(tab, file)
    } finally {
      tab.unmount()
    }
  },
)
