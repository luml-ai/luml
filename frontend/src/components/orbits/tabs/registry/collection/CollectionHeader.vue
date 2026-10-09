<template>
  <header class="header">
    <div class="row">
      <h3 class="title">
        {{ title }}
        <UiId :id="id" variant="button"></UiId>
      </h3>
      <div class="buttons">
        <Button @click="$emit('add')">
          <Plus :size="14" />
          <span>Add artifact</span>
        </Button>
      </div>
    </div>
    <div v-if="description" class="description">
      <p class="description-text">{{ description }}</p>
      <button type="button" class="description-button" @click="showDescription">
        <Info :size="11" />
      </button>
      <Dialog v-model:visible="dialogVisible" modal header="Description" :draggable="false">
        <div class="description-dialog-content">{{ description }}</div>
      </Dialog>
    </div>
  </header>
</template>

<script setup lang="ts">
import { Button, Dialog } from 'primevue'
import { Info, Plus } from 'lucide-vue-next'
import { ref } from 'vue'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  title: string
  addAvailable: boolean
  id: string
  description: string
}

type Emits = {
  add: []
}

defineProps<Props>()
defineEmits<Emits>()

const dialogVisible = ref(false)

function showDescription() {
  dialogVisible.value = true
}
</script>

<style scoped>
.header {
  margin-bottom: 20px;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.buttons {
  display: flex;
  gap: 8px;
}

.title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.description {
  padding-top: 4px;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 4px;
}

.description-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 257px;
}

.description-button {
  color: inherit;
  cursor: pointer;
  transition: color 0.3s;
  outline: none;
  transition: transform 0.3s;
}

.description-button:focus {
  color: var(--p-text-color);
  transform: scale(1.1);
}

.description-button:hover {
  color: var(--p-text-color);
  transform: scale(1.1);
}

.description-dialog-content {
  color: var(--p-text-muted-color);
  width: 444px;
  max-height: 255px;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .description-dialog-content {
    width: calc(100vw - 64px);
  }
}
</style>
