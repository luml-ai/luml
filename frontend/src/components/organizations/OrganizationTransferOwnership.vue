<template>
  <Button severity="secondary" variant="outlined" @click="open">Transfer ownership</Button>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Transfer ownership?"
    :style="{ width: '400px' }"
  >
    <div>
      <p v-if="candidates.length" class="text">
        The selected member becomes the owner of
        <span class="name">{{ organizationStore.currentOrganization?.name }}</span
        >. You stay in the organization as an admin.
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
        >Transfer</Button
      >
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, Dialog, Select, useToast } from 'primevue'
import { api } from '@/lib/api'
import type { Member } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useUserStore } from '@/stores/user'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const organizationStore = useOrganizationStore()
const userStore = useUserStore()
const toast = useToast()

const visible = ref(false)
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
    const newOwner = await api.transferOrganizationOwnership(
      organization.id,
      selectedMemberId.value,
    )
    visible.value = false
    toast.add(
      simpleSuccessToast(`${getMemberLabel(newOwner)} is now the owner of ${organization.name}.`),
    )
    await organizationStore.getAvailableOrganizations()
    await organizationStore.getOrganizationDetails(organization.id)
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not transfer ownership')))
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
