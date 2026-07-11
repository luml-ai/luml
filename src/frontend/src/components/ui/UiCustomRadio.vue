<template>
  <div class="app-custom-radio">
    <label
      v-for="option in options"
      :key="option"
      :for="id + option"
      class="app-custom-radio-label"
    >
      <input
        type="radio"
        :name="id"
        :id="id + option"
        :value="option"
        :disabled="disabled.includes(option)"
        :checked="option === modelValue"
        class="app-custom-radio-input"
        @change="$emit('update:modelValue', option)"
      />
      <span class="app-custom-radio-value">{{ option }}</span>
    </label>
  </div>
</template>

<script setup lang="ts">
import { useId } from 'vue'

const id = useId()

type Props = {
  modelValue: unknown
  options: string[]
  disabled?: string[]
}
type Emits = {
  'update:modelValue': [string]
}

withDefaults(defineProps<Props>(), {
  disabled: () => [],
})
defineEmits<Emits>()
</script>

<style scoped>
.app-custom-radio {
  padding: 5px 4px;
  border-radius: var(--p-togglebutton-border-radius);
  background-color: var(--p-togglebutton-checked-background);
  display: flex;
}
.app-custom-radio-label {
  position: relative;
  cursor: pointer;
}
.app-custom-radio-label:has(input:disabled) {
  cursor: not-allowed;
  opacity: 0.5;
}
.app-custom-radio-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 0;
  height: 0;
  opacity: 0;
}
.app-custom-radio-value {
  position: relative;
  padding: 3.5px 10.5px;
  font-size: 12px;
  color: var(--p-togglebutton-color);
  font-weight: 600;
  border-radius: var(--p-togglebutton-border-radius);
  display: block;
  overflow: hidden;
  z-index: 2;
}
.app-custom-radio-value::before {
  content: '';
  z-index: -1;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  transition: opacity 0.3s;
  opacity: 0;
  background-color: var(--p-togglebutton-content-checked-background);
}
.app-custom-radio-input:checked + .app-custom-radio-value {
  color: var(--p-togglebutton-checked-color);
}
.app-custom-radio-input:checked + .app-custom-radio-value::before {
  opacity: 1;
}
</style>
