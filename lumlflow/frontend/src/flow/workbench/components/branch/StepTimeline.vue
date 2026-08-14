<template>
  <div class="flex w-96 max-w-[92vw] min-w-0 flex-col gap-2">
    <!--
      Marking is the one thing here that adds to the history; everything below
      it moves within the history that already exists.
    -->
    <div v-if="marking" class="flex flex-col gap-2">
      <InputText
        ref="markInput"
        v-model="markIntent"
        aria-label="what this point is"
        placeholder="what this point is"
        @keyup.enter="confirmMark"
        @keyup.escape="marking = false"
      />
      <div class="flex justify-end gap-2">
        <Button text severity="secondary" label="cancel" @click="marking = false" />
        <Button label="mark this point" :disabled="!markIntent.trim()" @click="confirmMark" />
      </div>
    </div>
    <Button
      v-else
      class="self-start"
      text
      severity="secondary"
      label="mark this point"
      :disabled="busy"
      @click="openMark"
    >
      <template #icon><Flag :size="14" /></template>
    </Button>

    <p v-if="!entries.length" class="px-1.5 text-sm text-muted-color">
      nothing on this lane yet
    </p>

    <ol v-else class="flex max-h-96 min-w-0 flex-col overflow-y-auto">
      <li v-for="entry in entries" :key="entry.step" class="min-w-0">
        <Button
          text
          severity="secondary"
          size="small"
          data-testid="step-row"
          :aria-label="`step ${entry.step} · ${entry.intent}`"
          :aria-expanded="entry.step === pending"
          :pt="ROW_PT"
          @click="onPick(entry.step)"
        >
          <component
            :is="entry.kind === 'checkpoint' ? Flag : Dot"
            :size="14"
            class="mt-1 shrink-0"
            :class="entry.kind === 'checkpoint' ? 'text-(--p-primary-color)' : 'text-muted-color'"
          />
          <span class="flex min-w-0 flex-1 flex-col gap-0.5 text-left">
            <span class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
              <span class="min-w-0 break-words text-base">{{ entry.intent }}</span>
              <Tag
                v-if="entry.step === headStep"
                value="current"
                severity="secondary"
                :pt="TAG_PT"
              />
            </span>
            <span class="text-sm text-muted-color">
              <span class="font-mono">step {{ entry.step }}</span>
              · {{ entry.time }} · {{ entry.actor.label }}
            </span>
          </span>
        </Button>

        <!--
          The confirm names what moves rather than asking whether you are sure:
          rewinding recomputes nothing, and the only thing it costs is the
          files, on the branch that happens to be holding them.
        -->
        <div v-if="entry.step === pending" class="flex flex-col gap-2 px-1.5 pt-1 pb-2">
          <p class="text-sm text-muted-color">
            restores the cells <code class="font-mono">{{ branch }}</code> selected at step
            {{ entry.step
            }}<template v-if="checkedOut">, and rewrites the files to match</template>. nothing
            recomputes. nothing is lost. later steps stay in the history.
          </p>
          <div class="flex justify-end gap-2">
            <Button text severity="secondary" label="stay here" @click="pending = null" />
            <Button
              :label="`rewind to step ${entry.step}`"
              :disabled="busy"
              @click="confirmRewind(entry.step)"
            />
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef } from 'vue'
import { Button, InputText, Tag } from 'primevue'
import { Dot, Flag } from 'lucide-vue-next'
import type { JournalEntry } from '../../model/types'

/**
 * Where a branch stands and where it can go: its steps, newest first, with the
 * one it is on marked and every older one offering a rewind.
 *
 * This is navigation, not history. The panel's activity section reads the
 * journal — what happened, with its summaries, its offline windows and its
 * since-you-were-here divider — and stays read-only; this lists the same
 * transactions as *positions*, which is the one thing that surface does not do.
 * Every verb that moves a branch through its own history lives here and only
 * here.
 *
 * Marking is the other half of the same idea. The journal already records every
 * change, so a checkpoint copies nothing and freezes nothing: it is a line
 * saying this point was worth naming, and the name is what the timeline reads
 * back.
 */
const props = defineProps<{
  branch: string
  /** The branch's transactions, newest first, as the panel already filters them. */
  entries: JournalEntry[]
  /** The step the branch is on; the row that reads `current`. */
  headStep: number
  /** The files are on this branch, so a rewind moves them too. */
  checkedOut?: boolean
  /** An op is in flight; a second one would race it. */
  busy?: boolean
}>()

const emit = defineEmits<{
  rewind: [step: number]
  checkpoint: [intent: string]
}>()

const ROW_PT = { root: { class: 'w-full items-start justify-start gap-2 px-1.5 py-1.5 font-normal' } }
const TAG_PT = { root: { class: 'text-sm font-normal px-1.5 py-0 shrink-0' } }

/** The step whose confirm is open. One at a time — this is a decision, not a list. */
const pending = ref<number | null>(null)

const marking = ref(false)
const markIntent = ref('')
const markInput = useTemplateRef<{ $el: HTMLElement }>('markInput')

function onPick(step: number): void {
  // The current step is where the branch already is: offering to rewind to it
  // would be a gesture that does nothing and journals a line saying it did.
  if (step === props.headStep) return
  pending.value = pending.value === step ? null : step
}

function confirmRewind(step: number): void {
  pending.value = null
  emit('rewind', step)
}

async function openMark(): Promise<void> {
  marking.value = true
  markIntent.value = ''
  await nextTick()
  markInput.value?.$el.focus()
}

function confirmMark(): void {
  const intent = markIntent.value.trim()
  if (!intent) return
  marking.value = false
  markIntent.value = ''
  emit('checkpoint', intent)
}
</script>
