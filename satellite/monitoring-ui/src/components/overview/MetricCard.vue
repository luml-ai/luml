<template>
  <div class="metric-card card" :class="`tone-${tone}`" data-testid="metric-card">
    <div class="label eyebrow">{{ card.label }}</div>
    <div class="value">{{ value }}</div>

    <!--
      Drifted features get their own detail row: the list can run to every input the model
      has, which would stretch this card to several times the height of its neighbours. Two
      names in full and the rest behind a "+N" disclosure — the card is narrow, so the chips
      sit on their own rows and the disclosure shares the second one.
    -->
    <div v-if="isFeatureList" class="features" data-testid="drifted-features-detail">
      <template v-if="featureNames.length">
        <span v-if="previewNames[0]" class="feature mono">{{ previewNames[0] }}</span>
        <div v-if="previewNames[1] || hiddenCount" class="feature-row">
          <span v-if="previewNames[1]" class="feature mono">{{ previewNames[1] }}</span>
          <button
            v-if="hiddenCount"
            ref="moreButton"
            type="button"
            class="more"
            data-testid="drifted-more"
            :aria-expanded="expanded"
            @click="expanded = !expanded"
          >
            +{{ hiddenCount }}
          </button>
        </div>
      </template>
      <span v-else class="detail">none</span>

      <!--
        Teleported to the body: inside the card the list is painted under whatever section
        follows it on the page, because each card and chart block opens its own stacking
        context and a z-index set in here cannot escape it.
      -->
      <Teleport to="body">
        <div
          v-if="expanded"
          ref="popover"
          class="popover"
          :style="popoverStyle"
          data-testid="drifted-popover"
        >
          <p class="popover-title">Drifted features ({{ featureNames.length }})</p>
          <ul class="popover-list">
            <li v-for="name in featureNames" :key="name" class="mono">{{ name }}</li>
          </ul>
        </div>
      </Teleport>
    </div>

    <div v-else-if="detail" class="detail">{{ detail }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Card } from '@/api/types'
import { cardDetail, cardTone, formatCardValue } from '@/lib/format'

const PREVIEW_LIMIT = 2

const props = defineProps<{ card: Card }>()

const value = computed(() => formatCardValue(props.card))
const detail = computed(() => cardDetail(props.card))
const tone = computed(() => cardTone(props.card))

const isFeatureList = computed(() => props.card.key === 'drifted_features')
const featureNames = computed(() => props.card.feature_names ?? [])
const previewNames = computed(() => featureNames.value.slice(0, PREVIEW_LIMIT))
const hiddenCount = computed(() => Math.max(0, featureNames.value.length - PREVIEW_LIMIT))

const POPOVER_WIDTH = 260
const VIEWPORT_MARGIN = 8

const expanded = ref(false)
const popover = ref<HTMLElement | null>(null)
const moreButton = ref<HTMLElement | null>(null)
const anchor = ref({ top: 0, left: 0 })

// Viewport-fixed under the "+N" button, nudged back inside near the right edge.
const popoverStyle = computed(() => ({
  position: 'fixed' as const,
  top: `${anchor.value.top}px`,
  left: `${anchor.value.left}px`,
  width: `${POPOVER_WIDTH}px`,
}))

function placePopover() {
  const rect = moreButton.value?.getBoundingClientRect()
  if (!rect) return
  const maxLeft = window.innerWidth - POPOVER_WIDTH - VIEWPORT_MARGIN
  anchor.value = {
    top: rect.bottom + 6,
    left: Math.max(VIEWPORT_MARGIN, Math.min(rect.left, maxLeft)),
  }
}

function onPointerDown(event: MouseEvent) {
  const target = event.target as Node
  if (popover.value?.contains(target) || moreButton.value?.contains(target)) return
  expanded.value = false
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') expanded.value = false
}

function close(event?: Event) {
  // The list itself scrolling is use, not the page moving under the anchor.
  if (event && popover.value?.contains(event.target as Node)) return
  expanded.value = false
}

watch(expanded, (open) => {
  if (open) {
    placePopover()
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeydown)
    // Anchored in viewport coordinates: close on page scroll instead of drifting.
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
  } else {
    stopListening()
  }
})

function stopListening() {
  document.removeEventListener('pointerdown', onPointerDown)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('scroll', close, true)
  window.removeEventListener('resize', close)
}

onBeforeUnmount(stopListening)
</script>

<style scoped>
.metric-card {
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  /* the row of cards keeps one height whatever the detail line holds */
  min-height: 118px;
  position: relative;
}
.value {
  font-size: 25px;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--luml-fg-strong);
}
.detail {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.features {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
  /* two rows, fixed so the card keeps its height whatever the names are */
  height: 44px;
  overflow: hidden;
}
.feature-row {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-width: 0;
}
.feature {
  font-size: 11px;
  color: var(--luml-fg-muted);
  background: var(--luml-surface-100);
  border-radius: 4px;
  padding: 2px 6px;
  /* names show in full; only an unusually long one is cut */
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.more {
  font-size: 11px;
  font-weight: 500;
  color: var(--luml-brand);
  background: none;
  border: 1px solid var(--luml-border);
  border-radius: 4px;
  padding: 2px 6px;
  cursor: pointer;
  flex: 0 0 auto;
}
.more:hover {
  background: var(--luml-surface-100);
}
.popover {
  z-index: 1000;
  max-height: 240px;
  overflow-y: auto;
  overscroll-behavior: contain;
  background: var(--luml-bg-card);
  border: 1px solid var(--luml-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(28, 43, 64, 0.18);
  padding: 10px 12px;
}
.popover-title {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--luml-fg-muted);
}
.popover-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.popover-list li {
  font-size: 11px;
  color: var(--luml-fg);
  background: var(--luml-surface-100);
  border-radius: 4px;
  padding: 2px 6px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tone-danger {
  border-color: var(--luml-danger-tint-bg);
}
.tone-danger .label,
.tone-danger .value,
.tone-danger .detail {
  color: var(--luml-danger-tint-fg);
}
.tone-warning .detail {
  color: var(--luml-warn-tint-fg);
}
</style>
