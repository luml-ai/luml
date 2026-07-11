<template>
  <div class="notebooks">
    <div class="top">
      <div class="headings">
        <h1 class="main-title">Notebooks</h1>
      </div>
      <NotebookCreator></NotebookCreator>
    </div>
    <div class="notebook-content">
      <NotebooksList></NotebooksList>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import NotebooksList from './NotebooksList.vue'
import NotebookCreator from './NotebookCreator.vue'
import { useNotebooksStore } from '@/stores/notebooks'
import { useToast } from 'primevue'

const notebooksStore = useNotebooksStore()
const toast = useToast()
const loading = ref(false)

const fetchNotebooks = async () => {
  try {
    loading.value = true
    await notebooksStore.getNotebooks()
  } catch {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to receive notebooks',
      life: 2000,
    })
  } finally {
    loading.value = false
  }
}

const handleVisibilityChange = () => {
  if (!document.hidden) {
    fetchNotebooks()
  }
}

const handleWindowFocus = () => {
  fetchNotebooks()
}

onMounted(async () => {
  await fetchNotebooks()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('focus', handleWindowFocus)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('focus', handleWindowFocus)
})
</script>

<style scoped>
.top {
  display: flex;
  justify-content: space-between;
  gap: 30px;
  align-items: flex-end;
  margin-bottom: 44px;
}

.notebook-content {
  padding: 12px;
  border-radius: 8px;
  background-color: var(--p-card-background);
}
</style>
