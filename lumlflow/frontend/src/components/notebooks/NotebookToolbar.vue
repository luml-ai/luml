<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <NotebookCellCreator />
      <Button
        variant="text"
        :severity="flowStore.isTerminalOpen ? 'primary' : 'secondary'"
        @click="flowStore.toggleTerminal()"
      >
        <Terminal :size="14" />
        {{ flowStore.isTerminalOpen ? 'Hide Scratch' : 'Scratch' }}
      </Button>
    </div>
    <div class="toolbar-right">
      <Button
        v-if="isRerunning"
        variant="text"
        severity="danger"
        :loading="isStopping"
        :disabled="isStopping"
        @click="onStopSession"
      >
        <Pause :size="14" />
        Stop session
      </Button>
      <Button variant="text" :loading="isRerunning" :disabled="isRerunning" @click="onRerunLane">
        <Play :size="14" />
        Rerun lane
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Pause, Play, Terminal } from 'lucide-vue-next'
import { Button } from 'primevue'
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import NotebookCellCreator from '@/components/notebooks/cell/NotebookCellCreator.vue'

const toast = useToast()

const flowStore = useFlowStore()

const isRerunning = ref(false)
const isStopping = ref(false)

async function onRerunLane() {
  isRerunning.value = true
  try {
    const result = await flowStore.runLane()
    if (result.targets.length === 0) {
      toast.add(successToast('Nothing to rerun in this lane'))
    } else if (result.failed) {
      toast.add(errorToast(new Error(`\`${result.failed}\` failed to run`), 'Rerun failed'))
    } else {
      toast.add(
        successToast(
          `Reran lane: ${result.executed.length} executed, ${result.cached.length} cached`,
        ),
      )
    }
  } catch (error) {
    toast.add(errorToast(error, 'Failed to rerun lane'))
  } finally {
    isRerunning.value = false
  }
}

async function onStopSession() {
  isStopping.value = true
  try {
    const result = await flowStore.stopSession()
    if (result.left === 0) {
      toast.add(successToast('Nothing was running on this lane'))
    } else if (result.stopped) {
      toast.add(successToast('Session stopped'))
    } else {
      toast.add(
        successToast(
          `Left the run — still awaited by ${result.awaiting} other lane${result.awaiting === 1 ? '' : 's'}`,
        ),
      )
    }
  } catch (error) {
    toast.add(errorToast(error, 'Failed to stop session'))
  } finally {
    isStopping.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.toolbar {
  @apply flex items-center justify-between gap-2;
}

.toolbar-left {
  @apply flex items-center gap-2;
}

.toolbar-right {
  @apply flex items-center gap-4;
}
</style>
