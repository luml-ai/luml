<template>
  <Dialog
    :visible="sessionTokenRejected"
    header="Open this Flow"
    modal
    :closable="false"
    :draggable="false"
    :pt="DIALOG_PT"
  >
    <div class="mb-6 text-muted-color">
      This Flow only opens with the link that <code>lumlflow ui</code> printed when it started. Open
      that link, or paste it here.
    </div>
    <form @submit.prevent="open">
      <InputText
        id="flow-launch-url"
        v-model="launchUrl"
        placeholder="http://127.0.0.1:5000/#session-token=…"
        fluid
        :invalid="!!error"
      />
      <Message v-if="error" severity="error" size="small" variant="simple" class="mt-2">
        {{ error }}
      </Message>
    </form>
    <template #footer>
      <Button label="Open Flow" :loading="loading" @click="open" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog, InputText, Button, Message } from 'primevue'
import { isAxiosError } from 'axios'
import { ref, watch } from 'vue'
import { DIALOG_PT } from '@/components/api-key/data'
import { api } from '@/api/client'
import { page, saveSessionToken, sessionTokenRejected, tokenFromLaunchInput } from '@/api/session'

const launchUrl = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function open() {
  error.value = null
  const token = tokenFromLaunchInput(launchUrl.value)
  if (!token) {
    error.value = 'Paste the whole link printed by lumlflow ui, including #session-token=…'
    return
  }
  loading.value = true
  saveSessionToken(token)
  try {
    await api.get('/groups', { params: { limit: 1 } })
    page.reload()
  } catch (e) {
    error.value =
      isAxiosError(e) && e.response?.status === 401
        ? 'This Flow does not accept that token. Copy the latest link from lumlflow ui.'
        : 'Flow did not answer. Check that lumlflow ui is still running.'
  } finally {
    loading.value = false
  }
}

watch(launchUrl, () => {
  error.value = null
})
</script>

<style scoped></style>
