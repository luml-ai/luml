<template>
  <div class="plug">
    <p class="plug__text">{{ text }}</p>
    <button type="button" class="plug__button" @click="$emit('close')">
      <X :size="16" class="plug__icon" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'

type Props = {
  text: string
}
type Emits = {
  close: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.plug {
  padding: 12px 16px;
  display: flex;
  align-items: flex-start;
  gap: 18px;
  background-color: var(--p-content-color);
  color: var(--p-inputtext-filled-background);
}

.plug__text {
  flex: 1 1 auto;
  gap: 48px;
  font-size: 12px;
  text-align: center;
  font-weight: 500;
}

.plug__button {
  padding: 0;
  width: 14px;
  height: 14px;
  cursor: pointer;
  transition: transform 0.3s;
}

.plug__button:hover {
  transform: scale(1.2);
}

.plug__icon {
  color: var(--p-button-text-secondary-active-background);
}
</style>
