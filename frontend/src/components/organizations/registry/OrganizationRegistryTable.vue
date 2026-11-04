<template>
  <div class="table-wrapper">
    <UiPageLoader v-if="loading" />
    <div v-else class="table">
      <div class="simple-table__header">
        <div class="simple-table__row">
          <div>Name</div>
          <div>Endpoint</div>
          <div>Created</div>
          <div></div>
        </div>
      </div>
      <div class="simple-table__rows">
        <div v-if="loadError" class="simple-table__placeholder">Failed to load buckets.</div>
        <div v-else-if="!bucketsStore.buckets.length" class="simple-table__placeholder">
          No buckets created for this organization.
        </div>
        <div v-for="bucket in bucketsStore.buckets" :key="bucket.id" class="simple-table__row">
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
  </div>
</template>

<script setup lang="ts">
import { useBucketsStore } from '@/stores/buckets'
import { useOrganizationStore } from '@/stores/organization'
import { onMounted, ref } from 'vue'
import { useToast } from 'primevue'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import BucketSettings from './BucketSettings.vue'

const bucketsStore = useBucketsStore()
const organizationStore = useOrganizationStore()

const toast = useToast()
const loading = ref(false)
const loadError = ref(false)

onMounted(async () => {
  try {
    const organizationId = organizationStore.currentOrganization?.id
    if (!organizationId) return
    loading.value = true
    await bucketsStore.getBuckets(organizationId)
  } catch (e) {
    loadError.value = true
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load buckets')))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
@import '@/assets/tables.css';

.table-wrapper {
  overflow-x: auto;
  padding: 16px;
  border-radius: 8px;
  background: var(--p-card-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--card-shadow);
}

.table {
  min-width: 750px;
}

.simple-table__row {
  grid-template-columns: 300px 1fr 120px 35px;
}

.cell {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
