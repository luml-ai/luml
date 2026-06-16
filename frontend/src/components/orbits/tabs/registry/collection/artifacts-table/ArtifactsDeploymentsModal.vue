<template>
  <Dialog
    :pt="ARTIFACTS_DEPLOYMENTS_MODAL_PT"
    :visible="visible"
    modal
    :draggable="false"
    @update:visible="onUpdateVisible"
  >
    <template #header>Models with active deployments</template>
    <div class="description">
      Some models are associated with active deployments. If you want to delete these models, you
      need to stop the deployments first.
    </div>
    <div class="artifacts-list">
      <div
        v-for="artifact in artifactsStore.modelsWithActiveDeploymentsForDeletion"
        :key="artifact.id"
        class="artifact"
      >
        <div class="artifact-name">Artifact: {{ artifact.name }}</div>
        <div class="artifact-deployments">
          <template v-for="(deployment, index) in artifact.deployments" :key="deployment.id">
            <RouterLink
              :to="{
                name: 'orbit-deployments',
                params: {
                  organizationId: route.params.organizationId,
                  id: route.params.id,
                },
                query: {
                  deployment: deployment.id,
                },
              }"
              target="_blank"
              class="link deployment"
            >
              {{ deployment.name }}
            </RouterLink>
            <span v-if="index < artifact.deployments.length - 1">, </span>
          </template>
        </div>
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog } from 'primevue'
import { useArtifactsStore } from '@/stores/artifacts'
import { computed } from 'vue'
import { ARTIFACTS_DEPLOYMENTS_MODAL_PT } from './models-table.data'
import { RouterLink } from 'vue-router'
import { useRoute } from 'vue-router'

const artifactsStore = useArtifactsStore()
const route = useRoute()

const visible = computed(() => !!artifactsStore.modelsWithActiveDeploymentsForDeletion.length)

function onUpdateVisible(visible: boolean) {
  if (!visible) {
    artifactsStore.resetModelsWithActiveDeploymentsForDeletion()
  }
}
</script>

<style scoped>
.description {
  font-size: 14px;
  line-height: 1.5;
}
.artifacts-list {
  padding-top: 16px;
}
.artifact:not(:last-child) {
  margin-bottom: 16px;
}
.artifact-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--p-text-muted-color);
  margin-bottom: 4px;
}
.artifact-deployments {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
