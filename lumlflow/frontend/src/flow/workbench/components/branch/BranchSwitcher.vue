<template>
  <Select
    :model-value="viewedBranch"
    :options="options"
    option-label="name"
    option-value="name"
    :disabled="disabled"
    aria-label="viewed lane"
    :pt="SELECT_PT"
    @update:model-value="onView"
    @hide="confirming = false"
  >
    <!--
      Viewing is a store read, so the trigger says which branch is being read
      and whether that is the one the files are on: the two facts a reader
      needs before touching anything.
    -->
    <template #value>
      <span class="flex min-w-0 items-center gap-1.5">
        <Eye
          v-if="viewingOther"
          v-tooltip.bottom="'Viewing is a pure store read'"
          :size="14"
          class="shrink-0 text-muted-color"
        />
        <BranchTag :name="viewedBranch" :checked-out="!viewingOther" />
      </span>
    </template>

    <template #option="{ option }">
      <span class="flex min-w-0 flex-1 items-center gap-2">
        <BranchTag :name="option.name" :checked-out="option.name === worktreeBranch" />
        <span class="ml-auto shrink-0 font-mono text-sm text-muted-color">
          {{ formatCount(option.headStep, 'step') }}
        </span>
      </span>
    </template>

    <template #footer>
      <div class="flex flex-col gap-1.5 border-t border-surface-200 p-2 dark:border-surface-700">
        <!--
          Using a lane here is the one gesture that touches files, so it never
          rides a selection: browsing re-scopes the screen, and this is a
          separate ask with the sentence that says what it moves.
        -->
        <template v-if="viewingOther">
          <div v-if="confirming" class="flex flex-col gap-2 px-1 py-0.5">
            <p class="text-sm text-muted-color">
              rewrites the files in <code class="font-mono">cells/</code> to
              <code class="font-mono">{{ viewedBranch }}</code
              >. nothing recomputes. <code class="font-mono">{{ worktreeBranch }}</code> keeps
              everything it holds.
            </p>
            <div class="flex justify-end gap-2">
              <Button text severity="secondary" label="keep browsing" @click="confirming = false" />
              <Button label="use here" @click="emit('checkout', viewedBranch)" />
            </div>
          </div>
          <template v-else>
            <span v-if="worktreeLocked" v-tooltip.top="LOCKED_TOOLTIP" class="inline-flex">
              <Button
                text
                severity="secondary"
                :label="`use ${viewedBranch} here`"
                disabled
                :pt="ACTION_PT"
              >
                <template #icon><FolderInput :size="14" /></template>
              </Button>
            </span>
            <Button
              v-else
              text
              severity="secondary"
              :label="`use ${viewedBranch} here`"
              :pt="ACTION_PT"
              @click="confirming = true"
            >
              <template #icon><FolderInput :size="14" /></template>
            </Button>
            <Button
              v-if="worktreeLocked"
              v-tooltip.top="'use it here anyway. the agent loses its file view.'"
              link
              severity="danger"
              label="use here anyway"
              :pt="LINK_PT"
              @click="emit('checkout', viewedBranch, true)"
            />
          </template>
        </template>

        <Button
          v-if="!confirming"
          text
          severity="secondary"
          label="new lane"
          :pt="ACTION_PT"
          @click="emit('new-branch')"
        >
          <template #icon><Plus :size="14" /></template>
        </Button>
      </div>
    </template>
  </Select>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, Select } from 'primevue'
import { Eye, FolderInput, Plus } from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { BranchInfo } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'

/**
 * The shortcut between branches: pick one and the whole screen re-scopes to it.
 *
 * Switching here changes what is **viewed**, which is a store read costing no
 * lock and no kernel, and the URL follows so the new scope is a link. Making a
 * branch the working copy on disk is the other verb entirely and sits one
 * gesture deeper, behind a sentence naming what it moves — a dropdown that
 * rebound files as a side effect of browsing would make looking dangerous.
 *
 * The branch graph is still the map: it draws where each branch split and is
 * where two get picked for a comparison. This is the shortcut for the one
 * thing that map is opened for most.
 */
const props = defineProps<{
  branches: BranchInfo[]
  viewedBranch: string
  /** Where the files are — the one branch this list marks as checked out. */
  worktreeBranch: string
  /** Held by an agent session: checking out waits, or forces and takes it. */
  worktreeLocked?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  view: [name: string]
  /** `force` is the escape past an agent's worktree lock, never the default. */
  checkout: [name: string, force?: boolean]
  'new-branch': []
}>()

const SELECT_PT = { label: { class: 'flex items-center py-1.5' } }
const ACTION_PT = { root: { class: 'w-full justify-start font-normal' } }
const LINK_PT = { root: { class: 'self-start p-0 text-sm font-normal' } }

const LOCKED_TOOLTIP =
  'the agent is working in the files. you can look anywhere. using a lane here waits.'

const confirming = ref(false)

/** Archived branches live behind the graph's own toggle; this is the short list. */
const options = computed(() =>
  props.branches.filter((branch) => !branch.archived || branch.name === props.viewedBranch),
)

const viewingOther = computed(() => props.viewedBranch !== props.worktreeBranch)

function onView(name: string): void {
  confirming.value = false
  if (name && name !== props.viewedBranch) emit('view', name)
}
</script>
