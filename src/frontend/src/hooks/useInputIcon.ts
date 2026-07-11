import { X, PencilLine } from 'lucide-vue-next'
import { computed, onMounted, ref, type Ref } from 'vue'

export const useInputIcon = (
  inputs: Ref[],
  formRef: Ref<{ states: Record<string, { value: string }> }>,
  values: Ref,
  isShowEditIcon: boolean = true,
) => {
  const inputsStates = ref<Record<string, boolean>>({})
  const inputsRefs = ref<Record<string, HTMLInputElement>>({})

  const getCurrentInputIcon = computed(() => (inputName: string) => {
    if (inputsStates.value[inputName]) return X
    else return isShowEditIcon ? PencilLine : null
  })

  function setInputState(inputName: string, state: boolean) {
    setTimeout(() => {
      inputsStates.value[inputName] = state
    }, 200)
  }

  function onIconClick(inputName: string) {
    if (getCurrentInputIcon.value(inputName) === X && formRef.value?.states[inputName]) {
      formRef.value.states[inputName] = { ...formRef.value.states[inputName], value: '' }

      if (values.value[inputName]) values.value[inputName] = ''
    }
  }

  onMounted(() => {
    inputs.reduce((obj: Record<string, HTMLInputElement>, input) => {
      if (!input.value) return obj

      const el = input.value.$el as HTMLInputElement

      el.onblur = () => setInputState(el.name, false)
      el.onfocus = () => setInputState(el.name, true)

      obj[el.name] = el
      inputsStates.value[el.name] = false
      return obj
    }, inputsRefs.value)
  })

  return { getCurrentInputIcon, onIconClick }
}
