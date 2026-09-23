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
        <!-- Rewound and left there: the next change asks where it should go. -->
        <span v-if="behind" data-testid="behind" class="text-sm font-normal text-muted-color">
          at step {{ branch.headStep }} · {{ aheadLine }} · a change from here offers a new lane
        </span>
        <span v-if="viewingOnly" class="text-sm font-normal text-muted-color">
          viewing · the files stay on <code class="font-mono">{{ worktreeBranch }}</code>
        </span>
      </span>
    </Button>

    <!-- The actions for this lane and its steps, beside the count they are about. -->
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
      <Button
        text
        severity="secondary"
        size="small"
        label="mark this point"
        :pt="ACTION_PT"
        :disabled="busy"
        aria-haspopup="dialog"
        :aria-label="`Mark this point on ${branch.name}`"
        @click="onMark"
      >
        <template #icon><Flag :size="14" /></template>
      </Button>
    </div>

    <Popover ref="steps" @show="stepsOpen = true" @hide="stepsOpen = false">
      <StepTimeline
        ref="timeline"
        :branch="branch.name"
        :entries="journal"
        :children="children"
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
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import { Button, Popover } from 'primevue'
import { ChevronRight, Flag, History, Plus } from 'lucide-vue-next'
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
  children: BranchInfo[]
  /** An op is in flight; the timeline's verbs wait rather than race it. */
  busy?: boolean
}>()

const emit = defineEmits<{
  open: []
  'new-branch': []
  rewind: [step: number]
  checkpoint: [intent: string, step: number]
}>()

const ROOT_PT = { root: { class: 'w-full justify-start px-1.5 py-1 font-normal' } }
const ACTION_PT = { root: { class: 'px-1.5 py-1 font-normal' } }

const steps = useTemplateRef<InstanceType<typeof Popover>>('steps')
const timeline = useTemplateRef<InstanceType<typeof StepTimeline>>('timeline')
const stepsOpen = ref(false)

const familyLine = computed(() => {
  const { parent, forkedAtStep, parentStep, headStep } = props.branch
  if (parent === null || forkedAtStep === null || parentStep === null) return 'root lane'
  return `started from ${parent} · step ${parentStep} · ${formatCount(headStep - parentStep, 'step')} ago`
})

const stepsLabel = computed(() => formatCount(props.branch.headStep, 'step'))

/** Rewound and left there: the branch stands behind its newest step. */
const behind = computed(
  () => (props.branch.newestStep ?? props.branch.headStep) > props.branch.headStep,
)

/**
 * The steps ahead of where it stands, counted from the timeline's own rows
 * rather than from step numbers — those are flow-global and count every other
 * lane's lines in between.
 */
const aheadLine = computed(() => {
  const ahead = props.journal.filter((entry) => entry.step > props.branch.headStep).length
  return ahead > 0
    ? `${formatCount(ahead, 'step')} ahead`
    : `behind its newest step ${props.branch.newestStep}`
})

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

async function onMark(event: Event): Promise<void> {
  if (!stepsOpen.value) {
    stepsOpen.value = true
    steps.value?.show(event)
  }
  await nextTick()
  await timeline.value?.openMark()
}

function onRewind(step: number): void {
  steps.value?.hide()
  emit('rewind', step)
}

function onCheckpoint(intent: string, step: number): void {
  steps.value?.hide()
  emit('checkpoint', intent, step)
}
</script>
