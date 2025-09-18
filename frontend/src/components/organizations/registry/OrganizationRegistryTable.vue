<template>
  <div class="simple-table">
    <div class="simple-table__header">
      <div class="simple-table__row">
        <div>Name</div>
        <div>Endpoint</div>
        <div>Created</div>
        <div></div>
      </div>
    </div>
    <div class="simple-table__rows">
      <div v-if="!bucketsStore.buckets.length" class="simple-table__placeholder">
        No buckets created for this organization.
      </div>
      <div v-for="bucket in bucketsStore.buckets" class="simple-table__row">
        <div class="cell">
          {{ bucket.bucket_name }}
        </div>
        <div class="cell">
          {{ bucket.endpoint }}
        </div>
        <div>{{ new Date(bucket.created_at).toLocaleDateString() }}</div>
        <div>
          <BucketSettings :bucket="bucket" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useBucketsStore } from '@/stores/buckets'
import { useOrganizationStore } from '@/stores/organization'
import { onMounted, ref } from 'vue'
import BucketSettings from './BucketSettings.vue'

const bucketsStore = useBucketsStore()
const organizationStore = useOrganizationStore()

const loading = ref()

onMounted(async () => {
  try {
    const organizationId = organizationStore.currentOrganization?.id
    if (!organizationId) return
    await bucketsStore.getBuckets(organizationId)
  } catch {
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
@import '@/assets/tables.css';

.simple-table__row {
  grid-template-columns: 300px 1fr 120px 35px;
}

.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
