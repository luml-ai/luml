<template>
  <slot></slot>
  <Dialog
    v-model:visible="scaled"
    :header="title.toUpperCase()"
    blockScroll
    class="p-dialog-maximized"
  >
    <template #closeicon>
      <Minimize2 :size="14" />
    </template>
    <slot name="scaled"></slot>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog } from 'primevue'
import { Minimize2 } from 'lucide-vue-next'

type Props = {
  title: string
}

defineProps<Props>()

const scaled = defineModel<boolean>('modelValue')
</script>

<style scoped></style>
