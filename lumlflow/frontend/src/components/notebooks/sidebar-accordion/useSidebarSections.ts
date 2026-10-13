import { computed } from 'vue'
import { FlaskConical, SquareCode, Timer, CircuitBoard } from 'lucide-vue-next'
import { useFlowStore } from '@/store/flow'
import NotebookAccordionCells from './NotebookAccordionCells.vue'
import NotebookAccordionExperiments from './NotebookAccordionExperiments.vue'
import NotebookAccordionModels from './NotebookAccordionModels.vue'
import NotebookAccordionActivities from './NotebookAccordionActivities.vue'

export function useSidebarSections() {
  const flowStore = useFlowStore()

  const experimentsCount = computed(
    () => flowStore.notebookCells.filter((cell) => cell.produces.includes('experiment')).length,
  )
  const modelsCount = computed(
    () => flowStore.notebookCells.filter((cell) => cell.produces.includes('model')).length,
  )

  return computed(() => [
    {
      icon: SquareCode,
      label: 'Cells',
      value: 'cells',
      count: flowStore.cells.length,
      component: NotebookAccordionCells,
    },
    {
      icon: FlaskConical,
      label: 'Experiments',
      value: 'experiments',
      count: experimentsCount.value,
      component: NotebookAccordionExperiments,
    },
    {
      icon: CircuitBoard,
      label: 'Models',
      value: 'models',
      count: modelsCount.value,
      component: NotebookAccordionModels,
    },
    {
      icon: Timer,
      label: 'Activities',
      value: 'activities',
      count: undefined,
      component: NotebookAccordionActivities,
    },
  ])
}
