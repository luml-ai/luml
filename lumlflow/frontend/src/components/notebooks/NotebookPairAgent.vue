<template>
  <div class="pair-agent">
    <Tag v-if="!agentsOnFlow.length" value="Unpaired" severity="secondary" />
    <button
      v-else
      type="button"
      class="agents-trigger"
      :style="soleAgent ? { '--agent-color': soleAgent.color } : undefined"
      :title="soleAgent ? chipText(soleAgent) : undefined"
      aria-haspopup="dialog"
      @click="popover?.toggle($event)"
    >
      <span class="agent-dots">
        <span
          v-for="agent in agentsOnFlow.slice(0, MAX_DOTS)"
          :key="agent.actor"
          class="agent-dot"
          :class="{ 'agent-dot--busy': agent.tool }"
          :style="{ '--agent-color': agent.color }"
        />
      </span>
      <span class="truncate">{{
        soleAgent ? chipText(soleAgent) : `${agentsOnFlow.length} agents`
      }}</span>
    </button>
    <Popover ref="popover" :pt="POPOVER_PT">
      <ul class="agents-list">
        <li
          v-for="agent in agentsOnFlow"
          :key="agent.actor"
          class="agents-row"
          :style="{ '--agent-color': agent.color }"
          :data-agent="agent.actor"
        >
          <span class="agent-dot" :class="{ 'agent-dot--busy': agent.tool }" />
          <span class="agents-row-label">{{ agent.label }}</span>
          <span class="agents-row-state">
            <template v-if="agent.slug">
              {{ agent.tool ? agentToolVerb(agent.tool) : 'working on' }}
              <button type="button" class="agents-row-cell" @click="onCellClick(agent.slug)">
                {{ agent.slug }}
              </button>
            </template>
            <template v-else>{{ agent.tool ? 'working' : 'idle' }}</template>
          </span>
        </li>
      </ul>
    </Popover>
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
          An agent is paired when it connects over MCP. Set up a harness below, then start the agent
          in this workspace; this label updates by itself.
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
import type { DialogPassThroughOptions, PopoverPassThroughOptions } from 'primevue'
import { Button, Dialog, Popover, Tag } from 'primevue'
import { computed, ref, useTemplateRef } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import type { PairedAgent } from '@/store/flow'
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

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')
const agentsOnFlow = computed(() => flowStore.pairedAgents)
const soleAgent = computed(() =>
  agentsOnFlow.value.length === 1 ? (agentsOnFlow.value[0] ?? null) : null,
)

const MAX_DOTS = 4

const POPOVER_PT: PopoverPassThroughOptions = {
  content: { class: 'p-3' },
}

function onCellClick(slug: string) {
  flowStore.selectCell(slug)
  popover.value?.hide()
}

function chipText(agent: PairedAgent): string {
  if (!agent.slug && !agent.tool) return `${agent.label} paired`
  const verb = agent.tool ? agentToolVerb(agent.tool) : 'working on'
  if (agent.slug) return `${agent.label} · ${verb} ${agent.slug}`
  return `${agent.label} · working`
}
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
  @apply flex items-center gap-2 flex-wrap;
}
.agents-trigger {
  @apply inline-flex items-center gap-1.5 max-w-64 px-2 py-0.5 rounded-md text-xs font-medium cursor-pointer;
  color: var(--agent-color, var(--p-text-color));
  background: color-mix(in srgb, var(--agent-color, var(--p-text-muted-color)) 12%, transparent);
}
.agent-dots {
  @apply inline-flex items-center -space-x-0.5 shrink-0;
}
.agent-dot {
  @apply w-1.5 h-1.5 rounded-full shrink-0 ring-1 ring-(--p-content-background);
  background: var(--agent-color);
}
.agents-list {
  @apply flex flex-col gap-2 min-w-56 max-w-80;
}
.agents-row {
  @apply flex items-center gap-2 text-sm;
}
.agents-row-label {
  @apply font-medium shrink-0;
  color: var(--agent-color);
}
.agents-row-state {
  @apply text-muted-color truncate;
}
.agents-row-cell {
  @apply text-color cursor-pointer hover:underline;
}
.agent-dot--busy {
  @apply animate-pulse;
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
