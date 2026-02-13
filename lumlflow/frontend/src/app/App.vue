<template>
  <router-view></router-view>
  <UiDeleteConfirmation></UiDeleteConfirmation>
  <ConfirmDialog></ConfirmDialog>
  <Toast></Toast>
</template>

<script setup lang="ts">
import { ConfirmDialog, Toast } from 'primevue'
import UiDeleteConfirmation from '@/components/ui/UiDeleteConfirmation.vue'
</script>

<style scoped></style>
