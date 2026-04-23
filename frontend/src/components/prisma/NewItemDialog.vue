<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Dialog, SelectButton, Button } from 'primevue'
import { Plus, ListTodo, Waypoints } from 'lucide-vue-next'
import type { AgentRepository } from '@/lib/api/prisma/prisma.interfaces'
import { api } from '@/lib/api'
import TaskForm from './TaskForm.vue'
import WorkflowForm from './WorkflowForm.vue'

type ItemType = 'task' | 'workflow'

const props = defineProps<{
  visible: boolean
  initialType: ItemType
  repositories: AgentRepository[]
}>()

const emit = defineEmits<{
  close: []
  created: []
}>()

const selectedType = ref<ItemType>(props.initialType)
const loading = ref(false)
const error = ref('')
const formRef = ref<InstanceType<typeof TaskForm> | InstanceType<typeof WorkflowForm> | null>(null)

watch(() => props.visible, (v) => {
  if (v) {
    selectedType.value = props.initialType
    error.value = ''
  }
})

const typeOptions = [
  { label: 'Task', value: 'task' as const, icon: ListTodo },
  { label: 'Workflow', value: 'workflow' as const, icon: Waypoints },
]

const formComponent = computed(() =>
  selectedType.value === 'task' ? TaskForm : WorkflowForm,
)

async function onFormSubmit(data: Record<string, unknown>) {
  error.value = ''
  loading.value = true
  try {
    if (selectedType.value === 'task') {
      await api.dataAgent.createTask(data as any)
    } else {
      await api.dataAgent.createRun(data as any)
    }
    emit('created')
  } catch (e: any) {
    const label = selectedType.value === 'task' ? 'task' : 'workflow'
    error.value = e?.response?.data?.detail ?? `Failed to create ${label}`
  } finally {
    loading.value = false
  }
}

function onCreateClick() {
  formRef.value?.submit()
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="Create new item"
    modal
    :style="{ width: '540px' }"
    @update:visible="!$event && emit('close')"
  >
    <SelectButton
      v-model="selectedType"
      :options="typeOptions"
      optionLabel="label"
      optionValue="value"
      class="type-select"
    >
      <template #option="{ option }">
        <span class="type-option">
          <component :is="option.icon" :size="14" />
          {{ option.label }}
        </span>
      </template>
    </SelectButton>
    <component
      :is="formComponent"
      ref="formRef"
      :repositories="repositories"
      :loading="loading"
      @submit="onFormSubmit"
    />
    <div v-if="error" class="error">{{ error }}</div>
    <template #footer>
      <Button severity="secondary" @click="emit('close')">
        <span>Cancel</span>
      </Button>
      <Button :loading="loading" @click="onCreateClick">
        <Plus :size="14" />
        <span>Create</span>
      </Button>
    </template>
  </Dialog>
</template>

<style scoped>
.type-select {
  margin-bottom: 16px;
}

.type-option {
  display: flex;
  align-items: center;
  gap: 6px;
}

.error {
  color: var(--p-red-500);
  font-size: 14px;
  margin-top: 8px;
}
</style>
