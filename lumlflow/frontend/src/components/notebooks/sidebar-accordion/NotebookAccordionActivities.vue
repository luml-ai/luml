<template>
  <div v-if="activities.length === 0" class="text-sm text-muted-color">No activities yet</div>
  <div v-else class="activities-list">
    <div v-for="activity in activities" :key="activity.step" class="item">
      <component
        :is="activityIcon(activity)"
        :size="12"
        class="item-icon"
        color="var(--p-text-muted-color)"
      />
      <div class="item-content">
        <div class="item-title">{{ activity.intent }}</div>
        <div class="item-description">
          <component :is="activityActorIcon(activity)" :size="12" />
          <span class="item-type-label">{{ activityActorLabel(activity) }}</span>
          <span> · </span>
          <span>{{ activityTime(activity) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { JournalTransaction } from '@/api/slices/workspace/workspace.interface'
import { computed } from 'vue'
import {
  Bot,
  CloudUpload,
  GitMerge,
  MessageSquare,
  Pencil,
  Play,
  Settings,
  Split,
  Trash2,
  User,
} from 'lucide-vue-next'
import { useFlowStore } from '@/store/flow'

const flowStore = useFlowStore()

const activities = computed(() => flowStore.currentBranchActivities)

const OP_ICONS: [string, unknown][] = [
  ['run_recorded', Play],
  ['branch_created', Split],
  ['adopted', GitMerge],
  ['renamed', Pencil],
  ['cell_removed', Trash2],
  ['cell_noted', MessageSquare],
  ['env_changed', Settings],
  ['agent_begin', Bot],
  ['agent_end', Bot],
]

function activityIcon(activity: JournalTransaction) {
  if (activity.offline) return CloudUpload
  const ops = new Set(activity.ops.map((op) => op.op))
  const matched = OP_ICONS.find(([op]) => ops.has(op))
  return matched?.[1] ?? Pencil
}

function activityActorIcon(activity: JournalTransaction) {
  return activity.actor === 'user' ? User : Bot
}

function activityActorLabel(activity: JournalTransaction) {
  return activity.actor === 'user' ? 'User' : activity.actor
}

function activityTime(activity: JournalTransaction) {
  const at = new Date(activity.ts)
  if (Number.isNaN(at.getTime())) return ''
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.activities-list {
  @apply pb-2 max-h-74 overflow-y-auto;
}

.item {
  @apply flex items-start gap-1 not-last:mb-2;
}
.item-icon {
  @apply shrink-0 mt-0.5;
}
.item-content {
  @apply text-sm;
}
.item-title {
  @apply text-sm font-medium truncate;
}
.item-description {
  @apply flex items-center gap-1 text-muted-color;
}
.item-type-label {
  @apply max-w-30 truncate;
}
</style>
