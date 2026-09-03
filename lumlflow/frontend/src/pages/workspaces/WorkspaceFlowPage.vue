<template>
  <div>{{ directory }}</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const directory = computed(() => route.query.directory)
</script>

<style scoped></style>
