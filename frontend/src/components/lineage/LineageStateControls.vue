<template>
  <div class="buttons">
    <Button
      severity="secondary"
      label="Save changes"
      v-tooltip.top="`${isMac ? '⌘' : 'Ctrl'}+S`"
      class="button"
      :loading="saveLoading"
      :disabled="lineageStore.history.length === 0"
      @click="onSave"
    />
    <Button
      severity="secondary"
      v-tooltip.top="`${isMac ? '⌘' : 'Ctrl'}+Z`"
      class="button light-button"
      :disabled="lineageStore.history.length === 0"
      @click="onBack"
    >
      <template #icon>
        <Undo :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useLineageStore } from '@/stores/lineage'
import { Undo } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { onMounted, onUnmounted, ref } from 'vue'
import { getErrorMessage } from '@/helpers/helpers'

const isMac = navigator.platform.toUpperCase().includes('MAC')
const lineageStore = useLineageStore()
const toast = useToast()

const saveLoading = ref(false)

async function onSave() {
  saveLoading.value = true
  try {
    await lineageStore.save()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    saveLoading.value = false
  }
}

function onBack() {
  lineageStore.goBack()
}

function onKeydown(e: KeyboardEvent) {
  const hotkey = isMac ? e.metaKey : e.ctrlKey
  if (hotkey && e.key === 's') {
    e.preventDefault()
    onSave()
  }
  if (hotkey && e.key === 'z') {
    e.preventDefault()
    onBack()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}
.button {
  box-shadow: var(--card-shadow);
}
.light-button {
  background-color: var(--p-card-background) !important;
  border-color: transparent;
}
</style>
