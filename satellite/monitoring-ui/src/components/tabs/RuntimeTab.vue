<template>
  <div>Runtime</div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'

useMonitoringData((dims) => api.monitoring.getRuntime(dims))
</script>
