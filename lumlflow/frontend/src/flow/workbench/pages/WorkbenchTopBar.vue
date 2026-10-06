<template>
  <header
    class="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg border border-surface-200 bg-surface-0 px-4 py-1.5 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex min-w-0 items-center gap-2.5">
      <h2 class="font-mono text-lg font-semibold">{{ session.flowName }}</h2>
      <FlowStateDot :state="session.state" />
    </div>

    <BranchSwitcher
      :branches="branches"
      :viewed-branch="viewedBranch"
      :worktree-branch="session.worktreeBranch"
      :disabled="opsDisabled"
      @view="emit('view-branch', $event)"
      @checkout="emit('checkout-branch', $event)"
      @new-branch="emit('new-branch')"
    />

    <FlowTabs />

    <CatchUpMarker
      v-if="session.changesBehind"
      :count="session.changesBehind"
      @open="emit('open-catchup')"
    />

    <StaleSummary
      v-if="stale"
      v-model:show-tint="showTint"
      :unsynced="stale.unsynced"
      :downstream="stale.downstream"
      :unmaterialized="stale.unmaterialized"
      :waiting-on-threshold="stale.waitingOnThreshold"
      :never-timed="stale.neverTimed"
      :blocked-by-failure="stale.blockedByFailure"
      :refresh-failed="stale.refreshFailed"
      :cause="stale.cause"
    />

    <div class="ml-auto flex items-center gap-2">
      <SelectButton
        v-model="view"
        :options="VIEW_OPTIONS"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        aria-label="view"
      >
        <template #option="{ option }">
          <component :is="option.icon" :size="14" />
          <span class="sr-only">{{ option.label }}</span>
        </template>
      </SelectButton>

      <template v-if="runnable">
        <PreflightPopover
          v-if="!opsDisabled"
          :preflight="branchPreflight"
          :target="viewedBranch"
          label="Rerun lane"
          @open="emit('branch-preflight')"
          @run="emit('rerun-branch', $event)"
        />
        <Button v-else text label="Rerun lane" disabled>
          <template #icon><Play :size="14" /></template>
        </Button>

        <Button
          label="Stop session"
          severity="danger"
          text
          :disabled="opsDisabled"
          @click="stopPopover?.toggle($event)"
        >
          <template #icon><OctagonX :size="14" /></template>
        </Button>
        <Popover ref="stopPopover">
          <div class="flex w-80 flex-col gap-2.5">
            <p class="text-base font-medium">Stop this session?</p>
            <p class="text-sm text-muted-color">cancels the run and drains the queue.</p>
            <p class="text-sm text-muted-color">
              the agent stops in its own terminal (Ctrl+C), or hand it this:
            </p>
            <CopyField :value="stopPayload" />
            <div class="flex justify-end gap-2">
              <Button text severity="secondary" label="keep running" @click="stopPopover?.hide()" />
              <Button severity="danger" label="stop session" @click="confirmStop" />
            </div>
          </div>
        </Popover>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button, Popover, SelectButton } from 'primevue'
import { NotebookText, OctagonX, Play, Workflow } from 'lucide-vue-next'
import FlowTabs from '@/flow/FlowTabs.vue'
import BranchSwitcher from '../components/branch/BranchSwitcher.vue'
import PreflightPopover from '../components/card/PreflightPopover.vue'
import CatchUpMarker from '../components/session/CatchUpMarker.vue'
import StaleSummary from '../components/session/StaleSummary.vue'
import type { BranchInfo, Preflight, StaleCounts, WorkbenchSession } from '../model/types'
import CopyField from '../ui/CopyField.vue'
import FlowStateDot from '../ui/FlowStateDot.vue'

const props = defineProps<{
  session: WorkbenchSession
  viewedBranch: string
  branches: BranchInfo[]
  branchPreflight: Preflight | null
  runnable?: boolean
  opsDisabled?: boolean
  stale?: StaleCounts
}>()

const emit = defineEmits<{
  'rerun-branch': [payload: { force: boolean }]
  'branch-preflight': []
  'stop-session': []
  'open-catchup': []
  'view-branch': [name: string]
  'checkout-branch': [name: string]
  'new-branch': []
}>()

const view = defineModel<'canvas' | 'notebook'>('view', { required: true })

const showTint = defineModel<boolean>('showTint', { default: false })

const VIEW_OPTIONS = [
  { label: 'canvas', value: 'canvas', icon: Workflow },
  { label: 'notebook', value: 'notebook', icon: NotebookText },
]

const stopPopover = useTemplateRef<InstanceType<typeof Popover>>('stopPopover')

const stopPayload = computed(
  () =>
    `lumlflow cancelled the run on \`${props.session.worktreeBranch}\`. ` +
    `Stop working on it and move on. Nothing there is waiting on you.`,
)

function confirmStop(): void {
  emit('stop-session')
  stopPopover.value?.hide()
}
</script>
