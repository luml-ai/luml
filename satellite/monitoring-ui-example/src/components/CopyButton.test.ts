import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CopyButton from './CopyButton.vue'

function withClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
  })
}

afterEach(() => {
  vi.useRealTimers()
})

describe('CopyButton', () => {
  it('copies the value and confirms it for a moment', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    withClipboard(writeText)

    const wrapper = mount(CopyButton, { props: { value: 'evt-100', label: 'event id' } })
    expect(wrapper.attributes('aria-label')).toBe('Copy event id')

    await wrapper.trigger('click')
    await vi.waitFor(() => expect(wrapper.attributes('aria-label')).toBe('event id copied'))
    expect(writeText).toHaveBeenCalledWith('evt-100')

    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()
    expect(wrapper.attributes('aria-label')).toBe('Copy event id')
  })

  it('falls back to a textarea when the async clipboard is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const exec = vi.fn().mockReturnValue(true)
    document.execCommand = exec

    const wrapper = mount(CopyButton, { props: { value: '{"a":1}', label: 'inference.input' } })
    await wrapper.trigger('click')
    await vi.waitFor(() => expect(wrapper.attributes('aria-label')).toContain('copied'))

    expect(exec).toHaveBeenCalledWith('copy')
    // the throwaway textarea does not outlive the copy
    expect(document.querySelectorAll('textarea')).toHaveLength(0)
  })

  it('stays quiet when copying is refused', async () => {
    withClipboard(vi.fn().mockRejectedValue(new Error('denied')))
    document.execCommand = vi.fn().mockImplementation(() => {
      throw new Error('denied')
    })

    const wrapper = mount(CopyButton, { props: { value: 'x', label: 'span_id' } })
    await wrapper.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.attributes('aria-label')).toBe('Copy span_id')
  })
})
