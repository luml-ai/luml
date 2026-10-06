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
            <Button
              text
              severity="secondary"
              :label="`use ${viewedBranch} here`"
              :pt="ACTION_PT"
              @click="confirming = true"
            >
              <template #icon><FolderInput :size="14" /></template>
            </Button>
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

const props = defineProps<{
  branches: BranchInfo[]
  viewedBranch: string
  worktreeBranch: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  view: [name: string]
  checkout: [name: string]
  'new-branch': []
}>()

const SELECT_PT = { label: { class: 'flex items-center py-1.5' } }
const ACTION_PT = { root: { class: 'w-full justify-start font-normal' } }

const confirming = ref(false)

const options = computed(() =>
  props.branches.filter((branch) => !branch.archived || branch.name === props.viewedBranch),
)

const viewingOther = computed(() => props.viewedBranch !== props.worktreeBranch)

function onView(name: string): void {
  confirming.value = false
  if (name && name !== props.viewedBranch) emit('view', name)
}
</script>
