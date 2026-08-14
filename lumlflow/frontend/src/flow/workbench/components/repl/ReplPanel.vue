<template>
  <section
    class="flex flex-col gap-2 rounded-lg border border-surface-200 bg-surface-0 px-3 py-2.5 dark:border-surface-700 dark:bg-surface-900"
  >
    <div
      v-tooltip.top="'names hydrate as copies. nothing here writes an asset or moves the store.'"
      class="flex w-fit items-center gap-2"
    >
      <h3 class="text-base font-medium">scratch</h3>
      <BranchTag :name="branch" />
    </div>

    <div class="flex items-start gap-2">
      <Textarea
        v-model="code"
        class="flex-1 font-mono text-sm"
        rows="2"
        auto-resize
        aria-label="scratch expression"
        :disabled="disabled"
        placeholder="train_df.shape"
        @keydown.enter.exact.prevent="run"
      />
      <Button
        label="evaluate"
        :disabled="disabled || !code.trim() || running"
        :loading="running"
        @click="run"
      />
    </div>

    <p v-if="refusal" class="text-sm text-(--p-message-error-color)">{{ refusal }}</p>

    <template v-if="answer">
      <pre
        v-if="answer.output"
        class="max-h-40 overflow-auto whitespace-pre rounded-lg bg-surface-900 p-2.5 font-mono text-sm leading-relaxed text-surface-200 dark:bg-surface-950"
        >{{ answer.output.replace(/\n$/, '') }}</pre
      >
      <pre
        v-if="answer.error"
        class="max-h-40 overflow-auto whitespace-pre rounded-lg border border-(--p-message-error-border-color) bg-(--p-message-error-background) p-2.5 font-mono text-sm leading-relaxed text-(--p-message-error-color)"
        >{{ answer.error.traceback.replace(/\n$/, '') }}</pre
      >
      <pre
        v-else-if="answer.repr !== null"
        class="max-h-40 overflow-auto whitespace-pre rounded-lg border border-surface-200 bg-surface-50 p-2.5 font-mono text-sm leading-relaxed dark:border-surface-700 dark:bg-surface-800"
        >{{ answer.repr }}</pre
      >
      <p v-if="answer.mutated.length" class="text-sm text-muted-color">
        <!-- Naming it rather than hiding it: the reader's copy changed and the
             branch's value did not, which is the whole contract of this panel. -->
        mutated the copy of {{ named(answer.mutated) }}. the stored value is unchanged.
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button, Textarea } from 'primevue'
import type { EvalResult } from '@/flow/api/types'
import BranchTag from '../../ui/BranchTag.vue'

/**
 * The scratch REPL, scoped to the branch on screen.
 *
 * Reading a branch is a store read, so this evaluates against any branch —
 * including one whose files are nowhere. What comes back is a repr, whatever
 * the expression printed, and the names it touched; what never comes back is a
 * version, because the REPL writes no assets by construction.
 */
const props = defineProps<{
  branch: string
  disabled?: boolean
  evaluate: (code: string, branch: string) => Promise<EvalResult>
}>()

const code = ref('')
const answer = ref<EvalResult | null>(null)
const refusal = ref<string | null>(null)
const running = ref(false)

async function run(): Promise<void> {
  const asked = code.value.trim()
  if (!asked || running.value) return
  running.value = true
  refusal.value = null
  try {
    answer.value = await props.evaluate(asked, props.branch)
  } catch (refused) {
    answer.value = null
    refusal.value = refused instanceof Error ? refused.message : String(refused)
  } finally {
    running.value = false
  }
}

/** An answer belongs to the branch it was evaluated against, and only that one. */
watch(
  () => props.branch,
  () => {
    answer.value = null
    refusal.value = null
  },
)

function named(names: string[]): string {
  return names.map((name) => `\`${name}\``).join(', ')
}
</script>
