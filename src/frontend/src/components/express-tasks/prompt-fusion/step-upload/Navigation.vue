<template>
  <div class="navigation">
    <d-button severity="secondary" @click="$router.back()">Back</d-button>
    <d-button :disabled="!isNextStepAvailable" @click="$emit('continue')">
      <span>Continue</span>
      <arrow-right :size="14" />
    </d-button>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'

type Props = {
  isNextStepAvailable: boolean
}
type Emits = {
  continue: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.navigation {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  gap: 24px;
  background-color: var(--p-content-background);
  position: fixed;
  bottom: 0;
  left: 0;
  padding: 5px 100px 44px 0;
}
</style>
