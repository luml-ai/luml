<template>
  <TracesWrapper :artifactId="String(route.params.experimentId)" />
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { TracesWrapper } from '@luml/experiments'

const route = useRoute()
</script>

<style scoped></style>
