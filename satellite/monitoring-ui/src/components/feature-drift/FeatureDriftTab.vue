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
      <StaleWindowNotice
        v-if="featureDrift.stale"
        :computed-at="featureDrift.computed_at"
        :window="window"
      />

      <AlertBannerList
        v-if="featureDrift.alerts.length"
        :banners="featureDrift.alerts"
        inspectable
        @show-feature="$emit('show-feature', $event)"
        @acknowledge="$emit('acknowledge', $event)"
      />

      <div class="layout">
        <RankedDriftList
          :features="featureDrift.features"
          :selected="selectedFeature"
          @select="$emit('select-feature', $event)"
        />
        <FeatureDetailPanel
          :detail="featureDrift.selected"
          :kind="selectedKind"
          :has-features="featureDrift.features.length > 0"
          @open-reference="referenceOpen = true"
        />
      </div>

      <MultivariatePanel :panel="featureDrift.multivariate" />

      <!-- the baseline lives one click away instead of below the fold -->
      <DetailDrawer
        :open="referenceOpen"
        :feature="selectedFeature"
        :kind="selectedKind"
        :caption="baselineLabel"
        eyebrow="Reference profile"
        testid="reference-drawer"
        @close="referenceOpen = false"
      >
        <ReferenceProfilePanel :profile="referenceProfile" :status="referenceProfileStatus" />
      </DetailDrawer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AlertBanner, FeatureDriftResponse, ReferenceProfileResponse } from '@/api/types'
import { Window } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import StateBlock from '@/components/StateBlock.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'
import RankedDriftList from './RankedDriftList.vue'
import FeatureDetailPanel from './FeatureDetailPanel.vue'
import MultivariatePanel from './MultivariatePanel.vue'
import DetailDrawer from '@/components/DetailDrawer.vue'
import StaleWindowNotice from '@/components/StaleWindowNotice.vue'
import ReferenceProfilePanel from './ReferenceProfilePanel.vue'

const props = withDefaults(
  defineProps<{
    featureDrift: FeatureDriftResponse | null
    status: LoadStatus
    selectedFeature: string | null
    referenceProfile: ReferenceProfileResponse | null
    referenceProfileStatus: LoadStatus
    /** The selected range, so a snapshot from outside it can name what it fell out of. */
    window?: Window
  }>(),
  { window: Window.H24 },
)

defineEmits<{
  'select-feature': [string]
  'show-feature': [AlertBanner]
  acknowledge: [AlertBanner]
}>()

const view = computed(() => sectionView(props.status, props.featureDrift?.state))

// The profile knows every feature's kind; the drift payload only after a materialized window.
const selectedKind = computed(
  () => props.referenceProfile?.feature?.kind ?? props.featureDrift?.selected?.distribution?.kind,
)

const baselineLabel = computed(() => {
  const baseline = props.referenceProfile?.baseline_label
  return baseline ? `Computed at training · ${baseline}` : 'Training-time baseline'
})

const referenceOpen = ref(false)

// A drawer describing one feature must not survive a switch to another one.
watch(
  () => props.selectedFeature,
  () => {
    referenceOpen.value = false
  },
)
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
  /* The ranked list and the charts read as one section, so they end at the same line;
     the list scrolls inside whatever height the detail panel sets. */
  align-items: stretch;
}
@media (max-width: 720px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
