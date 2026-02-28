<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    :pt="dialogPt"
    v-bind="$attrs"
  >
    <template #header>
      <h2 class="dialog-title">
        <component :is="icon" :size="16" color="var(--p-primary-color)" />
        <span>{{ title }}</span>
      </h2>
    </template>
    <div class="content">
      <slot></slot>
    </div>
    <template #footer>
      <slot name="footer"></slot>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'
import type { DialogPassThroughOptions } from 'primevue'
import { Dialog } from 'primevue'
import { computed } from 'vue'

interface Props {
  icon: LucideIcon
  title: string
  maxWidth?: string
}

const props = withDefaults(defineProps<Props>(), {
  maxWidth: '550px',
})

const visible = defineModel<boolean>('visible', { default: false })

const dialogPt = computed<DialogPassThroughOptions>(() => ({
  root: {
    style: `margin-top: 78px; height: calc(100% - 120px); width: ${props.maxWidth}`,
  },
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}))
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
