<template>
  <div class="wrapper">
    <div class="content">
      <div class="heading">
        <div class="heading-left">
          <span>Test-1</span>
          <Tag severity="success">
            <CircleQuestionMark :size="10" />
            Setteled
          </Tag>
        </div>
        <div class="heading-right">
          <button class="heading-right-button">
            <ArrowLeftToLine :size="14" />
          </button>
        </div>
      </div>
      <div class="description">
        started from test · 0 steps ago viewing · the files stay on main
      </div>
    </div>
    <NotebooksLanes />
  </div>
</template>

<script setup lang="ts">
import { ArrowLeftToLine, CircleQuestionMark } from 'lucide-vue-next'
import { Tag } from 'primevue'
import NotebooksLanes from '@/components/notebooks/lanes/NotebooksLanes.vue'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.wrapper {
  @apply bg-(--p-card-background) border border-surface rounded-lg shadow-(--p-card-shadow) overflow-hidden;
}
.content {
  @apply py-4 px-5;
}
.heading {
  @apply flex items-center justify-between mb-2;
}
.heading-left {
  @apply flex items-center gap-1.5;
}
.heading-right {
}
.heading-right-button {
  @apply p-0 cursor-pointer hover:text-primary-600 transition-colors;
}
.description {
  @apply text-sm text-muted-color;
}
</style>
