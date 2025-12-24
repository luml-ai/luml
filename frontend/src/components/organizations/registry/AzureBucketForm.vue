<template>
  <Form
    id="bucketForm"
    v-slot="$form"
    :initialValues="initialValues"
    :resolver="resolver"
    @submit="onSubmit"
    class="form"
  >
    <div class="inputs">
      <div class="field">
        <label for="bucket_name" class="label required">Container name</label>
        <InputText
          v-model="initialValues.bucket_name"
          id="bucket_name"
          name="bucket_name"
          type="text"
          placeholder="Enter container name"
          fluid
        />
        <div v-if="($form as any).bucket_name?.invalid" class="message">
          Please enter a valid container name
        </div>
      </div>
      <div class="field">
        <label for="endpoint" class="label required">Connection string</label>
        <InputText
          v-model="initialValues.endpoint"
          id="endpoint"
          name="endpoint"
          type="text"
          placeholder="Enter connection string"
          fluid
        />
        <div v-if="($form as any).endpoint?.invalid" class="message">
          Please enter a valid connection string
        </div>
      </div>
    </div>

    <Button v-if="showSubmitButton" type="submit" fluid rounded :loading="loading">Create</Button>
  </Form>
</template>

<script setup lang="ts">
import { BucketTypeEnum, type AzureBucketFormData } from '@/lib/api/bucket-secrets/interfaces'
import { ref, watch, computed } from 'vue'
import { z } from 'zod'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { Button, InputText } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'

type Props = {
  initialData?: AzureBucketFormData
  loading: boolean
  showSubmitButton?: boolean
  update?: boolean
}

type Emits = {
  submit: [AzureBucketFormData]
}

const props = withDefaults(defineProps<Props>(), {
  showSubmitButton: true,
})
const emits = defineEmits<Emits>()

const initialValues = ref<AzureBucketFormData>({
  type: BucketTypeEnum.azure,
  endpoint: props.initialData?.endpoint || '',
  bucket_name: props.initialData?.bucket_name || '',
})

watch(
  () => props.initialData,
  (data) => {
    if (data) {
      initialValues.value.endpoint = data.endpoint || ''
      initialValues.value.bucket_name = data.bucket_name || ''
    }
  },
)

const createBucketResolver = zodResolver(
  z.object({
    endpoint: z.string().min(1),
    bucket_name: z.string().min(1),
  }),
)

const updateBucketResolver = zodResolver(
  z.object({
    endpoint: z.string().optional(),
    bucket_name: z.string().optional(),
  }),
)

const resolver = computed(() => (props.update ? updateBucketResolver : createBucketResolver))

function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return

  if (props.update) {
    const formData: AzureBucketFormData = {
      type: BucketTypeEnum.azure,
      endpoint: initialValues.value.endpoint || props.initialData?.endpoint || '',
      bucket_name: initialValues.value.bucket_name || props.initialData?.bucket_name || '',
    }

    emits('submit', formData)
  } else {
    emits('submit', { ...initialValues.value })
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
}
.inputs {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  gap: 12px;
  flex: 1 1 auto;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.label {
  align-self: flex-start;
  font-size: 14px;
  line-height: 1.5;
  display: flex;
  align-items: center;
  gap: 8px;
}
.field--protocol {
  flex-direction: row;
  gap: 12px;
  margin-bottom: 28px;
}
.message {
  font-size: 12px;
  line-height: 1.75;
}
@media (max-width: 768px) {
  .tooltip-icon {
    display: none;
  }
}
</style>
