<template>
  <Button @click="visible = true">
    <span>Invite member</span>
    <Plus :size="14" />
  </Button>
  <Dialog
    v-model:visible="visible"
    modal
    header="Invite member"
    :draggable="false"
    style="width: 604px"
    :pt="dialogPT"
  >
    <div class="dialog-content">
      <p class="dialog-text">Organization collaborators have access to specific orbits.</p>
      <div class="body">
        <h3 class="body-title">Email invite</h3>
        <p class="body-description">
          Enter the email and role to invite a new member to your organization.
        </p>
        <Form id="createInviteForm" :initialValues :resolver @submit="onFormSubmit" class="form">
          <InputText name="email" placeholder="Email" class="form-input" />
          <Select
            :options="OPTIONS"
            option-label="label"
            option-value="value"
            name="role"
            class="form-select"
          ></Select>
        </Form>
      </div>
    </div>
    <template #footer>
      <Button type="submit" :disabled="loading" :loading="loading" form="createInviteForm"
        >Invite</Button
      >
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, Dialog, InputText, Select, useToast } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { z } from 'zod'
import { OrganizationRoleEnum } from './organization.interfaces'
import { useInvitationsStore } from '@/stores/invitations'
import { useOrganizationStore } from '@/stores/organization'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const INITIAL_DATA = { email: '', role: OrganizationRoleEnum.admin }

const dialogPT = {
  root: {
    style: 'padding: 18px;',
  },
  header: {
    style: 'font-size: 20px; font-weight: 600; text-transform: uppercase; padding-bottom: 12px;',
  },
}

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

const invitationsStore = useInvitationsStore()
const organizationStore = useOrganizationStore()
const toast = useToast()

const initialValues = ref({ ...INITIAL_DATA })

const resolver = zodResolver(
  z.object({
    email: z.string().email(),
    role: z.string().min(1),
  }),
)

const visible = ref(false)
const loading = ref(false)

async function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  loading.value = true
  try {
    const payload = getPayload(values as any)
    const invite = await invitationsStore.createInvite(payload)
    organizationStore.addInviteToCurrentOrganization(invite)
    visible.value = false
    toast.add(simpleSuccessToast('An email invitation was sent to the user.'))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create invite'))
  } finally {
    loading.value = false
  }
}

function getPayload(values: { email: string; role: OrganizationRoleEnum }) {
  if (!organizationStore.currentOrganization) throw new Error('Current organization not found')
  return {
    email: values.email,
    role: values.role,
    organization_id: organizationStore.currentOrganization.id,
  }
}
</script>

<style scoped>
.dialog-text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.body {
  padding: 16px 12px;
  background: var(--p-content-background);
  border-radius: 4px;
}
.body-title {
  font-weight: 500;
  margin-bottom: 4px;
  font-size: 16px;
}
.body-description {
  font-size: 14px;
  color: var(--p-text-muted-color);
  margin-bottom: 16px;
}
.form {
  display: flex;
  gap: 13px;
}
.form-input {
  flex: 1 1 auto;
}
.form-select {
  flex: 0 0 160px;
}
@media (max-width: 768px) {
  .form {
    flex-direction: column;
  }
  .form-select {
    flex: 0 0 auto;
  }
}
</style>
