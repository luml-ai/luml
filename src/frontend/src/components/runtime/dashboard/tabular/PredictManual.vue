<template>
  <div class="manual-wrapper disabled">
    <div class="inputs">
      <div v-for="field in Object.keys(manualValues)" :key="field" class="input-wrapper">
        <d-float-label variant="on">
          <d-input-text
            v-model="manualValues[field as keyof typeof manualValues]"
            :id="field"
            fluid
          />
          <label class="label" :for="field">{{ cutStringOnMiddle(field, 24) }}</label>
        </d-float-label>
      </div>
    </div>
    <d-button
      label="Predict"
      type="submit"
      fluid
      rounded
      :disabled="isPredictButtonDisabled"
      @click="submit"
    />
    <Textarea
      class="prediction"
      id="prediction"
      v-model="prediction"
      fluid
      rows="4"
      :style="{ resize: 'none' }"
      disabled
      placeholder="Prediction"
    ></Textarea>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Textarea } from 'primevue'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { predictErrorToast } from '@/lib/primevue/data/toasts'
import { useToast } from 'primevue'

const toast = useToast()

type Props = {
  inputNames: string[]
  predictCallback: (data: Record<string, (string | number)[]>) => Promise<unknown>
}

const props = defineProps<Props>()

const manualValues = ref(createManualValuesObject(props.inputNames))
const isLoading = ref(false)
const prediction = ref('')

const isPredictButtonDisabled = computed(() => {
  for (const key in manualValues.value) {
    if (!manualValues.value[key]) return true
  }
  return isLoading.value
})

function createManualValuesObject(inputs: string[]) {
  return inputs.reduce<Record<string, string>>((acc, input) => {
    acc[input] = ''
    return acc
  }, {})
}
async function submit() {
  isLoading.value = true
  try {
    const data: Record<string, (string | number)[]> = {}
    for (const key in manualValues.value) {
      data[key] = [manualValues.value[key]]
    }
    const predictionResult = (await props.predictCallback(data)) as (string | number)[] | undefined
    if (predictionResult) prediction.value = predictionResult.join(', ')
  } catch (e) {
    toast.add(predictErrorToast(e as string))
  } finally {
    isLoading.value = false
  }
}

watch(
  manualValues,
  () => {
    prediction.value = ''
  },
  { deep: true },
)
</script>

<style scoped>
.manual-wrapper {
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 13px;
  max-height: 310px;
  overflow-y: auto;
  padding-top: 28px;
}
.prediction:disabled {
  background-color: var(--p-textarea-background) !important;
  color: var(--p-textarea-color);
}

.prediction.p-filled {
  border: 1px solid var(--p-textarea-focus-border-color);
  background-color: var(--p-textarea-filled-background) !important;
  font-weight: 500 !important;
}
</style>
