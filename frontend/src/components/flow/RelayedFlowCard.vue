<template>
  <FlowCard
    :name="flow.name"
    kind="relayed"
    :status-class="status.className"
    :status-tooltip="status.tooltip"
  >
    <template #actions>
      <Button
        v-if="isLive"
        variant="text"
        severity="secondary"
        v-tooltip.top="'Open in a new tab'"
        data-testid="open-flow"
        @click="openInNewTab"
      >
        <template #icon><ExternalLink :size="14" /></template>
      </Button>
      <Button
        variant="text"
        severity="secondary"
        v-tooltip.top="'Remove'"
        :loading="removing"
        data-testid="remove-flow"
        @click="confirmRemoval"
      >
        <template #icon><Trash2 :size="14" /></template>
      </Button>
    </template>
    <span data-testid="flow-updated">{{ updatedText }}</span>
  </FlowCard>
</template>

<script setup lang="ts">
import type { Flow } from '@/lib/api/flows/interfaces'
import { computed, ref } from 'vue'
import { Button, useConfirm, useToast } from 'primevue'
import { ExternalLink, Trash2 } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { LiveSessionStatusEnum } from '@/lib/api/live-sessions/interfaces'
import { useFlowsStore } from '@/stores/flows'
import { removeFlowConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage, getLastUpdateText } from '@/helpers/helpers'
import FlowCard from './FlowCard.vue'

type Props = {
  flow: Flow
  organizationId: string
  orbitId: string
}

const props = defineProps<Props>()

const flowsStore = useFlowsStore()
const confirm = useConfirm()
const toast = useToast()

const removing = ref(false)

const isLive = computed(() => props.flow.session.status === LiveSessionStatusEnum.live)

const status = computed(() =>
  isLive.value
    ? { className: 'status--success', tooltip: 'Active flow' }
    : { className: 'status--warn', tooltip: 'The flow appears to be offline' },
)

const updatedText = computed(() =>
  getLastUpdateText(props.flow.session.last_heartbeat_at ?? props.flow.session.started_at),
)

async function openInNewTab() {
  // Opened before the token request, while the click still allows a new tab.
  const tab = window.open('', '_blank')
  if (!tab) {
    toast.add(simpleErrorToast('The browser blocked the new tab'))
    return
  }
  tab.opener = null
  try {
    const { launch_url: launchUrl } = await api.liveSessions.issueViewToken(
      props.organizationId,
      props.orbitId,
      props.flow.session.id,
    )
    tab.location.href = launchUrl
  } catch (e: unknown) {
    tab.close()
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to open the flow')))
  }
}

async function remove() {
  try {
    removing.value = true
    await flowsStore.removeFlow(props.organizationId, props.orbitId, props.flow.id)
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to remove the flow')))
  } finally {
    removing.value = false
  }
}

function confirmRemoval() {
  confirm.require(removeFlowConfirmOptions(remove))
}
</script>
