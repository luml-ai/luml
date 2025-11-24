<template>
  <div class="runtime">
    <upload-data
      v-if="currentStep === 1"
      :remove-callback="removeModel"
      :upload-callback="createModelFromFile"
      @continue="currentStep = 2"
    />
    <RuntimeDashboard
      v-else-if="getModel && currentTag"
      :current-tag="currentTag"
      :model="getModel as Model"
      :model-id="modelId"
      @exit="exit"
    />
  </div>
</template>

<script setup lang="ts">
import type { Model } from '@fnnx/web'
import { onUnmounted, ref } from 'vue'
import UploadData from '@/components/runtime/UploadData.vue'
import RuntimeDashboard from '@/components/runtime/dashboard/RuntimeDashboard.vue'
import { useFnnxModel } from '@/hooks/useFnnxModel'
import { leavePageConfirmOptions } from '@/lib/primevue/data/confirm'
import { useConfirm } from 'primevue/useconfirm'

const confirm = useConfirm()
const { currentTag, getModel, modelId, createModelFromFile, removeModel, deinit } = useFnnxModel()

const currentStep = ref(1)

function exit() {
  confirm.require(
    leavePageConfirmOptions(() => {
      currentStep.value = 1
    }),
  )
}

onUnmounted(() => {
  deinit()
})
</script>

<style scoped></style>
