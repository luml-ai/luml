<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="editorDialogPt"
  >
    <template #header>
      <h2 class="dialog-title">
        <Rocket :size="20" color="var(--p-primary-color)" />
        <span>deployment settings</span>
      </h2>
    </template>
    <Form
      v-if="visible"
      ref="formRef"
      id="createDeploymentForm"
      class="content"
      :initial-values="initialValues"
      :resolver="createDeploymentResolver"
      @submit="saveChanges"
    >
      <DeploymentsFormBasicsSettings
        v-model:description="initialValues.description"
        v-model:name="initialValues.name"
        v-model:tags="initialValues.tags"
        :showTitle="false"
        class="base-settings"
      ></DeploymentsFormBasicsSettings>
      <Accordion v-if="initialValues.secretDynamicAttributes.length" style="margin-bottom: 12px">
        <template #expandicon>
          <ChevronDown :size="20"></ChevronDown>
        </template>
        <template #collapseicon>
          <ChevronUp :size="20"></ChevronUp>
        </template>
        <AccordionPanel value="0">
          <AccordionHeader>
            <div class="accordion-title">
              Secrets
              <HelpCircle :size="12" color="var(--p-button-text-secondary-color)"></HelpCircle>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <FormField
              v-for="(secret, index) in initialValues.secretDynamicAttributes"
              :key="secret.key"
              :name="`secretDynamicAttributes.${index}.value`"
              class="field"
            >
              <label class="label">{{ secret.label }} (dynamic attributes)</label>
              <SecretsSelect
                v-model="secret.value"
                :secrets-list="secretsStore.secretsList"
              ></SecretsSelect>
            </FormField>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </Form>
    <template #footer>
      <div>
        <Button
          v-if="isForceDelete"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onForceDeleteClick"
        >
          force delete deployment
        </Button>
        <Button
          v-else
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          stop deployment
        </Button>
      </div>
      <Button type="submit" :loading="loading" form="createDeploymentForm">save changes</Button>
    </template>
    <DeploymentsDelete
      v-if="isDeleting"
      :visible="isDeleting"
      :deploymentId="data.id"
      :organizationId="collectionsStore.requestInfo.organizationId"
      :orbitId="collectionsStore.requestInfo.orbitId"
      :name="data.name"
      @update:visible="isDeleting = false"
      @delete="onDelete"
    ></DeploymentsDelete>
    <ForceDeleteConfirmDialog
      v-if="isForceDeleting"
      v-model:visible="isForceDeleting"
      title="Force delete this deployment?"
      :text="FORCE_DELETE_TEXT"
      :loading="loading"
      @confirm="onForceDelete"
    ></ForceDeleteConfirmDialog>
  </Dialog>
</template>

