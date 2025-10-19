<template>
  <div>
    <DataTable :value="data" v-model:filters="filters">
      <template #header>
        <h4 class="title">{{ data.length }} Deployments</h4>
        <IconField>
          <InputText v-model="filters['global'].value" size="small" placeholder="Search" />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
      </template>
      <template #empty>Deployments not found...</template>
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
                name: 'model',
                params: { collectionId: data.collection_id, modelId: data.model_id },
              }"
              class="link"
            >
              {{ data.model_artifact_name }}
            </RouterLink>
          </div>
        </template>
      </Column>
      <Column header="Satellite" sortable field="satellite_name">
        <template #body="{ data }">
          <div class="cell">{{ data.satellite_name }}</div>
        </template>
      </Column>
      <Column header="Inference URL" field="inference_url">
        <template #body="{ data }">
          <div class="cell">
            <span :class="{ link: data.inference_url }">{{ data.inference_url || '-' }}</span>
          </div>
        </template>
      </Column>
      <Column header="Status" sortable field="status">
        <template #body="{ data }">
          <div class="cell">
            <Tag v-if="data.status === DeploymentStatusEnum.active" severity="success">Active</Tag>
            <Tag v-if="data.status === DeploymentStatusEnum.pending" severity="warn"> Pending </Tag>
            <Tag v-if="data.status === DeploymentStatusEnum.failed" severity="danger">Failed</Tag>
            <Tag v-if="data.status === DeploymentStatusEnum.deletion_pending" severity="warn">
              Shutting down
            </Tag>
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
          <Button
            v-if="
              ![DeploymentStatusEnum.deleted, DeploymentStatusEnum.deletion_pending].includes(
                data.status,
              )
            "
            severity="secondary"
            variant="text"
            @click="onSettingsClick(data)"
          >
            <template #icon>
              <Bolt :size="14"></Bolt>
            </template>
          </Button>
        </template>
      </Column>
    </DataTable>
    <DeploymentsEditor
      v-if="editableDeployment"
      :visible="!!editableDeployment"
      :data="editableDeployment"
      @update:visible="editableDeployment = null"
    ></DeploymentsEditor>
  </div>
</template>

<script setup lang="ts">
import { DataTable, Column, IconField, InputIcon, InputText, Tag, Button } from 'primevue'
import { FilterMatchMode } from '@primevue/core/api'
import { ref } from 'vue'
import { Search, Bolt } from 'lucide-vue-next'
import { DeploymentStatusEnum, type Deployment } from '@/lib/api/deployments/interfaces'
import DeploymentsEditor from '../edit/DeploymentsEditor.vue'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  data: Deployment[]
}

defineProps<Props>()

const filters = ref()
const editableDeployment = ref<Deployment | null>(null)

const initFilters = () => {
  filters.value = {
    global: { value: null, matchMode: FilterMatchMode.CONTAINS },
  }
}

function onSettingsClick(deployment: Deployment) {
  editableDeployment.value = deployment
}

initFilters()
</script>

<style scoped>
:deep(.p-datatable-header) {
  display: flex;
  gap: 20px;
  justify-content: space-between;
  align-items: center;
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

.id-row {
  font-size: 12px;
}

.id-text {
  color: var(--p-text-muted-color);
}
</style>
