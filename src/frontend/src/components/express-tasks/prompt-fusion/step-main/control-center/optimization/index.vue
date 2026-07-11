<template>
  <d-button
    ref="mainButton"
    severity="secondary"
    :disabled="disabled"
    @click="promptFusionService.changeOptimizationState(true)"
  >
    <span>optimization</span>
    <sliders-horizontal :size="14" />
  </d-button>
  <Transition>
    <Teleport to="body">
      <div
        v-if="visible"
        :options="{ ignore: [mainButton] }"
        class="sidebar-wrapper"
        @click.self="promptFusionService.changeOptimizationState(false)"
      >
        <div class="sidebar">
          <header class="header">
            <h2 class="dialog-title">
              <sliders-horizontal :size="20" color="var(--p-badge-secondary-color)" />
              Optimization settings
            </h2>
            <d-button
              severity="secondary"
              rounded
              variant="text"
              @click="promptFusionService.changeOptimizationState(false)"
            >
              <template #icon>
                <x width="16" height="16" color="var(--p-button-text-secondary-color)" />
              </template>
            </d-button>
          </header>
          <div class="body">
            <div class="description">
              <label class="description-label">task description</label>
              <CustomTextarea
                v-model="description"
                fluid
                rows="1"
                placeholder="Provide a short task description"
                size="small"
                autoResize
                :maxHeight="75"
                class="hint"
              />
            </div>
            <div class="teacher-model">
              <model-select
                title="teacher model"
                description="Model that provides reference outputs"
                :model-type="ModelTypeEnum.teacher"
              />
            </div>
            <div class="student-model">
              <model-select
                title="student model"
                description="Model being optimized"
                :model-type="ModelTypeEnum.student"
              />
            </div>
            <evaluation-metrics />
          </div>
          <footer class="footer">
            <div class="footer">
              <d-button as="a" label="Need help?" :href="helpLink" target="_blank" variant="text" />
              <d-button
                label="run optimization"
                severity="secondary"
                @click="onRunOptimizationClick"
              />
            </div>
          </footer>
        </div>
      </div>
    </Teleport>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue'
import { SlidersHorizontal, X } from 'lucide-vue-next'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { EvaluationModesEnum, ModelTypeEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { useConfirm, useToast } from 'primevue'
import { runOptimizationConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleSuccessToast, trainingErrorToast } from '@/lib/primevue/data/toasts'
import { useVueFlow } from '@vue-flow/core'
import CustomTextarea from '@/components/ui/CustomTextarea.vue'
import ModelSelect from './ModelSelect.vue'
import EvaluationMetrics from './EvaluationMetrics.vue'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'

const confirm = useConfirm()
const toast = useToast()
const { toObject } = useVueFlow()

type Props = {
  disabled: boolean
}

defineProps<Props>()

const mainButton = ref()
const visible = ref(false)
const description = ref(promptFusionService.taskDescription)

const helpLink = computed(() => `${import.meta.env.VITE_DOCS_URL}/task-guides/prompt-optimization`)

function onChangeOptimizationState(isOpen: boolean) {
  visible.value = isOpen
}
function onRunOptimizationClick() {
  const vueFlowObject = toObject()
  try {
    promptFusionService.prepareData(vueFlowObject)
    promptFusionService.checkIsOptimizationAvailable()
    confirm.require(runOptimizationConfirmOptions(runOptimization))
  } catch (e: unknown) {
    const error = e as Error
    promptFusionService.endTraining()
    toast.add(trainingErrorToast(error.message as string))
  }
}
async function runOptimization() {
  const teacher_model = promptFusionService.teacherModel as string
  const student_model = promptFusionService.studentModel as string
  let evaluation_metrics = ''
  switch (promptFusionService.evaluationMode) {
    case EvaluationModesEnum.exactMatch:
      evaluation_metrics = 'exact_match'
    case EvaluationModesEnum.llmBased:
      evaluation_metrics = 'llm_based'
    default:
      evaluation_metrics = 'none'
  }
  AnalyticsService.track(AnalyticsTrackKeysEnum.run_optimization, {
    task: 'prompt_optimization',
    teacher_model,
    student_model,
    evaluation_metrics,
  })
  try {
    await promptFusionService.runOptimization()
    toast.add(simpleSuccessToast('Your model is successfully trained'))
  } catch (e) {
    toast.add(trainingErrorToast(e as string))
  }
}

watch(description, (val) => {
  promptFusionService.taskDescription = val
})

onBeforeMount(() => {
  promptFusionService.on('CHANGE_OPTIMIZATION_STATE', onChangeOptimizationState)
})
onBeforeUnmount(() => {
  promptFusionService.off('CHANGE_OPTIMIZATION_STATE', onChangeOptimizationState)
})
</script>

<style scoped>
.sidebar-wrapper {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 10;
}
.sidebar {
  position: fixed;
  top: 136px;
  bottom: 44px;
  right: 16px;
  width: 100%;
  max-width: 420px;
  padding: 24px 20px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.header {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
}
.body {
  flex: 1 1 auto;
  overflow-y: auto;
}
.footer {
  flex: 0 0 auto;
}
.dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0.16px;
  text-transform: uppercase;
}
.description {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}
.description-label {
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.12px;
}
.description-label::after {
  content: ' *';
  color: var(--p-badge-warn-background);
}
.teacher-model {
  margin-bottom: 20px;
}
.student-model {
  margin-bottom: 20px;
}
.footer {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 15px;
}
.v-enter-active,
.v-leave-active {
  transition: transform 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  transform: translateX(100%);
}
</style>
