<template>
  <div class="flex w-96 max-w-[92vw] min-w-0 flex-col gap-2">
    <!--
      Marking writes on the current step; nothing here adds to the history, and
      everything below moves within the history that already exists.
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
      <p class="px-1.5 text-sm text-muted-color">
        goes on <span class="font-mono">step {{ headStep }}</span
        >, where <code class="font-mono">{{ branch }}</code> stands. it adds no step.
      </p>
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

    <p v-if="!entries.length" class="px-1.5 text-sm text-muted-color">nothing on this lane yet</p>

    <ol v-else class="flex max-h-96 min-w-0 flex-col overflow-y-auto">
      <li v-for="entry in entries" :key="entry.step" class="min-w-0">
        <Button
          text
          severity="secondary"
          size="small"
          data-testid="step-row"
          :aria-label="`step ${entry.step} · ${entry.mark ?? entry.intent}`"
          :aria-expanded="entry.step === pending"
          :pt="ROW_PT"
          @click="onPick(entry.step)"
        >
          <component
            :is="entry.mark ? Flag : Dot"
            :size="14"
            class="mt-1 shrink-0"
            :class="[
              entry.mark ? 'text-(--p-primary-color)' : 'text-muted-color',
              entry.step > headStep ? 'opacity-60' : '',
            ]"
          />
          <span class="flex min-w-0 flex-1 flex-col gap-0.5 text-left">
            <!--
              A marked step reads under its mark, the way a commit reads under
              its message; what the step did stays on the line below it.
            -->
            <span class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
              <span
                v-if="entry.mark"
                data-testid="step-mark"
                class="min-w-0 break-words text-base font-medium"
                >{{ entry.mark }}</span
              >
              <span v-else class="min-w-0 break-words text-base">{{ entry.intent }}</span>
              <Tag
                v-if="entry.step === headStep"
                value="current"
                severity="secondary"
                :pt="TAG_PT"
              />
              <!-- A step the lane was moved back from: still in its history, not where it stands. -->
              <Tag
                v-else-if="entry.step > headStep"
                value="ahead"
                severity="secondary"
                data-testid="ahead"
                :pt="TAG_PT"
              />
            </span>
            <span v-if="entry.mark" class="min-w-0 break-words text-sm text-muted-color">
              {{ entry.intent }}
            </span>
            <span class="text-sm text-muted-color">
              <span class="font-mono">step {{ entry.step }}</span>
              · {{ entry.time }} · {{ entry.actor.label }}
            </span>
            <span
              v-if="startedHere.has(entry.step)"
              data-testid="started-here"
              class="flex items-center gap-1 text-sm text-muted-color"
            >
              <Split :size="14" aria-hidden="true" />
              {{ startedHere.get(entry.step)?.join(', ') }} started here
            </span>
          </span>
        </Button>

        <!--
          The confirm names what moves rather than asking whether you are sure:
          moving recomputes nothing and adds no step, and the only thing it
          costs is the files, on the branch that happens to be holding them.
        -->
        <div v-if="entry.step === pending" class="flex flex-col gap-2 px-1.5 pt-1 pb-2">
          <p class="text-sm text-muted-color">
            <code class="font-mono">{{ branch }}</code> stands at step {{ entry.step }} with the
            cells it selected there<template v-if="checkedOut"
              >, and the files are rewritten to match</template
            >. nothing recomputes. nothing is lost. no step is added. the other steps stay in the
            history.
          </p>
          <div class="flex justify-end gap-2">
            <Button text severity="secondary" label="stay here" @click="pending = null" />
            <Button
              :label="`${entry.step < headStep ? 'rewind' : 'go'} to step ${entry.step}`"
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
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import { Button, InputText, Tag } from 'primevue'
import { Dot, Flag, Split } from 'lucide-vue-next'
import type { BranchInfo, JournalEntry } from '../../model/types'

/**
 * Where a branch stands and where it can go: its steps, newest first, with the
 * one it stands on marked and every other one offering to move there. Moving
 * adds no step: a rewound branch stands behind its newest step, the steps
 * ahead of it read as such, and the next change on it is what moves it on.
 *
 * This is navigation, not history. The panel's activity section reads the
 * journal — what happened, with its summaries, its offline windows and its
 * since-you-were-here divider — and stays read-only; this lists the same
 * transactions as *positions*, which is the one thing that surface does not do.
 * Every verb that moves a branch through its own history lives here and only
 * here.
 *
 * Marking is the other half of the same idea. The journal already records every
 * change, so a checkpoint copies nothing and freezes nothing — and adds no step
 * either. It is words written on the current step, the way a commit message
 * rides on its commit, and the marked row reads under them; a later click on
 * that row offers the rewind back to it like any other.
 */
const props = withDefaults(
  defineProps<{
    branch: string
    /** The branch's transactions, newest first, as the panel already filters them. */
    entries: JournalEntry[]
    children?: BranchInfo[]
    /** The step the branch is on; the row that reads `current`. */
    headStep: number
    /** The files are on this branch, so a rewind moves them too. */
    checkedOut?: boolean
    /** An op is in flight; a second one would race it. */
    busy?: boolean
  }>(),
  { children: () => [] },
)

const emit = defineEmits<{
  rewind: [step: number]
  /** Mark the current step under these words. */
  checkpoint: [intent: string, step: number]
}>()

const ROW_PT = {
  root: { class: 'w-full items-start justify-start gap-2 px-1.5 py-1.5 font-normal' },
}
const TAG_PT = { root: { class: 'text-sm font-normal px-1.5 py-0 shrink-0' } }

/** The step whose confirm is open. One at a time — this is a decision, not a list. */
const pending = ref<number | null>(null)

/** Which lanes started from each of this lane's own steps, in tree order. */
const startedHere = computed(() => {
  const at = new Map<number, string[]>()
  for (const child of props.children) {
    if (child.parentStep === null) continue
    at.set(child.parentStep, [...(at.get(child.parentStep) ?? []), child.name])
  }
  return at
})

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

defineExpose({ openMark })

function confirmMark(): void {
  const intent = markIntent.value.trim()
  if (!intent) return
  marking.value = false
  markIntent.value = ''
  emit('checkpoint', intent, props.headStep)
}
</script>
