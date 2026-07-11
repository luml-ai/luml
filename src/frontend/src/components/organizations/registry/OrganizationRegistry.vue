<template>
  <div>
    <div class="header">
      <h3 class="label">
        List of Buckets for current organization ({{ bucketsStore.buckets.length }})
      </h3>
      <OrganizationBucketCreator></OrganizationBucketCreator>
    </div>
    <OrganizationRegistryTable></OrganizationRegistryTable>
  </div>
</template>

<script setup lang="ts">
import OrganizationRegistryTable from './OrganizationRegistryTable.vue'
import OrganizationBucketCreator from './OrganizationBucketCreator.vue'
import { useBucketsStore } from '@/stores/buckets'

const bucketsStore = useBucketsStore()
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.label {
  font-weight: 500;
  font-size: 20px;
}
</style>
