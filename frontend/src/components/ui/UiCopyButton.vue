<template>
  <Button
    class="copy-button"
    severity="secondary"
    variant="text"
    @click.prevent.stop="copy"
    @mousedown.stop
    @pointerdown.stop
  >
    <component :is="copied ? CopyCheck : Copy" :size="12"></component>
  </Button>
</template>

<script setup lang="ts">
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { ref } from 'vue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'

const toast = useToast()

type Props = {
  text: string
}

const props = defineProps<Props>()

const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
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
.copy-button {
  width: 20px;
  height: 20px;
  padding: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  display: inline-flex;
  flex: 0 0 auto;
}
</style>
