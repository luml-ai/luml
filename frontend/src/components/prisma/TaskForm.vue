<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { InputText, Textarea, Select, Button, Checkbox } from 'primevue'
import type { AgentRepository, Agent } from '@/lib/api/prisma/prisma.interfaces'
import { api } from '@/lib/api'

defineProps<{
  repositories: AgentRepository[]
  loading: boolean
}>()

const emit = defineEmits<{
  submit: [data: { repository_id: string; name: string; agent_id: string; prompt: string; base_branch: string }]
}>()

const name = ref('')
const selectedRepository = ref<AgentRepository | null>(null)
const selectedAgent = ref<Agent | null>(null)
const prompt = ref('')
const agents = ref<Agent[]>([])
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
  if (!selectedRepository.value || !selectedAgent.value) return
  emit('submit', {
    repository_id: selectedRepository.value.id,
    name: name.value,
    agent_id: selectedAgent.value.id,
    prompt: prompt.value,
    base_branch: baseBranch.value,
  })
  name.value = ''
  prompt.value = ''
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
        <Checkbox v-model="showAgentBranches" :binary="true" inputId="showAgentBranchesTask" />
        <label for="showAgentBranchesTask">Show agent branches</label>
      </div>
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
    <div class="field">
      <label class="label">Task Name</label>
      <InputText v-model="name" placeholder="fix-auth-bug" class="w-full" />
    </div>
    <div class="field">
      <label class="label">Prompt</label>
      <Textarea v-model="prompt" rows="4" placeholder="Describe what the agent should do..." class="w-full" />
    </div>
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
</style>
