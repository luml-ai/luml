<template>
  <span
    class="id"
    :class="{
      'id--button': variant === 'button',
    }"
  >
    <span>{{ formattedId }}</span>
    <UiCopyButton :text="id"></UiCopyButton>
  </span>
</template>

<script setup lang="ts">
import { cutStringOnMiddle } from '@/helpers/helpers'
import { computed } from 'vue'
import UiCopyButton from './UiCopyButton.vue'

type Props = {
  id: string
  variant?: 'text' | 'button'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'text',
})

const formattedId = computed(() => cutStringOnMiddle(props.id, 8))
</script>

<style scoped>
.id {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  font-size: 12px;
  flex: 0 0 auto;
}

.id--button {
  padding: 4px 8px;
  border-radius: var(--p-border-radius-lg);
  background-color: var(--p-card-background);
}
</style>
