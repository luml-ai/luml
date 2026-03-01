<template>
  <Dialog v-model:visible="visible" header="Api key" modal :draggable="false" :pt="DIALOG_PT">
    <div class="mb-6 text-muted-color">
      It looks like you haven't provided your API key yet. You can generate one in your
      <a :href="lmlUrl" target="_blank" class="text-primary underline">LUML account settings</a>
    </div>
    <div>
      <InputText v-model="apiKey" placeholder="Enter api key" fluid :invalid="!!error" />
      <Message v-if="error" severity="error" size="small" variant="simple" class="mt-2">
        {{ error }}
      </Message>
    </div>
    <template #footer>
      <Button label="Add" fluid :loading="loading" @click="add" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog, InputText, Button, Message, useToast } from 'primevue'
import { API_KEY_SCHEMA, DIALOG_PT } from './data'
import { ref, watch } from 'vue'
import { useAuthStore } from '@/store/auth'
import { AxiosError } from 'axios'
import { getErrorMessage } from '@/helpers/errors'
import { apiService } from '@/api/api.service'
import z from 'zod'
import { successToast } from '@/toasts'

const authStore = useAuthStore()
const toast = useToast()
const visible = defineModel<boolean>('visible')

const apiKey = ref<string | null>(null)
const loading = ref<boolean>(false)
const error = ref<string | null>(null)

const lmlUrl = import.meta.env.VITE_LUML_URL

async function add() {
  resetError()
  if (!apiKey.value) {
    error.value = 'API key is required'
    return
  }
  loading.value = true
  try {
    API_KEY_SCHEMA.parse(apiKey.value)
    await authStore.setApiKey(apiKey.value)
    await apiService.checkAuth()
    visible.value = false
    toast.add(successToast('Authorization with the AРI key was successful!'))
  } catch (e) {
    if (e instanceof z.ZodError) {
      error.value = e.issues[0].message
    } else if (e instanceof AxiosError) {
      error.value = getErrorMessage(e)
    }
  } finally {
    loading.value = false
  }
}

function resetError() {
  error.value = null
}

watch(apiKey, () => {
  error.value = null
})

watch(visible, (v) => {
  if (!v) {
    apiKey.value = null
    error.value = null
  }
})
</script>

<style scoped></style>
