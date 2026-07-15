<template>
  <section class="feature-drift" data-testid="feature-drift-tab">
    <div class="intro">
      <p class="section-title">Feature drift</p>
      <p class="section-subtitle">
        How far the live input distribution has moved from the training reference.
      </p>
    </div>

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No feature drift computed yet"
      empty-detail="The worker has not materialized feature drift for this window yet."
    />

    <template v-else-if="featureDrift">
      <AlertBannerList v-if="featureDrift.alerts.length" :banners="featureDrift.alerts" />

      <div class="layout">
        <RankedDriftList
          :features="featureDrift.features"
          :selected="selectedFeature"
          @select="$emit('select-feature', $event)"
        />
        <FeatureDetailPanel :detail="featureDrift.selected" />
      </div>

      <MultivariatePanel :panel="featureDrift.multivariate" />

      <ReferenceProfilePanel :profile="referenceProfile" :status="referenceProfileStatus" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureDriftResponse, ReferenceProfileResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import StateBlock from '@/components/StateBlock.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'
import RankedDriftList from './RankedDriftList.vue'
import FeatureDetailPanel from './FeatureDetailPanel.vue'
import MultivariatePanel from './MultivariatePanel.vue'
import ReferenceProfilePanel from './ReferenceProfilePanel.vue'

const props = defineProps<{
  featureDrift: FeatureDriftResponse | null
  status: LoadStatus
  selectedFeature: string | null
  referenceProfile: ReferenceProfileResponse | null
  referenceProfileStatus: LoadStatus
}>()

defineEmits<{ 'select-feature': [string] }>()

const view = computed(() => sectionView(props.status, props.featureDrift?.state))
</script>

<style scoped>
.feature-drift {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.layout {
  display: grid;
  grid-template-columns: minmax(240px, 340px) 1fr;
  gap: var(--luml-space-4);
  align-items: start;
}
@media (max-width: 720px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
