<template>
  <Button severity="secondary" variant="text" @click="visible = true">
    <template #icon>
      <Bolt :size="14" />
    </template>
  </Button>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="popup-title">
        <UserCog :size="20" class="popup-title-icon" />
        <span>user settings</span>
      </h2>
    </template>
    <div class="dialog-content">
      <div class="user-info">
        <Avatar
          :label="member.user.photo ? undefined : member.user.full_name[0]"
          shape="circle"
          size="xlarge"
          :image="member.user.photo"
        />
        <div>
          <div class="user-name">{{ member.user.full_name }}</div>
          <div class="user-email">{{ member.user.email }}</div>
        </div>
      </div>
      <Form id="editOrganizationForm" :initialValues :resolver @submit="onFormSubmit" class="body">
        <label for="role" class="label">Role</label>
        <Select
          :options="OPTIONS"
          option-label="label"
          option-value="value"
          name="role"
          id="role"
          fluid
        ></Select>
      </Form>
    </div>
    <template #footer>
      <Button severity="warn" variant="outlined" :disabled="loading" @click="onDelete">
        delete user
      </Button>
      <Button type="submit" :disabled="loading" form="editOrganizationForm">save changes</Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { Member } from '@/lib/api/api.interfaces'
import { ref, watch } from 'vue'
import { Button, Dialog, Avatar, Select, useConfirm, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { useOrganizationStore } from '@/stores/organization'
import { Bolt, UserCog } from 'lucide-vue-next'
import { OrganizationRoleEnum } from './organization.interfaces'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { removeOrganizationUserConfirmOptions } from '@/lib/primevue/data/confirm'

const OPTIONS = [
  {
    label: 'Admin',
    value: OrganizationRoleEnum.admin,
  },
  {
    label: 'Member',
    value: OrganizationRoleEnum.member,
  },
]

const dialogPT = {
  footer: {
    class: 'organization-edit-footer',
  },
}

type Props = {
  member: Member
}

const props = defineProps<Props>()

const organizationStore = useOrganizationStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)
const initialValues = ref({
  role: props.member.role,
})
const resolver = zodResolver(
  z.object({
    role: z.string().min(1),
  }),
)

async function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    visible.value = false
    loading.value = true
    await organizationStore.updateMember(props.member.organization_id, props.member.id, {
      role: values.role,
    })
    toast.add(simpleSuccessToast('User role has been updated.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to update user'))
  } finally {
    loading.value = false
  }
}
function onDelete() {
  confirm.require(removeOrganizationUserConfirmOptions(deleteUser))
}
async function deleteUser() {
  try {
    visible.value = false
    loading.value = true
    await organizationStore.deleteMember(props.member.organization_id, props.member.id)
    toast.add(simpleSuccessToast('The user has been successfully removed.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to delete member'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.member.role,
  (role) => {
    initialValues.value.role = role
  },
)
</script>

<style scoped>
.info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.popup-title {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 16px;
  text-transform: uppercase;
  font-weight: 500;
}
.popup-title-icon {
  color: var(--p-primary-500);
}
.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
}
.user-name {
  margin-bottom: 4px;
}
.user-email {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.body {
  margin-bottom: 20px;
}
.label {
  display: inline-block;
  margin-bottom: 8px;
  font-weight: 500;
}
</style>
