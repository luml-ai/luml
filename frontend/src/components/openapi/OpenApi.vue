<template>
  <div class="scalar">
    <ApiReference
      class="api-reference"
      :configuration="configuration"
      :server="'http://localhost:8000'"
    />
  </div>
</template>

<script setup lang="ts">
import '@scalar/api-reference/style.css'
import { computed, watch } from 'vue'
import { ApiReference } from '@scalar/api-reference'
import { useThemeStore } from '@/stores/theme'
import { type AnyApiReferenceConfiguration } from '@scalar/types/api-reference'

const themeStore = useThemeStore()
const theme = computed(() => themeStore.getCurrentTheme)

type Props = {
  content: any
  serverUrl: string
}

const props = defineProps<Props>()

const configuration = computed<AnyApiReferenceConfiguration>(() => {
  return {
    content: props.content,
    showSidebar: false,
    theme: 'purple',
    hideTestRequestButton: true,
    hideDarkModeToggle: true,
    baseServerURL: 'https://scalar.com',
    showToolbar: 'never',
    servers: [
      {
        url: props.serverUrl,
      },
    ],
  }
})

watch(
  theme,
  (t) => {
    setTimeout(() => {
      if (t === 'dark') {
        document.body.classList.add('dark-mode')
        document.body.classList.remove('light-mode')
      } else {
        document.body.classList.remove('dark-mode')
        document.body.classList.add('light-mode')
      }
    }, 100)
  },
  { immediate: true },
)
</script>

<style>
.api-reference {
  max-height: 300px;
}
</style>
