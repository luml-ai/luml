<template>
  <div v-if="models.length" class="flex items-center gap-2">
    <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
    <button
      v-if="firstModel"
      class="max-w-[100px] text-nowrap overflow-hidden text-ellipsis hover:underline cursor-pointer"
      @click="onModelClick(firstModel.id)"
    >
      {{ firstModel.name }}
    </button>
    <Tag v-if="otherModels?.length" class="cursor-pointer" @click="toggle">
      +{{ otherModels.length }}
    </Tag>
    <Popover ref="popover" class="w-[200px]">
      <div class="flex flex-col gap-2">
        <div v-for="model in otherModels" :key="model.id" class="flex items-center gap-2">
          <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
          <button
            class="max-w-[150px] text-nowrap overflow-hidden text-ellipsis hover:underline cursor-pointer"
            @click="onModelClick(model.id)"
          >
            {{ model.name }}
          </button>
        </div>
      </div>
    </Popover>
  </div>
  <span v-else>-</span>
</template>

<script setup lang="ts">
import { CircuitBoardIcon } from 'lucide-vue-next'
import { computed, useTemplateRef } from 'vue'
import { Tag, Popover } from 'primevue'
import { useModelCardStore } from '@/store/model-card'

interface Props {
  models: { id: string; name: string }[]
}

const props = defineProps<Props>()

const popover = useTemplateRef('popover')

const modelCardStore = useModelCardStore()

const firstModel = computed(() => props.models[0])

const otherModels = computed(() => props.models.slice(1))

function toggle(event: Event) {
  popover.value?.toggle(event)
}

function onModelClick(modelId: string) {
  modelCardStore.showModelCard(modelId)
}
</script>

<style scoped></style>
