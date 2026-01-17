<template>
  <div class="card" @click="goToCollection">
    <div class="left">
      <div class="label">{{ data.name }}</div>
      <div class="info">
        <div class="info-item">
          <History :size="12" />
          <span>{{ updatedText }}</span>
        </div>
        <div v-if="data.collection_type === OrbitCollectionTypeEnum.model" class="info-item">
          <CircuitBoard :size="12" />
          <span>Model</span>
        </div>
        <div class="info-item">
          <Database :size="12" />
          <span>{{ data.total_models }}</span>
        </div>
      </div>
      <div class="id-row">
        <span class="id-text">Id: </span>
        <UiId :id="data.id" class="id-value"></UiId>
      </div>
      <div class="tags">
        <Tag v-for="tag in data.tags" class="tag">
          <TagIcon :size="12" class="tag-icon" />
          <span>{{ tag }}</span>
        </Tag>
      </div>
    </div>
    <div v-if="editAvailable" class="right">
      <Button severity="secondary" variant="text" @click.stop="isEditorVisible = true">
        <template #icon>
          <EllipsisVertical :size="14" />
        </template>
      </Button>
    </div>
  </div>
  <CollectionEditor v-model:visible="isEditorVisible" :data="data"></CollectionEditor>
</template>

<script setup lang="ts">
import {
  OrbitCollectionTypeEnum,
  type OrbitCollection,
} from '@/lib/api/orbit-collections/interfaces'
import { Button, Tag } from 'primevue'
import { EllipsisVertical, History, Database, Tag as TagIcon, CircuitBoard } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import CollectionEditor from './CollectionEditor.vue'
import { useRouter } from 'vue-router'
import { getLastUpdateText } from '@/helpers/helpers'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  data: OrbitCollection
  editAvailable: boolean
}

const props = defineProps<Props>()

const router = useRouter()

const isEditorVisible = ref(false)

const updatedText = computed(() => {
  return getLastUpdateText(props.data.updated_at || props.data.created_at)
})

function goToCollection() {
  router.push({
    name: 'collection',
    params: {
      id: props.data.orbit_id,
      collectionId: props.data.id,
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
  min-height: 120px;
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
</style>
