<script setup lang="ts">
import { ref } from 'vue'
import { Dialog, InputText, Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import FolderPicker from './FolderPicker.vue'
import { api } from '@/lib/api'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  created: []
}>()

const name = ref('')
const path = ref('')
const error = ref('')

async function submit() {
  error.value = ''
  if (!name.value.trim()) {
    error.value = 'Name is required'
    return
  }
  if (!path.value.trim()) {
    error.value = 'Repository path is required'
    return
  }
  try {
    await api.dataAgent.createRepository({ name: name.value.trim(), path: path.value })
    name.value = ''
    path.value = ''
    emit('created')
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') {
      error.value = detail
    } else if (e?.message) {
      error.value = e.message
    } else {
      error.value = 'Failed to create repository'
    }
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="New Repository"
    modal
    :style="{ width: '450px' }"
    @update:visible="!$event && emit('close')"
  >
    <div class="form">
      <div class="field">
        <label class="label">Name</label>
        <InputText v-model="name" placeholder="my-repo" class="w-full" />
      </div>
      <div class="field">
        <label class="label">Repository Path</label>
        <FolderPicker v-model="path" />
      </div>
      <div v-if="error" class="error">{{ error }}</div>
    </div>
    <template #footer>
      <Button severity="secondary" @click="emit('close')">
        <span>Cancel</span>
      </Button>
      <Button @click="submit">
        <Plus :size="14" />
        <span>Add</span>
      </Button>
    </template>
  </Dialog>
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

.error {
  color: var(--p-red-500);
  font-size: 14px;
}
</style>
