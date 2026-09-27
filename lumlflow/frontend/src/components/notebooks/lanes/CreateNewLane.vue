<template>
  <div>
    <Button variant="text" class="px-2.5!" @click="visible = true">
      <Plus :size="14" />
      <span>New lane</span>
    </Button>
    <CreateLaneDialog v-model:visible="visible" />
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { ref } from 'vue'
import CreateLaneDialog from './CreateLaneDialog.vue'

const visible = ref(false)
</script>
