<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="Status vocabulary"
      caption="Stale always names its cause in words. Unmaterialized is its own quiet state, never a flavor of stale. Transitive staleness is subdued."
    >
      <div class="flex flex-col gap-2.5">
        <StatusChip status="materialized" />
        <StatusChip status="running" />
        <StatusChip
          status="stale"
          :stale="{ kind: 'definition-changed', cause: 'definition changed · v4' }"
        />
        <StatusChip
          status="stale"
          :stale="{ kind: 'parent-rematerialized', cause: 'parent `features` rematerialized' }"
        />
        <StatusChip
          status="stale"
          :stale="{
            kind: 'deps-rewired',
            cause: 'inputs rewired · now reads `calibrated_eval.eval`',
          }"
        />
        <StatusChip
          status="stale"
          :stale="{ kind: 'workspace-code-changed', cause: '`helpers.py` changed' }"
        />
        <StatusChip
          status="stale"
          :stale="{
            kind: 'parent-rematerialized',
            cause: 'parent `features` rematerialized',
            transitive: true,
          }"
        />
        <StatusChip status="unmaterialized" />
        <StatusChip status="failed" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Kind iconography"
      caption="One icon per asset kind. The registry is open at runtime, so unknown kinds render as a generic asset, never an error."
    >
      <div class="flex flex-wrap gap-x-6 gap-y-3">
        <KindBadge v-for="kind in kinds" :key="kind" :kind="kind" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Factual badges"
      caption="Each states a recorded fact: a memo hit is not a 0-second run, an older-env result says so, settled is a highlight and never a gate."
    >
      <div class="flex flex-wrap gap-3">
        <MetaBadge variant="cached" />
        <MetaBadge variant="older-env" />
        <MetaBadge variant="settled" />
        <MetaBadge variant="external" />
        <MetaBadge variant="pinned" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Actor identity"
      caption="Agents and humans are distinct actor kinds. During mixed editing windows the card renders the uncertainty flag instead of a confident wrong name."
    >
      <div class="flex flex-wrap items-center gap-6">
        <ActorChip :actor="claude" />
        <ActorChip :actor="user" />
        <ActorChip :actor="claude" uncertain />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Lane identity"
      caption="A lane is addressed by name, never by a number. Its color comes from the name, so it holds across every view."
    >
      <div class="flex flex-col gap-2.5">
        <BranchTag name="main" checked-out />
        <BranchTag name="exp/lr-1e3" />
        <BranchTag name="exp/feature-drop" />
        <BranchTag name="old/baseline" archived />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Flow state"
      caption="Five states, because running/stopped is not enough to be honest."
    >
      <div class="flex flex-wrap gap-x-8 gap-y-3">
        <FlowStateDot v-for="state in flowStates" :key="state" :state="state" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Copyable command"
      caption="One line the UI hands to the terminal: init, a run, an export. It truncates to fit, selects, and copies whole."
    >
      <div class="max-w-md">
        <CopyField value="lumlflow run features" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Copyable block"
      caption="Its multi-line sibling, for what a reader reads before pasting: a handoff payload, the prompt that pairs an agent. The block is the preview and the copy at once, in one affordance in the corner."
    >
      <div class="max-w-lg">
        <CopyBlock :value="CONNECT_PROMPT" label="copy the connect prompt" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Formatting"
      caption="Costs, sizes, and metrics share one formatter each, so the same value never renders two ways."
    >
      <div class="grid grid-cols-3 gap-x-8 gap-y-2 text-base max-w-md font-mono">
        <template v-for="[input, output] in formats" :key="input">
          <span class="text-muted-color col-span-2">{{ input }}</span>
          <span>{{ output }}</span>
        </template>
      </div>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { CONNECT_PROMPT } from '../../components/session/connectPrompt'
import { claude, user } from '../../fixtures'
import { formatBytes, formatCost, formatMetric } from '../../model/format'
import type { AssetKind, FlowState } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'
import CopyBlock from '../../ui/CopyBlock.vue'
import CopyField from '../../ui/CopyField.vue'
import FlowStateDot from '../../ui/FlowStateDot.vue'
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StatusChip from '../../ui/StatusChip.vue'
import GallerySpecimen from '../GallerySpecimen.vue'

const kinds: AssetKind[] = [
  'frame',
  'plot',
  'metric',
  'note',
  'eval',
  'model',
  'dataset',
  'experiment',
  'checkpoint',
  'image',
  'text',
  'html',
  'unknown',
]

const flowStates: FlowState[] = ['running', 'idle', 'unpaired', 'kernel-not-started', 'daemon-down']

const formats: [string, string][] = [
  ['formatCost(0.04)', formatCost(0.04)],
  ['formatCost(9.8)', formatCost(9.8)],
  ['formatCost(312)', formatCost(312)],
  ['formatCost(5400)', formatCost(5400)],
  ['formatBytes(14_680_064)', formatBytes(14_680_064)],
  ['formatBytes(890)', formatBytes(890)],
  ['formatMetric(0.8412)', formatMetric(0.8412)],
  ['formatMetric(84312)', formatMetric(84312)],
]
</script>
