<template>
  <div class="wrapper">
    <LineageHeading v-if="isMaximized" title="Lineage" class="heading"></LineageHeading>
    <LineageToolbar class="toolbar"></LineageToolbar>
    <LineageStateControls class="state-controls"></LineageStateControls>
    <LineageActions class="actions" v-model:is-maximized="isMaximized"></LineageActions>
    <LineageArea></LineageArea>
  </div>
</template>

<script setup lang="ts">
import { useVueFlow } from '@vue-flow/core'
import LineageStateControls from './LineageStateControls.vue'
import LineageToolbar from './LineageToolbar.vue'
import LineageArea from './LineageArea.vue'
import LineageActions from './LineageActions.vue'
import LineageHeading from './LineageHeading.vue'

const {} = useVueFlow()

const isMaximized = defineModel('isMaximized', { default: false })
</script>

<style scoped>
.wrapper {
  height: 100%;
  position: relative;
}

.toolbar {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
}

.state-controls {
  position: absolute;
  left: 20px;
  bottom: 28px;
  z-index: 10;
}

.actions {
  position: absolute;
  right: 20px;
  top: 28px;
  z-index: 10;
}

.heading {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 10;
}
</style>
