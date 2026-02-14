<template>
  <Dialog v-model:visible="visible" :pt="dialogPt" position="right" :draggable="false">
    <template #header>
      <div class="flex items-center gap-2">
        <props.icon :size="20" color="var(--p-primary-color)" />
        <h3 class="">{{ props.title }}</h3>
      </div>
    </template>
    <template #closeicon>
      <X :size="14" />
    </template>
    <template #default>
      <slot></slot>
    </template>
    <template #footer>
      <slot name="footer"></slot>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'
import { Dialog, type DialogPassThroughOptions } from 'primevue'
import { X } from 'lucide-vue-next'

interface Props {
  title: string
  icon: LucideIcon
}

const dialogPt: DialogPassThroughOptions = {
  mask: {
    class: 'pt-22 pb-8 px-4',
  },
  root: {
    class: 'w-full max-w-[462px] h-full max-h-full! m-0!',
  },
  header: {
    class: 'text-lg font-medium uppercase',
  },
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible', { default: false })
</script>

<style></style>
