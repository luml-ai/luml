<template>
  <Dialog v-model:visible="visible" :pt="dialogPt" modal :draggable="false">
    <template #header>
      <div class="header-content">
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
      </div>
    </template>
    <template #default>
      <Form
        v-if="visible"
        ref="formRef"
        id="createDeploymentForm"
        class="content"
        :initial-values="initialValues"
        :resolver="resolver"
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
          @model-changed="onModelChanged"
        ></DeploymentsFormModelSettings>
        <DeploymentsFormSatelliteSettings
          :selected-model="selectedModel"
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
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { Dialog, Button, useToast } from 'primevue'
import { Form } from '@primevue/forms'
import { dialogPt, getInitialFormData } from '../deployments.const'
import { computed, ref } from 'vue'
import { createDeploymentResolver } from '@/utils/forms/resolvers'
import { getErrorMessage } from '@/helpers/helpers'
import { useCollectionsStore } from '@/stores/collections'
import { useDeploymentsStore } from '@/stores/deployments'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue'
import DeploymentsFormModelSettings from '../form/model-settings/DeploymentsFormModelSettings.vue'
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
const selectedModel = ref<MlModel | null>(null)
const initialValues = ref(getInitialFormData(props.initialCollectionId, props.initialModelId))
const resolver = ref(createDeploymentResolver(initialValues))

function areFieldsFilled(fields: FieldInfo<any>[] | undefined): boolean {
  if (!fields || fields.length === 0) return true
  return fields.every(
    (field) => field.value !== null && field.value !== '' && field.value !== undefined,
  )
}

const isFormValid = computed(() => {
  const form = initialValues.value

  const basicFieldsValid = !!(form.name && form.collectionId && form.modelId && form.satelliteId)

  if (!basicFieldsValid) return false

  return (
    areFieldsFilled(form.secretEnvs) &&
    areFieldsFilled(form.notSecretEnvs) &&
    areFieldsFilled(form.secretDynamicAttributes) &&
    areFieldsFilled(form.satelliteFields)
  )
})

function onCancel() {
  visible.value = false
}

function resetForm() {
  initialValues.value = getInitialFormData()
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) {
    toast.add(simpleErrorToast('Check the form for errors'))
    return
  }
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
    satellite_parameters: fieldsToRecord<string | number | boolean>(form.satelliteFields, (v) => v),
    dynamic_attributes_secrets: fieldsToRecord(
      form.secretDynamicAttributes,
      (v) => v,
    ) as unknown as Record<string, string>,
    env_variables_secrets: fieldsToRecord<string>(form.secretEnvs, (v) => String(v)),
    env_variables: fieldsToRecord(form.notSecretEnvs, (v) => String(v)),
    tags: form.tags,
  }
}

function fieldsToRecord<T extends string | number | boolean>(
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

function onModelChanged(model: MlModel | null) {
  selectedModel.value = model
}
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

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

@media (max-width: 992px) {
  .content {
    grid-template-columns: 1fr;
    height: auto;
    overflow: visible;
  }

  .header-content {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }
}
</style>
