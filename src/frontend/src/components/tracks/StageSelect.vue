<template>
  <div class="field">
    <label for="stage_name" class="label">Stage</label>
    <Select
      labelId="stage_name"
      :name="props.name"
      fluid
      placeholder="Select stage"
      :options="options"
      option-label="name"
      option-value="id"
    >
      <template #value="{ value, placeholder }">
        <Tag v-if="value" :severity="getStageTagSeverity(getStageNameById(value) ?? '')">
          {{ getStageNameById(value) }}
        </Tag>
        <div v-else class="placeholder">{{ placeholder }}</div>
      </template>
      <template #option="{ option }">
        <Tag :severity="getStageTagSeverity(option.name)">{{ option.name }}</Tag>
      </template>
    </Select>
  </div>
</template>

<script setup lang="ts">
import type { TrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { Select, Tag } from 'primevue'
import { getStageTagSeverity } from './tracks.const'

interface Props {
  options: TrackStage[]
  name?: string
}

const props = withDefaults(defineProps<Props>(), {
  name: 'stage_id',
})

function getStageNameById(id: string) {
  return props.options.find((stage) => stage.id === id)?.name
}
</script>

<style scoped></style>
