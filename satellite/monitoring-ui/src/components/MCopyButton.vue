<template>
  <Button
    class="copy-button"
    severity="secondary"
    variant="text"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click.prevent.stop="copy"
    @mousedown.stop
    @pointerdown.stop
  >
    <component :is="copied ? Check : Copy" :size="iconSize"></component>
  </Button>
</template>

<script setup lang="ts">
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { computed, onBeforeUnmount, ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { copyToClipboard } from '@/utils/clipboard'

const toast = useToast()

type Props = {
  text: string
  label?: string
  iconSize?: number
}

const props = withDefaults(defineProps<Props>(), { iconSize: 12, label: 'value' })

const copied = ref(false)
let resetTimer: ReturnType<typeof setTimeout> | undefined

const ariaLabel = computed(() => (copied.value ? `${props.label} copied` : `Copy ${props.label}`))

async function copy() {
  try {
    await copyToClipboard(props.text)
    copied.value = true
    clearTimeout(resetTimer)
    resetTimer = setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    copied.value = false
    toast.add(simpleErrorToast('Failed to copy to clipboard'))
  }
}

onBeforeUnmount(() => clearTimeout(resetTimer))
</script>

<style scoped>
.copy-button {
  width: 20px;
  height: 20px;
  padding: 0;
  justify-content: center;
  align-items: center;
  display: inline-flex;
  flex: 0 0 auto;
}
</style>
