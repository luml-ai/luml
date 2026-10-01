<template>
  <div class="pair-agent">
    <Tag :value="tagValue" :severity="tagSeverity" />
    <button type="button" class="toolbar-pair-button" @click="openDialog">{{ buttonLabel }}</button>

    <Dialog
      v-model:visible="visible"
      header="AGENTS"
      modal
      dismissable-mask
      :draggable="false"
      :pt="DIALOG_PT"
    >
      <div class="agents-body">
        <p class="agents-note">
          An agent is paired when it connects over MCP. Set up a harness below, then start the
          agent in this workspace; this label updates by itself.
        </p>

        <AgentsPanel
          :harnesses="agents.harnesses.value"
          :loading="agents.loading.value"
          :load-error="agents.loadError.value"
          :busy-ids="agents.busyIds.value"
          @setup="agents.setup"
          @update="agents.update"
          @remove="agents.remove"
        />

        <section v-if="flowStore.agentSessions.length" class="sessions">
          <h3 class="sessions-title">Registered sessions</h3>
          <ul class="sessions-list">
            <li
              v-for="session in flowStore.agentSessions"
              :key="session.actor"
              class="session-row"
              :data-actor="session.actor"
            >
              <span class="session-label">{{ session.label }}</span>
              <span class="session-state" :class="{ 'session-state--live': session.leased }">
                {{ session.leased ? 'connected' : 'registered, no connection' }}
              </span>
              <Button
                v-if="!session.leased"
                text
                size="small"
                severity="danger"
                label="End"
                :loading="ending === session.actor"
                @click="onEnd(session.actor)"
              />
            </li>
          </ul>
        </section>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Button, Dialog, Tag } from 'primevue'
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import AgentsPanel from '@/flow/workbench/components/panel/AgentsPanel.vue'
import { useAgentHarnesses } from '@/flow/workbench/live/useAgentHarnesses'
import { agentToolVerb } from '@/components/notebooks/cell/cell.const'

const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    class: 'w-[520px] max-w-[calc(100vw-2rem)] rounded-lg!',
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
const ending = ref<string | null>(null)

// Paired is read off the store, which reads it off the daemon's lease state.
// Nothing in this dialog sets it: the agent connects, and the tag follows.
// While the agent is inside a call the tag says which, and which cell: the
// daemon brackets every call a leased connection makes, so this is live.
const tagValue = computed(() => {
  const label = flowStore.pairedAgentLabel
  if (!label) return 'Unpaired'
  const doing = flowStore.currentActivity
  if (!doing) return `${label} paired`
  const verb = doing.inCall ? agentToolVerb(doing.tool) : 'working on'
  if (doing.slug) return `${label} · ${verb} ${doing.slug}`
  return doing.inCall ? `${label} · ${verb}` : `${label} · working`
})
const tagSeverity = computed(() => {
  if (!flowStore.pairedAgentLabel) return 'secondary'
  return flowStore.currentActivity ? 'info' : 'success'
})
const buttonLabel = computed(() => (flowStore.pairedAgentLabel ? 'Agents' : 'Pair an agent'))

const agents = useAgentHarnesses(
  {
    list: () => workspaceApi.agentHarnesses(),
    setup: (id, consent) => workspaceApi.setupAgentHarness(id, consent),
    remove: (id) => workspaceApi.removeAgentHarness(id),
  },
  (failure) => toast.add(errorToast(failure)),
)

function openDialog() {
  visible.value = true
  // Detected on every open: a harness installed since the last look is the
  // whole reason to look again.
  void agents.refresh()
}

async function onEnd(actor: string) {
  ending.value = actor
  try {
    await flowStore.endAgentSession(actor)
  } catch (failure) {
    toast.add(errorToast(failure))
  } finally {
    ending.value = null
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
.agents-body {
  @apply flex flex-col gap-4;
}
.agents-note {
  @apply text-sm text-muted-color;
}
.sessions {
  @apply flex flex-col gap-2 border-t border-surface-200 pt-3 dark:border-surface-700;
}
.sessions-title {
  @apply text-sm font-medium;
}
.sessions-list {
  @apply flex flex-col gap-1;
}
.session-row {
  @apply flex items-center gap-2 text-sm;
}
.session-label {
  @apply flex-1 min-w-0 truncate;
}
.session-state {
  @apply text-muted-color;
}
.session-state--live {
  @apply text-(--p-message-success-color);
}
</style>
