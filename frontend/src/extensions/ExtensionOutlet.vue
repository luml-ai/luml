<template>
  <template v-if="components.length">
    <component
      :is="component"
      v-for="(component, index) in components"
      :key="index"
      v-bind="$attrs"
    />
  </template>
  <slot v-else></slot>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { outletRegistryKey } from '.'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ name: string }>()

const outlets = inject(outletRegistryKey, new Map())

const components = computed(() => outlets.get(props.name) ?? [])
</script>
