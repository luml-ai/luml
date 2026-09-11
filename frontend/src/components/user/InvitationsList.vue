<template>
  <div v-if="!invitationsStore.isLoaded || invitationsStore.isLoading" class="status">
    <ProgressSpinner class="spinner" aria-label="Loading invitations" />
    <span>Loading invitations...</span>
  </div>
  <div v-else-if="invitationsStore.loadError" class="status">
    <span>Failed to load invitations.</span>
    <d-button label="Retry" size="small" :loading="invitationsStore.isLoading" @click="retry" />
  </div>
  <div v-else-if="invitationsStore.invitations.length" class="table">
    <div class="table-header">
      <div class="table-row">
        <div>Organization</div>
        <div>Role</div>
        <div>Invited by</div>
        <div>Invitation sent on</div>
        <div></div>
      </div>
    </div>
    <div class="table-body">
      <div
        v-for="invitation in invitationsStore.invitations"
        :key="invitation.id"
        class="table-row"
      >
        <div class="cell">{{ invitation.organization.name }}</div>
        <div class="cell">{{ invitation.role }}</div>
        <div class="cell">{{ invitation.invited_by_user.full_name }}</div>
        <div class="cell">{{ new Date(invitation.created_at).toLocaleDateString() }}</div>
        <div class="buttons">
          <d-button
            severity="secondary"
            variant="outlined"
            :disabled="loading"
            aria-label="Decline invitation"
            @click="reject(invitation.id)"
          >
            <template #icon>
              <Trash2 :size="12" />
            </template>
          </d-button>
          <d-button
            :disabled="loading"
            aria-label="Accept invitation"
            @click="accept(invitation.id, invitation.organization_id)"
          >
            <template #icon>
              <Check :size="12" />
            </template>
          </d-button>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="placeholder">There are currently no invitations awaiting response.</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Trash2, Check } from 'lucide-vue-next'
import { ProgressSpinner, useToast } from 'primevue'
import { useInvitationsStore } from '@/stores/invitations'
import { simpleErrorToast, simpleSuccessToast, simpleWardToast } from '@/lib/primevue/data/toasts'

const invitationsStore = useInvitationsStore()
const toast = useToast()
const loading = ref(false)

async function retry() {
  try {
    await invitationsStore.getInvitations()
  } catch {
    toast.add(simpleErrorToast('Failed to load invitations'))
  }
}

async function accept(inviteId: string, organizationId: string) {
  loading.value = true

  try {
    await invitationsStore.acceptInvitation(inviteId, organizationId)
    toast.add(simpleSuccessToast('You’ve joined the organization successfully.'))
  } catch {
    toast.add(simpleErrorToast('Failed to accept the invitation'))
  } finally {
    loading.value = false
  }
}

async function reject(inviteId: string) {
  loading.value = true

  try {
    await invitationsStore.rejectInvitation(inviteId)
    toast.add(simpleWardToast('The invitation has been declined.'))
  } catch {
    toast.add(simpleErrorToast('Failed to reject the invitation'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.table {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  padding: 16px;
  width: 100%;
  border-radius: 8px;
  overflow-x: auto;
}
.table-header {
  font-weight: 500;
  text-align: left;
  border-bottom: 1px solid var(--p-divider-border-color);
  padding: 10px 0;
  margin-bottom: 12px;
}
.table-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.table-row {
  display: grid;
  grid-template-columns: minmax(150px, 218px) 120px 190px 170px auto;
  align-items: center;
  gap: 24px;
  min-width: 800px;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.placeholder {
  font-size: 20px;
}
.status {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
}
.spinner {
  width: 28px;
  height: 28px;
}
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
