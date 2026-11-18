<template>
  <MScalableCard class="panel">
    <template #default="{ scaled }">
      <div class="panel-content" :class="{ loading }" :aria-busy="loading">
        <ReferenceProfileTabs v-model="view" />
        <ReferenceProfileSummary :items="summary" />
        <div class="view" :class="{ scaled }">
          <template v-if="profile.document">
            <ReferenceProfileStructure
              v-if="view === ReferenceProfileView.STRUCTURE"
              :document="profile.document"
            />
            <ReferenceProfileRawJson v-else :document="profile.document" />
          </template>
        </div>
      </div>
    </template>
  </MScalableCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ReferenceProfileResponse } from '@/api/monitoring/interfaces'
import { REFERENCE_PROFILE_CONTENT_HEIGHT } from '@/constants/reference-profile'
import { ReferenceProfileView } from '@/types/reference-profile'
import { getReferenceProfileSummary } from '@/utils/reference-profile'
import MScalableCard from '@/components/MScalableCard.vue'
import ReferenceProfileTabs from '@/components/reference-profile/ReferenceProfileTabs.vue'
import ReferenceProfileSummary from '@/components/reference-profile/ReferenceProfileSummary.vue'
import ReferenceProfileStructure from '@/components/reference-profile/ReferenceProfileStructure.vue'
import ReferenceProfileRawJson from '@/components/reference-profile/ReferenceProfileRawJson.vue'

interface Props {
  profile: ReferenceProfileResponse
  loading?: boolean
}

const props = defineProps<Props>()

const view = ref(ReferenceProfileView.STRUCTURE)

const summary = computed(() => getReferenceProfileSummary(props.profile))

const contentHeight = `${REFERENCE_PROFILE_CONTENT_HEIGHT}px`
</script>

<style scoped>
.panel-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  transition: opacity 0.2s;
}

.panel-content.loading {
  opacity: 0.5;
  pointer-events: none;
}

.view {
  height: v-bind(contentHeight);
}

.view.scaled {
  flex: 1;
  min-height: 0;
  height: auto;
}
</style>
