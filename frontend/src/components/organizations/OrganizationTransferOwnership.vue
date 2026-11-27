<template>
  <div v-if="pending">
    <p>Ownership transfer requested for {{ pending.recipient_email }}.</p>
    <p>
      Sent {{ new Date(pending.created_at).toLocaleString() }}. Expires
      {{ new Date(pending.expires_at).toLocaleString() }}.
    </p>
    <Button severity="secondary" :loading="loading" @click="cancel">Cancel transfer request</Button>
  </div>
  <Button v-else severity="secondary" variant="outlined" @click="open">Transfer ownership</Button>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Transfer ownership?"
    :style="{ width: '400px' }"
  >
    <div>
      <p v-if="candidates.length" class="text">
        The selected member will receive a request to become the owner of
        <span class="name">{{ organizationStore.currentOrganization?.name }}</span
        >. You remain the owner until they accept, then stay as an admin. The request expires in 7
        days.
      </p>
      <p v-else class="text">
        Invite a member to
        <span class="name">{{ organizationStore.currentOrganization?.name }}</span> before
        transferring ownership.
      </p>
      <Select
        v-if="candidates.length"
        v-model="selectedMemberId"
        :options="candidates"
        :optionLabel="getMemberLabel"
        optionValue="id"
        placeholder="Select new owner"
        class="select"
      />
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">Cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="!selectedMemberId"
        :loading="loading"
        @click="transferOwnership"
        >Send request</Button
      >
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { Button, Dialog, Select, useToast } from 'primevue'
import { api } from '@/lib/api'
import type { Member, OwnershipTransfer } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useUserStore } from '@/stores/user'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const organizationStore = useOrganizationStore()
const userStore = useUserStore()
const toast = useToast()

const pending = ref<OwnershipTransfer | null>(null)
const visible = ref(false)

async function loadPending() {
  const id = organizationStore.currentOrganization?.id
  if (!id) return
  try {
    pending.value = await api.getPendingOwnershipTransfer(id)
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not load transfer request')))
  }
}
watch(() => organizationStore.organizationDetails, loadPending, { immediate: true })
const expiryTimer = window.setInterval(() => {
  if (pending.value && new Date(pending.value.expires_at).getTime() <= Date.now())
    pending.value = null
}, 1000)
onUnmounted(() => window.clearInterval(expiryTimer))

async function cancel() {
  const id = organizationStore.currentOrganization?.id
  if (!id || !pending.value) return
  loading.value = true
  try {
    await api.cancelOwnershipTransfer(id, pending.value.id)
    pending.value = null
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not cancel transfer request')))
    await loadPending()
  } finally {
    loading.value = false
  }
}
const loading = ref(false)
const selectedMemberId = ref<string | null>(null)

const candidates = computed(() =>
  (organizationStore.organizationDetails?.members ?? []).filter(
    (member) =>
      member.user.id !== userStore.getUserId && member.role !== OrganizationRoleEnum.owner,
  ),
)

function getMemberLabel(member: Member) {
  return member.user.full_name
    ? `${member.user.full_name} (${member.user.email})`
    : member.user.email
}

function open() {
  selectedMemberId.value = null
  visible.value = true
}

async function transferOwnership() {
  const organization = organizationStore.currentOrganization
  if (!organization || !selectedMemberId.value) return
  loading.value = true
  try {
    pending.value = await api.requestOrganizationOwnership(organization.id, selectedMemberId.value)
    visible.value = false
    if (pending.value.email_delivery_failed) {
      toast.add(
        simpleErrorToast(
          'Request saved, but the email could not be delivered. The recipient can respond on the Invitations page.',
        ),
      )
    }
    toast.add(simpleSuccessToast(`Ownership transfer request sent for ${organization.name}.`))
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not send transfer request')))
    await loadPending()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.text {
  margin-bottom: 14px;
}
.name {
  font-weight: 600;
}
.select {
  width: 100%;
}
</style>
