<template>
  <div class="scalable-card" :class="variant">
    <div class="header" :class="{ floating: !title }">
      <div v-if="title" class="header-text">
        <h3 class="title">{{ title }}</h3>
        <span v-if="subtitle" class="subtitle">{{ subtitle }}</span>
      </div>
      <Button
        class="maximize-button"
        variant="text"
        severity="secondary"
        aria-label="Maximize"
        @click="isScaled = true"
      >
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </div>
    <div class="content">
      <slot :scaled="false" />
    </div>
    <Dialog
      v-model:visible="isScaled"
      modal
      block-scroll
      dismissable-mask
      :close-on-escape="false"
      :draggable="false"
      :style="dialogStyle"
      :aria-labelledby="title ? titleId : undefined"
      :aria-label="title ? undefined : 'Expanded chart'"
      :pt="{ mask: { class: maskClass, style: { '--px-mask-background': 'transparent' } } }"
      @after-hide="restoreScrollLock"
    >
      <template #header>
        <div v-if="title" class="header-text">
          <h3 :id="titleId" class="title">{{ title }}</h3>
          <span v-if="subtitle" class="subtitle">{{ subtitle }}</span>
        </div>
      </template>
      <template #closeicon>
        <Minimize2 :size="14" />
      </template>
      <div class="dialog-content">
        <slot :scaled="true" />
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import { Maximize2, Minimize2 } from 'lucide-vue-next'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useNestedDialog } from '@/composables/useNestedDialog'

const DIALOG_GAP = 15

interface Props {
  title?: string
  subtitle?: string
  variant?: 'bordered' | 'block'
}

interface Slots {
  default: (props: { scaled: boolean }) => unknown
}

withDefaults(defineProps<Props>(), {
  variant: 'bordered',
})

defineSlots<Slots>()

const isScaled = defineModel<boolean>('scaled', { default: false })

const titleId = useId()

const { maskClass, restoreScrollLock } = useNestedDialog(isScaled)

const dialogStyle = {
  width: `calc(100vw - ${2 * DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}
</script>

<style scoped>
.scalable-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.scalable-card.bordered {
  padding: 16px 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  color: var(--p-card-color);
}

.header {
  position: relative;
  padding-right: 35px;
}

.header.floating {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  padding-right: 0;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subtitle {
  overflow: hidden;
  font-size: 12px;
  color: var(--p-text-muted-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.maximize-button {
  position: absolute;
  top: 0;
  right: 0;
  width: 35px;
  padding-block: 10px;
}

.content {
  flex: 1;
  min-height: 0;
}

.dialog-content {
  height: 100%;
}
</style>
