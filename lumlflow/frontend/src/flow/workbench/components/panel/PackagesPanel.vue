<template>
  <div class="flex min-w-0 flex-col gap-2.5">
    <EnvMismatchBanner v-if="env.mismatch" :behind="behind" @restart="emit('restart-kernel')" />
    <ul class="flex flex-col">
      <li
        v-for="pkg in env.packages"
        :key="pkg.name"
        class="group flex min-w-0 items-center gap-2 px-1.5 py-1"
      >
        <span class="truncate font-mono text-base">{{ pkg.name }}</span>
        <Tag
          v-if="pkg.pendingRestart"
          v-tooltip.top="'the env has it. the running kernel does not yet.'"
          value="restart to apply"
          severity="warn"
          :pt="tinyTag"
        />
        <span class="ml-auto shrink-0 font-mono text-sm text-muted-color">
          {{ pkg.version }}
        </span>
        <Button
          v-tooltip.top="`remove ${pkg.name} from the workspace env`"
          class="shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100"
          text
          rounded
          severity="secondary"
          size="small"
          :disabled="busy"
          :aria-label="`remove ${pkg.name}`"
          @click="emit('remove-package', pkg.name)"
        >
          <template #icon><X :size="14" /></template>
        </Button>
      </li>
    </ul>
    <p v-if="!env.packages.length" class="px-1.5 text-sm text-muted-color">none installed yet</p>

    <div class="flex items-center gap-1.5 px-1.5">
      <InputText
        v-model="adding"
        class="flex-1 font-mono"
        size="small"
        aria-label="add packages"
        placeholder="lightgbm"
        :disabled="busy"
        @keyup.enter="add"
      />
      <Button text label="add" :disabled="busy || !adding.trim()" @click="add">
        <template #icon><Plus :size="14" /></template>
      </Button>
    </div>

    <!-- The version is the running kernel's; there is none to name until one runs. -->
    <p v-if="env.pythonVersion" class="px-1.5 text-sm text-muted-color">
      python {{ env.pythonVersion }} · uv.lock
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, InputText, Tag } from 'primevue'
import { Plus, X } from 'lucide-vue-next'
import type { EnvState } from '../../model/types'
import EnvMismatchBanner from '../session/EnvMismatchBanner.vue'

/**
 * The workspace env, read-mostly — one venv for every flow under it. This is
 * where the restart banner lives, because the packages are what it is about.
 * The section head and its disclosure belong to the panel's accordion.
 *
 * Add and remove go through the daemon to uv, so the lockfile stays the one
 * definition of the env. Neither invalidates anything: a materialization
 * records the lock hash it ran under, and what a running kernel already
 * imported is what the restart banner above is for.
 */
const props = defineProps<{ env: EnvState; busy?: boolean }>()

const emit = defineEmits<{
  'restart-kernel': []
  'add-packages': [packages: string[]]
  'remove-package': [name: string]
}>()

const adding = ref('')

function add(): void {
  const packages = adding.value
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean)
  if (!packages.length) return
  adding.value = ''
  emit('add-packages', packages)
}

const tinyTag = { root: { class: 'shrink-0 px-1.5 py-0 text-sm font-normal' } }

const behind = computed(() =>
  props.env.packages.filter((pkg) => pkg.pendingRestart).map((pkg) => pkg.name),
)
</script>
