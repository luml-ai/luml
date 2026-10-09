<template>
  <Button severity="secondary" @click="visible = true">
    <template #icon>
      <UserCog :size="14" />
    </template>
  </Button>
  <Dialog
    :visible="visible"
    :draggable="false"
    :closable="!loading"
    modal
    :pt="dialogPt"
    header="Manage Orbit Members"
    @update:visible="!loading && (visible = $event)"
  >
    <div class="dialog-content">
      <p class="text">
        Click Add members to add selected users immediately. Role changes require Save changes.
      </p>
      <div class="form">
        <AutoComplete
          v-model="searchModel"
          placeholder="Search users in organization"
          inputId="multiple-ac-1"
          multiple
          fluid
          :suggestions="searchedMembers"
          :disabled="loading"
          class="autocomplete"
          optionLabel="user.email"
          @complete="onComplete"
        />
        <Button
          class="add-button"
          :disabled="loading || !searchModel.length"
          :loading="loading"
          @click="addUsers"
          >Add members</Button
        >
      </div>
      <div class="body">
        <div v-if="!orbitMembers.length" class="placeholder">
          There are currently no active members for this Orbit.
        </div>
        <div v-else class="table-wrapper">
          <div class="table">
            <div class="table-header">
              <div class="table-row">
                <div>Orbit members</div>
                <div>Role</div>
                <div></div>
              </div>
            </div>
            <div class="table-body">
              <div v-for="member in orbitMembers" :key="member.id" class="table-row">
                <div class="cell cell-user">
                  <Avatar
                    :label="member.user.photo ? undefined : member.user.full_name[0]"
                    shape="circle"
                    :image="member.user.photo"
                    class="avatar"
                  />
                  <div>
                    <h4>{{ member.user.full_name }}</h4>
                  </div>
                </div>
                <div class="cell">
                  <Select
                    v-model="member.role"
                    :disabled="loading"
                    :options="OPTIONS"
                    option-label="label"
                    option-value="value"
                    name="role"
                    id="role"
                    fluid
                  ></Select>
                </div>
                <div class="buttons">
                  <Button
                    severity="secondary"
                    variant="outlined"
                    :disabled="loading"
                    @click="onTrashClick(member.id)"
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
      </div>
    </div>
    <template #footer>
      <div class="footer-buttons">
        <Button :disabled="loading || !changedMembers.length" @click="saveChanges">
          Save changes
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent, DialogPassThroughOptions } from 'primevue'
import type { Member, OrbitMember } from '@/lib/api/api.interfaces'
import { computed, ref, watch } from 'vue'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import { UserCog, Trash2 } from 'lucide-vue-next'
import { Dialog, AutoComplete, Button, useToast, Avatar, Select, useConfirm } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { OrbitRoleEnum } from '../orbits/orbits.interfaces'
import { deleteUserConfirmOptions } from '@/lib/primevue/data/confirm'
import { useUserStore } from '@/stores/user'
import { getErrorMessage } from '@/helpers/helpers'

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 800px; width: 100%;',
  },
  header: {
    style: 'padding: 36px 36px 12px; text-transform: uppercase; font-size: 20px; font-weight: 600;',
  },
  content: {
    style: 'padding: 0 36px 36px;',
  },
}

const OPTIONS = [
  {
    label: 'Admin',
    value: OrbitRoleEnum.admin,
  },
  {
    label: 'Member',
    value: OrbitRoleEnum.member,
  },
]

type Props = {
  orbitId: string
}

const props = defineProps<Props>()

const organizationsStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const confirm = useConfirm()
const userStore = useUserStore()

const visible = ref(false)
const loading = ref(false)
const initialOrbitMembers = ref<OrbitMember[]>([])
const orbitMembers = ref<OrbitMember[]>([])
const searchModel = ref<Member[]>([])
const searchedMembers = ref<Member[]>([])

const changedMembers = computed(() =>
  orbitMembers.value.filter(
    (member) =>
      initialOrbitMembers.value.find((newMember) => newMember.id === member.id)?.role !==
      member.role,
  ),
)

function onComplete(event: AutoCompleteCompleteEvent) {
  if (!organizationsStore.organizationDetails?.members?.length) return
  searchedMembers.value = organizationsStore.organizationDetails.members.filter((member) => {
    if (orbitMembers.value.find((memberInOrbit) => memberInOrbit.user.id === member.user.id))
      return false
    if (member.user.id === userStore.getUserId) return false

    return (
      member.user.email.toLowerCase().includes(event.query.toLowerCase()) ||
      member.user.full_name.toLowerCase().includes(event.query.toLowerCase())
    )
  })
}

