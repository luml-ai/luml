<template>
  <UICustomToast />
  <d-confirm-dialog style="width: 21.75rem" />
  <app-template>
    <RouterView />
  </app-template>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppTemplate from './templates/AppTemplate.vue'
import { onBeforeMount } from 'vue'
import { useThemeStore } from './stores/theme'
import { useAppScrollbarFix } from './hooks/useAppScrollbarFix'
import { DataProcessingWorker } from './lib/data-processing/DataProcessingWorker'
import UICustomToast from './components/ui/UICustomToast.vue'

const themeStore = useThemeStore()
useAppScrollbarFix()

onBeforeMount(() => {
  DataProcessingWorker.initPyodide()
  themeStore.checkTheme()
})
</script>

<style scoped></style>
