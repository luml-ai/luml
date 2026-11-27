import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount } from '@vue/test-utils'
import ExtensionOutlet from './ExtensionOutlet.vue'
import { installExtensions, outletRegistryKey, type OutletRegistry } from '.'

const First = defineComponent({
  props: { itemId: { type: String, required: true } },
  setup: (props) => () => h('span', { class: 'first' }, `first ${props.itemId}`),
})
const Second = defineComponent({
  props: { itemId: { type: String, required: true } },
  setup: (props) => () => h('span', { class: 'second' }, `second ${props.itemId}`),
})

function mountOutlet(registry: OutletRegistry, fallback?: string) {
  return mount(ExtensionOutlet, {
    props: { name: 'area', itemId: '42' },
    slots: fallback ? { default: () => h('p', fallback) } : {},
    global: { provide: { [outletRegistryKey as symbol]: registry } },
  })
}

describe('ExtensionOutlet', () => {
  it('renders registered components in order with the passed props', () => {
    const wrapper = mountOutlet(new Map([['area', [First, Second]]]), 'fallback')
    expect(wrapper.findAll('span').map((span) => span.text())).toEqual(['first 42', 'second 42'])
    expect(wrapper.text()).not.toContain('fallback')
  })

  it('renders the fallback slot when nothing is registered for its name', () => {
    const wrapper = mountOutlet(new Map([['other', [First]]]), 'fallback')
    expect(wrapper.html()).toBe('<p>fallback</p>')
  })

  it('renders no elements without registrations or fallback', () => {
    const Host = defineComponent({
      render: () => h('div', { class: 'host' }, [h(ExtensionOutlet, { name: 'area' })]),
    })
    const wrapper = mount(Host, {
      global: { provide: { [outletRegistryKey as symbol]: new Map() } },
    })
    expect(wrapper.get('.host').element.children).toHaveLength(0)
    expect(wrapper.text()).toBe('')
  })

  it('renders nothing when no registry was provided', () => {
    const wrapper = mount(ExtensionOutlet, { props: { name: 'area' } })
    expect(wrapper.text()).toBe('')
  })

  it('renders components registered by different extensions for the same name', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    const wrapper = mount(ExtensionOutlet, {
      props: { name: 'area', itemId: '7' },
      global: {
        plugins: [
          {
            install: (app) =>
              installExtensions(app, router, createPinia(), [
                { outlets: { area: First } },
                { outlets: { area: [Second] } },
              ]),
          },
        ],
      },
    })
    expect(wrapper.findAll('span').map((span) => span.text())).toEqual(['first 7', 'second 7'])
  })
})
