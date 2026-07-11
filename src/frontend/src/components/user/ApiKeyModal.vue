<template>
  <Dialog v-model:visible="show" header="Api key" modal :draggable="false" :pt="dialogPt">
    <div v-if="userStore.isUserApiKeyExist">
      <div class="description">Use the API key to access the platform programmatically.</div>
      <div class="form">
        <InputGroup>
          <InputText
            placeholder="Apy key"
            :disabled="!copyAvailable"
            :value="inputValue"
            readonly
            @input.prevent
          />
          <InputGroupAddon v-if="copyAvailable">
            <Button
              variant="text"
              severity="secondary"
              size="small"
              style="height: 100%"
              @click="copy"
            >
              <Copy :size="14" />
            </Button>
          </InputGroupAddon>
        </InputGroup>
        <Button
          severity="secondary"
          class="remove-button"
          :disabled="loading"
          @click="onDeleteClick"
        >
          <template #icon>
            <Trash2 :size="14" />
          </template>
        </Button>
      </div>
      <div v-if="!apiKey" class="message">
        For security reasons, this key is no longer visible. Generate a new one if needed.
      </div>
    </div>
    <div v-else class="description">
      No API key yet. Click the button below to generate your first one.
    </div>
    <template #footer>
      <Button
        :label="userStore.isUserApiKeyExist ? 'Regenerate key' : 'Generate key'"
        :loading="loading"
        @click="generate"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import {
  Dialog,
  InputGroup,
  InputGroupAddon,
  InputText,
  Button,
  useToast,
  useConfirm,
} from 'primevue'
import { Copy, Trash2 } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteAPIKeyConfirmOptions } from '@/lib/primevue/data/confirm'
import { useUserStore } from '@/stores/user'

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'width: 100%; max-width: 600px',
  },
  header: {
    style: 'text-transform: uppercase; font-size: 20px; padding: 36px 36px 12px;',
  },
  content: {
    style: 'padding: 0 36px;',
  },
  footer: {
    style: 'display: flex; justify-content: flex-end; padding: 28px 36px 36px;',
  },
}

const show = defineModel<boolean>('show')

const toast = useToast()
const confirm = useConfirm()
const userStore = useUserStore()

const loading = ref(false)
const apiKey = ref<null | string>(null)

const copyAvailable = computed(() => !!apiKey.value)
const inputValue = computed(() => apiKey.value || 'dfs_***************************************')

async function generate() {
  try {
    loading.value = true
    apiKey.value = await userStore.createApiKey()
    toast.add(simpleSuccessToast('A new API key has been generated successfully.'))
  } catch {
    toast.add(simpleErrorToast('Failed to generate API Key'))
  } finally {
    loading.value = false
  }
}

function copy() {
  if (!apiKey.value) return
  navigator.clipboard.writeText(apiKey.value)
  toast.add(simpleSuccessToast('API key copied to clipboard.'))
}

function onDeleteClick() {
  confirm.require(deleteAPIKeyConfirmOptions(remove))
}

async function remove() {
  try {
    loading.value = true
    await userStore.deleteApiKey()
    apiKey.value = null
    toast.add(simpleSuccessToast('API key was deleted.'))
  } catch {
    toast.add(simpleErrorToast('Failed to delete API key'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.description {
  color: var(--p-text-muted-color);
}

.form {
  padding-top: 28px;
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.remove-button {
  flex: 0 0 auto;
}

.message {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
