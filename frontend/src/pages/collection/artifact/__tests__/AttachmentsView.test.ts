import { Blob as NodeBlob } from 'node:buffer'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'
import { afterEach, expect, it, vi } from 'vitest'
import AttachmentsView from '../AttachmentsView.vue'
import {
  checkAttachmentSelection,
  largeParquet,
  pythonSource,
} from '../../../../../../extras/js/tests/attachmentSelection'

const store = vi.hoisted(() => ({ current: {} }))
vi.mock('@/stores/artifacts', () => ({ useArtifactsStore: () => store.current }))

afterEach(() => vi.unstubAllGlobals())

it(
  'opens a range-backed table and highlighted Python from the LUML attachment tree',
  { timeout: 20000 },
  async () => {
    vi.stubGlobal('Blob', NodeBlob)
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }))
    const file = largeParquet()
    const tarStart = 4096
    const parquetOffset = 512
    const tarSize = parquetOffset + file.size + pythonSource.length
    const archive = {
      'attachments.tar': [tarStart, tarSize],
      'attachments.index.json': [tarStart + tarSize, 100],
    }
    store.current = {
      attachmentsStatus: 'available',
      currentArtifact: { file_index: archive },
      attachmentsIndex: {
        'attachments/train.parquet': [parquetOffset, file.size],
        'attachments/train.py': [parquetOffset + file.size, pythonSource.length],
      },
      attachmentsDownloader: {
        url: 'https://download.test/experiment',
        async readRange(start: number, end: number) {
          return file.slice(start - tarStart - parquetOffset, end - tarStart - parquetOffset).buffer
        },
        async getFileFromBucket(_: unknown, name: string) {
          expect(name).toBe('attachments/train.py')
          return new TextEncoder().encode(pythonSource).buffer
        },
      },
    }
    const tab = mount(AttachmentsView, {
      global: {
        plugins: [PrimeVue, ToastService],
        directives: { tooltip: Tooltip },
      },
    })
    try {
      await checkAttachmentSelection(tab, file)
    } finally {
      tab.unmount()
    }
  },
)
