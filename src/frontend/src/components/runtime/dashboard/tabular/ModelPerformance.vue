<template>
  <div>
    <div class="radialbar-wrapper">
      <apexchart
        type="radialBar"
        :series="[totalScore]"
        :options="totalScoreOptions"
        :style="{ pointerEvents: 'none', marginTop: '-30px', height: '135px' }"
      />
    </div>
    <div class="metrics">
      <metric-card
        v-for="card in metrics"
        :key="card.title"
        :title="card.title"
        :items="card.items"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { getRadialBarOptions } from '@/lib/apex-charts/apex-charts'
import MetricCard from '@/components/ui/MetricCard.vue'

type Props = {
  metrics: { title: string; items: { value: string }[] }[]
  totalScore: number
}

defineProps<Props>()

const totalScoreOptions = ref(getRadialBarOptions())
</script>

<style scoped>
.radialbar-wrapper {
  max-width: 325px;
  margin: 0 auto;
  margin-bottom: 2rem;
}
.radialbar-wrapper .vue-apexcharts {
  min-height: 0 !important;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  width: 100%;
  padding-top: 16px;
}
</style>
