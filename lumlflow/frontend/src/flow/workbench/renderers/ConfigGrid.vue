<template>
  <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
    <template v-for="(value, key) in config" :key="key">
      <dt class="font-mono text-sm leading-5 text-muted-color">{{ key }}</dt>
      <dd class="font-mono text-sm leading-5 tabular-nums break-all">{{ formatParam(value) }}</dd>
    </template>
  </dl>
</template>

<script setup lang="ts">
import type { ParamValue } from '../model/types'
import { formatParam } from './shared'

defineProps<{ config: Record<string, ParamValue> }>()
</script>
