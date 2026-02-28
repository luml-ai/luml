<template>
  <div class="view">
    <AnnotationsViewHeader @close="$emit('close')" />
    <AnnotationsViewList v-if="annotations.length" :items="annotations" />
    <div v-else class="empty">
      <div class="card-wrapper">
        <AnnotationAddCard @add="onAdd" />
      </div>
      <AnnotationAddButton @add="onAdd" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AnnotationsViewHeader from './AnnotationsViewHeader.vue'
import AnnotationsViewList from './AnnotationsViewList.vue'
import AnnotationAddCard from './AnnotationAddCard.vue'
import AnnotationAddButton from './AnnotationAddButton.vue'

interface Emits {
  (event: 'close'): void
}

defineEmits<Emits>()

const annotations = ref([{ id: 1 }, { id: 2 }, { id: 3 }])

function onAdd() {
  console.log('addAnnotation')
}
</script>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  flex: 0 0 auto;
  width: 434px;
  padding: 0 20px;
}

.view:not(:last-child) {
  border-right: 1px solid var(--p-divider-border-color);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex: 1 1 auto;
  padding-bottom: 20px;
}

.card-wrapper {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-self: center;
}
</style>
