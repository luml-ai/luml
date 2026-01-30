<template>
  <UiCard title="Model parameters">
    <template #header-right>
      <Button severity="secondary" variant="text" @click="scaled = true">
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </template>
    <UiScalable v-model="scaled" title="Model parameters">
      <div class="parameters-in-card">
        <StaticParametersContent :parameters="parametersForShow"></StaticParametersContent>
      </div>
      <template #scaled>
        <StaticParametersContent :parameters="parametersForShow"></StaticParametersContent>
      </template>
    </UiScalable>
  </UiCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import UiCard from '../ui/UiCard.vue'
import UiScalable from '../ui/UiScalable.vue'
import StaticParametersContent from './StaticParametersContent.vue'

type Props = {
  parameters: Record<string, any>
}

const props = defineProps<Props>()

const scaled = ref(false)

const parametersForShow = computed(() => {
  const paramsClone = { ...props.parameters }
  delete paramsClone['modelId']
  return paramsClone
})
</script>

<style scoped>
.parameters-in-card {
  max-height: 133px;
  overflow-y: auto;
}
</style>
