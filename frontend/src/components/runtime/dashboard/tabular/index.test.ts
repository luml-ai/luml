import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Model } from '@fnnx-ai/web'
import {
  FNNX_PRODUCER_TAGS_MANIFEST_ENUM,
  FNNX_PRODUCER_TAGS_METADATA_ENUM,
} from '@/lib/fnnx/FnnxService'
import ModelTopFeatures from './ModelTopFeatures.vue'
import RuntimeDashboardTabular from './index.vue'

function createModel(featureCount: number) {
  const performance = { ACC: 0.9, PRECISION: 0.9, RECALL: 0.9, F1: 0.9, SC_SCORE: 0.9 }

  return {
    getManifest: () => ({ inputs: [] }),
    getMetadata: () => [
      {
        producer_tags: [FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_classification_metrics_v1],
        payload: {
          metrics: {
            performance: { eval_cv: performance, train: performance },
            permutation_feature_importance_train: {
              importances: Array.from({ length: featureCount }, (_, index) => ({
                feature_name: `feature_${index + 1}`,
                scaled_importance: 0.1,
              })),
            },
          },
        },
      },
    ],
  } as unknown as Model
}

function mountWithModel(model: Model) {
  return shallowMount(RuntimeDashboardTabular, {
    props: {
      model,
      currentTag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
    },
    global: { stubs: { 'd-button': true }, directives: { tooltip: {} } },
  })
}

describe('RuntimeDashboardTabular', () => {
  it.each([
    { featureCount: 1, heading: 'Top 1 feature' },
    { featureCount: 7, heading: 'Top 5 features' },
  ])('shows "$heading" for $featureCount importances', ({ featureCount, heading }) => {
    const wrapper = mountWithModel(createModel(featureCount))
    const titles = wrapper.findAll('.card-title').map((title) => title.text())

    expect(titles).toContain(heading)
    expect(wrapper.findComponent(ModelTopFeatures).exists()).toBe(true)
    wrapper.unmount()
  })

  it.each([
    { name: 'no importances', model: createModel(0) },
    {
      name: 'no metrics',
      model: { getManifest: () => ({ inputs: [] }), getMetadata: () => [] } as unknown as Model,
    },
  ])('hides the features card for a model with $name', ({ model }) => {
    const wrapper = mountWithModel(model)
    const titles = wrapper.findAll('.card-title').map((title) => title.text())

    expect(titles.some((title) => title.startsWith('Top'))).toBe(false)
    expect(wrapper.findComponent(ModelTopFeatures).exists()).toBe(false)
    wrapper.unmount()
  })
})
