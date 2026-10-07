<template>
  <div>
    <DataTable :value="data" v-model:filters="filters" v-model:selection="selection" data-key="id">
      <template #header>
        <div class="header-left">
          <h4 class="title">
            {{ data.length }} {{ data.length === 1 ? 'Deployment' : 'Deployments' }}
          </h4>
          <div class="toolbar">
            <div class="counter">{{ selection.length }} Selected</div>
            <Button
              variant="text"
              severity="secondary"
              aria-label="Stop"
              v-tooltip="'Stop'"
              :disabled="loading || !selection.length"
              data-testid="batch-stop"
              @click="onStopClick"
            >
              <template #icon>
                <CircleStop :size="14" />
              </template>
            </Button>
            <Button
              variant="text"
              severity="secondary"
              aria-label="Force delete"
              v-tooltip="'Force delete'"
              :disabled="loading || !selection.length"
              data-testid="batch-delete"
              @click="forceVisible = true"
            >
              <template #icon>
                <Trash2 :size="14" />
              </template>
            </Button>
          </div>
        </div>
        <IconField>
          <InputText v-model="filters['global'].value" size="small" placeholder="Search" />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
      </template>
      <template #empty>Deployments not found...</template>
      <Column selection-mode="multiple" />
      <Column header="Deployment name" field="name">
        <template #body="{ data }">
          <div class="cell cell--name">{{ data.name }}</div>
          <div class="id-row">
            <span class="id-text">Id: </span>
            <UiId :id="data.id" class="id-value"></UiId>
          </div>
        </template>
      </Column>
      <Column header="Model" sortable field="model_artifact_name">
        <template #body="{ data }">
          <div class="cell">
            <RouterLink
              :to="{
                name: 'artifact',
                params: { collectionId: data.collection_id, artifactId: data.artifact_id },
              }"
              class="link"
            >
              {{ data.artifact_name }}
            </RouterLink>
          </div>
        </template>
      </Column>
      <Column header="Satellite" sortable field="satellite_name">
        <template #body="{ data }">
          <div class="cell">{{ data.satellite_name }}</div>
        </template>
      </Column>
      <Column header="Status" sortable field="status">
        <template #body="{ data }">
          <div class="cell">
            <Tag v-if="data.status === DeploymentStatusEnum.active" severity="success">Active</Tag>
            <Tag v-if="data.status === DeploymentStatusEnum.pending" severity="warn"> Pending </Tag>
            <div v-if="data.status === DeploymentStatusEnum.failed" class="tag-with-icon">
              <Tag severity="danger">Failed</Tag>
              <TriangleAlert
                v-if="data.error_message"
                v-tooltip.top="'Show error'"
                :size="14"
                color="var(--p-tag-danger-color)"
                @click="error = data.error_message"
              />
            </div>
            <div v-if="data.status === DeploymentStatusEnum.not_responding" class="tag-with-icon">
              <Tag severity="danger">Not Responding</Tag>
              <TriangleAlert
                v-if="data.error_message"
                v-tooltip.top="'Show error'"
                :size="14"
                color="var(--p-tag-danger-color)"
                @click="error = data.error_message"
              />
            </div>
            <Tag v-if="data.status === DeploymentStatusEnum.deletion_pending" severity="warn">
              Shutting down
            </Tag>
            <span
              v-if="showProgressNote(data)"
              class="progress-note"
              data-testid="deployment-progress-note"
            >
              {{ data.progress_note }}
            </span>
          </div>
        </template></Column
      >
      <Column header="Creation time" sortable field="created_at">
        <template #body="{ data }">
          <div class="cell">{{ new Date(data.created_at).toLocaleString() }}</div>
        </template>
      </Column>
      <Column header="Created by" sortable field="created_by_user">
        <template #body="{ data }">
          <div class="cell">{{ data.created_by_user }}</div>
        </template>
      </Column>
      <Column header="Tags" field="tags">
        <template #body="{ data }">
          <div class="cell">
            <div class="tags">
              <Tag v-for="(tag, index) in data.tags" :key="index">{{ tag }}</Tag>
            </div>
          </div>
        </template>
      </Column>
      <Column>
        <template #body="{ data }">
          <div class="actions">
            <router-link
              v-if="data.schemas && !!Object.keys(data.schemas).length"
              v-tooltip.top="'View schema'"
              :to="{ name: 'deployment-schema', params: { deploymentId: data.id } }"
              class="icon-link"
            >
              <Braces :size="16" />
            </router-link>
            <span v-else v-tooltip.top="'No schema'" class="icon-link icon-link--disabled">
              <Braces :size="16" />
            </span>
            <router-link
              v-if="data.monitoring_mode !== MonitoringMode.off"
              v-tooltip.top="'View monitoring'"
              :to="{ name: 'deployment-monitoring', params: { deploymentId: data.id } }"
              class="icon-link"
            >
              <Activity :size="16" />
            </router-link>
            <span v-else v-tooltip.top="'Monitoring is off'" class="icon-link icon-link--disabled">
              <Activity :size="16" />
            </span>
            <Button severity="secondary" variant="text" @click="onSettingsClick(data)">
              <template #icon>
                <Bolt :size="14"></Bolt>
              </template>
            </Button>
          </div>
        </template>
      </Column>
    </DataTable>
    <ForceDeleteConfirmDialog
      v-model:visible="forceVisible"
      :title="
        selection.length > 1
          ? `Force delete ${selection.length} deployments?`
          : 'Force delete this deployment?'
      "
      text='This removes deployment records without shutting down satellite workloads. Active deployments must be stopped first. Records with dependencies cannot be deleted. Type "delete" to confirm.'
      :loading="loading"
      @confirm="runBatchAction('delete')"
    />
    <Dialog
      :pt="BATCH_RESULT_DIALOG_PT"
      :visible="!!failures.length"
      modal
      :draggable="false"
      @update:visible="failures = []"
    >
      <template #header>{{ failuresTitle }}</template>
      <div class="failures" data-testid="batch-results">
        <div v-for="failure in failures" :key="failure.deployment_id">
          <div class="failure-name">Deployment: {{ failure.name ?? failure.deployment_id }}</div>
          <div class="failure-reason">{{ failure.message }}</div>
        </div>
      </div>
      <template #footer>
        <Button @click="failures = []">Close</Button>
      </template>
    </Dialog>
    <DeploymentsEditor
      v-if="editableDeployment"
      :visible="!!editableDeployment"
      :data="editableDeployment"
      @update:visible="onUpdateEditorVisible"
    ></DeploymentsEditor>
  </div>
  <DeploymentErrorModal
    :error="error?.error || ''"
    :reason="error?.reason || ''"
    :visible="!!error"
    @update:visible="error = null"
  ></DeploymentErrorModal>
