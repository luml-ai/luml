import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import * as texts from '@/helpers/texts'
import CellWithTooltip from '../CellWithTooltip.vue'

vi.mock('@/helpers/texts', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/helpers/texts')>()
  return { ...original, valueToString: vi.fn(original.valueToString) }
})

// Exposes the tooltip text as an attribute.
const tooltip = {
  mounted(element: HTMLElement, binding: { value: string }) {
    element.dataset.tooltip = binding.value
  },
}

function mountCell(value: unknown) {
  return mount(CellWithTooltip, {
    props: { value },
    global: { directives: { tooltip } },
  })
}

function cellText(wrapper: ReturnType<typeof mountCell>) {
  return wrapper.get('.cell').text()
}

function tooltipText(wrapper: ReturnType<typeof mountCell>) {
  return wrapper.get('.cell').attributes('data-tooltip')
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('CellWithTooltip', () => {
  it('shows small values in full, as before', () => {
    const object = { role: 'user', tokens: 4 }
    const wrapper = mountCell(object)

    expect(cellText(wrapper)).toBe(texts.jsonToYaml(object).trim())
    expect(tooltipText(wrapper)).toBe(texts.jsonToYaml(object))
    expect(cellText(mountCell('a'.repeat(2_000)))).toBe('a'.repeat(2_000))
  })

  it('cuts a long string and ends it with an ellipsis', () => {
    const wrapper = mountCell('a'.repeat(2_001))

    expect(cellText(wrapper)).toBe('a'.repeat(2_000) + '…')
    expect(tooltipText(wrapper)).toBe('a'.repeat(2_000) + '…')
  })

  it('cuts a large object from compact JSON without converting it to YAML', () => {
    const object = { items: Array.from({ length: 1_000 }, (_, index) => ({ index })) }
    const wrapper = mountCell(object)

    expect(cellText(wrapper)).toBe(JSON.stringify(object).slice(0, 2_000) + '…')
    expect(tooltipText(wrapper)).toBe(JSON.stringify(object).slice(0, 2_000) + '…')
    expect(texts.valueToString).not.toHaveBeenCalled()
  })
})
