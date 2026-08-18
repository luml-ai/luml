<template>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    :pt="ARTIFACT_DETAILS_MODAL_PT"
    position="topright"
  >
    <template #header>
      <h2 class="dialog-title">
        <Info :size="20" color="var(--p-primary-color)" />
        <span>ARTIFACT Details</span>
      </h2>
    </template>
    <div v-if="data">Details</div>
    <template #footer>
      <Button label="View artifact" severity="secondary" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { Button, Dialog } from 'primevue'
import { ARTIFACT_DETAILS_MODAL_PT } from './artifact.data'
import type { Artifact } from '@/lib/api/artifacts/interfaces'

interface Props {
  data: Artifact | null
}

defineProps<Props>()

const visible = defineModel<boolean>('visible')
</script>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
  font-size: 20px;
  font-weight: 500;
}
</style>
