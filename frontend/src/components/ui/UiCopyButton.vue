<template>
  <Button class="copy-button" severity="secondary" variant="text" @click.stop="copy">
    <component :is="copied ? CopyCheck : Copy" :size="12"></component>
  </Button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { Button } from 'primevue'

type Props = {
  text: string
}

const props = defineProps<Props>()

const copied = ref(false)

function copy() {
  copied.value = true
  navigator.clipboard.writeText(props.text)
  setTimeout(() => {
    copied.value = false
  }, 2000)
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
