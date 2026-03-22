<template>
  <router-view></router-view>
  <UiDeleteConfirmation></UiDeleteConfirmation>
  <ConfirmDialog></ConfirmDialog>
  <Toast></Toast>
  <ApiKeyModal />
</template>

<script setup lang="ts">
import { ConfirmDialog, Toast } from 'primevue'
import UiDeleteConfirmation from '@/components/ui/UiDeleteConfirmation.vue'
import ApiKeyModal from '@/components/api-key/ApiKeyModal.vue'
</script>

<style scoped></style>
