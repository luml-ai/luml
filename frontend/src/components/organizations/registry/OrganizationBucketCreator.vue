<template>
  <div>
    <Button @click="visible = true">
      <Plus :size="14" />
      <span>Add new bucket</span>
    </Button>
    <Dialog
      v-model:visible="visible"
      modal
      :draggable="false"
      style="max-width: 500px; width: 100%"
      :pt="dialogPT"
    >
      <template #header>
        <h2 class="creator-title">Add a new storage bucket</h2>
      </template>
      <SelectButton
        v-model="selectedBucketType"
        :options="selectButtonOptions"
        option-label="label"
        option-value="value"
        class="select-button"
      ></SelectButton>
      <component
        :is="formComponent"
        @submit="create"
        :loading="loading"
        class="form-component"
      ></component>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { BucketTypeEnum, type BucketFormData } from '@/lib/api/bucket-secrets/interfaces'
import type { DialogPassThroughOptions } from 'primevue'
import { computed, ref } from 'vue'
import { Button, Dialog, useToast, SelectButton } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { BucketValidationError, useBucketsStore } from '@/stores/buckets'
import { useOrganizationStore } from '@/stores/organization'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import AzureBucketForm from './AzureBucketForm.vue'
import S3BucketForm from './S3BucketForm.vue'

const dialogPT: DialogPassThroughOptions = {
  header: {
    style: 'padding: 28px;',
  },
  content: {
    style: 'padding: 0 28px 28px',
  },
}

const selectButtonOptions = [
  {
    label: 'S3 bucket',
    value: BucketTypeEnum.s3,
  },
  {
    label: 'Azure',
    value: BucketTypeEnum.azure,
  },
]

const organizationStore = useOrganizationStore()
const bucketsStore = useBucketsStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)
const selectedBucketType = ref<BucketTypeEnum>(BucketTypeEnum.s3)

const formComponent = computed(() => {
  return selectedBucketType.value === BucketTypeEnum.s3 ? S3BucketForm : AzureBucketForm
})

async function create(data: BucketFormData) {
  const organizationId = organizationStore.currentOrganization?.id
  if (!organizationId) {
    toast.add(simpleErrorToast('Current organization not found'))
    return
  }
  try {
    loading.value = true
    await bucketsStore.checkBucket(data)
    await bucketsStore.createBucket(organizationId, data)
    visible.value = false
    toast.add(simpleSuccessToast('New bucket has been added.'))
  } catch (e: any) {
    if (e instanceof BucketValidationError) {
      toast.add(simpleErrorToast(e.getMessage()))
    } else {
      toast.add(
        simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create bucket'),
      )
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.creator-title {
  font-size: 20px;
  font-weight: 600;
  text-transform: uppercase;
}

.select-button {
  margin-bottom: 12px;
}
</style>
