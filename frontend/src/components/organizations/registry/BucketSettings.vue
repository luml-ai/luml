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
        <Bolt :size="20" class="popup-title-icon" />
        <span>bucket settings</span>
      </h2>
    </template>
    <div class="dialog-content">
      <div class="bucket-form-wrapper">
        <BucketForm
          :initial-data="initialData"
          :loading="loading"
          :show-submit-button="false"
          update
          @submit="onFormSubmit"
        />
      </div>
    </div>
    <template #footer>
      <Button severity="warn" variant="outlined" :disabled="loading" @click="onDelete">
        delete bucket
      </Button>
      <Button type="submit" :disabled="loading" form="bucketForm">save changes</Button>
    </template>
  </Dialog>
</template>
<script setup lang="ts">
import type { BucketSecret, BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { computed, ref } from 'vue'
import { Button, Dialog, useConfirm, useToast } from 'primevue'
import { BucketValidationError, useBucketsStore } from '@/stores/buckets'
import { Bolt } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteBucketConfirmOptions } from '@/lib/primevue/data/confirm'
import BucketForm from './BucketForm.vue'

const dialogPT = {
  footer: {
    class: 'organization-edit-footer',
  },
}

type Props = {
  bucket: BucketSecret
}

const props = defineProps<Props>()
const bucketsStore = useBucketsStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

const initialData = computed<BucketSecretCreator>(() => ({
  bucket_name: props.bucket.bucket_name,
  endpoint: props.bucket.endpoint,
  region: props.bucket.region,
  secure: props.bucket.secure,
  access_key: '',
  secret_key: '',
}))

async function onFormSubmit(formData: BucketSecretCreator) {
  try {
    loading.value = true
    await bucketsStore.checkExistingBucket(props.bucket.organization_id, props.bucket.id, formData)
    await bucketsStore.updateBucket(props.bucket.organization_id, props.bucket.id, {
      ...formData,
      id: props.bucket.id,
    })

    toast.add(simpleSuccessToast('Bucket has been updated.'))
    visible.value = false
  } catch (err: any) {
    if (err instanceof BucketValidationError) {
      toast.add(simpleErrorToast(err.getMessage()))
    } else {
      toast.add(
        simpleErrorToast(
          err?.response?.data?.detail || err.message || 'Failed to update bucket',
        ),
      )
    }
  } finally {
    loading.value = false
  }
}

function onDelete() {
  confirm.require(deleteBucketConfirmOptions(deleteBucket))
}

async function deleteBucket() {
  try {
    visible.value = false
    loading.value = true
    await bucketsStore.deleteBucket(props.bucket.organization_id, props.bucket.id)
    toast.add(simpleSuccessToast(`Bucket “${props.bucket.bucket_name}” was deleted.`))
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to delete bucket'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
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

.bucket-info {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
}

.bucket-name {
  margin-bottom: 4px;
}

.bucket-endpoint {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
