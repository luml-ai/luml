<template>
  <div ref="card" class="scalable-card">
    <div class="header">
      <div class="header-text">
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
      :draggable="false"
      :style="dialogStyle"
    >
      <template #header>
        <div class="header-text">
          <h3 class="title">{{ title }}</h3>
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
import { computed, useTemplateRef } from 'vue'
import { useElementSize, useWindowSize } from '@vueuse/core'
import { Maximize2, Minimize2 } from 'lucide-vue-next'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

const MAX_DIALOG_WIDTH = 800
const VIEWPORT_GAP = 32

interface Props {
  title: string
  subtitle?: string
}

interface Slots {
  default: (props: { scaled: boolean }) => unknown
}

defineProps<Props>()

defineSlots<Slots>()

const isScaled = defineModel<boolean>('scaled', { default: false })

const card = useTemplateRef<HTMLDivElement>('card')

const { width: cardWidth, height: cardHeight } = useElementSize(card, undefined, {
  box: 'border-box',
})
const { width: windowWidth, height: windowHeight } = useWindowSize()

const dialogStyle = computed(() => {
  if (!cardWidth.value || !cardHeight.value) return { width: `${MAX_DIALOG_WIDTH}px` }
  const ratio = cardHeight.value / cardWidth.value
  const width = Math.min(
    MAX_DIALOG_WIDTH,
    windowWidth.value - VIEWPORT_GAP,
    (windowHeight.value - VIEWPORT_GAP) / ratio,
  )
  return { width: `${width}px`, height: `${width * ratio}px` }
})
</script>

<style scoped>
.scalable-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
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
