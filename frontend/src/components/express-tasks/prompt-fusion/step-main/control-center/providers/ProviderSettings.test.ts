import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import PrimeVue from 'primevue/config'
import { Button, Checkbox, InputText } from 'primevue'
import ProviderSettings from './ProviderSettings.vue'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { getProviders } from '@/lib/promt-fusion/prompt-fusion.data'
import { ProvidersEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'

enableAutoUnmount(afterEach)

function mountSettings() {
  return mount(ProviderSettings, {
    props: {
      providerName: 'OpenAI',
      modelValue: true,
      settings: [
        {
          id: 'apiKey',
          label: 'API Key',
          placeholder: '',
          required: true,
          value: 'test-memory-key',
        },
      ],
    },
    global: {
      plugins: [PrimeVue],
      components: { 'd-button': Button, 'd-checkbox': Checkbox, 'd-input-text': InputText },
      stubs: { 'd-dialog': { template: '<div><slot /><slot name="footer" /></div>' } },
    },
  })
}

describe('provider API key storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('removes stored API keys on opt-out while preserving nonsecret settings and session values', async () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: true,
      openAi: { apiKey: 'test-stored-key' },
      ollama: { apiKey: 'another-test-key', apiBase: 'http://localhost:11434' },
    })
    const wrapper = mountSettings()
    await wrapper.get('input[type="checkbox"]').setValue(false)

    expect(LocalStorageService.get('providersSettings')).toEqual({
      saveApiKeys: false,
      openAi: {},
      ollama: { apiBase: 'http://localhost:11434' },
    })
    expect(wrapper.get<HTMLInputElement>('input[type="text"]').element.value).toBe(
      'test-memory-key',
    )
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('save')?.[0][0]).toEqual([
      expect.objectContaining({ id: 'apiKey', value: 'test-memory-key' }),
    ])

    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBeUndefined()
  })

  it.each([false, undefined])(
    'cleans up legacy stored keys when storage is disabled (%s)',
    (saveApiKeys) => {
      LocalStorageService.set('providersSettings', {
        saveApiKeys,
        openAi: { apiKey: 'test-legacy-key' },
      })
      mountSettings()

      expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBeUndefined()
    },
  )

  it('ignores saved API keys when storage is disabled', () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: false,
      openAi: { apiKey: 'test-legacy-key' },
      ollama: { apiBase: 'http://localhost:11434' },
    })

    const providers = getProviders()
    expect(
      providers.find((provider) => provider.id === ProvidersEnum.openAi)?.settings[0].value,
    ).toBe('')
    expect(
      providers.find((provider) => provider.id === ProvidersEnum.ollama)?.settings[0].value,
    ).toBe('http://localhost:11434')
  })

  it('keeps and loads stored API keys while storage is enabled', () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: true,
      openAi: { apiKey: 'test-stored-key' },
    })
    mountSettings()

    expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBe('test-stored-key')
    expect(
      getProviders().find((provider) => provider.id === ProvidersEnum.openAi)?.settings[0].value,
    ).toBe('test-stored-key')
  })
})
