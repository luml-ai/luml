<template>
  <div>
    <ReferenceProfileLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="reference-profile">
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <ReferenceProfilePanel v-else :profile="data" :loading="loading" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { getReferenceProfileEmptyState } from '@/utils/reference-profile'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import ReferenceProfileLoader from '@/components/reference-profile/ReferenceProfileLoader.vue'
import ReferenceProfilePanel from '@/components/reference-profile/ReferenceProfilePanel.vue'

const { data, loading, error, reload } = useMonitoringData(
  (dims) => api.monitoring.getReferenceProfile(dims),
  undefined,
  { autoRefresh: false },
)

const emptyState = computed(() => (data.value ? getReferenceProfileEmptyState(data.value) : null))
</script>

<style scoped>
.reference-profile {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
