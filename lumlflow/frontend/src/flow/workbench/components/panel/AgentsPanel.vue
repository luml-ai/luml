<template>
  <div class="flex flex-col gap-3 px-1.5">
    <p v-if="loading && !harnesses.length" class="text-sm text-muted-color">detecting agents…</p>
    <p v-else-if="loadError && !harnesses.length" class="text-sm text-(--p-message-error-color)">
      {{ loadError }}
    </p>
    <p v-else-if="!harnesses.length" class="text-sm text-muted-color">
      no supported agent harnesses detected
    </p>
    <p v-if="loadError && harnesses.length" class="text-sm text-(--p-message-error-color)">
      {{ loadError }}
    </p>

    <div
      v-for="harness in harnesses"
      :key="harness.id"
      class="flex min-w-0 flex-col gap-2 rounded-lg border border-surface-200 p-2.5 dark:border-surface-700"
    >
      <div class="flex min-w-0 items-center gap-2">
        <Checkbox
          v-if="harness.action === 'setup'"
          v-model="selected"
          :input-id="`agent-${harness.id}`"
          :value="harness.id"
          :disabled="busy(harness.id)"
        />
        <label
          :for="harness.action === 'setup' ? `agent-${harness.id}` : undefined"
          class="min-w-0 flex-1 text-base"
        >
          {{ harness.display_name }}
        </label>
        <span class="shrink-0 text-sm" :class="stateClass(harness.state)">
          {{ harness.state }}
        </span>
      </div>

      <p v-if="harness.shell_hint" class="text-sm text-muted-color">
        {{ harness.shell_hint }}
      </p>
      <p v-if="harness.error" class="text-sm text-(--p-message-error-color)">
        {{ harness.error }}
      </p>
      <p
        v-if="harness.state === 'set up' && harness.post_write_hint"
        class="text-sm text-muted-color"
      >
        {{ harness.post_write_hint }}
      </p>

      <template v-if="showSnippet(harness)">
        <p class="break-words text-sm text-muted-color">
          paste into <code class="font-mono text-sm">{{ harness.config_path }}</code>
        </p>
        <CopyBlock :value="harness.snippet" :label="`copy ${harness.display_name} MCP snippet`" />
      </template>

      <div
        v-if="harness.action === 'update' || harness.state === 'set up'"
        class="flex justify-end gap-1"
      >
        <Button
          v-if="harness.action === 'update'"
          text
          label="Update"
          :loading="busy(harness.id)"
          @click="emit('update', harness.id)"
        />
        <Button
          v-if="harness.state === 'set up'"
          text
          severity="danger"
          label="Remove"
          :loading="busy(harness.id)"
          @click="emit('remove', harness.id)"
        />
      </div>
    </div>

    <Button
      v-if="setupHarnesses.length"
      label="Set up"
      :disabled="!selectedHarnesses.length || selectedHarnesses.some((harness) => busy(harness.id))"
      @click="beginSetup"
    />

    <Dialog
      v-model:visible="consentVisible"
      modal
      header="Set up agents"
      :style="{ width: '30rem' }"
    >
      <div class="flex flex-col gap-3">
        <p v-for="line in consentLines" :key="line" class="text-base">
          {{ line }}
        </p>
        <div class="flex justify-end gap-2">
          <Button text severity="secondary" label="Not now" @click="consentVisible = false" />
          <Button label="Allow and set up" @click="approveSetup" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Checkbox, Dialog } from 'primevue'
import type { AgentHarness, AgentHarnessState } from '@/flow/api/types'
import CopyBlock from '../../ui/CopyBlock.vue'

const props = withDefaults(
  defineProps<{
    harnesses: AgentHarness[]
    loading?: boolean
    loadError?: string | null
    busyIds?: string[]
  }>(),
  { loading: false, loadError: null, busyIds: () => [] },
)

const emit = defineEmits<{
  setup: [ids: string[], consent: boolean]
  update: [id: string]
  remove: [id: string]
}>()

const selected = ref<string[]>([])
const consentVisible = ref(false)
const setupHarnesses = computed(() =>
  props.harnesses.filter((harness) => harness.action === 'setup'),
)
const selectedHarnesses = computed(() =>
  setupHarnesses.value.filter((harness) => selected.value.includes(harness.id)),
)
const consentLines = computed(() =>
  selectedHarnesses.value.flatMap((harness) =>
    harness.consent_required && harness.consent_prompt ? [harness.consent_prompt] : [],
  ),
)

watch(
  () => setupHarnesses.value.map((harness) => harness.id).join('\n'),
  () => {
    const available = new Set(setupHarnesses.value.map((harness) => harness.id))
    selected.value = selected.value.filter((id) => available.has(id))
  },
)

function busy(id: string): boolean {
  return props.busyIds.includes(id)
}

function showSnippet(harness: AgentHarness): boolean {
  return (
    !harness.can_setup ||
    harness.error !== null ||
    harness.state === 'out of date' ||
    harness.state === 'broken'
  )
}

function stateClass(state: AgentHarnessState): string {
  if (state === 'set up') return 'text-(--p-message-success-color)'
  if (state === 'out of date' || state === 'broken') return 'text-(--p-message-warn-color)'
  return 'text-muted-color'
}

function beginSetup(): void {
  if (!selectedHarnesses.value.length) return
  if (consentLines.value.length) {
    consentVisible.value = true
    return
  }
  emit(
    'setup',
    selectedHarnesses.value.map((harness) => harness.id),
    false,
  )
}

function approveSetup(): void {
  consentVisible.value = false
  emit(
    'setup',
    selectedHarnesses.value.map((harness) => harness.id),
    true,
  )
}
</script>
