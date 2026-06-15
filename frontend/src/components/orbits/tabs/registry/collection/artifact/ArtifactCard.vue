<template>
  <div class="card" :class="{ selected }">
    <div class="left">
      <div class="header">
        <component :is="icon" :size="12" class="icon" />
        <div class="title">{{ data.name }}</div>
        <span class="separator">/</span>
        <Folders :size="12" class="icon" />
        <div class="title">{{ collectionName }}</div>
      </div>
      <a :href="artifactPath" target="_blank" class="id">{{ cutStringOnMiddle(data.id, 8) }}</a>
      <div class="description">
        <template v-if="data.description"> {{ data.description }}</template>
        <div v-else class="placeholder">No description</div>
      </div>
      <div class="tags">
        <template v-if="data.tags?.length">
          <Tag v-for="tag in data.tags" :key="tag" class="tag">{{ tag }}</Tag>
        </template>
        <div v-else class="placeholder">No tags</div>
      </div>
    </div>
    <div class="right">
      <Button v-if="selected" severity="secondary" variant="text" disabled>
        <template #icon>
          <Check :size="16" class="check-icon" />
        </template>
      </Button>

      <Button v-else severity="secondary" variant="text" @click="$emit('add')">
        <template #icon>
          <CirclePlus :size="16" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { type Artifact } from '@/lib/api/artifacts/interfaces'
import { computed } from 'vue'
import { ARTIFACT_TYPE_TAGS_CONFIG } from '../artifacts-table/models-table.data'
import { Check, CirclePlus, FileIcon, Folders } from 'lucide-vue-next'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { Button, Tag } from 'primevue'

interface Props {
  data: Artifact
  collectionName: string
  selected: boolean
  organizationId: string
  orbitId: string
}

const props = defineProps<Props>()

const icon = computed(() => ARTIFACT_TYPE_TAGS_CONFIG[props.data.type]?.icon ?? FileIcon)

const artifactPath = computed(() => {
  return `/organization/${props.organizationId}/orbit/${props.orbitId}/collection/${props.data.collection_id}/artifacts/${props.data.id}`
})
</script>

<style scoped>
.card {
  display: flex;
  gap: 16px;
  padding: 16px 16px 6px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  overflow: hidden;
  height: 131px;
  transition: background-color 0.3s;
}
.card.selected {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.left {
  flex: 1 1 auto;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
}
.icon {
  margin-right: 6px;
  color: var(--p-button-outlined-secondary-color);
}
.title {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.separator {
  margin: 0 4px;
  color: var(--p-divider-border-color);
}
.id {
  color: var(--p-text-link-color);
  text-decoration: underline;
  margin-bottom: 16px;
  cursor: pointer;
  transition: color 0.3s;
  display: inline-block;
}
.id:hover {
  color: var(--p-text-link-hover-color);
}
.description {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 8px;
  font-size: 14px;
}
.tags {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding-bottom: 10px;
}
.tag {
  height: 19px;
}
.right {
  flex: 0 0 auto;
  align-self: center;
}
.check-icon {
  color: var(--p-multiselect-dropdown-color);
}
.placeholder {
  color: var(--p-text-muted-color);
  font-size: 12px;
}
</style>
