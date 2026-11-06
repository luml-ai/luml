<template>
  <Dialog v-model:visible="show" header="Delete account?" modal :draggable="false" :pt="dialogPt">
    <div class="description">
      Deleting your account is permanent and irreversible.
      <template v-if="rows.length">Here is what happens to your organizations:</template>
    </div>
    <div v-if="loading" class="loader">
      <ProgressSpinner style="width: 32px; height: 32px" />
    </div>
    <ul v-else-if="rows.length" class="organizations">
      <li v-for="row in rows" :key="row.organization.id" class="organization">
        <div class="organization-header">
          <span class="organization-name">{{ row.organization.name }}</span>
          <Button
            v-if="row.kind === 'transfer' && !row.picking"
            label="Transfer ownership"
            size="small"
            severity="secondary"
            @click="row.picking = true"
          />
        </div>
        <div class="organization-note">{{ getNote(row) }}</div>
        <div v-if="row.kind === 'transfer' && row.picking" class="transfer">
          <Select
            v-model="row.selectedMemberId"
            :options="row.candidates"
            :optionLabel="getMemberLabel"
            optionValue="id"
            placeholder="Select new owner"
            size="small"
            class="transfer-select"
          />
          <Button
            label="Transfer"
            size="small"
            :disabled="!row.selectedMemberId"
            :loading="row.transferring"
            @click="transfer(row)"
          />
          <Button
            label="Cancel"
            size="small"
            variant="text"
            severity="secondary"
            :disabled="row.transferring"
            @click="row.picking = false"
          />
        </div>
      </li>
    </ul>
    <template #footer>
      <Button label="Cancel" severity="secondary" :disabled="deleting" @click="show = false" />
      <Button
        label="Yes, delete my account"
        severity="warn"
        outlined
        :loading="deleting"
        :disabled="loading || isTransferring"
        @click="deleteAccount"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Button, Dialog, ProgressSpinner, Select, useToast } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/lib/api'
import type { Member, Organization } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useUserStore } from '@/stores/user'
import { useOrganizationStore } from '@/stores/organization'

type RowKind = 'delete' | 'transfer' | 'leave' | 'transferred'

interface OrganizationRow {
  organization: Organization
  kind: RowKind
  candidates: Member[]
  picking: boolean
  selectedMemberId: string | null
  transferring: boolean
  newOwner: Member | null
}

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'width: 100%; max-width: 600px',
  },
  header: {
    style: 'text-transform: uppercase; font-size: 20px; padding: 36px 36px 12px;',
  },
  content: {
    style: 'padding: 0 36px;',
  },
  footer: {
    style: 'display: flex; justify-content: flex-end; gap: 8px; padding: 28px 36px 36px;',
  },
}

const show = defineModel<boolean>('show')

const toast = useToast()
const router = useRouter()
const userStore = useUserStore()
const organizationStore = useOrganizationStore()

const loading = ref(false)
const deleting = ref(false)
const rows = ref<OrganizationRow[]>([])

const isTransferring = computed(() => rows.value.some((row) => row.transferring))

function getMemberLabel(member: Member) {
  return member.user.full_name
    ? `${member.user.full_name} (${member.user.email})`
    : member.user.email
}

function getNote(row: OrganizationRow) {
  if (row.kind === 'delete') {
    return 'You are the only member. The organization will be deleted with all its orbits, collections, models, satellites, deployments and bucket secrets.'
  }
  if (row.kind === 'transfer') {
    return 'You are the only owner. Transfer ownership to a member of your choice, otherwise it will pass to an admin or the longest-standing member.'
  }
  if (row.kind === 'transferred' && row.newOwner) {
    return `Ownership transferred to ${getMemberLabel(row.newOwner)}. You will be removed from this organization.`
  }
  return 'You will be removed from this organization.'
}

async function buildRow(organization: Organization): Promise<OrganizationRow> {
  const row: OrganizationRow = {
    organization,
    kind: 'leave',
    candidates: [],
    picking: false,
    selectedMemberId: null,
    transferring: false,
    newOwner: null,
  }
  if (organization.role !== OrganizationRoleEnum.owner) return row

  const members = await api.getOrganizationMembers(organization.id)
  const others = members.filter((member) => member.user.id !== userStore.getUserId)
  if (!others.length) {
    row.kind = 'delete'
  } else if (!others.some((member) => member.role === OrganizationRoleEnum.owner)) {
    row.kind = 'transfer'
    row.candidates = others
  }
  return row
}

async function load() {
  loading.value = true
  rows.value = []
  try {
    const organizations = await api.getOrganizations()
    rows.value = await Promise.all(organizations.map(buildRow))
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load organizations')))
  } finally {
    loading.value = false
  }
}

async function transfer(row: OrganizationRow) {
  if (!row.selectedMemberId) return
  row.transferring = true
  try {
    row.newOwner = await api.transferOrganizationOwnership(
      row.organization.id,
      row.selectedMemberId,
    )
    row.kind = 'transferred'
    row.picking = false
    toast.add(simpleSuccessToast(`Ownership of ${row.organization.name} was transferred.`))
    organizationStore.getAvailableOrganizations()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to transfer ownership')))
  } finally {
    row.transferring = false
  }
}

watch(
  show,
  (value) => {
    if (value) load()
  },
  { immediate: true },
)

async function deleteAccount() {
  deleting.value = true
  try {
    await userStore.deleteAccount()
    show.value = false
    router.push({ name: 'sign-up' })
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to delete account')))
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.description {
  color: var(--p-text-muted-color);
}

.loader {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}

.organizations {
  list-style: none;
  padding: 0;
  margin: 20px 0 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 50vh;
  overflow-y: auto;
}

.organization {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 12px 16px;
}

.organization-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
}

.organization-name {
  font-weight: 500;
}

.organization-note {
  margin-top: 4px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.transfer {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.transfer-select {
  flex: 1 1 auto;
  min-width: 0;
}
</style>
