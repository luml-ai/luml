<template>
  <Dialog v-model:visible="visible" position="topright" :draggable="false" :pt="dialogPT">
    <template #header>
      <slot name="header">
        <h2 class="dialog-title">
          <component :is="icon" :size="20" color="var(--p-primary-color)" />
          <span>{{ title }}</span>
        </h2>
      </slot>
    </template>
    <template #default>
      <slot></slot>
    </template>
    <template #footer>
      <slot name="footer">
        <div v-if="footerActions" class="footer-actions">
          <Button v-if="footerActions.leftButton" v-bind="footerActions.leftButton.props" />
          <div v-else></div>

          <Button v-if="footerActions.rightButton" v-bind="footerActions.rightButton.props" />
        </div>
      </slot>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'
import { Button, Dialog, type ButtonProps, type DialogPassThroughOptions } from 'primevue'
import { computed } from 'vue'

export interface FooterButton {
  props: ButtonProps
}

export interface FooterActions {
  leftButton?: FooterButton
  rightButton?: FooterButton
}

interface Props {
  icon: LucideIcon
  title: string
  maxWidth?: string
  footerActions?: FooterActions
}

const props = withDefaults(defineProps<Props>(), {
  maxWidth: '420px',
})

const visible = defineModel<boolean>('visible', { default: false })

const dialogPT = computed<DialogPassThroughOptions>(() => {
  return {
    header: {
      style: 'font-weight: 500; text-transform: uppercase; font-size: 16px;',
    },
    root: {
      style: `margin-top: 80px; height: calc(100% - 120px); width: ${props.maxWidth}`,
    },
    transition: {
      enterFromClass: 'right-dialog-enter-from',
      enterActiveClass: 'right-dialog-enter-active',
      leaveActiveClass: 'right-dialog-leave-active',
      leaveToClass: 'right-dialog-leave-to',
    },
  }
})
</script>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
}
.footer-actions {
  width: 100%;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding-top: var(--p-dialog-header-padding);
}
</style>

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
