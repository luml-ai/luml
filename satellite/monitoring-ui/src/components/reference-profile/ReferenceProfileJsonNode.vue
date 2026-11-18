<template>
  <div class="node" :class="{ nested: depth > 0 }">
    <div class="row" :class="{ branch }" @click="toggle">
      <ChevronRight v-if="branch" class="caret" :class="{ open }" :size="12" />
      <span v-else class="caret" />
      <span v-if="label !== null" class="key">{{ label }}</span>
      <span v-if="label !== null && !branch" class="colon">:</span>
      <span v-if="branch" class="badge">{{ badge }}</span>
      <span v-else class="value" :class="valueKind">{{ leaf }}</span>
      <MCopyButton v-if="copyable" class="copy" :text="copyText" />
    </div>
    <div v-if="branch && open" class="children">
      <ReferenceProfileJsonNode
        v-for="entry in visibleEntries"
        :key="entry.key"
        :label="entry.key"
        :value="entry.value"
        :depth="depth + 1"
      />
      <span v-if="hiddenCount" class="more">…{{ hiddenCount }} more</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import {
  JSON_COPY_MIN_LENGTH,
  JSON_TREE_AUTO_OPEN_DEPTH,
  JSON_TREE_PREVIEW_LIMIT,
} from '@/constants/reference-profile'
import {
  formatJsonLeaf,
  getJsonBadge,
  getJsonEntries,
  getJsonValueKind,
  isJsonBranch,
  isJsonPrimitiveArray,
} from '@/utils/reference-profile'
import { JsonValueKind } from '@/types/reference-profile'
import MCopyButton from '@/components/MCopyButton.vue'

interface Props {
  value: unknown
  label?: string | null
  depth?: number
}

const props = withDefaults(defineProps<Props>(), {
  label: null,
  depth: 0,
})

const open = ref(props.depth < JSON_TREE_AUTO_OPEN_DEPTH)

const branch = computed(() => isJsonBranch(props.value))

const entries = computed(() => getJsonEntries(props.value))

const visibleEntries = computed(() => entries.value.slice(0, JSON_TREE_PREVIEW_LIMIT))

const hiddenCount = computed(() => Math.max(0, entries.value.length - JSON_TREE_PREVIEW_LIMIT))

const badge = computed(() => getJsonBadge(props.value))

const leaf = computed(() => formatJsonLeaf(props.value))

const valueKind = computed(() =>
  isJsonPrimitiveArray(props.value) ? JsonValueKind.MUTED : getJsonValueKind(props.value),
)

const copyable = computed(() => branch.value || leaf.value.length > JSON_COPY_MIN_LENGTH)

const copyText = computed(() => JSON.stringify(props.value, null, 2))

function toggle() {
  if (branch.value) open.value = !open.value
}
</script>

<style scoped>
.node.nested {
  padding-left: 14px;
}

.row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  min-height: 22px;
}

.row.branch {
  cursor: pointer;
}

.row.branch:hover .key {
  color: var(--p-text-color);
}

.caret {
  flex: 0 0 auto;
  width: 12px;
  color: var(--p-text-muted-color);
  transition: transform 0.12s;
}

.caret.open {
  transform: rotate(90deg);
}

.key {
  flex: 0 0 auto;
  color: var(--p-text-color);
}

.colon {
  margin-left: -6px;
  color: var(--p-text-muted-color);
}

.badge {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.value {
  overflow: hidden;
  min-width: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.value.number {
  font-variant-numeric: tabular-nums;
  color: var(--p-text-color);
}

.value.string {
  color: var(--p-tag-success-color);
}

.value.muted {
  color: var(--p-text-muted-color);
}

.copy {
  opacity: 0;
  transition: opacity 0.12s;
}

.row:hover .copy {
  opacity: 1;
}

.children {
  border-left: 1px solid var(--p-listbox-border-color);
  margin-left: 5px;
}

.more {
  display: block;
  padding-left: 32px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
