<template>
  <div>
    <MultiSelect
      v-model="model"
      :options="options"
      size="small"
      placeholder="Tags"
      :pt="tagsSelectPt"
      class="rich-control-item"
    >
      <template #header>
        <div class="rich-tags-panel">
          <UiRadioSelect
            :options="options"
            :selected-options="model || []"
            :selected-by-default="false"
            :show-all-available="false"
            size="small"
            placeholder="Find tag"
            @edit="onEdit"
          />
        </div>
      </template>
    </MultiSelect>
  </div>
</template>

<script setup lang="ts">
import type { MultiSelectPassThroughOptions } from 'primevue'
import { MultiSelect } from 'primevue'
import UiRadioSelect from '@/components/ui/UiRadioSelect.vue'

type Props = {
  options: string[]
}

defineProps<Props>()

const model = defineModel<string[]>()

const tagsSelectPt: MultiSelectPassThroughOptions = {
  root: {
    style: 'width: 160px;',
  },
  header: {
    style: 'display: none;',
  },
  listContainer: {
    style: 'display: none;',
  },
  overlay: {
    style: 'background: transparent; border: none; box-shadow: none; overflow: visible;',
  },
}

function onEdit(options: string[]) {
  model.value = options
}
</script>

<style scoped>
.rich-control-item {
  border-radius: 8px 0 0 8px;
  height: 100%;
}

.rich-tags-panel {
  position: absolute;
  top: 0;
  right: -23px;
  box-sizing: border-box;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
}
</style>
