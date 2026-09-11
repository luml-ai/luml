<template>
  <section class="page">
    <div>
      <h1 class="title">Invitation center</h1>
      <p class="subtitle">Organization invitations awaiting your response.</p>
    </div>
    <InvitationsList />
  </section>
</template>

<script setup lang="ts">
import InvitationsList from '@/components/user/InvitationsList.vue'
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 40px 0;
}
.title {
  font-size: 24px;
  font-weight: 600;
  text-transform: uppercase;
}
.subtitle {
  color: var(--p-text-muted-color);
  margin-top: 8px;
}
</style>
