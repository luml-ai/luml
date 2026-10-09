<template>
  <div class="controls">
    <div class="buttons">
      <Button
        severity="secondary"
        label="Save changes"
        v-tooltip.top="saveTooltip"
        class="button"
        :loading="saveLoading"
        :disabled="
          !lineageStore.isEditable ||
          !lineageStore.hasEdits ||
          lineageStore.unconnectedArtifactsCount > 0
        "
        @click="onSave"
      />
      <Button
        severity="secondary"
        v-tooltip.top="`${isMac ? '⌘' : 'Ctrl'}+Z`"
        class="button light-button"
        :disabled="!lineageStore.isEditable || lineageStore.history.length === 0"
        @click="onBack"
      >
        <template #icon>
          <Undo :size="14" />
        </template>
      </Button>
    </div>
    <div v-if="saveBlocker" class="save-blocker">{{ saveBlocker }}</div>
  </div>
</template>

<script setup lang="ts">
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useLineageStore } from '@/stores/lineage'
import { Undo } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getErrorMessage } from '@/helpers/helpers'

const isMac = navigator.platform.toUpperCase().includes('MAC')
const lineageStore = useLineageStore()
const toast = useToast()

const saveLoading = ref(false)
const saveBlocker = computed(() => {
  const count = lineageStore.unconnectedArtifactsCount
  return count > 0 ? `${count} artifacts are not connected — connect or remove them` : null
})
const saveTooltip = computed(() => {
  return saveBlocker.value ?? `${isMac ? '⌘' : 'Ctrl'}+S`
})

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

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

function onKeydown(e: KeyboardEvent) {
  // Typing in a dialog field must not undo or save the canvas.
  if (isTypingTarget(e.target)) return
  const hotkey = isMac ? e.metaKey : e.ctrlKey
  if (hotkey && e.key.toLowerCase() === 's') {
    e.preventDefault()
    onSave()
  }
  if (hotkey && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    onBack()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.controls {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
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
.save-blocker {
  max-width: 320px;
  padding: 6px 9px;
  border-radius: 6px;
  color: var(--p-text-muted-color);
  background: var(--p-card-background);
  box-shadow: var(--card-shadow);
  font-size: 12px;
}
</style>
