<template>
  <div class="node" :style="{ paddingLeft: depth === 0 ? '0' : '14px' }">
    <div class="row" :class="{ clickable: isBranch }" @click="toggle">
      <span v-if="isBranch" class="caret" :class="{ open }">▸</span>
      <span v-else class="caret placeholder" />

      <span v-if="label !== null" class="key mono">{{ label }}</span>
      <span v-if="label !== null && !isBranch" class="colon">:</span>

      <span v-if="!isBranch" class="value mono" :class="valueClass">{{ leaf }}</span>
      <span v-else class="badge">{{ badge }}</span>

      <CopyButton
        v-if="isBranch || String(leaf).length > 12"
        class="copy"
        :value="copyValue"
        :label="label ?? 'value'"
      />
    </div>

    <div v-if="isBranch && open" class="children">
      <!-- A long array is a projection or a histogram: the first rows are enough to
           recognize it, and the copy button hands over the whole thing. -->
      <JsonNode
        v-for="entry in visibleEntries"
        :key="entry.key"
        :label="entry.key"
        :value="entry.value"
        :depth="depth + 1"
      />
      <p v-if="hidden > 0" class="more mono">…{{ hidden }} more</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CopyButton from '@/components/CopyButton.vue'

const PREVIEW_LIMIT = 20
const AUTO_OPEN_DEPTH = 1

const props = withDefaults(defineProps<{ label?: string | null; value: unknown; depth?: number }>(), {
  label: null,
  depth: 0,
})

const isBranch = computed(
  () => props.value !== null && typeof props.value === 'object' && !isPrimitiveArray.value,
)

// An array of plain numbers reads better as one line than as 400 nested rows.
const isPrimitiveArray = computed(
  () =>
    Array.isArray(props.value) &&
    props.value.length > 0 &&
    props.value.every((item) => item === null || typeof item !== 'object'),
)

const open = ref(props.depth < AUTO_OPEN_DEPTH)

function toggle(): void {
  if (isBranch.value) open.value = !open.value
}

const entries = computed<{ key: string; value: unknown }[]>(() => {
  const value = props.value
  if (Array.isArray(value)) return value.map((item, index) => ({ key: String(index), value: item }))
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([key, item]) => ({
      key,
      value: item,
    }))
  }
  return []
})

const visibleEntries = computed(() => entries.value.slice(0, PREVIEW_LIMIT))
const hidden = computed(() => Math.max(0, entries.value.length - PREVIEW_LIMIT))

const badge = computed(() => {
  const count = entries.value.length
  return Array.isArray(props.value) ? `[${count}]` : `{${count}}`
})

const leaf = computed(() => {
  const value = props.value
  if (isPrimitiveArray.value) {
    const items = value as unknown[]
    const head = items.slice(0, 6).map(format).join(', ')
    return items.length > 6 ? `[${head}, …] (${items.length})` : `[${head}]`
  }
  return format(value)
})

function format(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return `"${value}"`
  if (typeof value === 'number') return String(Number(value.toFixed(6)))
  return String(value)
}

const valueClass = computed(() => {
  const value = props.value
  if (isPrimitiveArray.value) return 'muted'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'string') return 'string'
  return 'muted'
})

const copyValue = computed(() => JSON.stringify(props.value, null, 2))
</script>

<style scoped>
.row {
  display: flex;
  align-items: baseline;
  gap: 5px;
  padding: 1px 0;
  min-width: 0;
}
.row.clickable {
  cursor: pointer;
}
.row.clickable:hover .key {
  color: var(--luml-fg-strong);
}
.caret {
  flex: 0 0 auto;
  width: 10px;
  font-size: 9px;
  color: var(--luml-fg-muted);
  transition: transform 0.12s ease;
}
.caret.open {
  transform: rotate(90deg);
}
.caret.placeholder {
  visibility: hidden;
}
.key {
  font-size: 12px;
  color: var(--luml-fg);
}
.colon {
  color: var(--luml-fg-muted);
  margin-left: -3px;
}
.value {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.value.number {
  color: var(--luml-fg-strong);
  font-variant-numeric: tabular-nums;
}
.value.string {
  color: var(--luml-success-tint-fg, var(--luml-fg-strong));
}
.value.muted {
  color: var(--luml-fg-muted);
}
.badge {
  font-size: 11px;
  color: var(--luml-fg-muted);
}
.more {
  margin: 1px 0 1px 14px;
  font-size: 11px;
  color: var(--luml-fg-muted);
}
.copy {
  opacity: 0;
}
.row:hover .copy {
  opacity: 1;
}
.children {
  border-left: 1px solid var(--luml-surface-100);
}
</style>
