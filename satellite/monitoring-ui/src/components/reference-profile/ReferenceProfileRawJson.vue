<template>
  <div class="raw-json">
    <MCode class="code" :code="code" copy-label="reference profile JSON" />
    <span class="lines">{{ formatLinesCount(code) }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatLinesCount, formatReferenceDocument } from '@/utils/reference-profile'
import MCode from '@/components/MCode.vue'

interface Props {
  document: Record<string, unknown>
}

const props = defineProps<Props>()

const code = computed(() => formatReferenceDocument(props.document))
</script>

<style scoped>
.raw-json {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.code {
  flex: 1;
}

.lines {
  font-size: 12px;
  font-weight: 500;
  color: var(--p-text-muted-color);
}
</style>
