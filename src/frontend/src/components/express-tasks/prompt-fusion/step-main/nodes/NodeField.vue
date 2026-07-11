<template>
  <div ref="fieldRef" class="field" :class="{ [variantClass]: field.variant }">
    <div class="content">
      <div v-if="label" class="label">{{ label }}</div>
      <span class="text">{{ field.value }}</span>
    </div>
    <div v-if="field.type || field.variadic" class="icons">
      <div v-if="field.type" class="icon">
        <component
          :is="PROMPT_FIELDS_ICONS[field.type]"
          width="16"
          height="16"
          color="var(--p-icon-muted-color)"
        />
      </div>
      <div v-if="field.variadic" class="icon">
        <brackets width="16" height="16" color="var(--p-icon-muted-color)" />
      </div>
    </div>
  </div>
  <handle
    v-if="handleTopPosition"
    :class="{ connected: connectingHandles.has(field.id) }"
    :id="field.id"
    :position="field.handlePosition"
    :style="{ top: handleTopPosition + 'px' }"
    :type="field.handlePosition === Position.Left ? 'target' : 'source'"
  />
</template>

<script setup lang="ts">
import type { NodeField } from '../../interfaces'
import { computed, onMounted, ref } from 'vue'
import { PROMPT_FIELDS_ICONS } from '../../interfaces'
import { Handle, Position } from '@vue-flow/core'
import { Brackets } from 'lucide-vue-next'
import { useVueFlow } from '@vue-flow/core'

const { edges } = useVueFlow()

type Props = {
  field: NodeField
  index?: number
}

const props = defineProps<Props>()

const fieldRef = ref<HTMLDivElement>()
const handleTopPosition = ref<number | null>(null)

const variantClass = computed(() => props.field.variant || '')
const connectingHandles = computed(() => {
  return edges.value.reduce((acc, edge) => {
    if (edge.sourceHandle) acc.add(edge.sourceHandle)
    if (edge.targetHandle) acc.add(edge.targetHandle)
    return acc
  }, new Set() as Set<string>)
})
const label = computed(() => (props.index ? `CONDITION ${props.index}` : null))

function calcHandlePosition() {
  if (!fieldRef.value) return
  handleTopPosition.value = fieldRef.value.offsetTop + fieldRef.value.clientHeight / 2
}

onMounted(() => {
  calcHandlePosition()
})
</script>

<style scoped>
.field {
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 4px;
  background-color: var(--p-highlight-background);
  white-space: nowrap;
  min-height: 28px;
}
.field.condition {
  background-color: var(--p-skeleton-background);
  min-height: 42px;
  align-items: flex-start;
}
.content {
  font-size: 12px;
  text-overflow: ellipsis;
  overflow: hidden;
}
.condition .content {
  font-size: 10px;
  line-height: 1.2;
}
.label {
  font-weight: 500;
}
.label:not(:last-child) {
  margin-bottom: 4px;
}
.icons {
  display: flex;
  gap: 4px;
  flex: 0 0 auto;
}
.icon {
  width: 20px;
  height: 20px;
  padding: 2px;
  background-color: var(--p-card-background);
  border-radius: 4px;
}
</style>
