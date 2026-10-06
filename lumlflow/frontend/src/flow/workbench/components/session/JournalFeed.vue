<template>
  <ol class="flex min-w-0 flex-col gap-2.5">
    <li v-for="entry in entries" :key="entry.step" class="min-w-0">
      <div
        v-if="entry.kind === 'offline'"
        class="flex items-start gap-2 rounded-lg border border-dashed border-surface-300 dark:border-surface-600 px-2.5 py-1.5 text-sm text-muted-color"
      >
        <WifiOff :size="14" class="shrink-0 mt-0.5" />
        <span class="min-w-0">
          <span class="text-surface-700 dark:text-surface-200"
            >edits while lumlflow was stopped</span
          >
        </span>
        <span class="ml-auto shrink-0 font-mono text-sm">{{ entry.time }}</span>
      </div>

      <div v-else class="flex min-w-0 items-start gap-2.5">
        <component :is="glyphOf(entry.kind)" :size="14" class="shrink-0 mt-1 text-muted-color" />
        <div class="flex flex-col gap-0.5 min-w-0 flex-1">
          <div
            v-if="entry.mark"
            data-testid="journal-mark"
            class="flex min-w-0 items-start gap-1.5 text-base font-medium"
          >
            <Flag :size="14" class="mt-1 shrink-0 text-(--p-primary-color)" aria-hidden="true" />
            <span class="min-w-0 break-words">{{ entry.mark }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-w-0">
            <span class="font-mono text-sm text-muted-color shrink-0">{{ entry.time }}</span>
            <ActorChip :actor="entry.actor" muted />
            <span class="min-w-0 break-words text-base font-medium">{{ entry.intent }}</span>
            <MetaBadge v-if="entry.settled" variant="settled" />
          </div>
          <p
            v-if="entry.summary || entry.failedAttempts"
            class="min-w-0 break-words text-sm text-muted-color"
          >
            <span v-html="monoHtml(entry.summary)" />
            <span v-if="entry.failedAttempts">
              · {{ formatCount(entry.failedAttempts, 'failed attempt') }}
            </span>
          </p>
        </div>
      </div>
    </li>
  </ol>
</template>

<script setup lang="ts">
import {
  Bot,
  BotOff,
  Flag,
  HardDrive,
  Package,
  Pencil,
  Play,
  Replace,
  Split,
  TextCursorInput,
  Trash2,
  TriangleAlert,
  Undo2,
  WifiOff,
  type LucideIcon,
} from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { JournalEntry, JournalKind } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import MetaBadge from '../../ui/MetaBadge.vue'

defineProps<{ entries: JournalEntry[] }>()

const GLYPHS: Record<JournalKind, LucideIcon> = {
  edit: Pencil,
  note: TriangleAlert,
  run: Play,
  rewind: Undo2,
  checkout: HardDrive,
  fork: Split,
  adopt: Replace,
  rename: TextCursorInput,
  delete: Trash2,
  'agent-begin': Bot,
  'agent-end': BotOff,
  offline: WifiOff,
  env: Package,
}

function glyphOf(kind: JournalKind): LucideIcon {
  return GLYPHS[kind]
}

function monoHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-sm">$1</code>')
}
</script>
