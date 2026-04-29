<template>
  <div>
    <div v-if="isEmpty">-</div>
    <div v-else v-tooltip.top="valueText" class="cell">
      {{ valueText }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { valueToString } from '@/helpers/texts'
import { computed } from 'vue'

interface Props {
  value: any
}

const props = defineProps<Props>()

const valueText = computed(() => valueToString(props.value))

const isEmpty = computed(
  () => props.value === null || props.value === undefined || props.value === '',
)
</script>

<style scoped>
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
</style>
