<template>
  <section aria-label="Ownership transfer requests">
    <p v-if="error">Could not load ownership requests. <Button label="Retry" @click="load" /></p>
    <article v-for="request in requests" :key="request.id" class="request">
      <h4>Ownership of {{ request.organization_name }}</h4>
      <p>
        {{ request.sender_email }} asks you to become the owner. Expires
        {{ new Date(request.expires_at).toLocaleString() }}.
      </p>
      <Button
        label="Decline"
        severity="secondary"
        :disabled="loading"
        @click="respond(request, 'decline')"
      />
      <Button label="Accept ownership" :disabled="loading" @click="selected = request" />
    </article>
    <Dialog
      :visible="!!selected"
      modal
      header="Accept organization ownership?"
      @update:visible="selected = null"
    >
      <p>
        You will become the owner of {{ selected?.organization_name }}, with full control and
        responsibility for the organization and its members. The current owner will become an admin.
      </p>
      <p>
        Ownership can include responsibility for payments. Review the organization before accepting.
      </p>
      <template #footer>
        <Button label="Cancel" severity="secondary" :disabled="loading" @click="selected = null" />
        <Button
          label="Confirm acceptance"
          :loading="loading"
          @click="selected && respond(selected, 'accept')"
        />
      </template>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { Button, Dialog, useToast } from 'primevue'
import { api } from '@/lib/api'
import type { OwnershipTransfer } from '@/lib/api/api.interfaces'
import { useInvitationsStore } from '@/stores/invitations'
import { useOrganizationStore } from '@/stores/organization'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'

const invitationsStore = useInvitationsStore()
const { ownershipTransfers: requests, ownershipTransfersLoadError: error } =
  storeToRefs(invitationsStore)
const selected = ref<OwnershipTransfer | null>(null)
const loading = ref(false)
const toast = useToast()
const organizationStore = useOrganizationStore()

async function load() {
  await invitationsStore.getOwnershipTransfers().catch(() => undefined)
}

async function respond(request: OwnershipTransfer, action: 'accept' | 'decline') {
  loading.value = true
  try {
    const response = await api.respondToOwnershipTransfer(request, action)
    if (response.email_delivery_failed) {
      toast.add(simpleErrorToast('Response saved, but the result email could not be delivered.'))
    }
    selected.value = null
    toast.add(
      simpleSuccessToast(
        action === 'accept' ? 'Ownership accepted.' : 'Ownership transfer declined.',
      ),
    )
    if (action === 'accept') {
      await organizationStore.getAvailableOrganizations()
      await organizationStore.switchOrganization(request.organization_id)
    }
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not respond to ownership request')))
  } finally {
    loading.value = false
    await load()
  }
}

onMounted(load)
const expiryTimer = window.setInterval(() => {
  requests.value = requests.value.filter(
    (request) => new Date(request.expires_at).getTime() > Date.now(),
  )
  if (selected.value && new Date(selected.value.expires_at).getTime() <= Date.now())
    selected.value = null
}, 1000)
onUnmounted(() => window.clearInterval(expiryTimer))
</script>

<style scoped>
.request {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
</style>
