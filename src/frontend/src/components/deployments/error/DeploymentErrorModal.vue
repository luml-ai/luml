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
import { deploymentErrorDialogPt } from '../deployments.const'
import { Button, Dialog } from 'primevue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { computed, ref } from 'vue'

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

function copy() {
  copied.value = true
  navigator.clipboard.writeText(formattedError.value)
  setTimeout(() => {
    copied.value = false
  }, 2000)
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
