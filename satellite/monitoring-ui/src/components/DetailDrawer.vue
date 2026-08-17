<template>
  <!--
    Teleported to the body so the panel slides over the whole dashboard: inside the tab it
    would be trapped in the grid and painted under the sections that follow it.
  -->
  <Teleport to="body">
    <div v-if="open" class="drawer-root" :data-testid="testid">
      <div class="scrim" :data-testid="`${testid}-scrim`" @click="$emit('close')" />
      <aside class="drawer" role="dialog" aria-modal="true" :aria-label="eyebrow">
        <header class="drawer-head">
          <div class="eyebrow-row">
            <span class="eyebrow">{{ eyebrow }}</span>
            <button
              type="button"
              class="close"
              :aria-label="`Close ${eyebrow.toLowerCase()}`"
              :data-testid="`${testid}-close`"
              @click="$emit('close')"
            >
              ✕
            </button>
          </div>
          <div class="identity">
            <h3 class="name mono">{{ feature ?? 'no feature selected' }}</h3>
            <span v-if="kind" class="kind">{{ kind }}</span>
            <slot name="status" />
          </div>
          <p v-if="caption" class="caption">{{ caption }}</p>
        </header>
        <div class="drawer-body">
          <slot />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

// The sliding panel shell: each tab supplies the header identity and the body itself.
const props = defineProps<{
  open: boolean
  feature: string | null
  kind?: string | null
  caption?: string | null
  eyebrow: string
  testid: string
}>()
const emit = defineEmits<{ close: [] }>()

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

// The panel covers the viewport, so the page behind it must not scroll away underneath.
function lockPage(locked: boolean) {
  document.body.style.overflow = locked ? 'hidden' : ''
}

watch(
  () => props.open,
  (open) => {
    lockPage(open)
    if (open) document.addEventListener('keydown', onKeydown)
    else document.removeEventListener('keydown', onKeydown)
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  lockPage(false)
})
</script>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 900;
}
.scrim {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.32);
}
.drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(480px, 94vw);
  display: flex;
  flex-direction: column;
  background: var(--luml-bg-card);
  border-left: 1px solid var(--luml-border);
  box-shadow: -12px 0 32px rgba(28, 43, 64, 0.16);
}
.drawer-head {
  padding: 16px 20px 18px;
  border-bottom: 1px solid var(--luml-border);
}
.eyebrow-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--luml-space-4);
  margin-bottom: 12px;
}
.eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--luml-fg-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kind {
  flex: 0 0 auto;
  background: var(--luml-surface-100);
  color: var(--luml-fg-muted);
  border-radius: 5px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.caption {
  margin: 7px 0 0;
  font-size: 12.5px;
  color: var(--luml-fg-muted);
}
.close {
  border: none;
  background: none;
  font-size: 14px;
  line-height: 1;
  color: var(--luml-fg-muted);
  cursor: pointer;
  padding: 4px;
}
.close:hover {
  color: var(--luml-fg-strong);
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}
</style>
