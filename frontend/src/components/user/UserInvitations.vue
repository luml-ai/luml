<template>
  <div class="user-notification">
    <div v-if="invitationsStore.invitations.length" class="user-notification__circle"></div>
    <d-button rounded severity="help" @click="visible = true">
      <template #icon>
        <Bell :size="12" />
      </template>
    </d-button>

    <Dialog
      v-model:visible="visible"
      modal
      :draggable="false"
      :style="{ maxWidth: '1000px', width: '100%', padding: '18px' }"
    >
      <template #header>
        <div>
          <h3 class="title">invitation center</h3>
        </div>
      </template>
      <h4 class="sub-title">
        Organization collaborators have access to all bases within the organization.
      </h4>
      <div v-if="invitationsStore.invitations.length" class="table">
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
          <div v-for="invitation in invitationsStore.invitations" class="table-row">
            <div class="cell">{{ invitation.organization.name }}</div>
            <div class="cell">{{ invitation.role }}</div>
            <div class="cell">{{ invitation.invited_by_user.full_name }}</div>
            <div class="cell">{{ new Date(invitation.created_at).toLocaleDateString() }}</div>
            <div class="buttons">
              <d-button
                severity="secondary"
                variant="outlined"
                :disabled="loading"
                @click="reject(invitation.id)"
              >
                <template #icon>
                  <Trash2 :size="12" />
                </template>
              </d-button>
              <d-button :disabled="loading" @click="accept(invitation.id, invitation.organization_id)">
                <template #icon>
                  <Check :size="12" />
                </template>
              </d-button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="placeholder">There are currently no invitations awaiting response.</div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Bell, Trash2, Check } from 'lucide-vue-next'
import { Dialog, useToast } from 'primevue'
import { useInvitationsStore } from '@/stores/invitations'
import { simpleErrorToast, simpleSuccessToast, simpleWardToast } from '@/lib/primevue/data/toasts'

const invitationsStore = useInvitationsStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

async function accept(inviteId: number, organizationId: number) {
  loading.value = true

  try {
    await invitationsStore.acceptInvitation(inviteId, organizationId)
    toast.add(simpleSuccessToast('You’ve joined the organization successfully.'))
  } catch (e) {
    toast.add(simpleErrorToast('Failed to accept the invitation'))
  } finally {
    loading.value = false
  }
}

async function reject(inviteId: number) {
  loading.value = true

  try {
    await invitationsStore.rejectInvitation(inviteId)
    toast.add(simpleWardToast('The invitation has been declined.'))
  } catch (e) {
    toast.add(simpleErrorToast('Failed to reject the invitation'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.user-notification {
  position: relative;
}
.user-notification__circle {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background-color: var(--p-badge-success-background);
  border-radius: 50%;
  z-index: 2;
}
.title {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 20px;
}
.sub-title {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.table {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  padding: 16px;
  width: 100%;
  border-radius: 8px;
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
  grid-template-columns: 218px 120px 190px 170px auto;
  align-items: center;
  gap: 24px;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.placeholder {
  font-size: 20px;
}
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
