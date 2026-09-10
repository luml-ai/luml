<template>
  <div class="pair-agent">
    <Tag :value="tagValue" :severity="tagSeverity" />
    <button type="button" class="toolbar-pair-button" @click="openDialog">Pair an agent</button>

    <Dialog
      v-model:visible="visible"
      header="PAIR AN AGENT"
      modal
      dismissable-mask
      :draggable="false"
      :pt="DIALOG_PT"
      @update:visible="onVisibleChange"
    >
      <Listbox
        v-model="selectedAgentId"
        :options="NOTEBOOK_PAIRABLE_AGENTS"
        option-label="name"
        option-value="id"
        fluid
      >
        <template #option="{ option }">
          <div class="agent-option">
            <component :is="(option as PairableAgentInterface).icon" :size="16" />
            <span>{{ (option as PairableAgentInterface).name }}</span>
          </div>
        </template>
      </Listbox>
      <template #footer>
        <Button
          label="Pair"
          :loading="loading"
          :disabled="!selectedAgentId || loading"
          fluid
          rounded
          @click="onPair"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { PairableAgentInterface } from '@/components/notebooks/notebooks.interface'
import { Button, Dialog, Listbox, Tag } from 'primevue'
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { NOTEBOOK_PAIRABLE_AGENTS } from '@/components/notebooks/notebooks.const'

function agentIdForLabel(label: string | null): string | null {
  if (!label) return null
  const agent = NOTEBOOK_PAIRABLE_AGENTS.find(
    (agent) => agent.name.toLowerCase() === label.toLowerCase(),
  )
  return agent?.id ?? null
}

const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    class: 'w-[420px] rounded-lg!',
  },
  header: {
    class: 'text-xl uppercase',
  },
  content: {
    class: 'pb-7',
  },
}

const toast = useToast()

const flowStore = useFlowStore()

const visible = ref(false)
const loading = ref(false)
const selectedAgentId = ref<string | null>(agentIdForLabel(flowStore.pairedAgentLabel))

const tagValue = computed(() =>
  flowStore.pairedAgentLabel ? `${flowStore.pairedAgentLabel} paired` : 'Unpaired',
)
const tagSeverity = computed(() => (flowStore.pairedAgentLabel ? 'success' : 'secondary'))

function openDialog() {
  selectedAgentId.value = agentIdForLabel(flowStore.pairedAgentLabel)
  visible.value = true
}

function onVisibleChange(value: boolean) {
  if (value) return
  selectedAgentId.value = agentIdForLabel(flowStore.pairedAgentLabel)
}

async function onPair() {
  const agent = NOTEBOOK_PAIRABLE_AGENTS.find((agent) => agent.id === selectedAgentId.value)
  if (!agent) return

  loading.value = true
  try {
    await flowStore.pairAgent(agent)
    visible.value = false
    toast.add(successToast(`${agent.name} paired successfully`))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.pair-agent {
  @apply flex items-center gap-2;
}
.toolbar-pair-button {
  @apply text-primary cursor-pointer hover:text-primary-600 transition-colors p-1;
}
.agent-option {
  @apply flex items-center gap-2;
}
</style>
