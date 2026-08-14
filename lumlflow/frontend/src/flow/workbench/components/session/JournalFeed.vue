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
          <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-w-0">
            <span class="font-mono text-sm text-muted-color shrink-0">{{ entry.time }}</span>
            <ActorChip :actor="entry.actor" muted />
            <!-- The feed's home is a 320 px panel: an intent wraps rather than
                 being cut, and a slug with no space in it breaks. -->
            <span class="min-w-0 break-words text-base font-medium">{{ entry.intent }}</span>
            <MetaBadge v-if="entry.settled" variant="settled" />
          </div>
          <p class="min-w-0 break-words text-sm text-muted-color">
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
  CloudUpload,
  Flag,
  Package,
  Pencil,
  Play,
  Replace,
  Split,
  TextCursorInput,
  Trash2,
  WifiOff,
  type LucideIcon,
} from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { JournalEntry, JournalKind } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import MetaBadge from '../../ui/MetaBadge.vue'

/**
 * Read-only activity feed over the journal. The `offline` kind is deliberately
 * coarse and visibly distinct: presenting it as a normal burst would claim a
 * fine-grained sequence nothing was there to record.
 */
defineProps<{ entries: JournalEntry[] }>()

const GLYPHS: Record<JournalKind, LucideIcon> = {
  edit: Pencil,
  run: Play,
  checkpoint: Flag,
  fork: Split,
  adopt: Replace,
  rename: TextCursorInput,
  delete: Trash2,
  promote: CloudUpload,
  'agent-begin': Bot,
  'agent-end': BotOff,
  offline: WifiOff,
  env: Package,
}

function glyphOf(kind: JournalKind): LucideIcon {
  return GLYPHS[kind]
}

/** Render backticked `slugs` as mono without a markdown pass (StatusChip's causeHtml pattern). */
function monoHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-sm">$1</code>')
}
</script>