</template>

<script setup lang="ts">
import {
  DataTable,
  Column,
  IconField,
  InputIcon,
  InputText,
  Tag,
  Button,
  Dialog,
  useConfirm,
  useToast,
} from 'primevue'
import type { DialogPassThroughOptions } from 'primevue'
import { FilterMatchMode } from '@primevue/core/api'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { Search, Bolt, TriangleAlert, Braces, Activity, CircleStop, Trash2 } from 'lucide-vue-next'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
  type DeploymentBatchAction,
  type DeploymentBatchFailure,
  type DeploymentErrorMessage,
} from '@/lib/api/deployments/interfaces'
import DeploymentsEditor from '../edit/DeploymentsEditor.vue'
import UiId from '@/components/ui/UiId.vue'
import DeploymentErrorModal from '../error/DeploymentErrorModal.vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores/deployments'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import { stopDeploymentsConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleSuccessToast } from '@/lib/primevue/data/toasts'

const BATCH_RESULT_DIALOG_PT: DialogPassThroughOptions = {
  root: { style: 'width: 450px;' },
  header: { style: 'text-transform: uppercase; font-size: 16px; font-weight: 600;' },
}

type Props = {
  data: Deployment[]
}

const props = defineProps<Props>()
const route = useRoute()
const router = useRouter()

const filters = ref()
const editableDeployment = ref<Deployment | null>(null)
const error = ref<DeploymentErrorMessage | null>(null)

const deploymentsStore = useDeploymentsStore()
const confirm = useConfirm()
const toast = useToast()
const selectedDeployments = ref<Deployment[]>([])
const loading = ref(false)
const forceVisible = ref(false)
const failures = ref<DeploymentBatchFailure[]>([])
const failuresAction = ref<DeploymentBatchAction>('undeploy')
const failuresTitle = computed(() => {
  const verb = failuresAction.value === 'delete' ? 'deleted' : 'stopped'
  return failures.value.length === 1
    ? `Deployment was not ${verb}`
    : `Some deployments were not ${verb}`
})
const selection = computed({
  get: () => selectedDeployments.value,
  set: (value: Deployment[]) => {
    if (!loading.value) selectedDeployments.value = value
  },
})

