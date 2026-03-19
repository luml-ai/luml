<template>
  <Form
    ref="form"
    v-slot="$form"
    id="annotation-edit-form"
    :initialValues="formInitialValues"
    :resolver="RESOLVER"
    class="form"
    @submit="onSubmit"
  >
    <FormField name="type" class="form-field">
      <label for="type">Annotation type</label>
      <SelectButton
        name="type"
        id="type"
        :options="TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        :disabled="isEdit"
        :allow-empty="false"
        @change="() => onTypeChange()"
      >
        <template #option="slotProps">
          <div class="option-item">
            <component
              v-if="TYPE_ICONS[slotProps.option.value as AnnotationKind]"
              :is="TYPE_ICONS[slotProps.option.value as AnnotationKind].icon"
              :color="TYPE_ICONS[slotProps.option.value as AnnotationKind].iconColor"
              :size="16"
            />
            <span>{{ slotProps.option.label }}</span>
          </div>
        </template>
      </SelectButton>
    </FormField>
    <FormField name="name" class="form-field">
      <label for="name">Annotation name</label>
      <AutoComplete
        name="name"
        id="name"
        placeholder="Enter an annotation name"
        fluid
        :suggestions="nameSuggestions"
        :disabled="isEdit"
        @complete="nameSearch"
      />
    </FormField>
    <FormField name="dataType" class="form-field">
      <label for="dataType">Data type</label>
      <Select
        name="dataType"
        id="dataType"
        :options="DATA_TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        :disabled="$form.type?.value === AnnotationKind.FEEDBACK || isEdit"
        @change="() => onDataTypeChange()"
      />
    </FormField>
    <AnnotationFormValue
      v-if="$form.dataType?.value"
      :type="$form.dataType.value"
      :value="$form.value?.value"
    />
    <FormField name="rationale" class="form-field">
      <label for="rationale">Rationale</label>
      <InputText name="rationale" id="rationale" placeholder="Enter a rationale" />
    </FormField>
  </Form>
</template>

<script setup lang="ts">
import { Form, FormField, type FormSubmitEvent, type FormInstance } from '@primevue/forms'
import {
  SelectButton,
  InputText,
  Select,
  AutoComplete,
  type AutoCompleteCompleteEvent,
} from 'primevue'
import { INITIAL_VALUES, RESOLVER, TYPE_OPTIONS, TYPE_ICONS, DATA_TYPE_OPTIONS } from './data'
import { AnnotationValueType, AnnotationKind, type Annotation } from '../annotations.interface'
import { ref } from 'vue'
import AnnotationFormValue from './AnnotationFormValue.vue'

interface Props {
  data?: Annotation
  isEdit?: boolean
  existingNames: string[]
}

interface Emits {
  (event: 'submit', data: any): void
}

const props = defineProps<Props>()

const emits = defineEmits<Emits>()

const nameSuggestions = ref<string[] | undefined>(
  props.existingNames.length ? props.existingNames : undefined,
)

const formInitialValues = props.data
  ? {
      type: props.data.annotation_kind,
      name: props.data.name,
      dataType: props.data.value_type,
      value: props.data.value,
      rationale: props.data.rationale,
    }
  : INITIAL_VALUES

const form = ref<FormInstance>()

function onTypeChange() {
  const type = form.value?.getFieldState('type')?.value

  if (type === AnnotationKind.FEEDBACK) {
    form.value?.setFieldValue('dataType', AnnotationValueType.BOOL)
  }
}

function onDataTypeChange() {
  const dataType = form.value?.getFieldState('dataType')?.value
  if (dataType === AnnotationValueType.BOOL) {
    form.value?.setFieldValue('value', true)
  } else if (dataType === AnnotationValueType.STRING) {
    form.value?.setFieldValue('value', '')
  } else if (dataType === AnnotationValueType.INT) {
    form.value?.setFieldValue('value', 0)
  }
}

function onSubmit(event: FormSubmitEvent) {
  const { valid, values } = event
  if (!valid) return
  emits('submit', values)
}

function nameSearch(event: AutoCompleteCompleteEvent) {
  const suggestions = props.existingNames.filter((name) =>
    name.toLowerCase().includes(event.query.toLowerCase()),
  )
  nameSuggestions.value = suggestions.length ? suggestions : undefined
}
</script>

<style scoped>
.option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
