<template>
  <Button
    variant="outlined"
    severity="secondary"
    size="small"
    class="settings-button"
    @click="toggle"
  >
    <template #icon> <Bolt :size="12" /> </template>
  </Button>
  <Popover ref="popoverRef" :pt="POPOVER_WITHOUT_ARROW_PT" class="w-90">
    <div class="content">
      <div class="content-column">
        <label class="label">Reactivity</label>
        <SelectButton
          :model-value="flowStore.reactivity"
          :options="NOTEBOOK_REACTIVITY_OPTIONS"
          :allow-empty="false"
          optionLabel="label"
          optionValue="value"
          size="small"
          @update:model-value="flowStore.setReactivity($event)"
        />
      </div>
      <div v-if="flowStore.reactivity === 'auto'" class="content-column">
        <label class="label">Auto below</label>
        <InputNumber
          :model-value="flowStore.autoThresholdSeconds"
          :min="1"
          :max="3600"
          suffix=" (s)"
          size="small"
          placeholder="5 (s)"
          input-class="w-full"
          @update:model-value="onThresholdChange"
        />
      </div>
    </div>
    <p class="text">{{ reactivityHint }}</p>
  </Popover>
</template>

<script setup lang="ts">
import { Button, InputNumber, Popover, SelectButton } from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useFlowStore } from '@/store/flow'
import { NOTEBOOK_REACTIVITY_HINTS, NOTEBOOK_REACTIVITY_OPTIONS } from './notebooks.const'
import { POPOVER_WITHOUT_ARROW_PT } from '@/prime-vue/pass-through/popover.pt'

const flowStore = useFlowStore()

const popoverRef = ref<InstanceType<typeof Popover>>()

const reactivityHint = computed(() => NOTEBOOK_REACTIVITY_HINTS[flowStore.reactivity])

const toggle = (event: Event) => {
  popoverRef.value?.toggle(event)
}

const onThresholdChange = (value: number | null) => {
  if (value !== null) flowStore.setAutoThresholdSeconds(value)
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.settings-button {
  @apply p-0 h-10! w-10!;
}
.content {
  @apply grid grid-cols-2 gap-4 mb-5;
}
.content-column {
  @apply flex flex-col gap-2;
}
.label {
  @apply text-sm font-medium text-color;
}
.text {
  @apply text-sm text-muted-color;
}
</style>
