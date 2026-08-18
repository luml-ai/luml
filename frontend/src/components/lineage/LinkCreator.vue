<template>
  <Dialog
    :visible="lineageStore.creatorVisible"
    header="LINK ARTIFACT"
    modal
    :draggable="false"
    :pt="LINK_CREATOR_DIALOG_PT"
    @update:visible="lineageStore.setCreatorVisible"
  >
    <ArtifactSelector
      v-if="lineageStore.creatorVisible"
      v-model:artifact="selectedArtifact"
      :organization-id="organizationId"
      :orbit-id="orbitId"
      :locked-artifacts="lineageStore.usedArtifactsIds"
    />
    <template #footer>
      <Button
        label="Link"
        fluid
        rounded
        type="submit"
        form="link-artifact-form"
        :loading="loading"
        :disabled="!selectedArtifact"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { useLineageStore } from '@/stores/lineage'
import { Button, Dialog } from 'primevue'
import { LINK_CREATOR_DIALOG_PT } from './lineage.data'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ArtifactSelector from './ArtifactSelector.vue'

const lineageStore = useLineageStore()
const route = useRoute()

const loading = ref(false)
const selectedArtifact = ref<Artifact | null>(null)

const organizationId = computed(() => String(route.params.organizationId))
const orbitId = computed(() => String(route.params.id))

function onSubmit() {
  if (!selectedArtifact.value) return
  loading.value = true
  lineageStore.addArtifact(selectedArtifact.value)
  lineageStore.setCreatorVisible(false)
  loading.value = false
}

async function onVisibleChanged(visible: boolean) {
  if (!visible) {
    selectedArtifact.value = null
  }
}

watch(() => lineageStore.creatorVisible, onVisibleChanged)
</script>

<style scoped></style>
