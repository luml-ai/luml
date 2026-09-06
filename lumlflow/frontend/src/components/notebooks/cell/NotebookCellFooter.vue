<template>
  <footer class="footer">
    <div class="footer-left">
      <User :size="14" color="var(--p-button-text-secondary-color)" class="mt-1" />
      <div>
        <h3 class="mb-1">User</h3>
        <div class="text-sm text-muted-color">offline edits: 8 cells changed</div>
      </div>
    </div>
    <div class="footer-right">
      <Button variant="outlined" severity="secondary" class="p-0 w-10 h-10">
        <template #icon>
          <Play :size="14" />
        </template>
      </Button>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { Play, User } from 'lucide-vue-next'
import { Button } from 'primevue'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.footer {
  @apply flex items-center justify-between gap-4;
}
.footer-left {
  @apply flex items-start gap-1;
}
</style>
