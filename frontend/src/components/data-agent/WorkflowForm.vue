<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { InputText, InputNumber, Textarea, Select, Checkbox } from 'primevue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import type { AgentRepository, Agent } from '@/lib/api/data-agent/data-agent.interfaces'
import { api } from '@/lib/api'

defineProps<{
  repositories: AgentRepository[]
  loading: boolean
}>()

export interface WorkflowFormData {
  repository_id: string
  name: string
  objective: string
  base_branch: string
  agent_id: string | undefined
  run_command: string | undefined
  max_depth: number
  max_children_per_fork: number
  max_debug_retries: number
  max_concurrency: number
  fork_auto_approve: boolean
  auto_mode: boolean
  auto_terminate_timeout: number
}

const emit = defineEmits<{
  submit: [data: WorkflowFormData]
}>()

const name = ref('')
const selectedRepository = ref<AgentRepository | null>(null)
const selectedAgent = ref<Agent | null>(null)
const objective = ref('')
const baseBranch = ref('main')
const branchOptions = ref<string[]>([])
const branchesLoading = ref(false)
const showAgentBranches = ref(false)

const AGENT_PREFIXES = ['agent/', 'luml-agent/']

function isAgentBranch(branch: string): boolean {
  return AGENT_PREFIXES.some((p) => branch.startsWith(p))
}

function filteredBranches(): string[] {
  if (showAgentBranches.value) return branchOptions.value
  return branchOptions.value.filter((b) => !isAgentBranch(b))
}

function hasAgentBranches(): boolean {
  return branchOptions.value.some((b) => isAgentBranch(b))
}
const runCommand = ref('uv run main.py')
const maxDepth = ref(3)
const maxChildrenPerFork = ref(4)
const maxDebugRetries = ref(2)
const maxConcurrency = ref(3)
const forkAutoApprove = ref(true)
const autoMode = ref(false)
const autoTerminateTimeout = ref(30)
const agents = ref<Agent[]>([])
const showAdvanced = ref(false)

let branchAbort: AbortController | null = null

onMounted(async () => {
  agents.value = await api.dataAgent.listAvailableAgents()
  if (agents.value.length > 0) {
    selectedAgent.value = agents.value[0]
  }
})

watch(selectedRepository, async (repo) => {
  branchAbort?.abort()
  branchOptions.value = []
  showAgentBranches.value = false

  if (!repo) return

  branchAbort = new AbortController()
  branchesLoading.value = true
  try {
    const branches = await api.dataAgent.listBranches(repo.path, { signal: branchAbort.signal })
    branchOptions.value = branches
    if (branches.length > 0) {
      baseBranch.value = branches.includes('main') ? 'main' : branches[0]
    }
  } catch {
    // ignore aborted or failed fetches
  } finally {
    branchesLoading.value = false
  }
})

function submit() {
  if (!selectedRepository.value) return
  emit('submit', {
    repository_id: selectedRepository.value.id,
    name: name.value,
    objective: objective.value,
    base_branch: baseBranch.value,
    agent_id: selectedAgent.value?.id,
    run_command: runCommand.value || undefined,
    max_depth: maxDepth.value,
    max_children_per_fork: maxChildrenPerFork.value,
    max_debug_retries: maxDebugRetries.value,
    max_concurrency: maxConcurrency.value,
    fork_auto_approve: forkAutoApprove.value,
    auto_mode: autoMode.value,
    auto_terminate_timeout: autoTerminateTimeout.value,
  })
  name.value = ''
  objective.value = ''
  runCommand.value = 'uv run main.py'
}

defineExpose({ submit })
</script>

<template>
  <div class="form">
    <div class="field">
      <label class="label">Repository</label>
      <Select
        v-model="selectedRepository"
        :options="repositories"
        optionLabel="name"
        placeholder="Select a repository"
        class="w-full"
      />
    </div>
    <div class="field">
      <label class="label">Base Branch</label>
      <Select
        v-model="baseBranch"
        :options="filteredBranches()"
        :disabled="!selectedRepository"
        :loading="branchesLoading"
        editable
        :placeholder="branchesLoading ? 'Loading branches…' : 'Select a repository first'"
        class="w-full"
      />
      <div v-if="hasAgentBranches()" class="agent-branch-toggle">
        <Checkbox v-model="showAgentBranches" :binary="true" inputId="showAgentBranchesWorkflow" />
        <label for="showAgentBranchesWorkflow">Show agent branches</label>
      </div>
    </div>
    <div class="field">
      <label class="label">Workflow Name</label>
      <InputText v-model="name" placeholder="my-feature-workflow" class="w-full" />
    </div>
    <div class="field">
      <label class="label">Objective</label>
      <Textarea v-model="objective" rows="3" placeholder="Describe what this workflow should accomplish..." class="w-full" />
    </div>
    <div class="field">
      <label class="label">Agent</label>
      <Select
        v-model="selectedAgent"
        :options="agents"
        optionLabel="name"
        placeholder="Select an agent"
        class="w-full"
      />
    </div>
    <button type="button" class="advanced-toggle" @click="showAdvanced = !showAdvanced">
      <component :is="showAdvanced ? ChevronUp : ChevronDown" :size="14" />
      <span>Advanced options</span>
    </button>
    <template v-if="showAdvanced">
      <div class="field">
        <label class="label">Run Command</label>
        <InputText v-model="runCommand" placeholder="uv run main.py" class="w-full" />
      </div>
      <div class="config-row">
        <div class="field field--small">
          <label class="label">Max Depth</label>
          <InputNumber v-model="maxDepth" :min="1" :max="10" />
        </div>
        <div class="field field--small">
          <label class="label">Max Fork Children</label>
          <InputNumber v-model="maxChildrenPerFork" :min="1" :max="10" />
        </div>
      </div>
      <div class="config-row">
        <div class="field field--small">
          <label class="label">Max Debug Retries</label>
          <InputNumber v-model="maxDebugRetries" :min="0" :max="10" />
        </div>
        <div class="field field--small">
          <label class="label">Concurrency</label>
          <InputNumber v-model="maxConcurrency" :min="1" :max="10" />
        </div>
      </div>
      <div class="field field--checkbox">
        <Checkbox v-model="forkAutoApprove" :binary="true" inputId="forkAutoApprove" />
        <label for="forkAutoApprove">Auto-approve fork proposals</label>
      </div>
      <div class="field field--checkbox">
        <Checkbox v-model="autoMode" :binary="true" inputId="autoMode" />
        <label for="autoMode">Auto mode (terminate idle agents)</label>
      </div>
      <div v-if="autoMode" class="field field--small">
        <label class="label">Auto-terminate timeout (seconds)</label>
        <InputNumber v-model="autoTerminateTimeout" :min="5" :max="300" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 14px;
  font-weight: 500;
}

.agent-branch-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--p-text-muted-color);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.advanced-toggle:hover {
  color: var(--p-text-color);
}

.config-row {
  display: flex;
  gap: 12px;
}

.field--small {
  flex: 1;
  min-width: 0;
}

.field--small :deep(.p-inputnumber),
.field--small :deep(.p-inputtext) {
  width: 100%;
}

.field--checkbox {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
</style>
