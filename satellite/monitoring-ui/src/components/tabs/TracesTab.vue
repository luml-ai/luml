<template>
  <div>Traces</div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'

useMonitoringData((dims) => api.monitoring.getTraces(dims, { limit: 50, offset: 0 }))
</script>
