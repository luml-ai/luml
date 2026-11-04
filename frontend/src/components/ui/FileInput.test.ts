import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import FileInput from './FileInput.vue'

const toast = vi.hoisted(() => ({ add: vi.fn() }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => toast,
}))

function mountInput(accept = ['text/csv']) {
  return mount(FileInput, {
    props: {
      accept,
      file: {},
      error: false,
      id: 'file',
      acceptText: 'CSV',
      uploadText: 'Choose file',
    },
  })
}
describe('file type validation', () => {
  it.each(['application/vnd.ms-excel', '', 'text/csv'])(
    'accepts CSV filenames with MIME %s',
    async (type) => {
      const wrapper = mountInput()
      expect(wrapper.get('input').attributes('accept')).toBe('text/csv')
      const file = new File(['col\nvalue'], 'DATA.CSV', { type })
      Object.defineProperty(wrapper.get('input').element, 'files', { value: [file] })
      await wrapper.get('input').trigger('change')
      expect(wrapper.emitted('selectFile')).toEqual([[file]])
      expect(toast.add).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )
  it('rejects unrelated files and supports explicit extensions and MIME wildcards', async () => {
    const wrapper = mountInput()
    await wrapper.trigger('drop', {
      dataTransfer: { files: [new File(['x'], 'bad.exe', { type: 'application/octet-stream' })] },
    })
    expect(wrapper.emitted('selectFile')).toBeUndefined()
    expect(toast.add).toHaveBeenCalledOnce()
    await wrapper.setProps({ accept: ['.fnnx', 'image/*'] })
    for (const file of [
      new File(['x'], 'model.FNNX'),
      new File(['x'], 'picture.png', { type: 'image/png' }),
    ]) {
      await wrapper.trigger('drop', { dataTransfer: { files: [file] } })
    }
    expect(wrapper.emitted('selectFile')).toHaveLength(2)
    wrapper.unmount()
  })
})
