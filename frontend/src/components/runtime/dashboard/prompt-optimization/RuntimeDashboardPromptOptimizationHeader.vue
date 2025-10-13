<template>
  <header class="header">
    <h1 class="title">Runtime</h1>
    <div class="buttons">
      <div class="provider">
        <div class="provider-info">
          <img src="@/assets/img/providers/open-ai.svg" alt="" width="20" height="20" />
          <span>OpenAI</span>
          <div
            class="status"
            :class="{ 'status--success': currentProvider?.status === ProviderStatus.connected }"
          ></div>
        </div>
        <Button severity="secondary" variant="text" @click="showProviderSettings()">
          <template #icon>
            <Bolt :size="14" />
          </template>
        </Button>
      </div>
      <Button asChild v-slot="slotProps">
        <RouterLink :to="{ name: 'home' }" :class="slotProps.class">finish</RouterLink>
      </Button>
    </div>
    <provider-settings
      v-if="openedProvider"
      :model-value="!!openedProvider"
      :settings="openedProvider.settings"
      :provider-name="openedProvider.name"
      @save="saveSettings"
      @update:model-value="openedProvider = null"
    />
  </header>
</template>

<script setup lang="ts">
import type { BaseProviderInfo, ProviderSetting } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import type { LocalStorageProviderSettings } from '@/utils/services/LocalStorageService.interfaces'
import { Button } from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { ProviderStatus, ProvidersEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { getProviders } from '@/lib/promt-fusion/prompt-fusion.data'
import ProviderSettings from '@/components/express-tasks/prompt-fusion/step-main/control-center/providers/ProviderSettings.vue'

type Props = {
  providerId: ProvidersEnum
}

const props = defineProps<Props>()

const providers = ref(getProviders())
const openedProvider = ref<BaseProviderInfo | null>(null)

const currentProvider = computed(() => {
  return providers.value.find(
    (provider) => provider.id.toLowerCase() === props.providerId.toLowerCase(),
  )
})

function showProviderSettings() {
  if (!currentProvider.value) return
  openedProvider.value = currentProvider.value
}

function saveSettings(settings: ProviderSetting[]) {
  if (!openedProvider.value) return
  const newStatus = getStatus(settings)
  openedProvider.value.status = newStatus
  openedProvider.value.settings = settings
  const settingsInStorage = LocalStorageService.get('dataforce.providersSettings')
  promptFusionService.updateProviderSettings(openedProvider.value.id, settings)
  const isNeedToSaveData = settingsInStorage?.saveApiKeys
  if (isNeedToSaveData) {
    saveSettingsInLocalStorage(settings, settingsInStorage, openedProvider.value.id)
  }
  openedProvider.value = null
  promptFusionService.closeProviderSettings()
}

function getStatus(settings: ProviderSetting[]) {
  return settings.reduce((acc: ProviderStatus, setting) => {
    if (setting.required && !setting.value) return ProviderStatus.disconnected
    return acc
  }, ProviderStatus.connected)
}

function saveSettingsInLocalStorage(
  settings: ProviderSetting[],
  settingsInStorage: LocalStorageProviderSettings | null,
  provider: ProvidersEnum,
) {
  const oldSettings = settingsInStorage || {}
  oldSettings[provider] = settings.reduce((acc: Record<string, string>, setting) => {
    acc[setting.id] = setting.value
    return acc
  }, {})
  LocalStorageService.set('dataforce.providersSettings', oldSettings)
}

onBeforeMount(() => {
  if (!currentProvider.value) return
  promptFusionService.updateProviderSettings(
    currentProvider.value.id,
    currentProvider.value.settings,
  )
  promptFusionService.closeProviderSettings()
})

onUnmounted(() => {
  promptFusionService.resetState()
})
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.buttons {
  display: flex;
  gap: 12px;
  align-items: center;
}

.provider {
  padding: 4px 6px;
  display: flex;
  gap: 12px;
  align-items: center;
  background-color: var(--p-card-background);
  border-radius: var(--p-border-radius-lg);
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
}

.status {
  margin-left: 4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  position: relative;
  border: 1px solid var(--p-toast-error-border-color);
  background-color: var(--p-toast-error-background);
  display: flex;
  justify-content: center;
  align-items: center;
}

.status::before {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: var(--p-badge-danger-background);
  box-shadow: 0 2px 8px 0 rgba(239, 68, 68, 0.5);
}

.status--success {
  border-color: var(--p-toast-success-border-color);
  background-color: var(--p-toast-success-background);
}

.status--success::before {
  background-color: var(--p-badge-success-background);
  box-shadow: 0 2px 8px 0 rgba(34, 197, 94, 0.5);
}
</style>
