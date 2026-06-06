<template>
  <!-- eslint-disable vue/no-mutating-props -- editor mutates the shared reactive node-field object in place -->
  <div class="field">
    <header class="field-header">
      <h4 class="field-type">condition {{ index }}</h4>
      <div class="field-actives">
        <d-button
          severity="secondary"
          rounded
          variant="text"
          class="filed-actives-button"
          @click="onTrashClick"
        >
          <template #icon>
            <trash width="14" height="14" />
          </template>
        </d-button>
      </div>
    </header>
    <CustomTextarea
      v-model="data.value"
      fluid
      rows="1"
      placeholder="Hint"
      size="small"
      autoResize
      :maxHeight="75"
    />
  </div>
</template>

<script setup lang="ts">
import type { NodeField } from '../../interfaces'
import { Trash } from 'lucide-vue-next'
import CustomTextarea from '@/components/ui/CustomTextarea.vue'

type Props = {
  data: NodeField
  index: number
}
type Emits = {
  delete: []
}

defineProps<Props>()
const emit = defineEmits<Emits>()

function onTrashClick() {
  emit('delete')
}
</script>

<style scoped>
.field {
  padding: 8px;
  border-radius: 8px;
  background-color: var(--p-badge-secondary-background);
}
.field-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.field-type {
  font-size: 12px;
  font-weight: 500;
}
.field-actives {
  display: flex;
  gap: 8px;
  align-items: center;
}
.p-button.filed-actives-button {
  width: 16px;
  height: 16px;
  padding: 0;
}
</style>
