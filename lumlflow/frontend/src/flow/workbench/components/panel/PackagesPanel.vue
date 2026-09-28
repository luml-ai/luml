<template>
  <div class="flex min-w-0 flex-col gap-2.5">
    <EnvMismatchBanner v-if="env.mismatch" :behind="behind" @restart="emit('restart-kernel')" />
    <ul class="flex flex-col">
      <li
        v-for="pkg in env.packages"
        :key="pkg.name"
        class="flex min-w-0 items-center gap-2 px-1.5 py-1"
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
      </li>
    </ul>
    <p v-if="!env.packages.length" class="px-1.5 text-sm text-muted-color">
      no uv-managed environment here
    </p>

    <!-- The version is the running kernel's; there is none to name until one runs. -->
    <p v-if="env.pythonVersion" class="px-1.5 text-sm text-muted-color">
      python {{ env.pythonVersion }} · uv.lock
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { EnvState } from '../../model/types'
import EnvMismatchBanner from '../session/EnvMismatchBanner.vue'

const props = defineProps<{ env: EnvState }>()

const emit = defineEmits<{
  'restart-kernel': []
}>()

const tinyTag = { root: { class: 'shrink-0 px-1.5 py-0 text-sm font-normal' } }

const behind = computed(() =>
  props.env.packages.filter((pkg) => pkg.pendingRestart).map((pkg) => pkg.name),
)
</script>
