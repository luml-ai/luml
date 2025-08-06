<template>
  <div class="runtime">
    <upload-data v-if="currentStep === 1"
      :remove-callback="removeModel"
      :upload-callback="createModelFromFile"
      @continue="currentStep = 2"/>
    <runtime-dashboard v-else-if="getModel && currentTag"
      :current-tag="currentTag"
      :model="(getModel as Model)"
      @exit="currentStep = 1" />
  </div>
</template>

<script setup lang="ts">
import type { Model } from '@fnnx/web'
import { ref } from 'vue'
import UploadData from '@/components/runtime/UploadData.vue'
import RuntimeDashboard from '@/components/runtime/dashboard/index.vue'
import { useFnnxModel } from '@/hooks/useFnnxModel'

const { currentTag, getModel, createModelFromFile, removeModel } = useFnnxModel()

const currentStep = ref(1)
</script>

<style scoped></style>
