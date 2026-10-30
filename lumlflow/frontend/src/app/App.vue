<template>
  <ModelModal />
  <router-view></router-view>
  <UiDeleteConfirmation></UiDeleteConfirmation>
  <ConfirmDialog></ConfirmDialog>
  <Toast></Toast>
  <ApiKeyModal />
  <SessionTokenModal />
</template>

<script setup lang="ts">
import { ConfirmDialog, Toast } from 'primevue'
import UiDeleteConfirmation from '@/components/ui/UiDeleteConfirmation.vue'
import ApiKeyModal from '@/components/api-key/ApiKeyModal.vue'
import ModelModal from '@/components/model-card/ModelModal.vue'
import SessionTokenModal from '@/components/session-token/SessionTokenModal.vue'
</script>

<style scoped></style>
