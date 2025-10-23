<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 650px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="dialog-title">
        <FileJson2 :size="20" color="var(--p-primary-color)" />
        <span>Model manifest</span>
      </h2>
    </template>
    <UiMultiTypeText
      :title="''"
      :text="manifest"
      :initial-type="ContentTypeEnum.yaml"
    ></UiMultiTypeText>
  </Dialog>
</template>

<script setup lang="ts">
import type { Manifest } from '@fnnx/common/dist/interfaces'
import { Dialog, type DialogPassThroughOptions } from 'primevue'
import { FileJson2 } from 'lucide-vue-next'
import { ContentTypeEnum } from '../ui/multi-type-text/interfaces'
import UiMultiTypeText from '../ui/multi-type-text/UiMultiTypeText.vue'

type Props = {
  manifest: Manifest
}

defineProps<Props>()

const visible = defineModel<boolean>('visible')

const dialogPT: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
