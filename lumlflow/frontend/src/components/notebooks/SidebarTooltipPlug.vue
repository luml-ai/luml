<template>
  <div class="not-last:border-b! border-surface">
    <Button
      variant="text"
      severity="secondary"
      v-tooltip.bottom="tooltip"
      class="sidebar-tooltip-plug"
      :aria-label="label"
    >
      <CircleQuestionMark :size="14" />
    </Button>
  </div>
</template>

<script setup lang="ts">
import { CircleQuestionMark } from 'lucide-vue-next'
import { Button } from 'primevue'

interface Props {
  tooltip: string
  label: string
}

defineProps<Props>()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.sidebar-tooltip-plug {
  @apply flex items-center justify-center w-[54px] h-[49px] p-0;
}
</style>
