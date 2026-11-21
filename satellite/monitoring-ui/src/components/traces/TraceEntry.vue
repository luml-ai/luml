<template>
  <div class="entry">
    <header class="header">
      <h4 class="title">{{ title }}</h4>
      <span v-if="stats" class="stats">{{ stats }}</span>
      <Button
        v-if="stats"
        v-tooltip.top="'Open full screen'"
        class="expand"
        variant="text"
        severity="secondary"
        size="small"
        :aria-label="`Open ${title} full screen`"
        @click="isExpanded = true"
      >
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </header>
    <div class="value" :class="{ code: !!stats }">
      <pre class="text">{{ text }}</pre>
      <MCopyButton class="copy" :text="text" :label="title" :icon-size="14" />
    </div>
    <Dialog
      v-if="stats"
      v-model:visible="isExpanded"
      modal
      block-scroll
      dismissable-mask
      :close-on-escape="false"
      :draggable="false"
      :style="dialogStyle"
      :aria-labelledby="titleId"
      :pt="{ mask: { class: maskClass, style: { '--px-mask-background': 'transparent' } } }"
      @after-hide="restoreScrollLock"
    >
      <template #header>
        <div class="fullscreen-header">
          <h3 :id="titleId" class="fullscreen-title">{{ title }}</h3>
          <span class="stats">{{ stats }}</span>
          <MCopyButton :text="text" :label="title" :icon-size="14" />
        </div>
      </template>
      <template #closeicon>
        <Minimize2 :size="14" />
      </template>
      <pre class="text fullscreen-text">{{ text }}</pre>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef, useId } from 'vue'
import { Button, Dialog } from 'primevue'
import { Maximize2, Minimize2 } from 'lucide-vue-next'
import { formatTraceValue, getTraceValueStats } from '@/utils/traces'
import { TRACE_DIALOG_GAP } from '@/constants/traces'
import { useNestedDialog } from '@/composables/useNestedDialog'
import MCopyButton from '@/components/MCopyButton.vue'

interface Props {
  title: string
  value: unknown
}

const props = defineProps<Props>()

const isExpanded = shallowRef(false)

const titleId = useId()

const { maskClass, restoreScrollLock } = useNestedDialog(isExpanded)

const dialogStyle = {
  width: `calc(100vw - ${2 * TRACE_DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * TRACE_DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}

const text = computed(() => formatTraceValue(props.value))

const stats = computed(() => getTraceValueStats(text.value))
</script>

<style scoped>
.entry {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-content-background);
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
  overflow-wrap: anywhere;
}

.stats {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.expand {
  flex-shrink: 0;
}

.value {
  position: relative;
  padding: 8px 40px 8px 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  background: var(--p-card-background);
}

.text {
  display: block;
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  color: var(--p-text-color);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.code .text,
.fullscreen-text {
  font-family: 'IBM Plex Mono', Consolas, 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
}

.code .text {
  max-height: 240px;
  overflow: auto;
}

.copy {
  position: absolute;
  top: 8px;
  right: 8px;
}

.fullscreen-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.fullscreen-title {
  overflow: hidden;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