async function addUsers() {
  if (loading.value || !searchModel.value.length) return
  const organizationId = organizationsStore.organizationDetails?.id
  if (!organizationId) return

  const payloads = searchModel.value.map((member) => {
    return {
      role: OrbitRoleEnum.member,
      orbit_id: props.orbitId,
      user_id: member.user.id,
    }
  })

  try {
    loading.value = true
    const results = await Promise.allSettled(
      payloads.map((payload) => orbitsStore.addMemberToOrbit(organizationId, payload)),
    )
    for (const result of results) {
      if (result.status === 'fulfilled') {
        orbitMembers.value.push({ ...result.value })
        initialOrbitMembers.value.push({ ...result.value })
      }
    }
    searchModel.value = searchModel.value.filter(
      (_, index) => results[index]?.status === 'rejected',
    )
    searchedMembers.value = []
    if (results.some((result) => result.status === 'fulfilled')) {
      toast.add(simpleSuccessToast('Members added to orbit'))
    }
    if (searchModel.value.length) {
      toast.add(simpleErrorToast('Failed to add selected members to orbit. Please try again.'))
    }
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to add members to orbit')))
  } finally {
    loading.value = false
  }
}

async function getOrbitDetails() {
  loading.value = true
  try {
    const organizationId = organizationsStore.currentOrganization?.id
    if (!organizationId) throw new Error('Current organization not found')
    const details = await orbitsStore.getOrbitDetails(organizationId, props.orbitId)
    orbitMembers.value = details.members.map((member) => ({ ...member }))
    initialOrbitMembers.value = details.members.map((member) => ({ ...member }))
  } catch {
    toast.add(simpleErrorToast('Failed to load orbit details'))
  } finally {
    loading.value = false
  }
}

function onTrashClick(memberId: string) {
  confirm.require(
    deleteUserConfirmOptions(
      () => deleteMember(memberId),
      'You can add a user to your orbit at any time.',
    ),
  )
}

async function deleteMember(memberId: string) {
  try {
    loading.value = true
    const organizationId = organizationsStore.currentOrganization?.id
    if (!organizationId) throw new Error('Current organization not found')
    await orbitsStore.deleteMember(organizationId, props.orbitId, memberId)
    orbitMembers.value = orbitMembers.value.filter((member) => member.id !== memberId)
    initialOrbitMembers.value = initialOrbitMembers.value.filter((member) => member.id !== memberId)
    toast.add(simpleSuccessToast('The user has been successfully removed.'))
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to delete member')))
  } finally {
    loading.value = false
  }
}

async function saveChanges() {
  try {
    loading.value = true
    const organizationId = organizationsStore.currentOrganization?.id
    if (!organizationId) throw new Error('Current organization not found')
    const requests = changedMembers.value.map((member) =>
      orbitsStore.updateMember(organizationId, props.orbitId, { id: member.id, role: member.role }),
    )
    await Promise.all(requests)
    toast.add(simpleSuccessToast('Changes saved'))
    visible.value = false
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to save changes')))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    getOrbitDetails()
  } else {
    orbitMembers.value = []
    initialOrbitMembers.value = []
    searchModel.value = []
    searchedMembers.value = []
  }
})
</script>

<style scoped>
.text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.form {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.add-button {
  flex-shrink: 0;
  min-height: 46px;
  white-space: nowrap;
}
.footer-buttons {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}
.autocomplete {
  flex: 1 1 auto;
}
.body {
  padding: 28px 0 14px;
}
.placeholder {
  font-size: 20px;
}
.table-wrapper {
  overflow-x: auto;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  padding: 16px;
  width: 100%;
  border-radius: 8px;
}
.table {
  min-width: 450px;
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
  grid-template-columns: 1fr 160px 35px;
  align-items: center;
  gap: 24px;
}
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-user {
  display: flex;
  gap: 8px;
  align-items: center;
}
@media (max-width: 768px) {
  .form {
    flex-direction: column;
    gap: 8px;
  }
  .body {
    padding: 16px 0 8px;
  }
  .placeholder {
    font-size: 16px;
  }
}
</style>
