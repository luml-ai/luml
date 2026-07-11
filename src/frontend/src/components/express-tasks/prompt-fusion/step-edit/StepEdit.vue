<template>
  <div class="step">
    <slot></slot>
    <div class="navigation">
      <d-button label="Back" severity="secondary" @click="$emit('back')" />
      <d-button @click="$emit('continue')">
        <span style="font-weight: 500">Continue</span>
        <arrow-right width="14" height="14" />
      </d-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'

type Emits = {
  back: []
  continue: []
}

defineEmits<Emits>()
</script>

<style scoped>
.step {
  padding-top: 32px;
}
.navigation {
  padding-top: 20px;
  display: flex;
  gap: 24px;
  justify-content: flex-end;
}
@media (max-height: 1050px) {
  .navigation {
    position: fixed;
    bottom: 0;
    right: 0;
    background-color: var(--p-content-background);
    padding-top: 4px;
    padding-bottom: 44px;
    padding-right: 105px;
    width: 100%;
    z-index: 5;
  }
}
@media (max-width: 968px) {
  .navigation {
    position: fixed;
    bottom: 0;
    right: 0;
    background-color: var(--p-content-background);
    padding-top: 4px;
    padding-bottom: 44px;
    padding-right: 105px;
    width: 100%;
    z-index: 5;
  }
}
@media (max-width: 768px) {
  .navigation {
    padding-right: 15px;
  }
}
</style>
