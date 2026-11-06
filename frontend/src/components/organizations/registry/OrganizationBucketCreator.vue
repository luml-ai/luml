<template>
  <div>
    <Button @click="visible = true">
      <Plus :size="14" />
      <span>New bucket</span>
    </Button>
    <OrganizationBucketDialog v-model:visible="visible" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import OrganizationBucketDialog from './OrganizationBucketDialog.vue'

const visible = ref(false)
</script>
