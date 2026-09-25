<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="The full panel · main"
      caption="Scoped to one viewed lane: identifier with family line, the agent's current task from the journal, then one disclosure per section. Cells open, everything else waits on demand, and a lens with nothing on the lane never renders at all. Every row is an address, never a number."
    >
      <div :class="frameClass">
        <LeftPanel
          :branches="branches"
          :cells="cellsByBranch['main']"
          viewed-branch="main"
          :session="session"
          :env="env"
          :settings="liveSettings"
          :journal="journal"
          @open-graph="onOpenGraph"
          @select-cell="onSelectCell"
          @update-settings="onUpdateSettings"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Re-scoped to exp/feature-drop"
      caption="The same component with viewedBranch changed: identifier, task line, and every inventory lens re-scope together. Viewing is a pure read, and the caption says the files stay on main."
    >
      <div :class="frameClass">
        <LeftPanel
          :branches="branches"
          :cells="cellsByBranch['exp/feature-drop']"
          viewed-branch="exp/feature-drop"
          :session="session"
          :env="env"
          :settings="liveSettings"
          :journal="journal"
          @open-graph="onOpenGraph"
          @select-cell="onSelectCell"
          @update-settings="onUpdateSettings"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Unpaired"
      caption="Unpaired is a working state, not an error: the task line reads 'not paired' with the link that pairs one, and everything else keeps working. This is the only place the workbench says it."
    >
      <div :class="frameClass">
        <LeftPanel
          :branches="branches"
          :cells="cellsByBranch['main']"
          viewed-branch="main"
          :session="unpairedSession"
          :env="env"
          :settings="liveSettings"
          :journal="journal"
          @open-graph="onOpenGraph"
          @select-cell="onSelectCell"
          @update-settings="onUpdateSettings"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Env mismatch"
      caption="The lane's lockfile differs from the live venv: the packages header carries the mark while it is folded, and the banner inside names the fix. A warning that hides is not a warning."
    >
      <div :class="frameClass">
        <LeftPanel
          :branches="branches"
          :cells="cellsByBranch['main']"
          viewed-branch="main"
          :session="idleSession"
          :env="mismatchEnv"
          :settings="liveSettings"
          :journal="journal"
          @open-graph="onOpenGraph"
          @select-cell="onSelectCell"
          @update-settings="onUpdateSettings"
        />
      </div>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import LeftPanel from '../../components/panel/LeftPanel.vue'
import { branches, cellsByBranch, env, journal, session, settings } from '../../fixtures'
import type { EnvState, FlowSettings, WorkbenchSession } from '../../model/types'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

const frameClass =
  'w-80 h-[560px] rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden'

const liveSettings = ref<FlowSettings>({ ...settings })

const unpairedSession: WorkbenchSession = {
  ...session,
  state: 'unpaired',
  paired: undefined,
}

const idleSession: WorkbenchSession = {
  ...session,
  state: 'idle',
  paired: { ...session.paired!, state: 'idle', idleFor: '24m', task: undefined },
}

const mismatchEnv: EnvState = { ...env, mismatch: true }

function onOpenGraph(): void {
  toast.add({
    severity: 'secondary',
    summary: 'open-graph',
    detail: 'would open the lane map overlay',
    life: 2500,
  })
}

function onSelectCell(slug: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'select-cell',
    detail: `would scroll the canvas to \`${slug}\` and highlight it`,
    life: 2500,
  })
}

function onUpdateSettings(next: FlowSettings): void {
  liveSettings.value = next
  toast.add({
    severity: 'secondary',
    summary: 'update-settings',
    detail: `reactivity ${next.reactivity} (${next.autoThresholdSeconds}s)`,
    life: 2500,
  })
}
</script>
