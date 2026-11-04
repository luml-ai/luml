<template>
  <div class="table-wrapper">
    <div class="table">
      <div class="simple-table__header">
        <div class="simple-table__row">
          <div>Label</div>
          <div>Base domain</div>
          <div>Kind</div>
          <div>Status</div>
          <div>Sessions</div>
          <div></div>
        </div>
      </div>
      <div class="simple-table__rows">
        <div v-if="!relaysStore.relays.length" class="simple-table__placeholder">
          No relays available for this organization.
        </div>
        <div
          v-for="relay in relaysStore.relays"
          :key="relay.id"
          class="simple-table__row"
          data-test="relay-row"
        >
          <div class="label-cell">
            <span class="cell">{{ relay.label }}</span>
            <Cable
              v-if="relay.present_capabilities.includes('sessions')"
              v-tooltip.top="'Sessions'"
              :size="14"
              data-test="sessions-capability"
            />
          </div>
          <div class="cell">{{ relay.base_domain }}</div>
          <div>
            <Tag v-if="relay.kind === RelayKindEnum.managed" value="Managed" severity="secondary" />
            <Tag v-else value="Own" severity="info" />
          </div>
          <div class="connection" v-tooltip.top="lastSeenText(relay.last_seen_at)">
            <span :class="['dot', { 'dot--online': relay.online }]"></span>
            <span>{{ relay.online ? 'Online' : 'Offline' }}</span>
            <span v-if="relay.status === RelayStatusEnum.draining" class="muted">Draining</span>
          </div>
          <div>{{ relay.connected_agents }}</div>
          <div>
            <RelaySettings
              v-if="canManage && relay.kind === RelayKindEnum.own"
              :relay="relay"
              :organization-id="organizationId"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RelayKindEnum, RelayStatusEnum } from '@/lib/api/relays/interfaces'
import { useRelaysStore } from '@/stores/relays'
import { useToast, Tag } from 'primevue'
import { Cable } from 'lucide-vue-next'
import { onMounted } from 'vue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import RelaySettings from './RelaySettings.vue'

type Props = {
  organizationId: string
  canManage: boolean
}

const props = defineProps<Props>()
const relaysStore = useRelaysStore()
const toast = useToast()

function lastSeenText(lastSeenAt: string | null) {
  return lastSeenAt ? `Last seen ${new Date(lastSeenAt).toLocaleString()}` : 'Never seen'
}

onMounted(async () => {
  try {
    await relaysStore.getRelays(props.organizationId)
  } catch (error: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to load relays')))
  }
})
</script>

<style scoped>
@import '@/assets/tables.css';

.table-wrapper {
  overflow-x: auto;
  padding: 16px;
  border-radius: 8px;
  background: var(--p-card-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--card-shadow);
}

.table {
  min-width: 720px;
}

.simple-table__row {
  grid-template-columns: 1fr 1fr 100px 160px 70px 35px;
}

.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}

.label-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.connection {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--p-text-muted-color);
}

.dot--online {
  background: var(--p-green-500);
}

.muted {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
