<template>
  <Button variant="outlined">
    {{ props.count }}
    <Pencil :size="14" />
  </Button>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Pencil } from 'lucide-vue-next'

interface Props {
  count: number
}

const props = defineProps<Props>()
</script>

<style scoped></style>
