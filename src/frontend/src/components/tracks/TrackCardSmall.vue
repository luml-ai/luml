<template>
  <div class="card">
    <div class="label">
      <TrainTrack :size="24" color="var(--p-primary-color)" />
      <div class="name">{{ data.name }}</div>
    </div>
    <div class="id-row">
      <span class="id-text"> Id: </span>
      <UiId :id="data.id" />
    </div>
    <div class="info">
      <div class="info-item">
        <History :size="12" />
        <span>{{ getLastUpdateText(data.updated_at ?? data.created_at) }}</span>
      </div>
      <div class="info-item">
        <component
          v-if="TRACK_TYPE_CONFIG[data.artifact_type]"
          :is="TRACK_TYPE_CONFIG[data.artifact_type].icon"
          :size="12"
        />
        <span>{{ TRACK_TYPE_CONFIG[data.artifact_type]?.label ?? 'Unknown type' }}</span>
      </div>
      <div class="info-item">
        <Database :size="12" />
        <span>{{ data.total_entries }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Track } from '@/lib/api/orbit-tracks/interfaces'
import { Database, History, TrainTrack } from 'lucide-vue-next'
import { getLastUpdateText } from '@/helpers/helpers'
import { TRACK_TYPE_CONFIG } from './tracks.const'
import UiId from '../ui/UiId.vue'

interface Props {
  data: Track
}

defineProps<Props>()
</script>

<style scoped>
.card {
  height: 107px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  padding: 16px;
  width: 100%;
  cursor: pointer;
  transition: background-color 0.3s;
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 8px;
}
.id-row {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}
.id-text {
  color: var(--p-text-muted-color);
}
.info {
  display: flex;
  gap: 12px;
}
.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  color: var(--p-text-muted-color);
}
</style>
