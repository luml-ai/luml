<template>
  <div class="flex min-w-0 flex-col gap-4">
    <div class="flex flex-col gap-1.5 px-1.5">
      <p class="text-sm font-medium">reactivity</p>
      <SelectButton
        :model-value="settings.reactivity"
        :options="reactivityOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        :pt="smallOptions"
        @update:model-value="setReactivity"
      />
      <div v-if="settings.reactivity === 'auto'" class="flex items-center gap-2 text-sm">
        <span class="text-muted-color">auto below</span>
        <InputNumber
          :model-value="settings.autoThresholdSeconds"
          :min="1"
          :max="3600"
          suffix="s"
          size="small"
          :input-style="{ width: '4.5rem' }"
          @update:model-value="setThreshold"
        />
      </div>
      <!-- The setting decides whether the daemon runs things by itself, which
           is worth one sentence at the control rather than only in the guide. -->
      <p class="text-sm text-muted-color">{{ reactivityHint }}</p>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InputNumber, SelectButton } from 'primevue'
import type { FlowSettings } from '../../model/types'

const props = defineProps<{ settings: FlowSettings }>()

const emit = defineEmits<{ update: [settings: FlowSettings] }>()

const reactivityOptions = [
  { label: 'lazy', value: 'lazy' },
  { label: 'auto', value: 'auto' },
]

const smallOptions = { pcToggleButton: { root: { class: 'text-sm' } } }

const reactivityHint = computed(() =>
  props.settings.reactivity === 'lazy'
    ? 'nothing runs until you ask for it'
    : 'a cell already timed under this refreshes itself when something above it changes. anything dearer waits for you, and says so on the card.',
)

function setReactivity(value: FlowSettings['reactivity']): void {
  emit('update', { ...props.settings, reactivity: value })
}

function setThreshold(value: number | null): void {
  if (value !== null) emit('update', { ...props.settings, autoThresholdSeconds: value })
}
</script>
