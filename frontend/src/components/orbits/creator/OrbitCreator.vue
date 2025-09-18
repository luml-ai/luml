<template>
  <Dialog
    v-model:visible="visible"
    header="CREATE A NEW ORBIT"
    modal
    :draggable="false"
    :pt="dialogPt"
  >
    <Form
      :initial-values="initialValues"
      :resolver="resolver"
      :validate-on-value-update="false"
      @submit="onSubmit"
    >
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Orbit name </label>
          <InputText
            v-model="initialValues.name"
            id="name"
            name="name"
            placeholder="e.g. Data Science Core, Growth Experiments"
            fluid
          />
        </div>

        <div class="field">
          <label for="members" class="label">Members</label>
          <MultiSelect
            v-model="membersModel"
            :options="membersList"
            option-label="full_name"
            display="chip"
            filter
            id="members"
            placeholder="Select members to add to this Orbit"
            fluid
            :pt="multiSelectPt"
          />
        </div>

        <div v-if="membersModel.length" class="field">
          <label class="label">Assign roles</label>
          <div class="members">
            <div v-for="member in initialValues.members" :key="member.user_id" class="member">
              <div class="member-name">{{ getMemberFullName(member.user_id) }}</div>
              <Select v-model="member.role" :options="memberRoleOptions" size="small"></Select>
            </div>
          </div>
        </div>

        <div class="field">
          <label for="bucket" class="label">Bucket</label>
          <Select
            v-model="initialValues.bucket_secret_id"
            name="bucket_secret_id"
            :options="bucketsStore.buckets"
            option-label="bucket_name"
            option-value="id"
            filter
            id="bucket"
            placeholder="Select a storage bucket for this Orbit"
            fluid
            :pt="multiSelectPt"
          >
            <template #footer>
              <div v-if="!bucketsStore.buckets.length" class="select-footer">
                <d-button variant="text" as-child v-slot="slotProps" size="small">
                  <RouterLink
                    :to="{
                      name: 'organization-buckets',
                      params: { id: +route.params.organizationId },
                    }"
                    :class="slotProps.class"
                  >
                    <Plus :size="14" />
                    <span>Create new bucket</span>
                  </RouterLink>
                </d-button>
              </div>
            </template>
          </Select>
        </div>
      </div>

      <div class="checkbox">
        <Checkbox v-model="initialValues.notify" inputId="notify" binary />
        <label for="notify" class="checkbox-label"> Notify added members by email </label>
      </div>

      <Button type="submit" fluid rounded :loading="loading">Create</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { CreateOrbitPayload, IGetUserResponse } from '@/lib/api/DataforceApi.interfaces'
import type { DialogPassThroughOptions, MultiSelectPassThroughOptions } from 'primevue'
import { Dialog, Button, InputText, Checkbox, MultiSelect, Select, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { computed, ref, watch } from 'vue'
import { useOrganizationStore } from '@/stores/organization'
import { OrbitRoleEnum } from '../orbits.interfaces'
import { useBucketsStore } from '@/stores/buckets'
import { Plus } from 'lucide-vue-next'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useUserStore } from '@/stores/user'
import { orbitCreatorResolver } from '@/utils/forms/resolvers'
import { useRoute } from 'vue-router'

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const multiSelectPt: MultiSelectPassThroughOptions = {
  pcFilter: {
    root: {
      class: 'p-inputtext-sm p-inputfield-sm',
    },
  },
  overlay: {
    style: 'max-width: 442px; overflow: hidden;',
  },
  optionLabel: {
    style: 'overflow: hidden; text-overflow: ellipsis;',
  },
}

const memberRoleOptions = [OrbitRoleEnum.admin, OrbitRoleEnum.member]

const organizationStore = useOrganizationStore()
const bucketsStore = useBucketsStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const userStore = useUserStore()
const route = useRoute()

const membersList = computed(() => {
  if (!organizationStore.organizationDetails) return []
  return organizationStore.organizationDetails.members
    .map((member) => member.user)
    .filter((user) => user.id !== userStore.getUserId)
})

const visible = defineModel<boolean>('visible')

const resolver = orbitCreatorResolver(orbitsStore.orbitsList)

const initialValues = ref<Partial<CreateOrbitPayload>>({
  name: '',
  members: [],
  bucket_secret_id: undefined,
  notify: true,
})
const loading = ref(false)
const membersModel = ref<Omit<IGetUserResponse, 'auth_method'>[]>([])

const getMemberFullName = computed(() => (userId: number) => {
  return membersList.value.find((member) => +member.id === userId)?.full_name || ''
})

watch(
  membersModel,
  (members) => {
    initialValues.value.members = members.map((member) => {
      const includedMember = initialValues.value.members?.find((m) => m.user_id === +member.id)
      return includedMember || { user_id: +member.id, role: OrbitRoleEnum.member }
    })
  },
  { deep: true },
)

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    loading.value = true
    const payload = initialValues.value as CreateOrbitPayload
    await orbitsStore.createOrbit(+route.params.organizationId, payload)
    toast.add(simpleSuccessToast('Orbit created'))
    loading.value = true
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create orbit'))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  val && bucketsStore.getBuckets(+route.params.organizationId)
})
</script>

<style scoped>
.inputs {
  margin-bottom: 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.checkbox {
  margin-bottom: 28px;
}
.checkbox-label {
  font-size: 14px;
}
.members {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.member {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
  align-items: center;
}
.member-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.select-footer {
  padding: 4px 12px;
  border-top: 1px solid var(--p-divider-border-color);
}
</style>
