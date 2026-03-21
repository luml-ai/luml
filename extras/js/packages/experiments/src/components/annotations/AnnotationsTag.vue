<template>
  <Tag class="tag">
    {{ props.count }}
    <Pencil :size="12" />
  </Tag>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { Pencil } from 'lucide-vue-next'

interface Props {
  count: number
}

const props = defineProps<Props>()
</script>

<style scoped>
.tag {
  flex: 0 0 auto;
}
</style>