<script setup lang="ts">
import {
  Dialog,
  Button,
  useToast,
  Accordion,
  AccordionPanel,
  AccordionHeader,
  AccordionContent,
} from 'primevue'
import {
  DeploymentStatusEnum,
  type Deployment,
  type UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'
import type { FieldInfo } from '../deployments.interfaces'
import type { Var } from '@fnnx/common/dist/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { ChevronDown, ChevronUp, HelpCircle, Rocket } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { createDeploymentResolver } from '@/utils/forms/resolvers'
import { Form, FormField } from '@primevue/forms'
import { useCollectionsStore } from '@/stores/collections'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { useDeploymentsStore } from '@/stores/deployments'
import { editorDialogPt } from '../deployments.const'
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue'
import DeploymentsDelete from '@/components/orbits/delete/DeploymentsDelete.vue'
import SecretsSelect from '../form/SecretsSelect.vue'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import { getErrorMessage } from '@/helpers/helpers'

const FORCE_DELETE_TEXT =
  'This action will schedule a task for your satellite to shut down this deployment. <br /> If you are sure, then write "delete" below'

interface FormValues {
  name: string
  description: string
  tags: string[]
  collectionId: string
  modelId: string
  secretDynamicAttributes: FieldInfo[]
}

type Props = {
  data: Deployment
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')

const toast = useToast()
const collectionsStore = useCollectionsStore()
const secretsStore = useSecretsStore()
const modelsStore = useModelsStore()
const route = useRoute()
const deploymentsStore = useDeploymentsStore()

const isDeleting = ref(false)
const isForceDeleting = ref(false)
const initialValues = ref<FormValues>({
  name: props.data.name,
  description: props.data.description,
  tags: props.data.tags,
  collectionId: props.data.collection_id,
  modelId: props.data.model_id,
  secretDynamicAttributes: [],
})

const loading = ref(false)

const organizationId = computed(() => {
  if (typeof route.params.organizationId !== 'string') throw new Error('Incorrect organization ID')
  return route.params.organizationId
})

const isForceDelete = computed(() => {
  return DeploymentStatusEnum.active !== props.data.status
})

async function saveChanges() {
  try {
    loading.value = true
    const dynamic_attributes_secrets = initialValues.value.secretDynamicAttributes.reduce(
      (acc: Record<string, string>, attribute) => {
        if (!attribute.value) return acc
        acc[attribute.key] = attribute.value
        return acc
      },
      {},
    )
    const payload: UpdateDeploymentPayload = {
      name: initialValues.value.name,
      description: initialValues.value.description,
      tags: initialValues.value.tags,
      dynamic_attributes_secrets,
    }
    await deploymentsStore.update(organizationId.value, props.data.orbit_id, props.data.id, payload)
    toast.add(simpleSuccessToast('Deployment changes saved successfully.'))
    visible.value = false
  } catch (e) {
    toast.add(simpleErrorToast('Failed to update deployment'))
  } finally {
    loading.value = false
  }
}

function onDeleteClick() {
  isDeleting.value = true
}

function onForceDeleteClick() {
  isForceDeleting.value = true
}

async function onForceDelete() {
  try {
    loading.value = true
    await deploymentsStore.forceDeleteDeployment(
      organizationId.value,
      props.data.orbit_id,
      props.data.id,
    )
    toast.add(simpleSuccessToast('Deployment is being deleted.'))
    isForceDeleting.value = false
    visible.value = false
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not force delete deployment')))
  } finally {
    loading.value = false
  }
}

function onDelete() {
  isDeleting.value = false
  visible.value = false
}

async function initModels() {
  const modelsList = await modelsStore.getModelsList(
    organizationId.value,
    props.data.orbit_id,
    props.data.collection_id,
  )
  modelsStore.setModelsList(modelsList)
}

function setSecrets(secrets: Var[]) {
  initialValues.value.secretDynamicAttributes = secrets.map((attribute) => {
    const existingValue = props.data.dynamic_attributes_secrets[attribute.name]
    return {
      key: attribute.name,
      label: attribute.description || attribute.name,
      value: existingValue || null,
    }
  })
}

onBeforeMount(async () => {
  await initModels()
  await secretsStore.loadSecrets(organizationId.value, props.data.orbit_id)
  const currentModel = modelsStore.modelsList.find((model) => model.id === props.data.model_id)
  if (!currentModel) return
  const { secrets } = FnnxService.getDynamicAttributes(currentModel.manifest)
  setSecrets(secrets)
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

.base-settings {
  margin: -20px;
}

.model-settings {
  margin: -20px;
}

.accordion-title {
  display: flex;
  align-items: center;
  gap: 4px;
  text-transform: uppercase;
  font-size: 12px;
  padding: 2px 0;
  font-weight: 500;
  color: var(--p-text-color);
}

:deep(.p-accordionheader) {
  margin-top: 20px;
  padding: 12px;
}

:deep(.p-accordionpanel) {
  border: none;
}

:deep(.p-accordioncontent-content) {
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 0 0 8px 8px;
  padding: 6px 12px 12px;
}

:deep(.p-accordioncontent-content) .label {
  font-size: 12px;
  line-height: 1.75;
}
</style>
