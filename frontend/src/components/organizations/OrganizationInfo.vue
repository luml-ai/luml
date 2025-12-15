<template>
  <div class="info">
    <Avatar size="large" :label="avatarLabel" class="avatar" />
    <div class="name">{{ organizationStore.currentOrganization?.name }}</div>
    <Button severity="secondary" variant="text" @click="visible = true" class="edit-button">
      <template #icon>
        <PenLine :size="14" />
      </template>
    </Button>
    <div class="id-row" v-if="organizationStore.currentOrganization?.id">
      <UiId :id="organizationStore.currentOrganization.id" variant="button"></UiId>
    </div>
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
          <span>Organization settings</span>
        </h2>
      </template>
      <div class="dialog-content">
        <!--<ImageInput
          shape="square"
          :image="organizationStore.currentOrganization?.logo"
          class="photo"
          @on-image-change="onImageChange"
        />-->
        <Avatar size="xlarge" :label="avatarLabel" />
        <Form
          id="editOrganizationForm"
          :initialValues
          :resolver
          @submit="onFormSubmit"
          class="body"
        >
          <label for="name" class="label">Name</label>
          <InputText v-model="initialValues.name" name="name" id="name" class="input" />
        </Form>
      </div>
      <template #footer>
        <OrganizationDelete></OrganizationDelete>
        <Button type="submit" form="editOrganizationForm">save changes</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { computed, onMounted, ref, watch } from 'vue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { Form } from '@primevue/forms'
import { PenLine, UserCog } from 'lucide-vue-next'
import { useOrganizationStore } from '@/stores/organization'
import { Avatar, Button, Dialog, useToast, InputText } from 'primevue'
import ImageInput from '../ui/ImageInput.vue'
import OrganizationDelete from './OrganizationDelete.vue'
import UiId from '../ui/UiId.vue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const organizationStore = useOrganizationStore()
const toast = useToast()

const dialogPT = {
  footer: {
    class: 'organization-edit-footer',
  },
}

const resolver = zodResolver(
  z.object({
    name: z.string().min(3),
  }),
)

const initialValues = ref({
  name: '',
})
const visible = ref(false)
const logo = ref<File | null>(null)
const loading = ref(false)

const avatarLabel = computed(() => {
  return organizationStore.currentOrganization?.name.charAt(0).toUpperCase()
})

function onImageChange(event: File | null) {
  logo.value = event
}

async function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  const payload = {
    logo: 'https://framerusercontent.com/images/Ks0qcMuaRUt9YEMHOZIkAAXLwl0.png',
    name: values.name,
  }
  try {
    loading.value = true
    if (!organizationStore.currentOrganization) throw new Error('Current organization not found')
    await organizationStore.updateOrganization(organizationStore.currentOrganization.id, payload)
    toast.add(simpleSuccessToast('All changes have been saved.'))
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e.message || 'Could not create organization'))
  } finally {
    loading.value = false
  }
}

function setOrganizationData() {
  initialValues.value.name = organizationStore.currentOrganization?.name || ''
}

watch(
  () => organizationStore.currentOrganization,
  () => setOrganizationData(),
)

onMounted(() => {
  setOrganizationData()
})
</script>

<style scoped>
.info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar {
  flex: 0 0 auto;
}
.edit-button {
  flex: 0 0 auto;
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
.name {
  font-size: 24px;
  font-weight: 500;
  line-height: 1.25;
}
.id-row {
  margin-left: auto;
}

.body {
  padding-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
}
@media (max-width: 768px) {
  .name {
    font-size: 16px;
  }
}
</style>

<style>
:global(.organization-edit-footer) {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-top: auto;
}
</style>
