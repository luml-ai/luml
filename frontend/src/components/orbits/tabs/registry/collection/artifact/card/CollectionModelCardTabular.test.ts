import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { TabularMetrics } from '@/lib/data-processing/interfaces'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import CollectionModelCardTabular from './CollectionModelCardTabular.vue'

function createMetrics(featureCount: number): TabularMetrics {
  const performance = { ACC: 0.9, PRECISION: 0.9, RECALL: 0.9, F1: 0.9, SC_SCORE: 0.9 }

  return {
    performance: { eval_cv: performance, train: performance },
    permutation_feature_importance_train: {
      importances: Array.from({ length: featureCount }, (_, index) => ({
        feature_name: `feature_${index + 1}`,
        scaled_importance: 0.1,
      })),
    },
  }
}

describe('CollectionModelCardTabular', () => {
  it.each([
    { featureCount: 0, heading: 'Top 0 features', renderedCount: 0 },
    { featureCount: 1, heading: 'Top 1 feature', renderedCount: 1 },
    { featureCount: 3, heading: 'Top 3 features', renderedCount: 3 },
    { featureCount: 5, heading: 'Top 5 features', renderedCount: 5 },
    { featureCount: 7, heading: 'Top 5 features', renderedCount: 5 },
  ])(
    'shows "$heading" for $featureCount importances',
    ({ featureCount, heading, renderedCount }) => {
      const wrapper = shallowMount(CollectionModelCardTabular, {
        props: {
          tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
          metrics: createMetrics(featureCount),
        },
      })

      expect(wrapper.get('.features .card-title').text()).toBe(heading)
      expect(wrapper.findAll('.features-list > li')).toHaveLength(renderedCount)
      wrapper.unmount()
    },
  )
})
