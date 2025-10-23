<template>
  <Dialog v-model:visible="visible" :pt="dialogPt" modal :draggable="false">
    <template #header>
      <h3>Create deployment</h3>
      <div class="buttons">
        <Button
          form="createDeploymentForm"
          label="Deploy"
          :disabled="!isFormValid"
          :loading="loading"
          type="submit"
        ></Button>
        <Button label="Cancel" severity="secondary" @click="onCancel"></Button>
      </div>
    </template>
    <template #default>
      <Form
        v-if="visible"
        ref="formRef"
        id="createDeploymentForm"
        class="content"
        :initial-values="initialValues"
        :resolver="createDeploymentResolver"
        @submit="onSubmit"
      >
        <DeploymentsFormBasicsSettings
          v-model:description="initialValues.description"
          v-model:name="initialValues.name"
          v-model:tags="initialValues.tags"
        ></DeploymentsFormBasicsSettings>
        <DeploymentsFormModelSettings
          :initial-collection-id="initialCollectionId"
          :initial-model-id="initialModelId"
          v-model:collection-id="initialValues.collectionId"
          v-model:model-id="initialValues.modelId"
          v-model:secret-dynamic-attributes="initialValues.secretDynamicAttributes"
          v-model:dynamic-attributes="initialValues.dynamicAttributes"
          v-model:secret-envs="initialValues.secretEnvs"
          v-model:not-secret-envs="initialValues.notSecretEnvs"
          v-model:custom-variables="initialValues.customVariables"
        ></DeploymentsFormModelSettings>
        <DeploymentsFormSatelliteSettings
          v-model:satellite-id="initialValues.satelliteId"
          v-model:fields="initialValues.satelliteFields"
        ></DeploymentsFormSatelliteSettings>
      </Form>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { CreateDeploymentForm, FieldInfo } from '../deployments.interfaces'
import type { CreateDeploymentPayload } from '@/lib/api/deployments/interfaces'
import type { FormSubmitEvent } from '@primevue/forms'
import { Dialog, Button, useToast } from 'primevue'
import { Form } from '@primevue/forms'
import { dialogPt, getInitialFormData } from '../deployments.const'
import { computed, onMounted, ref, watch } from 'vue'
import { createDeploymentResolver } from '@/utils/forms/resolvers'
import { getErrorMessage, getNumberOrString } from '@/helpers/helpers'
import { useCollectionsStore } from '@/stores/collections'
import { useDeploymentsStore } from '@/stores/deployments'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue'
import DeploymentsFormModelSettings from '../form/DeploymentsFormModelSettings.vue'
import DeploymentsFormSatelliteSettings from '../form/DeploymentsFormSatelliteSettings.vue'

type Props = {
  initialCollectionId?: string
  initialModelId?: string
}

const props = defineProps<Props>()

const collectionsStore = useCollectionsStore()
const deploymentsStore = useDeploymentsStore()
const toast = useToast()

const visible = defineModel<boolean>('visible')

const formRef = ref<any>()
const loading = ref(false)

const initialValues = ref(getInitialFormData(props.initialCollectionId, props.initialModelId))

const isFormValid = computed(() => formRef.value?.valid)

function onCancel() {
  visible.value = false
}

function resetForm() {
  initialValues.value = getInitialFormData()
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  const formData = initialValues.value as any as CreateDeploymentForm
  const payload = getPayload(formData)
  try {
    loading.value = true
    await deploymentsStore.createDeployment(
      collectionsStore.requestInfo.organizationId,
      collectionsStore.requestInfo.orbitId,
      payload,
    )
    visible.value = false
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `Deployment ${payload.name} was successfully created.<br><a href="#" class="toast-action-link" data-route="orbit-deployments" data-params="{}">Go to Deployments</a>`,
      life: 5000,
    })
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to create deployment')))
  } finally {
    loading.value = false
  }
}

function getPayload(form: CreateDeploymentForm): CreateDeploymentPayload {
  return {
    name: form.name,
    description: form.description,
    satellite_id: form.satelliteId,
    model_artifact_id: form.modelId,
    satellite_parameters: fieldsToRecord(form.satelliteFields, getNumberOrString),
    dynamic_attributes_secrets: fieldsToRecord(
      form.secretDynamicAttributes,
      (v) => v,
    ) as unknown as Record<string, string>,
    env_variables_secrets: fieldsToRecord<string>(form.secretEnvs, (v) => String(v)),
    env_variables: fieldsToRecord(form.notSecretEnvs, getNumberOrString),
    tags: form.tags,
  }
}

function fieldsToRecord<T extends string | number>(
  fields: FieldInfo<T>[],
  transform: (value: NonNullable<T>) => T,
): Record<string, T> {
  return fields.reduce(
    (acc, { key, value }) => {
      if (value === null) return acc
      acc[key] = transform(value as NonNullable<T>)
      return acc
    },
    {} as Record<string, T>,
  )
}

watch(visible, (val) => {
  if (val) return
  resetForm()
})

onMounted(() => {})
</script>

<style scoped>
.buttons {
  display: flex;
  gap: 12px;
}

.content {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  height: 100%;
  overflow: hidden;
}
</style>
