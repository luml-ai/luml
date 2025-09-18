<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="dialog-title">
        <Orbit :size="20" color="var(--p-primary-color)" />
        <span>orbit settings</span>
      </h2>
    </template>
    <Form id="orbit-edit-form" :initialValues :resolver class="form" @submit="saveChanges">
      <div class="form-item">
        <label for="name" class="label">Name</label>
        <InputText v-model="initialValues.name" name="name" id="name" />
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
    <template #footer>
      <div>
        <Button
          v-if="orbit.permissions.orbit.includes(PermissionEnum.delete)"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          delete Orbit
        </Button>
      </div>
      <Button type="submit" :loading="loading" form="orbit-edit-form"> save changes </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import {
  PermissionEnum,
  type Orbit as OrbitType,
  type UpdateOrbitPayload,
} from '@/lib/api/DataforceApi.interfaces'
import { ref, watch } from 'vue'
import {
  Dialog,
  Button,
  InputText,
  Select,
  type DialogPassThroughOptions,
  useToast,
  useConfirm,
} from 'primevue'
import { Orbit } from 'lucide-vue-next'
import { Form } from '@primevue/forms'
import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { useBucketsStore } from '@/stores/buckets'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteOrbitConfirmOptions } from '@/lib/primevue/data/confirm'

const dialogPT: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

const resolver = zodResolver(
  z.object({
    name: z.string().min(1),
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

const initialValues = ref({
  name: props.orbit.name,
  bucket_secret_id: props.orbit.bucket_secret_id,
})
const loading = ref(false)

async function saveChanges() {
  try {
    loading.value = true
    const payload: UpdateOrbitPayload = {
      id: props.orbit.id,
      name: initialValues.value.name,
      bucket_secret_id: initialValues.value.bucket_secret_id,
    }
    await orbitsStore.updateOrbit(props.orbit.organization_id, payload)
    toast.add(simpleSuccessToast('Orbit info successfully updated'))
    visible.value = false
  } catch (e) {
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
  } catch (e) {
    toast.add(simpleErrorToast('Failed to delete orbit'))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  val && bucketsStore.getBuckets(props.orbit.organization_id)
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
