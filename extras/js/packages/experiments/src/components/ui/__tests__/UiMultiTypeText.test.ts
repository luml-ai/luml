import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import { Select } from 'primevue'
import * as texts from '@/helpers/texts'
import UiMultiTypeText from '../UiMultiTypeText.vue'
import JsonValueView from '../JsonValueView.vue'
import { formatBytes, previewText, utf8ByteLength } from '../largeValue'
import { mockVirtualLayout } from './virtualLayout'

vi.mock('@/helpers/texts', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/helpers/texts')>()
  return { ...original, isYamlLike: vi.fn(original.isYamlLike) }
})

const MB = 1024 * 1024

let mounted: VueWrapper[] = []

function mountText(text: unknown, title = 'input.value') {
  const wrapper = mount(UiMultiTypeText, {
    props: { title, text },
    global: { plugins: [[PrimeVue, { unstyled: true }]], directives: { tooltip: Tooltip } },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

function mountViewer(text: string) {
  const wrapper = mount(JsonValueView, {
    props: { visible: true, title: 'input.value', value: text, text, bytes: utf8ByteLength(text) },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return wrapper
}

function optionDisabled(wrapper: ReturnType<typeof mountViewer>, label: string) {
  const options = wrapper.findComponent(Select).props('options') as {
    label: string
    disabled?: boolean
  }[]
  return options.find((option) => option.label === label)?.disabled ?? false
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
})

afterEach(() => {
  // Unmount before clearing the body: Vue cannot unmount an app whose DOM is already gone.
  mounted.forEach((wrapper) => wrapper.unmount())
  mounted = []
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('UiMultiTypeText', () => {
  it('renders a value of 2,000 characters in full, as before', () => {
    const text = 'a'.repeat(2_000)
    const wrapper = mountText(text)

    expect(wrapper.findComponent(Select).exists()).toBe(true)
    expect(wrapper.get('.content').text()).toBe(text)
    expect(wrapper.text()).not.toContain('First 2,000 characters')
    expect(wrapper.text()).not.toContain('Show all')
  })

  it('renders small objects as indented JSON with the format choice, as before', () => {
    const wrapper = mountText({ role: 'user', tokens: 4 })

    expect(wrapper.findComponent(Select).exists()).toBe(true)
    expect(wrapper.get('.content').text()).toBe(
      JSON.stringify({ role: 'user', tokens: 4 }, null, 2),
    )
  })

  it('shows a preview of a value above 2,000 characters', () => {
    const text = 'a'.repeat(2_001)
    const wrapper = mountText(text)

    expect(wrapper.findComponent(Select).exists()).toBe(false)
    expect(wrapper.get('.content > div').text()).toBe('a'.repeat(2_000))
    expect(wrapper.text()).toContain('First 2,000 characters of 2.0 KB.')
    expect(wrapper.text()).toContain('Show all')
    expect(wrapper.text()).toContain('Download')
  })

  it('states the real size of a 5.2 MB value without converting it to JSON or YAML', () => {
    const text = 'x'.repeat(Math.round(5.2 * MB))
    const stringify = vi.spyOn(JSON, 'stringify')
    const wrapper = mountText(text)

    expect(wrapper.text()).toContain('First 2,000 characters of 5.2 MB.')
    expect(stringify.mock.calls.some(([value]) => value === text)).toBe(false)
    expect(texts.isYamlLike).not.toHaveBeenCalled()
  })

  it('copies compact JSON of a large object, as for a small one', async () => {
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const value = { items: Array.from({ length: 500 }, (_, index) => ({ index })) }
    const wrapper = mountText(value)

    expect(wrapper.text()).toContain('Show all')
    await wrapper.get('header button').trigger('click')

    expect(writeText).toHaveBeenCalledExactlyOnceWith(JSON.stringify(value))
  })

  it('does not cut a character in two at the end of the preview', () => {
    const wrapper = mountText('a'.repeat(1_999) + '😀'.repeat(10))

    expect(wrapper.get('.content > div').text()).toBe('a'.repeat(1_999))
  })

  it('opens the full value viewer from Show all', async () => {
    const text = 'b'.repeat(3_000)
    const wrapper = mountText(text)

    const showAll = wrapper.findAll('button').find((button) => button.text() === 'Show all')
    await showAll!.trigger('click')

    const viewer = wrapper.findComponent(JsonValueView)
    expect(viewer.exists()).toBe(true)
    expect(viewer.props('text')).toBe(text)
    expect(viewer.props('bytes')).toBe(3_000)
  })
})

describe('JsonValueView', () => {
  beforeEach(() => {
    mockVirtualLayout(400)
  })

  it('offers YAML and Markdown for a value under 1 MB', async () => {
    const wrapper = mountViewer('c'.repeat(MB - 1))
    await wrapper.vm.$nextTick()

    expect(optionDisabled(wrapper, 'YAML')).toBe(false)
    expect(optionDisabled(wrapper, 'Markdown')).toBe(false)
  })

  it('offers only plain text for a value of 1 MB and above', async () => {
    const wrapper = mountViewer('c'.repeat(MB))
    await wrapper.vm.$nextTick()

    expect(optionDisabled(wrapper, 'YAML')).toBe(true)
    expect(optionDisabled(wrapper, 'Markdown')).toBe(true)
    expect(optionDisabled(wrapper, 'Raw')).toBe(false)
  })

  it('renders only the lines in view of a 20 MB value', async () => {
    const line = 'd'.repeat(99) + '\n'
    const wrapper = mountViewer(line.repeat((20 * MB) / line.length))
    await wrapper.vm.$nextTick()

    const lines = document.body.querySelectorAll('.line')
    expect(lines.length).toBeGreaterThan(0)
    expect(lines.length).toBeLessThan(100)
    expect(document.body.textContent).toContain('Copy')
    expect(document.body.textContent).toContain('Download')
  })
})

describe('large value helpers', () => {
  it('counts UTF-8 bytes and formats sizes', () => {
    expect(utf8ByteLength('aé€😀')).toBe(1 + 2 + 3 + 4)
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2_001)).toBe('2.0 KB')
    expect(formatBytes(Math.round(5.2 * MB))).toBe('5.2 MB')
  })

  it('cuts a preview at 2,000 characters, one earlier before a surrogate pair', () => {
    expect(previewText('a'.repeat(2_000))).toBe('a'.repeat(2_000))
    expect(previewText('a'.repeat(2_001))).toBe('a'.repeat(2_000))
    expect(previewText('a'.repeat(1_998) + '😀😀')).toBe('a'.repeat(1_998) + '😀')
    expect(previewText('a'.repeat(1_999) + '😀😀')).toBe('a'.repeat(1_999))
  })
})
