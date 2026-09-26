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
      :resolver="deploymentEditorResolver"
      @submit="saveChanges"
    >
      <DeploymentsFormBasicsSettings
        v-model:description="initialValues.description"
        v-model:name="initialValues.name"
        v-model:tags="initialValues.tags"
        :showTitle="false"
        class="base-settings"
      ></DeploymentsFormBasicsSettings>
      <div
        v-if="data.provider_ref"
        class="provider-reference"
        data-testid="deployment-provider-reference"
      >
        <span class="label">Provider handle</span>
        <span class="provider-reference__value">{{ data.provider_ref }}</span>
      </div>
      <div v-if="showMonitoringField" class="monitoring-field">
        <div class="monitoring-header">
          <label class="label">Live monitoring</label>
          <ToggleSwitch
            v-model="initialValues.monitoringEnabled"
            name="monitoringEnabled"
            data-testid="editor-monitoring-toggle"
          />
        </div>
        <p
          v-if="satelliteSupportsMonitoring"
          class="monitoring-hint"
          data-testid="monitoring-sections-hint"
        >
          Monitoring sections: {{ monitoringHint.sectionLabels.join(', ') }}.
        </p>
        <p
          v-if="satelliteSupportsMonitoring && monitoringHint.recommendRepack"
          class="monitoring-hint"
          data-testid="monitoring-repack-hint"
        >
          Repack this model with reference data to enable data quality and drift monitoring.
        </p>
        <p
          v-if="initialValues.monitoringEnabled && !satelliteSupportsMonitoring"
          class="monitoring-warning"
        >
          <Info :size="12" class="monitoring-warning-icon" />
          The selected satellite does not report the monitoring capability, so the dashboard stays
          unavailable until it does.
        </p>
      </div>
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
          Force delete deployment
        </Button>
        <Button
          v-else
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          Stop deployment
        </Button>
      </div>
      <Button type="submit" :loading="loading" form="createDeploymentForm">Save changes</Button>
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
  ToggleSwitch,
} from 'primevue'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
  type UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'
import type { FieldInfo } from '../deployments.interfaces'
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import type { MonitoringFeature } from '@/lib/api/satellites/interfaces'
import type { Var } from '@fnnx-ai/common/dist/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { ChevronDown, ChevronUp, HelpCircle, Info, Rocket } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deploymentEditorResolver } from '@/utils/forms/resolvers'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { useCollectionsStore } from '@/stores/collections'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useArtifactsStore } from '@/stores/artifacts'
import { useRoute } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { useDeploymentsStore } from '@/stores/deployments'
import { useSatellitesStore } from '@/stores/satellites'
import { editorDialogPt } from '../deployments.const'
import { getErrorMessage } from '@/helpers/helpers'
import DeploymentsFormBasicsSettings from '../form/DeploymentsFormBasicsSettings.vue'
import DeploymentsDelete from '@/components/orbits/delete/DeploymentsDelete.vue'
import SecretsSelect from '../form/SecretsSelect.vue'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import { getMonitoringHint } from '../monitoring-hint'

const FORCE_DELETE_TEXT =
  'This action will schedule a task for your satellite to shut down this deployment. <br /> If you are sure, then write "delete" below'

interface FormValues {
  name: string
  description: string
  tags: string[]
  collectionId: string
  modelId: string
  monitoringEnabled: boolean
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
const artifactsStore = useArtifactsStore()
const route = useRoute()
const deploymentsStore = useDeploymentsStore()

const isDeleting = ref(false)
const isForceDeleting = ref(false)
const initialValues = ref<FormValues>({
  name: props.data.name,
  description: props.data.description,
  tags: props.data.tags,
  collectionId: props.data.collection_id,
  modelId: props.data.artifact_id,
  monitoringEnabled: props.data.monitoring_mode === MonitoringMode.full,
  secretDynamicAttributes: [],
})

const loading = ref(false)
const modelArtifact = ref<ModelArtifact | null>(null)

const satellitesStore = useSatellitesStore()

const selectedSatellite = computed(() => {
  return satellitesStore.satellitesList.find(({ id }) => id === props.data.satellite_id) ?? null
})

const satelliteSupportsMonitoring = computed(() => {
  return selectedSatellite.value?.present_capabilities.includes('monitoring') ?? false
})

const showMonitoringField = computed(
  () => satelliteSupportsMonitoring.value || initialValues.value.monitoringEnabled,
)

const monitoringHint = computed(() => {
  const features = satelliteSupportsMonitoring.value
    ? (selectedSatellite.value?.capabilities.monitoring?.features ?? [])
    : []
  return getMonitoringHint(
    modelArtifact.value?.manifest.producer_tags ?? [],
    features as MonitoringFeature[],
  )
})

const organizationId = computed(() => {
  if (typeof route.params.organizationId !== 'string') throw new Error('Incorrect organization ID')
  return route.params.organizationId
})

const isForceDelete = computed(() => {
  return DeploymentStatusEnum.active !== props.data.status
})

async function saveChanges({ valid }: FormSubmitEvent) {
  if (!valid) return
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
      monitoring_mode: initialValues.value.monitoringEnabled
        ? MonitoringMode.full
        : MonitoringMode.off,
    }
    await deploymentsStore.update(organizationId.value, props.data.orbit_id, props.data.id, payload)
    toast.add(simpleSuccessToast('Deployment changes saved successfully.'))
    visible.value = false
  } catch {
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
  try {
    if (!satellitesStore.satellitesList.length) {
      const satellites = await satellitesStore.loadSatellites(
        organizationId.value,
        props.data.orbit_id,
      )
      satellitesStore.setList(satellites)
    }
    await secretsStore.loadSecrets(organizationId.value, props.data.orbit_id)
    const requestInfo = {
      organizationId: organizationId.value,
      orbitId: props.data.orbit_id,
      collectionId: props.data.collection_id,
    }
    const currentModel = await artifactsStore.getArtifact(props.data.artifact_id, requestInfo)
    if (!currentModel) return
    modelArtifact.value = currentModel
    const { secrets } = FnnxService.getDynamicAttributes(currentModel.manifest)
    setSecrets(secrets)
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load model')))
  }
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

.monitoring-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.provider-reference {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.provider-reference__value {
  overflow-wrap: anywhere;
  color: var(--p-text-muted-color);
  text-align: right;
}

.monitoring-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.monitoring-header .label {
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--p-text-color);
}

.monitoring-hint {
  font-size: 12px;
  line-height: 1.5;
  color: var(--p-button-text-secondary-color);
  margin: 0;
}

.monitoring-warning {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}

.monitoring-warning-icon {
  flex: 0 0 auto;
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
