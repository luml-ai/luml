<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { InputText, InputNumber, Textarea, Select, Checkbox } from 'primevue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import type { AgentRepository, Agent } from '@/lib/api/prisma/prisma.interfaces'
import type { Orbit } from '@/lib/api/api.interfaces'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useOrganizationStore } from '@/stores/organization'

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
  auto_mode: boolean
  auto_terminate_timeout: number
  implement_timeout: number
  run_timeout: number
  debug_timeout: number
  fork_timeout: number
  luml_collection_id: string | undefined
  luml_organization_id: string | undefined
  luml_orbit_id: string | undefined
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

const AGENT_PREFIXES = ['prisma/']

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
const maxDepth = ref(2)
const maxChildrenPerFork = ref(2)
const maxDebugRetries = ref(2)
const maxConcurrency = ref(1)
const autoMode = ref(false)
const autoTerminateTimeout = ref(30)
const implementTimeout = ref(3600)
const runTimeout = ref(0)
const debugTimeout = ref(1800)
const forkTimeout = ref(1200)

const agents = ref<Agent[]>([])
const showAdvanced = ref(false)

const authStore = useAuthStore()
const orgStore = useOrganizationStore()
const orbits = ref<Orbit[]>([])
const selectedOrbit = ref<Orbit | null>(null)
const orbitsLoading = ref(false)
const collections = ref<OrbitCollection[]>([])
const selectedCollection = ref<OrbitCollection | null>(null)
const collectionsLoading = ref(false)
const uploadEnabled = ref(false)

const showCollectionSelector = computed(() => authStore.isAuth && orgStore.currentOrganization)

let branchAbort: AbortController | null = null

async function loadOrbits() {
  const orgId = orgStore.currentOrganization?.id
  if (!orgId) return

  orbitsLoading.value = true
  try {
    orbits.value = await api.getOrganizationOrbits(orgId)
  } catch {
    orbits.value = []
  } finally {
    orbitsLoading.value = false
  }
}

async function loadCollections() {
  const orgId = orgStore.currentOrganization?.id
  const orbitId = selectedOrbit.value?.id
  if (!orgId || !orbitId) return

  collectionsLoading.value = true
  try {
    const resp = await api.orbitCollections.getCollectionsList(orgId, orbitId, {
      cursor: null,
      limit: 100,
    })
    collections.value = resp.items
  } catch {
    collections.value = []
  } finally {
    collectionsLoading.value = false
  }
}

onMounted(async () => {
  agents.value = await api.dataAgent.listAvailableAgents()
  if (agents.value.length > 0) {
    selectedAgent.value = agents.value[0]
  }
})

watch(uploadEnabled, (enabled) => {
  if (!enabled) {
    selectedOrbit.value = null
    selectedCollection.value = null
  } else if (orbits.value.length === 0) {
    loadOrbits()
  }
})

watch(selectedOrbit, (orbit) => {
  selectedCollection.value = null
  collections.value = []
  if (orbit) {
    loadCollections()
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
  const col = selectedCollection.value
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
    auto_mode: autoMode.value,
    auto_terminate_timeout: autoTerminateTimeout.value,
    implement_timeout: implementTimeout.value,
    run_timeout: runTimeout.value,
    debug_timeout: debugTimeout.value,
    fork_timeout: forkTimeout.value,
    luml_collection_id: col?.id,
    luml_organization_id: col ? orgStore.currentOrganization?.id : undefined,
    luml_orbit_id: col ? selectedOrbit.value?.id : undefined,
  })
  name.value = ''
  objective.value = ''
  runCommand.value = 'uv run main.py'
  uploadEnabled.value = false
  selectedOrbit.value = null
  selectedCollection.value = null
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
      <Textarea
        v-model="objective"
        rows="3"
        placeholder="Describe what this workflow should accomplish..."
        class="w-full"
      />
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
    <div class="field field--checkbox">
      <Checkbox v-model="autoMode" :binary="true" inputId="autoMode" />
      <label for="autoMode">Auto mode (bypass permission)</label>
    </div>
    <div v-if="autoMode" class="field field--small">
      <label class="label">Auto-terminate timeout (seconds)</label>
      <InputNumber v-model="autoTerminateTimeout" :min="5" :max="300" />
    </div>
    <div class="option-group">
      <div class="field field--checkbox">
        <Checkbox
          v-model="uploadEnabled"
          :binary="true"
          inputId="uploadEnabled"
          :disabled="!showCollectionSelector"
        />
        <label for="uploadEnabled" :class="{ 'label--disabled': !showCollectionSelector }"
          >Upload artifacts to collection</label
        >
      </div>
      <p v-if="!showCollectionSelector" class="hint">
        Sign in to upload artifacts to a collection.
      </p>
      <template v-if="uploadEnabled && showCollectionSelector">
        <div class="field">
          <label class="label">Orbit</label>
          <Select
            v-model="selectedOrbit"
            :options="orbits"
            optionLabel="name"
            :loading="orbitsLoading"
            placeholder="Select an orbit"
            showClear
            class="w-full"
          />
        </div>
        <div v-if="selectedOrbit" class="field">
          <label class="label">Collection</label>
          <Select
            v-model="selectedCollection"
            :options="collections"
            optionLabel="name"
            :loading="collectionsLoading"
            placeholder="Select a collection"
            showClear
            class="w-full"
          />
        </div>
      </template>
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
      <div class="config-row">
        <div class="field field--small">
          <label class="label">Implement timeout (s)</label>
          <InputNumber v-model="implementTimeout" :min="0" :max="7200" />
        </div>
        <div class="field field--small">
          <label class="label">Run timeout (s, 0=none)</label>
          <InputNumber v-model="runTimeout" :min="0" :max="86400" />
        </div>
      </div>
      <div class="config-row">
        <div class="field field--small">
          <label class="label">Debug timeout (s)</label>
          <InputNumber v-model="debugTimeout" :min="0" :max="7200" />
        </div>
        <div class="field field--small">
          <label class="label">Fork timeout (s)</label>
          <InputNumber v-model="forkTimeout" :min="0" :max="7200" />
        </div>
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

.option-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
}

.hint {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin: 0;
}

.label--disabled {
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
