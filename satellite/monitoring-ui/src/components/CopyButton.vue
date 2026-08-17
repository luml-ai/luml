<template>
  <button
    type="button"
    class="copy"
    :class="{ done: copied }"
    :aria-label="copied ? `${label} copied` : `Copy ${label}`"
    :title="copied ? 'Copied' : `Copy ${label}`"
    data-testid="copy-button"
    @click.stop="copy"
  >
    <Check v-if="copied" :size="13" />
    <Copy v-else :size="13" />
  </button>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'

const COPIED_MS = 1400

const props = defineProps<{ value: string; label: string }>()

const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

/**
 * The dashboard is also served over plain http inside the Platform iframe, where the async
 * clipboard API is unavailable — fall back to a throwaway textarea there.
 */
async function copy(): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(props.value)
    } else {
      legacyCopy(props.value)
    }
    flash()
  } catch {
    try {
      legacyCopy(props.value)
      flash()
    } catch {
      // nothing else to try: leave the icon untouched so the click reads as "did not copy"
    }
  }
}

function legacyCopy(text: string): void {
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  document.execCommand('copy')
  document.body.removeChild(area)
}

function flash(): void {
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), COPIED_MS)
}

onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: var(--luml-radius-sm, 4px);
  background: transparent;
  color: var(--luml-fg-muted);
  cursor: pointer;
  line-height: 0;
}
.copy:hover {
  border-color: var(--luml-border);
  background: var(--luml-bg-card);
  color: var(--luml-fg-strong);
}
.copy.done {
  color: var(--luml-success-tint-fg);
}
</style>
