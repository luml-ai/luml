<template>
  <OverlayBadge v-if="hideColumnsCount" :value="hideColumnsCount">
    <Button severity="secondary" :rounded="roundedButton" variant="outlined" @click="togglePopover">
      <span class="button-label">Edit columns</span>
      <component :is="buttonIcon" :size="14" />
    </Button>
  </OverlayBadge>
  <Button
    v-else
    severity="secondary"
    :rounded="roundedButton"
    variant="outlined"
    @click="togglePopover"
  >
    <span class="button-label">Edit columns</span>
    <component :is="buttonIcon" :size="14" />
  </Button>
  <Popover ref="popover">
    <UiRadioSelect
      :target="target"
      :options="columns"
      :selected-options="selectedColumns"
      placeholder="Column"
      @edit="onEdit"
    />
  </Popover>
</template>

<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { OverlayBadge, Button, Popover } from 'primevue'
import UiRadioSelect from '@/components/ui/UiRadioSelect.vue'

type Props = {
  target?: string
  columns: string[]
  selectedColumns: string[]
  roundedButton: boolean
  buttonIcon: LucideIcon
}
type Emits = {
  (event: 'edit', list: string[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const popover = ref()

const hideColumnsCount = computed(() => {
  if (!props.selectedColumns.length) return 0

  return props.columns.length - props.selectedColumns.length
})

function togglePopover(event: Event) {
  popover.value.toggle(event)
}

function onEdit(list: string[]) {
  emit('edit', list)
  popover.value.toggle()
}
</script>

<style scoped>
@media (max-width: 768px) {
  .button-label {
    display: none;
  }
}
</style>
