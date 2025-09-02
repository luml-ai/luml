<template>
  <Form id="bucketForm" v-slot="$form" :initialValues="initialValues" :resolver="resolver" @submit="onSubmit">
    <div class="inputs">
      <div class="field">
        <label for="endpoint" :class="{
          'label required': !update,
          'label--medium': update,
          }">Endpoint</label>
        <InputText
          v-model="initialValues.endpoint"
          id="endpoint"
          name="endpoint"
          type="text"
          placeholder="e.g. s3.amazonaws.com"
          fluid
        />
        <div v-if="($form as any).endpoint?.invalid" class="message">Please enter a valid endpoint URL</div>
      </div>
      <div class="field">
        <label for="bucket_name" :class="{
          'label required': !update,
          'label--medium': update,
          }">Bucket name</label>
        <InputText
          v-model="initialValues.bucket_name"
          id="bucket_name"
          name="bucket_name"
          type="text"
          placeholder="e.g. dataforce-storage"
          fluid
        />
        <div v-if="($form as any).bucket_name?.invalid" class="message">Please enter a name for the bucket</div>
      </div>
      <div class="field">
        <label for="access_key" :class="{
          'label required': !update,
          'label--medium': update,
          }">Access key</label>
        <InputText
          v-model="initialValues.access_key"
          id="access_key"
          name="access_key"
          type="text"
          placeholder="Enter access key"
          fluid
        />
      </div>
      <div class="field">
        <label for="secret_key" :class="{
          'label required': !update,
          'label--medium': update,
          }">Secret key</label>
        <InputText
          v-model="initialValues.secret_key"
          id="secret_key"
          name="secret_key"
          type="text"
          placeholder="Enter secret key"
          fluid
        />
      </div>
      <div class="field">
        <label for="region" :class="{
          'label': !update,
          'label--medium': update,
          }">Region</label>
        <InputText
          v-model="initialValues.region"
          id="region"
          name="region"
          type="text"
          placeholder="e.g. us-west-2"
          fluid
        />
      </div>
    </div>

    <div class="field field--protocol">
      <label :class="{
        'label': !update,
        'label--medium': update,
        }">Secure (http/https)</label>
      <ToggleSwitch v-model="initialValues.secure" name="secure" />
    </div>

    <Button v-if="showSubmitButton" type="submit" fluid rounded :loading="loading">Create</Button>
  </Form>
</template>

<script setup lang="ts">
import type { BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { ref, watch, withDefaults } from 'vue'
import { z } from 'zod'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { Button, InputText, ToggleSwitch } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'

type Props = {
  initialData?: BucketSecretCreator
  loading: boolean
  showSubmitButton?: boolean
  update?: boolean
}

type Emits = {
  submit: [BucketSecretCreator]
}

const props = withDefaults(defineProps<Props>(), {
  showSubmitButton: true
})
const emits = defineEmits<Emits>()

const initialValues = ref<BucketSecretCreator>({
  endpoint: props.initialData?.endpoint || '',
  bucket_name: props.initialData?.bucket_name || '',
  access_key: props.initialData?.access_key || '',
  secret_key: props.initialData?.secret_key || '',
  session_token: props.initialData?.session_token || '',
  secure: props.initialData?.secure ?? true,
  region: props.initialData?.region || '',
})

watch(() => props.initialData, (data) => {
  if (data) {
    initialValues.value.endpoint = data.endpoint || ''
    initialValues.value.bucket_name = data.bucket_name || ''
    initialValues.value.access_key = data.access_key || ''
    initialValues.value.secret_key = data.secret_key || ''
    initialValues.value.session_token = data.session_token || ''
    initialValues.value.secure = data.secure ?? true
    initialValues.value.region = data.region || ''
  }
})

const resolver = zodResolver(
  z.object({
    endpoint: z.string().min(1),
    bucket_name: z.string().min(1),
    access_key: z.string(),
    secret_key: z.string(),
    session_token: z.string(),
    region: z.string(),
  }),
)

function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return

  emits('submit', { ...initialValues.value })
}

</script>

<style scoped>
.inputs {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  gap: 12px;
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
.label--medium {
  font-weight: 500;
}
</style>
