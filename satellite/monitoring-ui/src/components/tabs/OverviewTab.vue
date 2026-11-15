<template>
  <div>Overview</div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'

useMonitoringData((dims) => api.monitoring.getOverview(dims))
</script>
