<template>
  <d-button severity="secondary" @click="onProviderButtonClick">
    <span>Providers</span>
    <brain :size="14" />
  </d-button>
  <d-dialog v-model:visible="visible" modal style="width: 100%; max-width: 500px" dismissable-mask>
    <template #header>
      <h2 class="dialog-title">Model provider</h2>
    </template>
    <div class="providers">
      <provider-item v-for="provider in providers" :key="provider.name" :provider="provider" />
    </div>
  </d-dialog>
  <provider-settings
    v-if="openedProvider"
    v-model="isProviderSettingsOpened"
    :settings="openedProvider.settings"
    :provider-name="openedProvider.name"
    @save="saveSettings"
  />
</template>

<script setup lang="ts">
import {
  type ProvidersEnum,
  type BaseProviderInfo,
  type ProviderSetting,
  ProviderStatus,
} from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { onBeforeMount, onBeforeUnmount, ref, watch } from 'vue'
import {
  applySavedProviders,
  getProviders,
  loadProviders,
} from '@/lib/promt-fusion/prompt-fusion.data'
import { Brain } from 'lucide-vue-next'
import { saveProviderSettings } from '@/lib/promt-fusion/provider-settings.storage'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import ProviderItem from './ProviderItem.vue'
import ProviderSettings from './ProviderSettings.vue'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'

const providers = ref(getProviders())
const visible = ref(false)
const openedProvider = ref<BaseProviderInfo | null>(null)
const isProviderSettingsOpened = ref(false)

function saveSettings(settings: ProviderSetting[]) {
  if (!openedProvider.value) return
  const newStatus = settings.reduce((acc: ProviderStatus, setting) => {
    if (setting.required && !setting.value) return ProviderStatus.disconnected
    return acc
  }, ProviderStatus.connected)
  openedProvider.value.status = newStatus
  openedProvider.value.settings = settings
  promptFusionService.updateProviderSettings(openedProvider.value.id, settings)
  saveProviderSettings(openedProvider.value.id, settings)
  promptFusionService.closeProviderSettings()
}
function showSettings(provider: BaseProviderInfo) {
  openedProvider.value = provider
  promptFusionService.closeSettings()
  isProviderSettingsOpened.value = true
}
function onChangeSettingsStatus(open: boolean) {
  if (open) {
    visible.value = true
  } else {
    visible.value = false
  }
}
function onOpenProviderSettings(providerId: ProvidersEnum) {
  const provider = providers.value.find((p) => p.id === providerId)
  if (provider) showSettings(provider)
}
function onCloseProviderSettings() {
  isProviderSettingsOpened.value = false
  openedProvider.value = null
  promptFusionService.openSettings()
}
function onProviderButtonClick() {
  AnalyticsService.track(AnalyticsTrackKeysEnum.choose_provider, { task: 'prompt_optimization' })
  promptFusionService.openSettings()
}

async function restoreSavedProviders() {
  const savedProviders = await loadProviders()
  applySavedProviders(providers.value, savedProviders)
  promptFusionService.restoreSavedProviders(savedProviders)
}

watch(isProviderSettingsOpened, (val) => {
  if (!val) promptFusionService.closeProviderSettings()
})

onBeforeMount(() => {
  promptFusionService.on('OPEN_PROVIDER_SETTINGS', onOpenProviderSettings)
  promptFusionService.on('CLOSE_PROVIDER_SETTINGS', onCloseProviderSettings)
  promptFusionService.on('CHANGE_SETTINGS_STATUS', onChangeSettingsStatus)
  restoreSavedProviders()
})

onBeforeUnmount(() => {
  promptFusionService.off('OPEN_PROVIDER_SETTINGS', onOpenProviderSettings)
  promptFusionService.off('CLOSE_PROVIDER_SETTINGS', onCloseProviderSettings)
  promptFusionService.off('CHANGE_SETTINGS_STATUS', onChangeSettingsStatus)
})
</script>

<style scoped>
.dialog-title {
  font-size: 20px;
  font-weight: 600;
  text-transform: uppercase;
}
.providers {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 6px 0 4px;
  padding-right: 10px;
  max-height: 263px;
  overflow-y: auto;
}
</style>
