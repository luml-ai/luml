<template>
  <div v-if="warnings.length" class="mb-3 space-y-1.5">
    <Message
      v-for="(warning, index) in warnings"
      :key="index"
      :severity="warning.kind === 'divergent-pin' ? 'error' : 'warn'"
      size="small"
    >
      <div class="min-w-0 text-sm">
        <p class="font-medium">{{ title(warning.kind) }}</p>
        <p>{{ warning.message }}</p>
      </div>
    </Message>
  </div>
</template>

<script setup lang="ts">
import { Message } from 'primevue'
import type { IntegrityWarning } from '../types'

/**
 * Reasons a comparison may not be apples to apples.
 *
 * The divergent-pin case is the flagship: content addressing lets us detect
 * exactly that two lanes read different versions of a shared upstream, where
 * every competing tool can only guess. Without this warning, pin-at-fork quietly
 * destroys the trustworthiness of every metric shown next to it.
 */
defineProps<{ warnings: IntegrityWarning[] }>()

const title = (kind: IntegrityWarning['kind']): string => {
  switch (kind) {
    case 'divergent-pin':
      return 'Divergent upstream pins'
    case 'dataset-mismatch':
      return 'Dataset inconsistency detected'
    case 'scoring-mismatch':
      return 'Scoring inconsistency detected'
    case 'nondeterministic-input':
      return 'Non-deterministic asset'
  }
}
</script>
