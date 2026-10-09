<template>
  <div class="evaluation">
    <h3 class="title">Evaluation metrics</h3>
    <div class="description">Choose a model evaluation metric</div>
    <div class="modes">
      <ui-custom-radio
        v-model="mode"
        :options="Object.values(EvaluationModesEnum)"
        :disabled="disabledMetrics"
        style="display: inline-flex"
      />
    </div>
    <div v-if="mode === EvaluationModesEnum.llmBased" class="based-info">
      <ul class="criteria-list">
        <li v-for="criteria in criteriaList" :key="criteria.id" class="criteria-item">
          <d-input-text
            v-model="criteria.value"
            placeholder="Criteria"
            size="small"
            class="criteria-input"
          />
          <d-button
            severity="secondary"
            variant="text"
            rounded
            class="criteria-trash"
            @click="() => removeCriteria(criteria.id)"
          >
            <template #icon>
              <trash2 :size="14" />
            </template>
          </d-button>
        </li>
      </ul>
      <d-button label="Add evaluation criteria" variant="text" size="small" @click="addCriteria">
        <template #icon>
          <plus :size="14" />
        </template>
      </d-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { EvaluationModesEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { Trash2, Plus } from 'lucide-vue-next'
import { v4 as uuid4 } from 'uuid'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import UiCustomRadio from '@/components/ui/UiCustomRadio.vue'
import { useRoute } from 'vue-router'

type CriteriaItem = {
  id: string
  value: string
}

const route = useRoute()

const mode = ref<EvaluationModesEnum>(promptFusionService.evaluationMode)
const criteriaList = ref<CriteriaItem[]>(getInitialCriteriaList())

const disabledMetrics = computed(() =>
  route.params.mode === 'data-driven'
    ? []
    : [EvaluationModesEnum.exactMatch, EvaluationModesEnum.llmBased],
)

function getInitialCriteriaList() {
  return promptFusionService.evaluationCriteriaList.length
    ? promptFusionService.evaluationCriteriaList.map((value) => createCriteria(value))
    : [createCriteria()]
}
function createCriteria(value = '') {
  return { id: uuid4(), value }
}
function addCriteria() {
  criteriaList.value.push(createCriteria())
}
function removeCriteria(id: string) {
  criteriaList.value = criteriaList.value.filter((criteria) => criteria.id !== id)
}

watch(
  mode,
  (val) => {
    promptFusionService.evaluationMode = val
    if (val === EvaluationModesEnum.llmBased) criteriaList.value = [createCriteria()]
    else criteriaList.value = []
  },
  {},
)
watch(
  criteriaList,
  (val) => {
    promptFusionService.evaluationCriteriaList = val.map((criteria) => criteria.value)
  },
  { deep: true },
)
</script>

<style scoped>
.evaluation {
  padding: 8px;
}
.title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}
.description {
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.modes {
  margin-bottom: 18px;
}
.criteria-list {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.criteria-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.criteria-input {
  flex: 1 1 auto;
}
.criteria-trash {
  flex: 0 0 auto;
}
</style>
