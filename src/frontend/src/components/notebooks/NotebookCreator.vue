<template>
  <div>
    <Button label="Create instance" @click="visible = true" />
    <Dialog v-model:visible="visible" modal header="CREATE A NEW INSTANCE" :pt="dialogPt">
      <NotebookCreateUpdateForm :loading="loading" @submit="onSubmit"></NotebookCreateUpdateForm>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, Dialog, useToast, type DialogPassThroughOptions } from 'primevue'
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue'
import { useNotebooksStore } from '@/stores/notebooks'

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const notebooksStore = useNotebooksStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

async function onSubmit(payload: { fullname: string }) {
  loading.value = true
  await notebooksStore.create(payload)
  loading.value = false
  visible.value = false
  toast.add({ severity: 'success', summary: 'Success', detail: 'Instance Created', life: 2000 })
}
</script>

<style scoped></style>
