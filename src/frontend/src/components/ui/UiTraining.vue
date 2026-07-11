<template>
  <d-dialog
    :visible="modelValue"
    modal
    :closable="false"
    :closeOnEscape="false"
    @update:visible="(event: boolean) => $emit('update:modelValue', event)"
  >
    <template #container>
      <div class="wrapper">
        <div class="loader">
          <ui-loader />
        </div>
        <div class="content">
          <h2 class="title">Training in progress...</h2>
          <div class="text">
            Training duration may vary depending on the volume of data, typically ranging from 1 to
            10 minutes.
          </div>
          <progress-bar mode="indeterminate" style="height: 6px" />
          <d-button v-if="isCancelAvailable" label="cancel" @click="$emit('cancel')" />
        </div>
      </div>
    </template>
  </d-dialog>
</template>

<script setup lang="ts">
import { ProgressBar } from 'primevue'
import UiLoader from '@/components/ui/UiLoader.vue'

type Props = {
  modelValue: boolean
  isCancelAvailable?: boolean
}
defineEmits<{
  (e: 'cancel'): void
  (e: 'update:modelValue', value: boolean): void
}>()

defineProps<Props>()
</script>

<style scoped>
.wrapper {
  padding: 48px;
  display: flex;
  align-items: center;
  gap: 60px;
  max-width: 901px;
  width: 100%;
}
.loader {
  padding: 80px;
}
.title {
  margin-bottom: 12px;
  font-size: 24px;
}
.text {
  margin-bottom: 28px;
  color: var(--p-text-muted-color);
  line-height: 1.18;
}
@media (max-width: 992px) {
  .wrapper {
    flex-direction: column;
    gap: 36px;
    max-width: 600px;
  }
  .loader {
    padding: 48px;
  }
}
</style>
