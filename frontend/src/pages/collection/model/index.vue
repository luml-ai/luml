<template>
  <div v-if="modelsStore.currentModel">
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
        <component :is="Component" />
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
    :data="modelForEdit"
    @update:visible="onUpdateModelEditorVisible"
    @updateModel="onUpdateModel"
    @modelDeleted="onModelDeleted"
  ></CollectionModelEditor>
</template>

<script setup lang="ts">
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { useModelsStore } from '@/stores/models'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { Button, useToast } from 'primevue'
import { Bolt, Rocket, Download } from 'lucide-vue-next'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useCollectionsStore } from '@/stores/collections'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import CollectionModelTabs from '@/components/orbits/tabs/registry/collection/model/CollectionModelTabs.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import CollectionModelEditor from '@/components/orbits/tabs/registry/collection/model/CollectionModelEditor.vue'

const modelsStore = useModelsStore()
const route = useRoute()
const router = useRouter()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()

const modelForDeployment = ref<string | null>(null)
const modelForEdit = ref<MlModel | null>(null)

const isModelCardAvailable = computed(() => {
  if (!modelsStore.currentModel) return false
  const fileIndex = modelsStore.currentModel.file_index
  const includeSupportedTag = FnnxService.getTypeTag(modelsStore.currentModel.manifest)
  return !!(includeSupportedTag || FnnxService.findHtmlCard(fileIndex))
})

const isExperimentSnapshotCardAvailable = computed(() => {
  if (!modelsStore.currentModel) return false
  const fileIndex = modelsStore.currentModel.file_index
  return !!FnnxService.findExperimentSnapshotArchiveName(fileIndex)
})

const isModelAttachmentsAvailable = computed(() => {
  if (!modelsStore.currentModel) return false
  const fileIndex = modelsStore.currentModel.file_index
  if (!fileIndex) return false
  return FnnxService.hasAttachments(fileIndex)
})

function initDeploy() {
  if (modelsStore.currentModel) {
    modelForDeployment.value = modelsStore.currentModel.id
  }
}

function openModelEditor() {
  const m = modelsStore.currentModel
  if (!m) return
  modelForEdit.value = {
    ...m,
  }
}

function onUpdateModelDeploymentVisible(val?: boolean) {
  if (!val) modelForDeployment.value = null
}

function onUpdateModelEditorVisible(val?: boolean) {
  if (!val) modelForEdit.value = null
}

function onModelDeleted() {
  modelsStore.resetCurrentModel()
  navigateToCollectionModels()
}

function onUpdateModel(model: MlModel) {
  modelsStore.setCurrentModel(model)
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
  if (!modelsStore.currentModel) return
  try {
    await modelsStore.downloadModel(modelsStore.currentModel.id, modelsStore.currentModel.file_name)
  } catch (e) {
    console.error('Download failed', e)
  }
}

async function onModelIdChange(modelId: string | string[] | null) {
  try {
    modelsStore.resetCurrentModel()
    if (typeof modelId !== 'string') return
    const requestInfo = {
      organizationId: route.params.organizationId as string,
      orbitId: route.params.id as string,
      collectionId: route.params.collectionId as string,
    }
    const model = await modelsStore.getModel(modelId, requestInfo)
    modelsStore.setCurrentModel(model)
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to set current model')
    toast.add(simpleErrorToast(message))
  }
}

watch(() => route.params.modelId, onModelIdChange, { immediate: true })

onUnmounted(() => {
  modelsStore.resetCurrentModel()
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
