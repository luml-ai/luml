<template>
  <div v-if="currentModel">
    <div class="header">
      <div class="title">Model details</div>
      <div class="toolbar">
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.update)"
          variant="text"
          severity="secondary"
          v-tooltip="'Settings'"
          @click="openModelEditor"
        >
          <template #icon>
            <Bolt :size="16" />
          </template>
        </Button>
        <Button variant="text" severity="secondary" v-tooltip="'Deploy'" @click="initDeploy">
          <template #icon>
            <Rocket :size="16" />
          </template>
        </Button>
        <Button variant="text" severity="secondary" v-tooltip="'Download'" @click="downloadClick">
          <template #icon>
            <Download :size="16" />
          </template>
        </Button>
      </div>
    </div>
    <CollectionModelTabs
      :show-model-card="isModelCardAvailable"
      :show-experiment-snapshot="isExperimentSnapshotCardAvailable"
      :show-model-attachments="isModelAttachmentsAvailable"
    ></CollectionModelTabs>
    <div class="view-wrapper">
      <RouterView v-slot="{ Component }">
        <component :is="Component" :model="currentModel" />
      </RouterView>
    </div>
  </div>
  <DeploymentsCreateModal
    v-if="modelForDeployment"
    :visible="!!modelForDeployment"
    :initial-collection-id="collectionsStore.currentCollection?.id"
    :initial-model-id="modelForDeployment"
    @update:visible="onUpdateModelDeploymentVisible"
  ></DeploymentsCreateModal>

  <CollectionModelEditor
    v-if="modelForEdit"
    :visible="!!modelForEdit"
    @update:visible="onUpdateModelEditorVisible"
    @model-deleted="onModelDeleted"
    :data="modelForEdit"
  ></CollectionModelEditor>
</template>

<script setup lang="ts">
import { useModelsStore } from '@/stores/models'
import { computed, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import CollectionModelTabs from '@/components/orbits/tabs/registry/collection/model/CollectionModelTabs.vue'
import { Button } from 'primevue'
import { Bolt, Rocket, Download } from 'lucide-vue-next'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useCollectionsStore } from '@/stores/collections'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import CollectionModelEditor from '@/components/orbits/tabs/registry/collection/model/CollectionModelEditor.vue'
import type { SelectedModel } from '@/components/orbits/tabs/registry/collection/CollectionModelsTable.vue'
import { getSizeText } from '@/helpers/helpers'

const modelsStore = useModelsStore()
const route = useRoute()
const router = useRouter()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()

const modelForDeployment = ref<string | null>(null)
const modelForEdit = ref<SelectedModel | null>(null)

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === route.params.modelId)
})

const isModelCardAvailable = computed(() => {
  if (!currentModel.value) return false
  const fileIndex = currentModel.value.file_index
  const includeSupportedTag = FnnxService.getTypeTag(currentModel.value.manifest)
  return !!(includeSupportedTag || FnnxService.findHtmlCard(fileIndex))
})

const isExperimentSnapshotCardAvailable = computed(() => {
  if (!currentModel.value) return false
  const fileIndex = currentModel.value.file_index
  return !!FnnxService.findExperimentSnapshotArchiveName(fileIndex)
})

const isModelAttachmentsAvailable = computed(() => {
  if (!currentModel.value) return false
  const fileIndex = currentModel.value.file_index
  if (!fileIndex) return false
  return FnnxService.hasAttachments(fileIndex)
})

function initDeploy() {
  if (currentModel.value) {
    modelForDeployment.value = currentModel.value.id
  }
}

function openModelEditor() {
  const m = currentModel.value
  if (!m) return
  modelForEdit.value = {
    id: m.id,
    model_name: m.model_name,
    file_name: m.file_name,
    status: m.status,
    description: m.description,
    tags: m.tags,
    created_at: m.created_at,
    metrics: m.metrics,
    size: getSizeText(m.size),
  }
}

function onUpdateModelDeploymentVisible(val?: boolean) {
  if (!val) modelForDeployment.value = null
}

function onUpdateModelEditorVisible(val?: boolean) {
  if (!val) modelForEdit.value = null
}

function onModelDeleted() {
  modelForEdit.value = null
  navigateToCollectionModels()
}

function navigateToCollectionModels() {
  router.replace({
    name: 'collection',
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
      collectionId: route.params.collectionId,
    },
  })
}

async function downloadClick() {
  if (!currentModel.value) return
  try {
    await modelsStore.downloadModel(currentModel.value.id, currentModel.value.file_name)
  } catch (e) {
    console.error('Download failed', e)
  }
}

onUnmounted(() => {
  modelsStore.resetCurrentModelTag()
  modelsStore.resetCurrentModelMetadata()
  modelsStore.resetCurrentModelHtmlBlobUrl()
  modelsStore.resetExperimentSnapshotProvider()
})
</script>

<style scoped>
.header {
  display: flex;
}

.title {
  margin-bottom: 20px;
}

.toolbar {
  margin-left: auto;
}

.view-wrapper {
  padding-top: 20px;
}
</style>
