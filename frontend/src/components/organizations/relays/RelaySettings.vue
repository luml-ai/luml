<template>
  <Button severity="secondary" variant="text" aria-label="Relay settings" @click="open">
    <template #icon>
      <Bolt :size="14" />
    </template>
  </Button>
  <UiDialogRight
    v-model:visible="visible"
    :icon="Bolt"
    title="relay settings"
    :footer-actions="footerActions"
  >
    <div class="dialog-content">
      <RelayForm v-model="formData" form-id="relaySettingsForm" @submit="save" />
      <div class="setting">
        <div>
          <div class="setting-title">Draining</div>
          <div class="setting-hint">Takes no new sessions.</div>
        </div>
        <ToggleSwitch
          :model-value="relay.status === RelayStatusEnum.draining"
          :disabled="loading"
          @update:model-value="setDraining"
        />
      </div>
      <div class="setting">
        <div class="setting-title">Token</div>
        <Button
          label="Rotate"
          severity="secondary"
          variant="outlined"
          size="small"
          :loading="rotating"
          @click="onRotate"
        />
      </div>
    </div>
  </UiDialogRight>
  <RelayTokenDialog v-if="token" :token="token" @close="token = null" />
</template>

<script setup lang="ts">
import {
  RelayStatusEnum,
  type Relay,
  type RelayCreatePayload,
  type RelayUpdatePayload,
} from '@/lib/api/relays/interfaces'
import { computed, ref } from 'vue'
import { Button, ToggleSwitch, useConfirm, useToast } from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { useRelaysStore } from '@/stores/relays'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import {
  deleteRelayConfirmOptions,
  rotateRelayTokenConfirmOptions,
} from '@/lib/primevue/data/confirm'
import { getErrorMessage } from '@/helpers/helpers'
import UiDialogRight, { type FooterActions } from '@/components/ui/dialogs/UiDialogRight.vue'
import RelayForm from './RelayForm.vue'
import RelayTokenDialog from './RelayTokenDialog.vue'

type Props = {
  relay: Relay
  organizationId: string
}

const props = defineProps<Props>()
const relaysStore = useRelaysStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)
const rotating = ref(false)
const token = ref<string | null>(null)
const formData = ref<RelayCreatePayload>({ label: '', base_domain: '', agent_url: '' })

const footerActions = computed<FooterActions>(() => ({
  leftButton: {
    props: {
      label: 'Remove relay',
      severity: 'warn',
      variant: 'outlined',
      disabled: loading.value,
      onClick: onRemove,
    },
  },
  rightButton: {
    props: {
      label: 'Save changes',
      type: 'submit',
      form: 'relaySettingsForm',
      loading: loading.value,
    },
  },
}))

function open() {
  formData.value = {
    label: props.relay.label,
    base_domain: props.relay.base_domain,
    agent_url: props.relay.agent_url,
  }
  visible.value = true
}

function changedFields(): RelayUpdatePayload {
  const payload: RelayUpdatePayload = {}
  for (const field of ['label', 'base_domain', 'agent_url'] as const) {
    if (formData.value[field] !== props.relay[field]) payload[field] = formData.value[field]
  }
  return payload
}

async function update(payload: RelayUpdatePayload, successMessage: string, errorMessage: string) {
  try {
    loading.value = true
    await relaysStore.updateRelay(props.organizationId, props.relay.id, payload)
    toast.add(simpleSuccessToast(successMessage))
    return true
  } catch (error: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(error, errorMessage)))
    return false
  } finally {
    loading.value = false
  }
}

async function save() {
  const payload = changedFields()
  if (!Object.keys(payload).length) {
    visible.value = false
    return
  }
  if (await update(payload, 'Relay has been updated.', 'Failed to update relay')) {
    visible.value = false
  }
}

async function setDraining(draining: boolean) {
  const status = draining ? RelayStatusEnum.draining : RelayStatusEnum.enabled
  await update({ status }, `Relay is ${status}.`, 'Failed to change relay status')
}

function onRotate() {
  confirm.require(rotateRelayTokenConfirmOptions(rotate))
}

async function rotate() {
  try {
    rotating.value = true
    token.value = await relaysStore.rotateRelayToken(props.organizationId, props.relay.id)
  } catch (error: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to rotate relay token')))
  } finally {
    rotating.value = false
  }
}

function onRemove() {
  confirm.require(deleteRelayConfirmOptions(remove))
}

async function remove() {
  try {
    loading.value = true
    await relaysStore.deleteRelay(props.organizationId, props.relay.id)
    visible.value = false
    toast.add(simpleSuccessToast(`Relay “${props.relay.label}” was removed.`))
  } catch (error: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to remove relay')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.setting {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.setting-title {
  font-size: 14px;
  margin-bottom: 4px;
}
.setting-hint {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
