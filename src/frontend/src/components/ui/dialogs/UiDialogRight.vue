<template>
  <Dialog v-model:visible="visible" position="topright" :draggable="false" :pt="dialogPT">
    <template #header>
      <slot name="header"></slot>
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
import { Dialog, type DialogPassThroughOptions } from 'primevue'

const dialogPT: DialogPassThroughOptions = {
  header: {
    style: 'font-weight: 500; text-transform: uppercase;',
  },
  root: {
    style: 'margin-top: 80px; height: 86%; width: 420px',
  },
  transition: {
    enterFromClass: 'right-dialog-enter-from',
    enterActiveClass: 'right-dialog-enter-active',
    leaveActiveClass: 'right-dialog-leave-active',
    leaveToClass: 'right-dialog-leave-to',
  },
}

const visible = defineModel<boolean>('visible', { default: false })
</script>

<style>
.right-dialog-enter-from,
.right-dialog-leave-to {
  transform: translateX(100%);
}
.right-dialog-enter-active,
.right-dialog-leave-active {
  transition: transform 0.3s ease;
}
</style>
