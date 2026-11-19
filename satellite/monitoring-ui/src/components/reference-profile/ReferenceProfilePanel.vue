<template>
  <div class="panel">
    <Button
      v-if="profile.document"
      class="maximize-button"
      variant="text"
      severity="secondary"
      aria-label="Maximize"
      @click="dialogVisible = true"
    >
      <template #icon>
        <Maximize2 :size="14" />
      </template>
    </Button>
    <div class="panel-content" :class="{ loading }" :aria-busy="loading">
      <ReferenceProfileTabs v-model="view" />
      <ReferenceProfileSummary :items="summary" />
      <div class="view">
        <template v-if="profile.document">
          <ReferenceProfileStructure
            v-if="view === ReferenceProfileView.STRUCTURE"
            :document="profile.document"
          />
          <ReferenceProfileRawJson v-else :document="profile.document" />
        </template>
      </div>
    </div>
    <ReferenceProfileDialog
      v-if="profile.document"
      v-model:visible="dialogVisible"
      :document="profile.document"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import Button from 'primevue/button'
import type { ReferenceProfileResponse } from '@/api/monitoring/interfaces'
import { REFERENCE_PROFILE_CONTENT_HEIGHT } from '@/constants/reference-profile'
import { ReferenceProfileView } from '@/types/reference-profile'
import { getReferenceProfileSummary } from '@/utils/reference-profile'
import ReferenceProfileTabs from '@/components/reference-profile/ReferenceProfileTabs.vue'
import ReferenceProfileSummary from '@/components/reference-profile/ReferenceProfileSummary.vue'
import ReferenceProfileStructure from '@/components/reference-profile/ReferenceProfileStructure.vue'
import ReferenceProfileRawJson from '@/components/reference-profile/ReferenceProfileRawJson.vue'
import ReferenceProfileDialog from '@/components/reference-profile/ReferenceProfileDialog.vue'

interface Props {
  profile: ReferenceProfileResponse
  loading?: boolean
}

const props = defineProps<Props>()

const view = ref(ReferenceProfileView.STRUCTURE)

const dialogVisible = ref(false)

const summary = computed(() => getReferenceProfileSummary(props.profile))

const contentHeight = `${REFERENCE_PROFILE_CONTENT_HEIGHT}px`
</script>

<style scoped>
.panel {
  position: relative;
  padding: 16px 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  color: var(--p-card-color);
}

.maximize-button {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  width: 35px;
  padding-block: 10px;
}

.panel-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: opacity 0.2s;
}

.panel-content.loading {
  opacity: 0.5;
  pointer-events: none;
}

.view {
  height: v-bind(contentHeight);
}
</style>