watch(
  () => props.data,
  (data) => {
    const rows = new Map(data.map((deployment) => [deployment.id, deployment]))
    selectedDeployments.value = selectedDeployments.value.map(
      (deployment) => rows.get(deployment.id) ?? deployment,
    )
  },
)

watch(
  () => [route.params.organizationId, route.params.id],
  () => {
    selectedDeployments.value = []
    failures.value = []
  },
)

function onStopClick() {
  if (loading.value || !selection.value.length) return
  confirm.require(
    stopDeploymentsConfirmOptions(() => runBatchAction('undeploy'), selection.value.length),
  )
}

async function runBatchAction(action: DeploymentBatchAction) {
  if (loading.value || !selection.value.length) return
  const selected = [...selection.value]
  const names = new Map(selected.map(({ id, name }) => [id, name]))
  const organizationId = route.params.organizationId as string
  const orbitId = route.params.id as string
  loading.value = true
  try {
    const result = await deploymentsStore.batchAction(
      organizationId,
      orbitId,
      selected.map(({ id }) => id),
      action,
    )
    const succeeded = new Set(result.succeeded)
    selectedDeployments.value = selectedDeployments.value.filter(({ id }) => !succeeded.has(id))
    if (result.succeeded.length) {
      toast.add(simpleSuccessToast(successMessage(action, result.succeeded, names)))
    }
    failuresAction.value = action
    failures.value = result.failed.map((failure) => ({
      ...failure,
      name: failure.name ?? names.get(failure.deployment_id) ?? null,
    }))
  } finally {
    loading.value = false
    forceVisible.value = false
  }
}

function successMessage(
  action: DeploymentBatchAction,
  ids: string[],
  names: Map<string, string>,
): string {
  if (ids.length === 1) {
    const name = names.get(ids[0]) ?? ids[0]
    return action === 'delete' ? `Deployment "${name}" deleted` : `Deployment "${name}" is stopping`
  }
  return action === 'delete'
    ? `${ids.length} deployments deleted`
    : `${ids.length} deployments are stopping`
}

const initFilters = () => {
  filters.value = {
    global: { value: null, matchMode: FilterMatchMode.CONTAINS },
  }
}

function onSettingsClick(deployment: Deployment) {
  editableDeployment.value = deployment
}

function showProgressNote(deployment: Deployment) {
  return (
    !!deployment.progress_note &&
    [DeploymentStatusEnum.pending, DeploymentStatusEnum.not_responding].includes(deployment.status)
  )
}

function checkDeploymentInQuery() {
  if (!route.query.deployment) return
  const deployment = props.data.find((d) => d.id === route.query.deployment)
  if (!deployment) return
  editableDeployment.value = deployment
}

function onUpdateEditorVisible() {
  editableDeployment.value = null
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { deployment: _deployment, ...restQuery } = route.query
  router.replace({
    name: 'orbit-deployments',
    params: route.params,
    query: restQuery,
  })
}

initFilters()

onBeforeMount(() => {
  checkDeploymentInQuery()
})
</script>

<style scoped>
:deep(.p-datatable-header) {
  display: flex;
  gap: 20px;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
}

.counter {
  font-variant-numeric: tabular-nums;
}

.failures {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.failure-name {
  margin-bottom: 4px;
  color: var(--p-text-muted-color);
  font-size: 12px;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.failure-reason {
  font-size: 14px;
  line-height: 1.5;
}

.title {
  font-size: 16px;
}

:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 9px;
}

:deep(.p-datatable-header) {
  border: none;
  background-color: transparent;
  padding: 0 0 16px 12px;
}

:deep(.p-datatable) {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
}

@media (min-width: 769px) {
  :deep(.p-datatable) {
    margin: 0 -87px;
  }
}

:deep(.p-datatable-tbody > tr) {
  background-color: transparent;
}

.cell {
  width: 145px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
}

.cell--name {
  width: 168px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

:deep(.p-tag) {
  padding: 2px 4px;
}

.link {
  text-decoration: underline;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.icon-link {
  display: inline-flex;
  align-items: center;
  color: var(--p-primary-color);
}

.icon-link--disabled {
  color: var(--p-text-muted-color);
  opacity: 0.4;
  cursor: default;
}

.id-row {
  font-size: 12px;
}

.id-text {
  color: var(--p-text-muted-color);
}

.tag-with-icon {
  display: flex;
  align-items: center;
  gap: 6px;
}

.progress-note {
  display: block;
  margin-top: 4px;
  color: var(--p-text-muted-color);
  font-size: 12px;
  white-space: normal;
}
</style>
