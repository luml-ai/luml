<template>
  <div class="row">
    <div>
      <label for="field" class="label">Field</label>
      <Select
        v-model="modelValue.field"
        id="field"
        placeholder="Choose field"
        fluid
        size="small"
        :options="props.fields"
      />
    </div>
    <div>
      <label for="operator" class="label">Operator</label>
      <Select
        v-model="modelValue.operator"
        id="operator"
        fluid
        size="small"
        :options="FILTER_OPERATORS"
        option-label="label"
        option-value="value"
      />
    </div>
    <div>
      <label for="value" class="label">Operator</label>
      <InputText v-model="modelValue.value" id="value" placeholder="Put value" fluid size="small" />
    </div>
    <Button variant="text" severity="secondary" class="button" @click="$emit('remove')">
      <template #icon>
        <X :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import type { FilterItem, FilterItemEmits, FilterItemProps } from './filter.interface'
import { InputText, Select, Button } from 'primevue'
import { X } from 'lucide-vue-next'
import { FILTER_OPERATORS } from './filter.const'

const props = defineProps<FilterItemProps>()

defineEmits<FilterItemEmits>()

const modelValue = defineModel<FilterItem>('modelValue', { required: true })
</script>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 180px 80px 180px 35px;
  gap: 13px;
  align-items: flex-end;
}

.label {
  font-size: 14px;
  margin-bottom: 7px;
  display: inline-block;
}

.button {
  width: 27px;
  height: 27px;
}
</style>
