<template>
  <Button severity="secondary" @click="visible = true">Manage invites</Button>
  <Dialog
    v-model:visible="visible"
    modal
    header="Manage invites"
    :draggable="false"
    style="width: 938px; max-width: 100%"
    :pt="dialogPT"
  >
    <div class="dialog-content">
      <p class="dialog-text">
        Organization members have access to all data within the organization.
      </p>
      <div v-if="invites.length" class="table-wrapper">
        <div class="table">
          <div class="table-header">
            <div class="table-row">
              <div>Email</div>
              <div>Role</div>
              <div>Invited by</div>
              <div>Invitation sent on</div>
              <div></div>
            </div>
          </div>
          <div class="table-body">
            <div v-for="invitation in invites" class="table-row">
              <div class="cell">{{ invitation.email }}</div>
              <div class="cell">{{ invitation.role }}</div>
              <div class="cell">{{ invitation.invited_by_user.full_name }}</div>
              <div class="cell">{{ new Date(invitation.created_at).toLocaleDateString() }}</div>
              <div class="buttons">
                <Button
                  severity="secondary"
                  variant="outlined"
                  :disabled="loading"
                  @click="reject(invitation.organization_id, invitation.id)"
                >
                  <template #icon>
                    <Trash2 :size="12" />
                  </template>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="placeholder">
        There are currently no pending invitations for this organization.
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, Dialog, useToast } from 'primevue'
import { Trash2 } from 'lucide-vue-next'
import { useOrganizationStore } from '@/stores/organization'
import { useInvitationsStore } from '@/stores/invitations'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const dialogPT = {
  root: {
    style: 'padding: 18px;',
  },
  header: {
    style: 'font-size: 20px; font-weight: 600; text-transform: uppercase; padding-bottom: 12px;',
  },
}

const organizationStore = useOrganizationStore()
const invitationStore = useInvitationsStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

const invites = computed(() => organizationStore.organizationDetails?.invites || [])

async function reject(organizationId: string, inviteId: string) {
  loading.value = true
  try {
    await invitationStore.cancelInvite(organizationId, inviteId)
    organizationStore.removeInviteFromCurrentOrganization(inviteId)
    toast.add(simpleSuccessToast('The user is no longer invited to the organization.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to remove invite'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.table-wrapper {
  overflow-x: auto;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  padding: 16px;
  border-radius: 8px;
}
.table {
  min-width: 858px;
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
  grid-template-columns: 263px 120px 150px 150px auto;
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
