<template>
  <div class="card">
    <div class="content">
      <div class="header">
        <h3 class="title">
          <div
            class="status"
            v-tooltip.top="statusData.tooltip"
            :class="statusData.className"
          ></div>
          <span>{{ data.name }}</span>
        </h3>
        <Button variant="text" severity="secondary" @click.stop.prevent="toggle">
          <template #icon>
            <EllipsisVertical :size="14" />
          </template>
        </Button>
        <Menu
          ref="menu"
          :model="menuItems"
          :popup="true"
          style="background-color: var(--p-card-background)"
        ></Menu>
      </div>
      <div class="body">
        <div class="description">
          <p v-if="data.description" class="text">
            {{ data.description }}
          </p>
        </div>
        <p class="text">{{ updatedText }}</p>
        <div class="capabilities">
          <Rocket v-if="data.capabilities.deploy" v-tooltip="'Deploy'" :size="16"></Rocket>
        </div>
      </div>
    </div>
  </div>
  <SatellitesEditModal v-model:visible="showEditModal" :data="data"></SatellitesEditModal>
  <SatellitesApiKeyModal
    v-model:visible="showApiKey"
    :api-key="null"
    :satellite-id="data.id"
  ></SatellitesApiKeyModal>
</template>

<script setup lang="ts">
import { SatelliteStatusEnum, type Satellite } from '@/lib/api/satellites/interfaces'
import { getLastUpdateText } from '@/helpers/helpers'
import { EllipsisVertical, Rocket } from 'lucide-vue-next'
import { Button, Menu } from 'primevue'
import { computed, ref } from 'vue'
import SatellitesEditModal from './SatellitesEditModal.vue'
import SatellitesApiKeyModal from './SatellitesApiKeyModal.vue'

type Props = {
  data: Satellite
}

const props = defineProps<Props>()

const showEditModal = ref(false)

const showApiKey = ref(false)

const menu = ref()

const menuItems = ref([
  {
    label: 'Settings',
    command: () => {
      showEditModal.value = true
    },
  },
  {
    label: 'API Key',
    command: () => {
      showApiKey.value = true
    },
  },
])

const updatedText = computed(() => {
  return getLastUpdateText(props.data.updated_at || props.data.created_at)
})

const statusData = computed(() => {
  switch (props.data.status) {
    case SatelliteStatusEnum.active:
      return { className: 'status--success', tooltip: 'Active satellite' }
    case SatelliteStatusEnum.error:
      return { className: 'status--warn', tooltip: 'Error' }
    case SatelliteStatusEnum.inactive:
      return { className: 'status--danger', tooltip: 'Not connected' }
    default:
      return { className: '', tooltip: '' }
  }
})

const toggle = (event: MouseEvent) => {
  menu.value.toggle(event)
}
</script>

<style scoped>
.card {
  padding: 16px 16px 20px;
  border-radius: 8px;
  background-color: var(--p-card-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--p-card-shadow);
  transition: background-color 0.2s;
  cursor: pointer;
  color: inherit;
  text-decoration: none;
}

.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  gap: 6px;
  align-items: center;
}

.status {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1px solid transparent;
  display: flex;
  justify-content: center;
  align-items: center;
}

.status::before {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status--success {
  border-color: var(--p-toast-success-border-color);
  background-color: var(--p-toast-success-background);
}

.status--success::before {
  background-color: var(--p-badge-success-background);
  box-shadow: 0 2px 8px 0 rgba(34, 197, 94, 0.5);
}

.status--warn {
  border-color: var(--p-toast-warn-border-color);
  background-color: var(--p-toast-warn-background);
}

.status--warn::before {
  background-color: var(--p-badge-warn-background);
  box-shadow: 0 2px 8px 0 rgba(249, 115, 22, 0.5);
}

.status--danger {
  border-color: var(--p-toast-error-border-color);
  background-color: var(--p-toast-error-background);
}

.status--danger::before {
  background-color: var(--p-badge-danger-background);
  box-shadow: 0 2px 8px 0 rgba(249, 115, 22, 0.5);
}

.body {
  padding: 0 8px 0 4px;
}

.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.description {
  margin-bottom: 8px;
  overflow: hidden;
  height: 30px;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.capabilities {
  padding-top: 12px;
  display: flex;
  gap: 12px;
  color: var(--p-icon-muted-color);
}
</style>
