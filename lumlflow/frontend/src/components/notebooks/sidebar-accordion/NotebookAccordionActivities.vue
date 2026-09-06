<template>
  <div>
    <div class="item">
      <Pencil :size="12" class="item-icon" color="var(--p-text-muted-color)" />
      <div class="item-content">
        <div class="item-title">put main-2 on disk</div>
        <div class="item-description">
          <User :size="12" />
          <span class="item-type-label">User</span>
          <span> · </span>
          <span>14:19</span>
        </div>
      </div>
    </div>
    <div class="item">
      <Split :size="12" class="item-icon" color="var(--p-text-muted-color)" />
      <div class="item-content">
        <div class="item-title">started main-2 from main branch main-2</div>
        <div class="item-description">
          <User :size="12" />
          <span class="item-type-label">User</span>
          <span> · </span>
          <span>14:18</span>
        </div>
      </div>
    </div>
    <div class="item">
      <CloudUpload :size="12" class="item-icon" color="var(--p-text-muted-color)" />
      <div class="item-content">
        <div class="item-title">correlation_heatmap.plot did not upload</div>
        <div class="item-description">
          <Bot :size="12" />
          <span class="item-type-label">system</span>
          <span> · </span>
          <span>14:13</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bot, CloudUpload, Pencil, Split, User } from 'lucide-vue-next'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.item {
  @apply flex items-start gap-1 not-last:mb-2;
}
.item-icon {
  @apply shrink-0 mt-0.5;
}
.item-content {
  @apply text-sm;
}
.item-title {
  @apply text-sm font-medium truncate;
}
.item-description {
  @apply flex items-center gap-1 text-muted-color;
}
.item-type-label {
  @apply max-w-30 truncate;
}
</style>
