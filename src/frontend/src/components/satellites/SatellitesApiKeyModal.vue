<template>
  <Dialog
    v-model:visible="visible"
    header="Connect a new satellite"
    :pt="dialogPt"
    modal
    :draggable="false"
  >
    <div>
      <div class="text">Use the pairing key to connect your Satellite.</div>
      <InputGroup>
        <InputText
          placeholder="Apy key"
          :value="inputValue"
          :disabled="!copyAvailable"
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
            <component :is="isCopied ? CopyCheck : Copy" :size="14" />
          </Button>
        </InputGroupAddon>
      </InputGroup>
      <div v-if="!currentApiKey" class="message">
        For security reasons, this key is no longer visible. Generate a new one if needed.
      </div>
    </div>
    <template #footer>
      <Button v-if="!currentApiKey" label="Regenerate key" :loading="loading" @click="generate" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Dialog, InputText, InputGroup, InputGroupAddon, Button, useToast } from 'primevue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { computed, ref, watch } from 'vue'
import { useSatellitesStore } from '@/stores/satellites'
import { useRoute } from 'vue-router'

type Props = {
  apiKey: string | null
  satelliteId: string
}

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

const toast = useToast()
const route = useRoute()
const satellitesStore = useSatellitesStore()

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible')

const currentApiKey = ref<string | null>(null)
const loading = ref(false)
const isCopied = ref(false)

const organizationId = computed(() => {
  const param = route.params.organizationId
  if (!param) throw new Error('Current organization was not found')
  return typeof param === 'string' ? param : param[0]
})
const orbitId = computed(() => {
  const param = route.params.id
  if (!param) throw new Error('Current orbit was not found')
  return typeof param === 'string' ? param : param[0]
})

const copyAvailable = computed(() => !!currentApiKey.value)

const inputValue = computed(() => {
  if (!currentApiKey.value) return 'sat_***************************************'
  if (currentApiKey.value.length > 20) {
    return currentApiKey.value.slice(0, 10) + '*******************' + currentApiKey.value.slice(-10)
  } else {
    return currentApiKey.value
  }
})

function copy() {
  if (!currentApiKey.value) return
  navigator.clipboard.writeText(currentApiKey.value)
  toast.add(simpleSuccessToast('API key copied to clipboard.'))
  isCopied.value = true
  setTimeout(() => {
    isCopied.value = false
  }, 1000)
}

async function generate() {
  try {
    loading.value = true
    const { key } = await satellitesStore.regenerateApiKey(
      organizationId.value,
      orbitId.value,
      props.satelliteId,
    )
    currentApiKey.value = key
    toast.add(simpleSuccessToast('A new API key has been generated successfully.'))
  } catch {
    toast.add(simpleErrorToast('Failed to generate API Key'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.apiKey,
  (val) => {
    if (val) {
      currentApiKey.value = val
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}

.message {
  padding-top: 7px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
