<template>
  <div class="wrapper">
    <Button
      v-tooltip.left="'Clear'"
      class="clear-button"
      severity="secondary"
      variant="text"
      @click="onClear"
    >
      <template #icon>
        <Eraser :size="14" />
      </template>
    </Button>
    <Terminal
      ref="terminalRef"
      welcome-message="scratch — evaluates code against copies of the current branch's values"
      prompt=">"
      class="h-full!"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Button } from 'primevue'
import { Eraser } from 'lucide-vue-next'
import { useFlowStore } from '@/store/flow'
import { NOTEBOOK_TERMINAL_HEIGHT } from '@/components/notebooks/notebooks.const'
import Terminal from 'primevue/terminal'
import TerminalService from 'primevue/terminalservice'

const flowStore = useFlowStore()

const terminalHeight = `${NOTEBOOK_TERMINAL_HEIGHT}px`
const terminalRef = ref<{ commands: { text: string; response?: string }[] } | null>(null)

function formatResponse(result: Awaited<ReturnType<typeof flowStore.evalScratch>>): string {
  if (result.error) return `${result.error.type}: ${result.error.message}`
  const output = result.output.replace(/\n$/, '')
  const parts = [output, result.repr].filter((part): part is string => !!part)
  return parts.join('\n')
}

async function onCommand(code: string) {
  try {
    const result = await flowStore.evalScratch(code)
    TerminalService.emit('response', formatResponse(result))
  } catch (error) {
    TerminalService.emit('response', error instanceof Error ? error.message : String(error))
  }
}

function onClear() {
  flowStore.terminalHistory.length = 0
}

onMounted(() => {
  if (terminalRef.value) terminalRef.value.commands = flowStore.terminalHistory
  TerminalService.on('command', onCommand)
})

onBeforeUnmount(() => {
  TerminalService.off('command', onCommand)
})
</script>

<style scoped>
.wrapper {
  position: relative;
  height: v-bind(terminalHeight);
  overflow-y: auto;
  margin-bottom: 8px;
}

.clear-button {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 10;
  padding: 0;
  width: 2rem;
  height: 2rem;
}
</style>
