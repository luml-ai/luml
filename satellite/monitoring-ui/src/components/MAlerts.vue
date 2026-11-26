<template>
  <Card v-if="sortedAlerts.length" class="alerts">
    <template #content>
      <div class="alerts-list">
        <template v-for="(alert, index) in sortedAlerts" :key="getAlertKey(alert)">
          <Divider v-if="index > 0" :dt="{ horizontal: { margin: '8px 0' } }" />
          <div class="alert" :class="`alert--${alert.severity}`">
            <div class="alert-title">
              <TriangleAlert :size="14" class="alert-icon" />
              <button type="button" class="alert-name" @click="emit('select', alert)">
                {{ getAlertTitle(alert) }}
              </button>
              <Tag v-if="alert.feature" :value="alert.feature" severity="secondary" />
            </div>
            <span class="alert-message">{{ alert.message }}</span>
          </div>
        </template>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertBanner } from '@/api/monitoring/interfaces'
import { getAlertKey, getAlertTitle, getOpenAlerts, sortAlertsBySeverity } from '@/utils/alerts'
import { TriangleAlert } from 'lucide-vue-next'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'

interface Props {
  alerts: AlertBanner[]
}

const props = withDefaults(defineProps<Props>(), {
  alerts: () => [],
})

const emit = defineEmits<{
  select: [alert: AlertBanner]
}>()

const sortedAlerts = computed(() => sortAlertsBySeverity(getOpenAlerts(props.alerts)))
</script>

<style scoped>
.alerts {
  border: 1px solid var(--p-content-border-color);
}

.alerts-list {
  max-height: 220px;
  overflow-y: auto;
}

.alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.alert-title {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.alert-icon {
  flex-shrink: 0;
}

.alert-name {
  min-width: 0;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-name:hover {
  text-decoration: underline;
}

.alert-message {
  overflow: hidden;
  font-size: 12px;
  color: var(--p-text-muted-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert--critical .alert-icon {
  color: var(--p-badge-danger-background);
}

.alert--critical .alert-message {
  font-weight: 500;
  color: var(--p-text-color);
}

.alert--warning .alert-icon {
  color: var(--p-badge-warn-background);
}
</style>
