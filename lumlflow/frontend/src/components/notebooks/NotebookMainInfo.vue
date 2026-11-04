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
          <span>{{ flowStore.currentBranch?.branch }}</span>
          <Tag v-if="health" :severity="health.severity" v-tooltip.bottom="health.tooltip">
            <component
              :is="health.icon"
              :size="10"
              :class="{ 'animate-spin': flowStore.laneHealth === 'running' }"
            />
            {{ health.label }}
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
        {{ flowStore.currentBranchFamilyLine }}
      </div>
    </div>
    <template v-if="flowStore.isSidebarOpened">
      <NotebookLanesSteps />
      <NotebooksLanes />
    </template>

    <template v-else>
      <SidebarTooltipPlug
        class="border-t border-surface"
        :icon="History"
        :tooltip="`Lanes (${flowStore.branches.length})`"
        label="Lanes"
      />
      <SidebarTooltipPlug
        class="border-t border-surface"
        :icon="ListTree"
        :tooltip="`Lanes (${flowStore.branches.length})`"
        label="Lanes"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ArrowRightToLine, History, ListTree } from 'lucide-vue-next'
import { Tag } from 'primevue'
import { computed } from 'vue'
import { useFlowStore } from '@/store/flow'
import { NOTEBOOK_HEALTH } from '@/components/notebooks/notebooks.const'
import NotebooksLanes from '@/components/notebooks/lanes/NotebooksLanes.vue'
import SidebarTooltipPlug from '@/components/notebooks/SidebarTooltipPlug.vue'
import NotebookLanesSteps from '@/components/notebooks/lanes/NotebookLanesSteps.vue'

const flowStore = useFlowStore()

const health = computed(() => (flowStore.laneHealth ? NOTEBOOK_HEALTH[flowStore.laneHealth] : null))
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
