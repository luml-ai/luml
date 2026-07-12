<template>
  <UiDialogRight
    v-model:visible="visible"
    :icon="Orbit"
    title="Orbit settings"
    :footer-actions="footerActions"
  >
    <Form
      id="orbit-edit-form"
      :initial-values="initialValues"
      :resolver
      class="form"
      @submit="saveChanges"
    >
      <div class="form-item">
        <label for="name" class="label">Name</label>
        <InputText name="name" id="name" />
      </div>
      <div class="form-item">
        <label for="bucket" class="label">Bucket</label>
        <Select
          v-model="initialValues.bucket_secret_id"
          disabled
          :options="bucketsStore.buckets"
          option-label="bucket_name"
          option-value="id"
          name="bucket_secret_id"
          id="bucket"
        ></Select>
        <p class="message">
          Please contact <a href="mailto:contact@dataforce.solutions" class="link">Support</a> to
          change the bucket
        </p>
      </div>
    </Form>
  </UiDialogRight>
</template>

<script setup lang="ts">
import {
  PermissionEnum,
  type Orbit as OrbitType,
  type UpdateOrbitPayload,
} from '@/lib/api/api.interfaces'
import { computed, ref, watch } from 'vue'
import { InputText, Select, useToast, useConfirm } from 'primevue'
import { Orbit } from 'lucide-vue-next'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { useBucketsStore } from '@/stores/buckets'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteOrbitConfirmOptions } from '@/lib/primevue/data/confirm'
import type { FooterActions, FooterButton } from '@/components/ui/dialogs/UiDialogRight.vue'
import UiDialogRight from '@/components/ui/dialogs/UiDialogRight.vue'

const resolver = zodResolver(
  z.object({
    name: z.string().min(1).max(100),
    bucket_secret_id: z.string(),
  }),
)

type Props = {
  orbit: OrbitType
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')

const bucketsStore = useBucketsStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const confirm = useConfirm()

const initialValues = computed(() => ({
  name: props.orbit.name,
  bucket_secret_id: props.orbit.bucket_secret_id,
}))

const leftButton = computed<FooterButton | undefined>(() => {
  if (props.orbit.permissions.orbit.includes(PermissionEnum.delete)) {
    return {
      props: {
        label: 'Delete Orbit',
        severity: 'warn',
        variant: 'outlined',
        loading: loading.value,
        onClick: onDeleteClick,
      },
    }
  }
  return undefined
})

const footerActions = computed<FooterActions>(() => {
  return {
    leftButton: leftButton.value,
    rightButton: {
      props: {
        label: 'Save changes',
        type: 'submit',
        form: 'orbit-edit-form',
        loading: loading.value,
      },
    },
  }
})

const loading = ref(false)

type FormValues = {
  name: string
  bucket_secret_id: string
}

async function saveChanges({ valid, values }: FormSubmitEvent) {
  if (!valid) return
  const formValues = values as FormValues
  try {
    loading.value = true
    const payload: UpdateOrbitPayload = {
      id: props.orbit.id,
      name: formValues.name,
      bucket_secret_id: formValues.bucket_secret_id,
    }
    await orbitsStore.updateOrbit(props.orbit.organization_id, payload)
    toast.add(simpleSuccessToast('Orbit info successfully updated'))
    visible.value = false
  } catch {
    toast.add(simpleErrorToast('Failed to update orbit'))
  } finally {
    loading.value = false
  }
}

function onDeleteClick() {
  confirm.require(deleteOrbitConfirmOptions(deleteOrbit))
}

async function deleteOrbit() {
  try {
    loading.value = true
    await orbitsStore.deleteOrbit(props.orbit.organization_id, props.orbit.id)
    toast.add(simpleSuccessToast('Orbit successfully deleted'))
    visible.value = false
  } catch {
    toast.add(simpleErrorToast('Failed to delete orbit'))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  if (val) bucketsStore.getBuckets(props.orbit.organization_id)
})
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
.message {
  font-size: 12px;
}
</style>
