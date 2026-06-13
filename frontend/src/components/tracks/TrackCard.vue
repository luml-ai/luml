<template>
  <RouterLink :to="{ name: 'track', params: { trackId: props.id } }" class="card">
    <div>
      <h3 class="label">{{ props.name }}</h3>
      <div class="info">
        <div class="info-item">
          <History :size="12" />
          <span>{{ updatedText }}</span>
        </div>
        <div class="info-item">
          <component
            v-if="TRACK_TYPE_CONFIG[props.type]"
            :is="TRACK_TYPE_CONFIG[props.type].icon"
            :size="12"
          />
          <span>{{ TRACK_TYPE_CONFIG[props.type]?.label ?? 'Unknown type' }}</span>
        </div>
        <div class="info-item">
          <Database :size="12" />
          <span>{{ props.artifactsCount }}</span>
        </div>
      </div>
      <div class="id-row">
        <span class="id-text">Id: </span>
        <UiId :id="props.id" class="id-value"></UiId>
      </div>
    </div>
    <Button variant="text" severity="secondary" @click.prevent.stop="showEditor">
      <template #icon>
        <EllipsisVertical :size="14" />
      </template>
    </Button>
  </RouterLink>
</template>

<script setup lang="ts">
import type { TrackCardProps } from './tracks.interface'
import { Database, EllipsisVertical, History } from 'lucide-vue-next'
import { computed } from 'vue'
import { getLastUpdateText } from '@/helpers/helpers'
import { TRACK_TYPE_CONFIG } from './tracks.const'
import { Button } from 'primevue'
import { useTracksStore } from '@/stores/tracks'
import UiId from '../ui/UiId.vue'

const props = defineProps<TrackCardProps>()

const tracksStore = useTracksStore()

const updatedText = computed(() => {
  return getLastUpdateText(props.date)
})

function showEditor() {
  tracksStore.showEditor({
    id: props.id,
    name: props.name,
    description: props.description,
    stages: props.stages,
    lockedStages: ['Production', 'Pre-Production'],
  })
}
</script>

<style scoped>
.card {
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  display: grid;
  grid-template-columns: 1fr 35px;
  align-items: center;
  gap: 24px;
  height: 102px;
  overflow: hidden;
  cursor: pointer;
  transition: background-color 0.3s;
  text-decoration: none;
  color: inherit;
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.label {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}
.info {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}
.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  color: var(--p-text-muted-color);
}
.id-row {
  font-size: 12px;
}
.id-text {
  color: var(--p-text-muted-color);
}
</style>
