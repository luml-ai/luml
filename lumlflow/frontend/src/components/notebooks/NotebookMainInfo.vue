<template>
  <div class="wrapper">
    <div class="content">
      <div class="heading">
        <div
          class="heading-left"
          :style="{
            display: flowStore.isSidebarOpened ? 'flex' : 'none',
          }"
        >
          <span>Test-1</span>
          <Tag severity="success">
            <CircleQuestionMark :size="10" />
            Setteled
          </Tag>
        </div>
        <div class="heading-right">
          <button class="heading-right-button" @click="flowStore.toggleSidebar">
            <ArrowRightToLine :size="14" :class="{ 'rotate-180': flowStore.isSidebarOpened }" />
          </button>
        </div>
      </div>
      <div
        class="description"
        :class="{
          hidden: !flowStore.isSidebarOpened,
        }"
      >
        started from test · 0 steps ago viewing · the files stay on main
      </div>
    </div>
    <NotebooksLanes v-if="flowStore.isSidebarOpened" />
    <SidebarTooltipPlug
      v-else
      class="border-t border-surface"
      tooltip="What is this?"
      label="Lanes"
    />
  </div>
</template>

<script setup lang="ts">
import { ArrowRightToLine, CircleQuestionMark } from 'lucide-vue-next'
import { Tag } from 'primevue'
import { useFlowStore } from '@/store/flow'
import NotebooksLanes from '@/components/notebooks/lanes/NotebooksLanes.vue'
import SidebarTooltipPlug from '@/components/notebooks/SidebarTooltipPlug.vue'

const flowStore = useFlowStore()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.wrapper {
  @apply bg-(--p-card-background) border border-surface rounded-lg shadow-(--p-card-shadow) overflow-hidden;
}
.content {
  @apply py-4 px-5 min-h-[100px];
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
  @apply p-0 cursor-pointer hover:text-primary-600 transition-colors h-6.25;
}
.description {
  @apply text-sm text-muted-color;
}
</style>
