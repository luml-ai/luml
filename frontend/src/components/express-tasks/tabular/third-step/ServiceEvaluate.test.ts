import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { Tasks } from '@/lib/data-processing/interfaces'
import ServiceEvaluate from './ServiceEvaluate.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: null }),
}))

function mountWithFeatures(featureCount: number) {
  return shallowMount(ServiceEvaluate, {
    props: {
      predictionFields: [],
      totalScore: 0.9,
      testMetrics: [],
      trainingMetrics: [],
      features: Array.from({ length: featureCount }, (_, index) => ({
        feature_name: `feature_${index + 1}`,
        scaled_importance: 0.1,
      })),
      predictedData: {},
      isTrainMode: false,
      downloadModelCallback: vi.fn(),
      trainingModelId: 'model-id',
      currentTask: Tasks.TABULAR_CLASSIFICATION,
      modelBlob: null,
    },
    global: {
      stubs: { apexchart: true, 'd-dialog': true, 'd-button': true },
      directives: { tooltip: {} },
    },
  })
}

describe('ServiceEvaluate', () => {
  it.each([
    { featureCount: 1, heading: 'Top 1 feature' },
    { featureCount: 5, heading: 'Top 5 features' },
  ])('shows "$heading" for $featureCount features', ({ featureCount, heading }) => {
    const wrapper = mountWithFeatures(featureCount)

    expect(wrapper.get('.features .card-title').text()).toBe(heading)
    wrapper.unmount()
  })

  it('hides the features card when there are no features', () => {
    const wrapper = mountWithFeatures(0)

    expect(wrapper.find('.features').exists()).toBe(false)
    wrapper.unmount()
  })
})
