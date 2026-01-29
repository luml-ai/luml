<template>
  <div v-if="artifactsStore.currentArtifact">
    <div class="header">
      <div class="title">Artifact details</div>
      <div class="toolbar">
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.update)"
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
    <ArtifactTabs
      :show-model-card="isModelCardAvailable"
      :show-experiment-snapshot="isExperimentSnapshotCardAvailable"
      :show-model-attachments="isModelAttachmentsAvailable"
    ></ArtifactTabs>
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

  <ArtifactEditor
    v-if="modelForEdit"
    :visible="!!modelForEdit"
    :data="modelForEdit"
    @update:visible="onUpdateModelEditorVisible"
    @updateArtifact="onUpdateModel"
    @artifactDeleted="onModelDeleted"
  ></ArtifactEditor>
</template>

<script setup lang="ts">
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { useArtifactsStore } from '@/stores/artifacts'
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
import ArtifactTabs from '@/components/orbits/tabs/registry/collection/artifact/ArtifactTabs.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import ArtifactEditor from '@/components/orbits/tabs/registry/collection/artifact/ArtifactEditor.vue'

const artifactsStore = useArtifactsStore()
const route = useRoute()
const router = useRouter()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()

const modelForDeployment = ref<string | null>(null)
const modelForEdit = ref<Artifact | null>(null)

const isModelCardAvailable = computed(() => {
  if (!artifactsStore.currentArtifact) return false
  const fileIndex = artifactsStore.currentArtifact.file_index
  const includeSupportedTag = FnnxService.getTypeTag(artifactsStore.currentArtifact.manifest)
  return !!(includeSupportedTag || FnnxService.findHtmlCard(fileIndex))
})

const isExperimentSnapshotCardAvailable = computed(() => {
  if (!artifactsStore.currentArtifact) return false
  const fileIndex = artifactsStore.currentArtifact.file_index
  return !!FnnxService.findExperimentSnapshotArchiveName(fileIndex)
})

const isModelAttachmentsAvailable = computed(() => {
  if (!artifactsStore.currentArtifact) return false
  const fileIndex = artifactsStore.currentArtifact.file_index
  if (!fileIndex) return false
  return FnnxService.hasAttachments(fileIndex)
})

function initDeploy() {
  if (artifactsStore.currentArtifact) {
    modelForDeployment.value = artifactsStore.currentArtifact.id
  }
}

function openModelEditor() {
  const m = artifactsStore.currentArtifact
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
  artifactsStore.resetCurrentArtifact()
  navigateToArtifactsList()
}

function onUpdateModel(model: Artifact) {
  artifactsStore.setCurrentArtifact(model)
}

function navigateToArtifactsList() {
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
  if (!artifactsStore.currentArtifact) return
  try {
    await artifactsStore.downloadArtifact(
      artifactsStore.currentArtifact.id,
      artifactsStore.currentArtifact.file_name,
    )
  } catch (e) {
    console.error('Download failed', e)
  }
}

async function onArtifactIdChange(artifactId: string | string[] | null) {
  try {
    artifactsStore.resetCurrentArtifact()
    if (typeof artifactId !== 'string') return
    const requestInfo = {
      organizationId: route.params.organizationId as string,
      orbitId: route.params.id as string,
      collectionId: route.params.collectionId as string,
    }
    const artifact = await artifactsStore.getArtifact(artifactId, requestInfo)
    artifactsStore.setCurrentArtifact(artifact)
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to set current artifact')
    toast.add(simpleErrorToast(message))
  }
}

watch(() => route.params.artifactId, onArtifactIdChange, { immediate: true })

onUnmounted(() => {
  artifactsStore.resetCurrentArtifact()
  artifactsStore.resetCurrentModelTag()
  artifactsStore.resetCurrentModelMetadata()
  artifactsStore.resetCurrentModelHtmlBlobUrl()
  artifactsStore.resetExperimentSnapshotProvider()
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
