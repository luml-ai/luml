<template>
  <div class="chart-frame">
    <div class="head">
      <div class="labels">
        <p v-if="title" class="chart-title">{{ title }}</p>
        <p v-if="subtitle" class="chart-subtitle">{{ subtitle }}</p>
      </div>
      <button
        type="button"
        class="expand"
        :aria-label="`Open ${title || 'chart'} full screen`"
        data-testid="chart-expand"
        @click="expanded = true"
      >
        <Maximize2 :size="14" />
      </button>
    </div>

    <slot :height="CHART_HEIGHT" :expanded="false" />

    <!--
      Teleported to the body so a chart opened from inside a drawer covers the drawer too,
      the same way the span-field viewer does.
    -->
    <Teleport to="body">
      <div
        v-if="expanded"
        class="viewer"
        role="dialog"
        aria-modal="true"
        :aria-label="title || 'Chart'"
        data-testid="chart-fullscreen"
      >
        <header class="viewer-head">
          <div class="labels">
            <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
            <h3 class="viewer-title">{{ title }}</h3>
            <p v-if="subtitle" class="chart-subtitle">{{ subtitle }}</p>
          </div>
          <button
            type="button"
            class="close"
            aria-label="Close full screen"
            data-testid="chart-fullscreen-close"
            @click="expanded = false"
          >
            <X :size="16" />
          </button>
        </header>
        <div class="stage">
          <slot :height="stageHeight" :expanded="true" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Maximize2, X } from 'lucide-vue-next'
import { CHART_HEIGHT } from '@/lib/charts'

withDefaults(
  defineProps<{
    title?: string
    subtitle?: string
    eyebrow?: string
  }>(),
  { title: '', subtitle: '', eyebrow: '' },
)

// Room taken by the header and the page's own padding, so the chart fills what is left.
const CHROME_HEIGHT = 150
const MIN_STAGE_HEIGHT = 320

const expanded = ref(false)
const stageHeight = ref(measure())

function measure(): number {
  const available = (globalThis.innerHeight ?? 900) - CHROME_HEIGHT
  return Math.max(MIN_STAGE_HEIGHT, available)
}

function onResize(): void {
  stageHeight.value = measure()
}

function onKeydown(event: KeyboardEvent): void {
  // Escape belongs to the topmost layer: swallow it so a drawer underneath stays open.
  if (event.key !== 'Escape') return
  event.stopPropagation()
  expanded.value = false
}

watch(expanded, (open) => {
  if (open) {
    stageHeight.value = measure()
    document.addEventListener('keydown', onKeydown, true)
    globalThis.addEventListener?.('resize', onResize)
    document.body.style.overflow = 'hidden'
  } else {
    stopListening()
  }
})

function stopListening(): void {
  document.removeEventListener('keydown', onKeydown, true)
  globalThis.removeEventListener?.('resize', onResize)
  document.body.style.overflow = ''
}

onBeforeUnmount(stopListening)
</script>

<style scoped>
.chart-frame {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--luml-space-3);
}
.labels {
  min-width: 0;
}
.chart-title {
  margin: 0;
  font-size: var(--luml-text-base);
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.chart-subtitle {
  margin: 2px 0 0;
  font-size: var(--luml-caption-size);
  color: var(--luml-fg-muted);
}
.expand {
  flex: 0 0 auto;
  display: inline-flex;
  padding: 4px;
  border: 1px solid transparent;
  border-radius: var(--luml-radius-sm);
  background: transparent;
  color: var(--luml-fg-faint);
  cursor: pointer;
}
/* Quiet until wanted: the charts are the content, the control is not. */
.chart-frame:hover .expand,
.expand:focus-visible {
  color: var(--luml-fg-muted);
  border-color: var(--luml-border);
}
.expand:hover {
  background: var(--luml-surface-100);
  color: var(--luml-fg-strong);
}
.viewer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  background: var(--luml-bg);
}
.viewer-head {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--luml-space-4);
  padding: 14px 20px;
  border-bottom: 1px solid var(--luml-border);
  background: var(--luml-bg-card);
}
.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.viewer-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.close {
  flex: 0 0 auto;
  display: inline-flex;
  padding: 5px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg-muted);
  cursor: pointer;
}
.close:hover {
  background: var(--luml-bg-hover);
}
.stage {
  flex: 1 1 auto;
  overflow: auto;
  padding: 18px 20px;
}
</style>
