<template>
  <div class="flex min-w-0 flex-col">
    <Button
      text
      severity="secondary"
      size="small"
      class="group"
      :pt="ROOT_PT"
      :aria-label="`Open the lane map (viewing ${branch.name})`"
      @click="emit('open')"
    >
      <span class="flex min-w-0 flex-1 flex-col gap-1 text-left">
        <span class="flex w-full min-w-0 items-center gap-2">
          <BranchTag
            :name="branch.name"
            :checked-out="branch.checkedOut"
            :archived="branch.archived"
          />
          <MetaBadge v-if="branch.settled" variant="settled" />
          <span v-else class="text-sm text-muted-color">working</span>
          <ChevronRight
            :size="15"
            class="ml-auto shrink-0 text-muted-color transition-transform group-hover:translate-x-0.5"
          />
        </span>
        <span class="text-sm font-normal text-muted-color">{{ familyLine }}</span>
        <span v-if="viewingOnly" class="text-sm font-normal text-muted-color">
          viewing · the files stay on <code class="font-mono">{{ worktreeBranch }}</code>
        </span>
      </span>
    </Button>

    <!--
      The two verbs that move this branch through its own history, beside the
      count they are about. The graph above is where branches sit next to each
      other; this is where one branch's steps do.
    -->
    <div class="flex items-center gap-0.5">
      <Button
        ref="stepsButton"
        text
        severity="secondary"
        size="small"
        :label="stepsLabel"
        :pt="ACTION_PT"
        aria-haspopup="dialog"
        :aria-expanded="stepsOpen"
        :aria-label="`Steps on ${branch.name}`"
        @click="onSteps"
      >
        <template #icon><History :size="14" /></template>
      </Button>
      <Button
        text
        severity="secondary"
        size="small"
        label="new lane"
        :pt="ACTION_PT"
        @click="emit('new-branch')"
      >
        <template #icon><Plus :size="14" /></template>
      </Button>
    </div>

    <Popover ref="steps" @show="stepsOpen = true" @hide="stepsOpen = false">
      <StepTimeline
        :branch="branch.name"
        :entries="journal"
        :head-step="branch.headStep"
        :checked-out="branch.checkedOut"
        :busy="busy"
        @rewind="onRewind"
        @checkpoint="onCheckpoint"
      />
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { Button, Popover } from 'primevue'
import { ChevronRight, History, Plus } from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { BranchInfo, JournalEntry } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StepTimeline from '../branch/StepTimeline.vue'

/**
 * The viewed branch's identity, its family position, and the two ways out of
 * it: sideways into the lane map, and backwards through its own steps.
 *
 * Viewing is a pure store read; only using a lane here rebinds files. The
 * caption keeps the verbs apart.
 */
const props = defineProps<{
  branch: BranchInfo
  worktreeBranch: string
  /** This branch's transactions, newest first — what the timeline navigates. */
  journal: JournalEntry[]
  /** An op is in flight; the timeline's verbs wait rather than race it. */
  busy?: boolean
}>()

const emit = defineEmits<{
  open: []
  'new-branch': []
  rewind: [step: number]
  checkpoint: [intent: string]
}>()

const ROOT_PT = { root: { class: 'w-full justify-start px-1.5 py-1 font-normal' } }
const ACTION_PT = { root: { class: 'px-1.5 py-1 font-normal' } }

const steps = useTemplateRef<InstanceType<typeof Popover>>('steps')
const stepsOpen = ref(false)

const familyLine = computed(() => {
  const { parent, forkedAtStep, headStep } = props.branch
  if (parent === null || forkedAtStep === null) return 'root lane'
  return `started from ${parent} · ${formatCount(headStep - forkedAtStep, 'step')} ago`
})

const stepsLabel = computed(() => formatCount(props.branch.headStep, 'step'))

const viewingOnly = computed(() => props.branch.name !== props.worktreeBranch)

/**
 * The disclosure state is set here as well as read off the popover's own
 * events: `show` lands a frame later, and an `aria-expanded` that is a frame
 * behind the overlay is a lie to exactly the reader who cannot see it.
 */
function onSteps(event: Event): void {
  stepsOpen.value = !stepsOpen.value
  steps.value?.toggle(event)
}

function onRewind(step: number): void {
  steps.value?.hide()
  emit('rewind', step)
}

function onCheckpoint(intent: string): void {
  steps.value?.hide()
  emit('checkpoint', intent)
}
</script>
