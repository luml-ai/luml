<template>
  <div class="flex items-center gap-2">
    <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
    <div v-if="firstModel" class="max-w-[100px] text-nowrap overflow-hidden text-ellipsis">
      {{ firstModel.name }}
    </div>
    <Tag v-if="otherModels?.length" class="cursor-pointer" @click="toggle"
      >+{{ otherModels.length }}</Tag
    >
    <Popover ref="popover" class="w-[200px]">
      <div class="flex flex-col gap-2">
        <div v-for="model in otherModels" :key="model.id" class="flex items-center gap-2">
          <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
          <div class="max-w-[150px] text-nowrap overflow-hidden text-ellipsis">
            {{ model.name }}
          </div>
        </div>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { CircuitBoardIcon } from 'lucide-vue-next'
import { computed, useTemplateRef } from 'vue'
import { Tag, Popover } from 'primevue'

interface Props {
  models: { id: string; name: string }[]
}

const props = defineProps<Props>()

const popover = useTemplateRef('popover')

const firstModel = computed(() => props.models[0])

const otherModels = computed(() => props.models.slice(1))

function toggle(event: Event) {
  popover.value?.toggle(event)
}
</script>

<style scoped></style>
