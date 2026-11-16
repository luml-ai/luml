<template>
  <div class="multivariate-drift">
    <MultivariateDriftProjection class="projection" :multivariate="multivariate" />
    <MultivariateDriftMetrics class="metrics" :metrics="metrics" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MultivariatePanel } from '@/api/monitoring/interfaces'
import { getMultivariateMetrics } from '@/utils/drift'
import MultivariateDriftProjection from '@/components/feature-drift/MultivariateDriftProjection.vue'
import MultivariateDriftMetrics from '@/components/feature-drift/MultivariateDriftMetrics.vue'

interface Props {
  multivariate: MultivariatePanel
  totalFeatures: number
}

const props = defineProps<Props>()

const metrics = computed(() => getMultivariateMetrics(props.multivariate, props.totalFeatures))
</script>

<style scoped>
.multivariate-drift {
  display: flex;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
}

.projection {
  flex: 1;
  min-width: 0;
  border-right: 1px solid var(--p-content-border-color);
}

.metrics {
  flex-shrink: 0;
  width: 200px;
}

@media (max-width: 720px) {
  .multivariate-drift {
    flex-direction: column;
  }

  .projection {
    border-right: none;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  .metrics {
    width: auto;
  }
}
</style>
