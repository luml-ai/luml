<template>
  <div class="card" @click="goToTrack">
    <div class="left">
      <div class="label">{{ data.name }}</div>
      <div class="info">
        <div class="info-item">
          <History :size="12" />
          <span>{{ updatedText }}</span>
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
      <div class="id-row">
        <span class="id-text">Id: </span>
        <UiId :id="data.id" class="id-value"></UiId>
      </div>
      <div class="tags">
        <Tag v-for="tag in data.tags" :key="tag" class="tag">
          <TagIcon :size="12" class="tag-icon" />
          <span>{{ tag }}</span>
        </Tag>
      </div>
    </div>
    <div v-if="editAvailable" class="right">
      <Button severity="secondary" variant="text" @click.stop="isSettingsVisible = true">
        <template #icon>
          <Settings :size="14" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Track } from '@/lib/api/orbit-tracks/interfaces'
import { Button, Tag } from 'primevue'
import { History, Database, Tag as TagIcon, Settings } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getLastUpdateText } from '@/helpers/helpers'
import { TRACK_TYPE_CONFIG } from './track.const'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  data: Track
  editAvailable: boolean
}

const props = defineProps<Props>()

const isSettingsVisible = defineModel<boolean>('settingsVisible', { default: false })

const router = useRouter()

const updatedText = computed(() => {
  return getLastUpdateText(props.data.updated_at || props.data.created_at)
})

function goToTrack() {
  router.push({
    name: 'track',
    params: {
      id: props.data.orbit_id,
      trackId: props.data.id,
    },
  })
}
</script>

<style scoped>
.card {
  display: flex;
  gap: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  padding: 16px 16px 6px;
  border-radius: 8px;
  justify-content: space-between;
  cursor: pointer;
  transition: background-color 0.3s;
  height: 147px;
  width: calc(100vw - 379px);
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.left {
  width: calc(100% - 60px);
}
.label {
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
.tags {
  overflow-x: auto;
  display: flex;
  gap: 12px;
  padding-bottom: 10px;
}
.tag {
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}
.tag-icon {
  transform: scaleX(-1);
}
.right {
  flex: 0 0 auto;
  align-self: center;
  padding-bottom: 10px;
}
.id-row {
  font-size: 12px;
  margin-bottom: 20px;
}
.id-text {
  color: var(--p-text-muted-color);
}

@media (max-width: 768px) {
  .card {
    width: calc(100vw - 30px);
  }
}
</style>
