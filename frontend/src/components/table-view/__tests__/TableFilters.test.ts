import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { Button, Divider, InputText, OverlayBadge, Popover, Select } from 'primevue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TableFilters from '../TableFilters.vue'

function mountFilters() {
  return mount(TableFilters, {
    attachTo: document.body,
    props: {
      data: [{ name: 'score', type: 'number' }],
      filters: [],
      columnTypes: { score: 'number' },
    },
    global: {
      plugins: [PrimeVue],
      components: {
        DButton: Button,
        DDivider: Divider,
        DInputText: InputText,
        DOverlayBadge: OverlayBadge,
        DPopover: Popover,
        DSelect: Select,
      },
    },
  })
}

async function selectOption(combobox: Element, label: string, popover: Element) {
  combobox.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()

  const option = Array.from(document.querySelectorAll('[role="option"]')).find(
    (element) => element.getAttribute('aria-label') === label,
  )
  expect(option).toBeDefined()
  expect(option!.closest('.p-popover')).toBe(popover)
  option!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
  option!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('TableFilters', () => {
  it('stays open while each filter field is configured', async () => {
    const wrapper = mountFilters()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    const popover = document.querySelector('.p-popover')
    expect(popover).not.toBeNull()

    let comboboxes = popover!.querySelectorAll('[role="combobox"]')
    await selectOption(comboboxes[0]!, 'score', popover!)
    expect(document.body.contains(popover)).toBe(true)

    comboboxes = popover!.querySelectorAll('[role="combobox"]')
    await selectOption(comboboxes[1]!, 'Equals', popover!)
    expect(document.body.contains(popover)).toBe(true)

    const valueInput = popover!.querySelector<HTMLInputElement>('input[placeholder="Value"]')!
    valueInput.value = '10'
    valueInput.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()
    expect(document.body.contains(popover)).toBe(true)

    wrapper.unmount()
  })
})
