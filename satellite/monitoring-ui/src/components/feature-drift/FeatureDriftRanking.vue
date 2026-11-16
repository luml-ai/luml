<template>
  <div class="ranking">
    <h3 class="title">Ranked feature drift</h3>
    <div class="list">
      <button
        v-for="feature in features"
        :key="feature.feature"
        type="button"
        class="row"
        :class="{ selected: feature.feature === selected }"
        :aria-pressed="feature.feature === selected"
        @click="emit('select', feature.feature)"
      >
        <Tag class="feature-tag" severity="secondary">
          <MEllipsis :text="feature.feature" />
        </Tag>
        <span class="meta">
          <span class="psi">{{ formatPsiLabel(feature.psi) }}</span>
          <Tag
            :value="getSeverityLabel(feature.severity)"
            :severity="getSeverityTagSeverity(feature.severity)"
            :dt="STATUS_TAG_TOKENS"
          />
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import type { DriftedFeature } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatPsiLabel } from '@/utils/drift'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  features: DriftedFeature[]
  selected?: string | null
}

defineProps<Props>()

const emit = defineEmits<{
  select: [feature: string]
}>()
</script>

<style scoped>
.ranking {
  display: flex;
  flex-direction: column;
  flex: 0 0 280px;
  gap: 20px;
  min-width: 0;
  padding: 20px 0;
  border-right: 1px solid var(--p-divider-border-color);
}

.title {
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 0 20px;
  overflow-y: auto;
  contain: size;
}

.row {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s;
}

.row:hover,
.row.selected {
  border-color: var(--p-primary-hover-color);
}

.row:focus-visible {
  outline: 1px solid var(--p-primary-color);
  outline-offset: 2px;
}

.feature-tag {
  min-width: 0;
  max-width: 100%;
}

.meta {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.psi {
  font-size: 12px;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

@media (max-width: 720px) {
  .ranking {
    flex-basis: auto;
    border-right: none;
    border-bottom: 1px solid var(--p-divider-border-color);
  }

  .list {
    max-height: 320px;
    contain: none;
  }
}
</style>
