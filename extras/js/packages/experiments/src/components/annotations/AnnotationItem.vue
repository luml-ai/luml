<template>
  <div class="wrapper" :class="{ expanded: isExpanded }">
    <div class="main" @click="toggle">
      <ChevronDown :size="16" class="chevron" color="var(--p-datatable-row-toggle-button-color)" />
      <div class="content">
        <div class="header-row">
          <div class="name">
            <ThumbsDown :size="16" color="var(--p-red-500)" class="icon" />
            AnnoName 2
          </div>
          <AnnotationOptions v-if="isEditable" @edit="$emit('edit')" @delete="$emit('delete')" />
        </div>
        <div class="row">
          <span class="username">UserName</span>
          <span class="date">1 day(s) ago</span>
        </div>
      </div>
    </div>
    <div class="secondary-info">
      <div class="row">
        <span>Boolean:</span>
        <span class="result">
          <ThumbsUp :size="16" />
          True
        </span>
      </div>
      <div class="description">
        This is an example of rationale. It shows how this field looks when there is a large amount
        of text.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import AnnotationOptions from './AnnotationOptions.vue'

interface Props {
  isEditable: boolean
}

interface Emits {
  (event: 'edit'): void
  (event: 'delete'): void
}

defineProps<Props>()
defineEmits<Emits>()

const isExpanded = ref(false)

function toggle() {
  isExpanded.value = !isExpanded.value
}
</script>

<style scoped>
.wrapper {
  border-radius: var(--p-card-border-radius);
  padding: 8px 12px;
  border: 1px solid transparent;
}

.expanded {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  box-shadow: var(--p-card-shadow);
}

.main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
}

.chevron {
  flex: 0 0 auto;
  margin: 6px 0;
}

.expanded .chevron {
  transform: rotate(180deg);
}

.content {
  flex: 1 1 auto;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.name {
  min-height: 26px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  margin-bottom: 4px;
}

.icon {
  flex: 0 0 auto;
}

.row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: space-between;
}

.username {
  color: var(--p-text-link-color);
  font-size: 12px;
}

.date {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.secondary-info {
  display: none;
  padding: 12px 0 0 22px;
}

.expanded .secondary-info {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.result {
  color: var(--p-green-500);
}

.description {
}
</style>
