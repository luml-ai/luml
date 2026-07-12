<template>
  <Button severity="secondary" variant="text" @click="visible = true">
    <template #icon>
      <Bolt :size="14" />
    </template>
  </Button>
  <UiDialogRight
    v-model:visible="visible"
    :icon="Bolt"
    title="bucket settings"
    position="topright"
    :footer-actions="footerActions"
  >
    <div class="dialog-content">
      <div class="bucket-form-wrapper">
        <S3BucketForm
          v-if="initialData.type === BucketTypeEnum.s3"
          :initial-data="initialData as S3BucketFormData"
          :loading="loading"
          :show-submit-button="false"
          update
          @submit="onFormSubmit"
        />
        <AzureBucketForm
          v-else
          :initial-data="initialData as AzureBucketFormData"
          :loading="loading"
          :show-submit-button="false"
          update
          @submit="onFormSubmit"
        />
      </div>
      <ConnectedOrbitsList v-if="props.bucket.orbits?.length" :orbits="props.bucket.orbits" />
    </div>
  </UiDialogRight>
</template>
<script setup lang="ts">
import {
  BucketTypeEnum,
  type AzureBucketFormData,
  type BucketSecret,
  type BucketFormData,
  type S3BucketFormData,
} from '@/lib/api/bucket-secrets/interfaces'
import { computed, ref } from 'vue'
import { Button, useConfirm, useToast } from 'primevue'
import { BucketValidationError, useBucketsStore } from '@/stores/buckets'
import { Bolt } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteBucketConfirmOptions } from '@/lib/primevue/data/confirm'
import { getErrorMessage } from '@/helpers/helpers'
import S3BucketForm from './S3BucketForm.vue'
import AzureBucketForm from './AzureBucketForm.vue'
import ConnectedOrbitsList from './connected-orbits/ConnectedOrbitsList.vue'
import UiDialogRight, { type FooterActions } from '@/components/ui/dialogs/UiDialogRight.vue'

type Props = {
  bucket: BucketSecret
}

const props = defineProps<Props>()
const bucketsStore = useBucketsStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

const footerActions = computed<FooterActions>(() => {
  return {
    leftButton: {
      props: {
        label: 'Delete bucket',
        severity: 'warn',
        variant: 'outlined',
        disabled: loading.value,
        onClick: onDelete,
      },
    },
    rightButton: {
      props: {
        label: 'Save changes',
        type: 'submit',
        form: 'bucketForm',
        loading: loading.value,
      },
    },
  }
})

const initialData = computed<BucketFormData>(() => {
  switch (props.bucket.type) {
    case BucketTypeEnum.s3:
      return {
        type: BucketTypeEnum.s3,
        bucket_name: props.bucket.bucket_name,
        endpoint: props.bucket.endpoint,
        region: props.bucket.region,
        secure: props.bucket.secure,
        access_key: '',
        secret_key: '',
      }
    case BucketTypeEnum.azure:
      return {
        type: BucketTypeEnum.azure,
        bucket_name: props.bucket.bucket_name,
        endpoint: props.bucket.endpoint,
      }
    default:
      throw new Error(`Invalid bucket type: ${props.bucket?.type}`)
  }
})

async function onFormSubmit(formData: BucketFormData) {
  try {
    loading.value = true
    await bucketsStore.checkExistingBucket(props.bucket.organization_id, props.bucket.id, formData)
    await bucketsStore.updateBucket(props.bucket.organization_id, props.bucket.id, {
      ...formData,
      id: props.bucket.id,
    })

    toast.add(simpleSuccessToast('Bucket has been updated.'))
    visible.value = false
  } catch (err: unknown) {
    if (err instanceof BucketValidationError) {
      toast.add(simpleErrorToast(err.getMessage()))
    } else {
      toast.add(simpleErrorToast(getErrorMessage(err, 'Failed to update bucket')))
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
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to delete bucket')))
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
