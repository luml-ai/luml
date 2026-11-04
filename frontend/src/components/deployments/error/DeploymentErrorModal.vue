<template>
  <Dialog
    v-model:visible="visible"
    :pt="deploymentErrorDialogPt"
    modal
    :draggable="false"
    dismissable-mask
  >
    <template #header>
      <h3>{{ reason }}</h3>
    </template>
    <template #default>
      <pre class="error-body">{{ formattedError }}</pre>
    </template>
    <template #footer>
      <Button label="copy" @click="copy">
        <template #icon>
          <component :is="copied ? CopyCheck : Copy" :size="12"></component>
        </template>
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { deploymentErrorDialogPt } from '../deployments.const'
import { Button, Dialog, useToast } from 'primevue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { computed, ref } from 'vue'

const toast = useToast()

type Props = {
  error: string
  reason: string
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')

const formattedError = computed(() => {
  return props.error
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .trim()
    .replace(/^\{/, '')
    .replace(/\}$/, '')
})

const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(formattedError.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    copied.value = false
    toast.add(simpleErrorToast('Failed to copy to clipboard'))
  }
}
</script>

<style scoped>
.error-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.5;
  color: var(--p-text-color);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  max-height: calc(100vh - 300px);
  overflow: auto;
}
</style>
