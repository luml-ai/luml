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

    <div class="flex flex-col gap-1.5 px-1.5">
      <p class="text-sm font-medium">on env change</p>
      <Select
        :model-value="settings.onEnvChange"
        :options="envChangeOptions"
        option-label="label"
        option-value="value"
        size="small"
        class="w-full"
        @update:model-value="setEnvPolicy"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InputNumber, Select, SelectButton } from 'primevue'
import type { FlowSettings } from '../../model/types'

/**
 * The two settings that are real. A per-flow policy is set once and read back
 * rarely, so it rides in the panel's accordion, collapsed. Reactivity ships on
 * `auto` and is the only setting here that makes the daemon do anything by
 * itself; the third state, eager, is per-asset and lives on the card. The
 * env-change policy governs third-party packages only.
 */
const props = defineProps<{ settings: FlowSettings }>()

const emit = defineEmits<{ update: [settings: FlowSettings] }>()

const reactivityOptions = [
  { label: 'lazy', value: 'lazy' },
  { label: 'auto', value: 'auto' },
]

const envChangeOptions = [
  { label: 'ask to restart', value: 'ask' },
  { label: 'restart automatically', value: 'restart' },
  { label: 'never', value: 'never' },
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

function setEnvPolicy(value: FlowSettings['onEnvChange']): void {
  emit('update', { ...props.settings, onEnvChange: value })
}
</script>
