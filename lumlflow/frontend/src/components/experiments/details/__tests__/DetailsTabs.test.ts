import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import DetailsTabs from '../DetailsTabs.vue'
import { ROUTE_NAMES } from '@/router/router.const'

const Empty = defineComponent({ render: () => h('div') })

function createExperimentRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/experiments/:groupId/:experimentId',
        component: Empty,
        children: [
          { name: ROUTE_NAMES.EXPERIMENT_OVERVIEW, path: '', component: Empty },
          { name: ROUTE_NAMES.EXPERIMENT_METRICS, path: 'metrics', component: Empty },
          { name: ROUTE_NAMES.EXPERIMENT_TRACES, path: 'traces', component: Empty },
          { name: ROUTE_NAMES.EXPERIMENT_EVALS, path: 'evals', component: Empty },
          { name: ROUTE_NAMES.EXPERIMENT_ATTACHMENTS, path: 'attachments', component: Empty },
        ],
      },
    ],
  })
}

function selectedTab(wrapper: ReturnType<typeof mount>) {
  return wrapper.get('[role="tab"][aria-selected="true"]').text()
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('[role="tab"]').find((tab) => tab.text() === label)!
}

describe('DetailsTabs', () => {
  it('follows the route and navigates on click without a model', async () => {
    const router = createExperimentRouter()
    await router.push('/experiments/g/e/metrics')
    const wrapper = mount(DetailsTabs, { global: { plugins: [router] } })
    expect(selectedTab(wrapper)).toBe('Metrics')
    await findTab(wrapper, 'Evals').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(ROUTE_NAMES.EXPERIMENT_EVALS)
    expect(selectedTab(wrapper)).toBe('Evals')
  })

  it('switches the model and leaves the route alone with a model', async () => {
    const router = createExperimentRouter()
    await router.push('/experiments/g/e/metrics')
    const wrapper = mount(DetailsTabs, {
      props: {
        modelValue: 'Overview',
        'onUpdate:modelValue': (value: string | undefined) =>
          wrapper.setProps({ modelValue: value }),
      },
      global: { plugins: [router] },
    })
    expect(selectedTab(wrapper)).toBe('Overview')
    expect(wrapper.findAll('.tab')).toHaveLength(5)
    await findTab(wrapper, 'Traces').trigger('click')
    await flushPromises()
    expect(wrapper.props('modelValue')).toBe('Traces')
    expect(selectedTab(wrapper)).toBe('Traces')
    expect(router.currentRoute.value.name).toBe(ROUTE_NAMES.EXPERIMENT_METRICS)
  })
})
