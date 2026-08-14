<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="Pair link"
      caption="One direction only: the flow hands over the prompt that pairs an agent, whatever harness it runs in, and then detects the agent_begin transaction the connection files. Unpaired is a working state, not an error: it gets a link and a popover, never a panel."
    >
      <div class="flex flex-col gap-3">
        <AgentTaskLine viewed-branch="main" :connect="CONNECT_PROMPT" />
        <AgentTaskLine :paired="session.paired" viewed-branch="main" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Catch-up marker"
      caption="Reopening after an overnight run knows exactly how far behind it was, because the cursor is durable. A marker, not an inbox: the reopen rule still lands on the active lane."
    >
      <CatchUpMarker :count="12" @open="onOpenAtCursor" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Stale summary"
      caption="What the lane owes, in one line of the bar that names the lane. Three counts stay apart, because stale, downstream and never-materialized are three different claims. The first cause and the downstream lens ride in its popover: a lane mid-edit is this product's ordinary state and does not get a page-wide colour field."
    >
      <StaleSummary
        v-model:show-tint="tinted"
        :unsynced="1"
        :downstream="14"
        :unmaterialized="1"
        cause="`helpers.py` changed"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Journal feed"
      caption="Read-only activity over the journal: time, actor, intent, and a one-line summary with slugs in mono. Failed attempts fold into their repair. The offline window renders visibly coarse instead of posing as a normal burst."
    >
      <JournalFeed :entries="journal" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Not running"
      caption="Nothing live: the surface keeps the last-known state, marks it stale and carries the command to start lumlflow again. Never a blank screen."
    >
      <DaemonDownBanner />
    </GallerySpecimen>

    <GallerySpecimen
      title="Not connected"
      caption="A tab opened without the key is not a server that is down: nothing is claimed about it, and the remedy is the address lumlflow ui prints."
    >
      <div class="max-w-xl">
        <NotConnectedNotice />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Socket reconnect"
      caption="A dropped socket is a latency event, never a data event: reconnect replays from the cursor, so the banner promises no refresh and no loss."
    >
      <SocketReconnectBanner />
    </GallerySpecimen>

    <GallerySpecimen
      title="Env mismatch"
      caption="The lane's lockfile differs from the live venv. Restart under this lane's lock. Background work waits meanwhile, and the UI says so rather than looking idle."
    >
      <div class="max-w-lg">
        <EnvMismatchBanner @restart="onRestartKernel" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="An agent holds the files"
      caption="The one real lock: use, rewind and adopt wait while an agent session holds the files. UI edits still land in the store. The write to files waits."
    >
      <div class="max-w-xl">
        <WorktreeLockNotice holder="claude-1" @force="onForce" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Kernel start hint"
      caption="Every surface has a kernel-free tier. The hint rides next to expand, page, and diff affordances, so the UI says so before it starts a kernel."
    >
      <div class="flex items-center gap-3">
        <Button label="Expand full value" severity="secondary" outlined>
          <template #icon>
            <Maximize2 :size="14" />
          </template>
        </Button>
        <KernelStartHint />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Degraded states, enumerated"
      caption="A failure mode without a surface is a spinner that never resolves. Every condition in ui-draft §10 has its surface."
    >
      <table class="w-full text-base border-collapse">
        <thead>
          <tr>
            <th :class="cellClass" class="font-medium w-1/3">Condition</th>
            <th :class="cellClass" class="font-medium">Surface</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="[condition, surface] in degradedStates" :key="condition">
            <td :class="cellClass">{{ condition }}</td>
            <td :class="cellClass" class="text-muted-color">{{ surface }}</td>
          </tr>
        </tbody>
      </table>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import { useToast } from 'primevue/usetoast'
import CatchUpMarker from '../../components/session/CatchUpMarker.vue'
import DaemonDownBanner from '../../components/session/DaemonDownBanner.vue'
import EnvMismatchBanner from '../../components/session/EnvMismatchBanner.vue'
import JournalFeed from '../../components/session/JournalFeed.vue'
import KernelStartHint from '../../components/session/KernelStartHint.vue'
import NotConnectedNotice from '../../components/session/NotConnectedNotice.vue'
import { CONNECT_PROMPT } from '../../components/session/connectPrompt'
import AgentTaskLine from '../../components/panel/AgentTaskLine.vue'
import SocketReconnectBanner from '../../components/session/SocketReconnectBanner.vue'
import StaleSummary from '../../components/session/StaleSummary.vue'
import WorktreeLockNotice from '../../components/session/WorktreeLockNotice.vue'
import { journal, session } from '../../fixtures'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

const tinted = ref(false)

const cellClass = 'border border-surface-200 dark:border-surface-700 px-3 py-2 text-left align-top'

// ui-draft.md §10's condition→surface table, rendered so the enumeration itself is visible.
const degradedStates: [string, string][] = [
  [
    'lumlflow not running',
    'Last-known session, read-only, marked stale, with the command to start it.',
  ],
  [
    'Tab holds no token',
    'Its own notice: nothing is claimed about the server, and the address to reopen is named.',
  ],
  [
    'Kernel not started',
    'Full browsing from previews. Expand/page/diff announce "this starts the kernel".',
  ],
  ['Socket dropped', 'Banner, auto-reconnect, cursor replay. No refresh, no loss.'],
  [
    'An agent holds the files',
    'Use, rewind and adopt disabled with the reason and a force escape. UI edits still land; the write to files waits.',
  ],
  [
    'Env mismatch on the viewed lane',
    'Header flag "env mismatch". Restart under this lane\'s lock. Background work for that lane waits, and the UI says so rather than looking idle.',
  ],
  ['Value never persisted', 'Materialize and download with preflight, not a broken download.'],
  // No irrecoverable-rewind row: persist-everything means every referenced
  // value is still in the store, so rewind is instant and prompt-free and
  // there is no state for a preflight to declare.
  [
    'Unknown preview/kind version',
    'Key-value fallback with an explicit "newer preview format" note.',
  ],
]

function onOpenAtCursor(): void {
  toast.add({
    severity: 'secondary',
    summary: 'open',
    detail: 'would open the transaction list at the cursor. it still lands on the active lane.',
    life: 2500,
  })
}

function onRestartKernel(): void {
  toast.add({
    severity: 'secondary',
    summary: 'restart',
    detail: "would restart the kernel under this lane's lock",
    life: 2500,
  })
}

function onForce(): void {
  toast.add({
    severity: 'secondary',
    summary: 'force',
    detail: 'would take the files from claude-1. the agent loses its file view.',
    life: 2500,
  })
}
</script>
