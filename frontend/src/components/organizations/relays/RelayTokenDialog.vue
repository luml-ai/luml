<template>
  <Dialog
    :visible="true"
    header="Relay token"
    :pt="dialogPt"
    modal
    :draggable="false"
    @update:visible="emit('close')"
  >
    <div class="text">Copy the token now. You cannot see it again.</div>
    <InputGroup>
      <InputText :value="maskedToken" readonly />
      <InputGroupAddon>
        <Button variant="text" severity="secondary" size="small" @click="copy(token, 'Token')">
          <Copy :size="14" />
        </Button>
      </InputGroupAddon>
    </InputGroup>
    <div class="section-title">
      <span>Environment</span>
      <Button
        variant="text"
        severity="secondary"
        size="small"
        @click="copy(environmentFor(token), 'Environment')"
      >
        <Copy :size="14" />
      </Button>
    </div>
    <pre class="code">{{ environmentFor(maskedToken) }}</pre>
    <div class="section-title">
      <span>Run command</span>
      <Button
        variant="text"
        severity="secondary"
        size="small"
        @click="copy(commandFor(token), 'Command')"
      >
        <Copy :size="14" />
      </Button>
    </div>
    <pre class="code">{{ commandFor(maskedToken) }}</pre>
    <div class="note">
      The base domain needs a wildcard DNS record and a wildcard certificate. Put TLS in front of
      the relay.
    </div>
    <template #footer>
      <Button label="Done" @click="emit('close')" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Dialog, InputText, InputGroup, InputGroupAddon, Button, useToast } from 'primevue'
import { Copy } from 'lucide-vue-next'
import { simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { computed } from 'vue'

const RELAY_IMAGE = 'ghcr.io/luml-ai/luml-tunnel-relay:latest'
const RELAY_PORT = 8080

type Props = {
  token: string
}

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'width: 100%; max-width: 640px',
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

const props = defineProps<Props>()
const emit = defineEmits<{ close: [] }>()
const toast = useToast()

const lumlBaseUrl = import.meta.env.VITE_API_URL

const maskedToken = computed(() => {
  if (props.token.length <= 20) return props.token
  return props.token.slice(0, 10) + '*******************' + props.token.slice(-6)
})

function environmentFor(token: string) {
  return `LUML_BASE_URL=${lumlBaseUrl}\nLUML_TUNNEL_RELAY_TOKEN=${token}`
}

function commandFor(token: string) {
  return (
    `docker run -d -p ${RELAY_PORT}:${RELAY_PORT} \\\n` +
    `  -e LUML_BASE_URL=${lumlBaseUrl} \\\n` +
    `  -e LUML_TUNNEL_RELAY_TOKEN=${token} \\\n` +
    `  ${RELAY_IMAGE}`
  )
}

function copy(text: string, what: string) {
  navigator.clipboard.writeText(text)
  toast.add(simpleSuccessToast(`${what} copied to clipboard.`))
}
</script>

<style scoped>
.text {
  color: var(--p-text-muted-color);
  margin-bottom: 20px;
}
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 30px;
  margin: 20px 0 7px;
  font-size: 14px;
}
.code {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--p-content-hover-background);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
.note {
  padding-top: 12px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
