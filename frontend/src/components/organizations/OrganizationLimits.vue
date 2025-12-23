<template>
  <div v-if="organizationStore.organizationDetails" class="limits">
    <h3 class="limits-title">Monitor usage limits</h3>
    <p class="limits-text">
      Limits are based on the current plan. Upgrades will be available soon.
    </p>
    <div class="items">
      <div class="item">
        <UiCircleProgress
          :progress="
            ((organizationStore.organizationDetails.total_members || 0) /
              organizationStore.organizationDetails.members_limit) *
            100
          "
          class="progress"
        ></UiCircleProgress>
        <div class="item-content">
          <div class="item-values">
            {{ organizationStore.organizationDetails?.members.length }}/{{
              organizationStore.organizationDetails.members_limit
            }}
          </div>
          <div class="item-label">users limit per organization</div>
        </div>
      </div>
      <div class="item">
        <UiCircleProgress
          :progress="
            ((organizationStore.organizationDetails.total_orbits || 0) /
              organizationStore.organizationDetails.orbits_limit) *
            100
          "
          class="progress"
        ></UiCircleProgress>
        <div class="item-content">
          <div class="item-values">
            {{ organizationStore.organizationDetails.total_orbits }}/{{
              organizationStore.organizationDetails.orbits_limit
            }}
          </div>
          <div class="item-label">orbits limit per organization</div>
        </div>
      </div>
      <div class="item">
        <UiCircleProgress
          :progress="
            ((organizationStore.organizationDetails.total_satellites || 0) /
              organizationStore.organizationDetails.satellites_limit) *
            100
          "
          class="progress"
        />
        <div class="item-content">
          <div class="item-values">
            {{ organizationStore.organizationDetails.total_satellites }}/{{
              organizationStore.organizationDetails.satellites_limit
            }}
          </div>
          <div class="item-label">satellites limit per organization</div>
        </div>
      </div>

      <div class="item">
        <UiCircleProgress
          :progress="
            ((organizationStore.organizationDetails.total_model_artifacts || 0) /
              organizationStore.organizationDetails.model_artifacts_limit) *
            100
          "
          class="progress"
        />
        <div class="item-content">
          <div class="item-values">
            {{ organizationStore.organizationDetails.total_model_artifacts }}/{{
              organizationStore.organizationDetails.model_artifacts_limit
            }}
          </div>
          <div class="item-label">artifacts limit per organization</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useOrganizationStore } from '@/stores/organization'
import UiCircleProgress from '../ui/UiCircleProgress.vue'

const organizationStore = useOrganizationStore()
</script>

<style scoped>
.limits {
  padding: 16px 24px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  box-shadow: var(--card-shadow);
}
.limits-title {
  font-size: 20px;
  font-weight: 500;
  margin-bottom: 8px;
}
.limits-text {
  font-size: 14px;
  color: var(--p-text-muted-color);
  margin-bottom: 20px;
}
.items {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}
.item {
  display: flex;
  gap: 12px;
  align-items: center;
}
.item-content {
  font-size: 12px;
}
.item-values {
  margin-bottom: 2px;
}
.item-label {
  color: var(--p-text-muted-color);
}
.progress {
  flex: 0 0 auto;
}
@media (max-width: 1100px) {
  .items {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 768px) {
  .items {
    grid-template-columns: 1fr;
  }
}
</style>
