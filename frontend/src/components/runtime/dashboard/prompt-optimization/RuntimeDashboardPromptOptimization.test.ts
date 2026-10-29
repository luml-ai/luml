import type { Model } from '@fnnx-ai/web'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Button, Checkbox, InputText } from 'primevue'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { ProvidersEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import ProviderSettings from '@/components/express-tasks/prompt-fusion/step-main/control-center/providers/ProviderSettings.vue'
import RuntimeDashboardPromptOptimization from './RuntimeDashboardPromptOptimization.vue'

const { computePythonModel } = vi.hoisted(() => ({ computePythonModel: vi.fn() }))

vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    computePythonModel,
    deallocateModels: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: {},
}))
vi.mock('@/hooks/useDataTable', async () => {
  const { ref } = await import('vue')
  return {
    useDataTable: () => ({
      isUploadWithErrors: ref(false),
      fileData: ref({}),
      onSelectFile: vi.fn(),
      onRemoveFile: vi.fn(),
      getDataForTraining: vi.fn(),
    }),
  }
})

enableAutoUnmount(afterEach)

async function mountRuntime(provider = ProvidersEnum.openAi) {
  const tag =
    provider === ProvidersEnum.openAi
      ? 'dataforce.studio/prompt-fusion::provider_api_key:v1'
      : 'dataforce.studio/prompt-fusion::provider_base_url:v1'
  const model = {
    getMetadata: () => [{ provider: provider.toLowerCase(), payload: {} }],
    getDtypes: () => ({ 'ext::in': { type: 'object', properties: { text: { type: 'string' } } } }),
    getManifest: () => ({ dynamic_attributes: [{ tags: [tag] }, { tags: ['unrelated'] }] }),
  } as unknown as Model
  const wrapper = mount(RuntimeDashboardPromptOptimization, {
    props: { model, modelId: 'runtime-model' },
    global: {
      plugins: [PrimeVue],
      components: { 'd-button': Button, 'd-checkbox': Checkbox, 'd-input-text': InputText },
      stubs: {
        'd-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        PresentationArea: true,
        FileInput: true,
        SelectButton: true,
        FloatLabel: { template: '<div><slot /></div>' },
      },
    },
  })
  await vi.runAllTimersAsync()
  await wrapper.get('.manual input').setValue('test input')
  return wrapper
}

describe('runtime provider session credentials', () => {
  beforeEach(async () => {
    localStorage.clear()
    await promptFusionService.resetState()
    computePythonModel.mockResolvedValue({ status: 'success', predictions: { out: 'prediction' } })
    vi.useFakeTimers()
  })

  afterEach(() => vi.useRealTimers())

  it('keeps predictions authenticated after deleting a stored key on opt-out', async () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: true,
      openAi: { apiKey: 'test-saved-key' },
    })
    const wrapper = await mountRuntime()
    await wrapper.get('.manual button').trigger('click')
    await flushPromises()
    expect(computePythonModel).toHaveBeenLastCalledWith(
      expect.objectContaining({ dynamic_attributes: { api_key: 'test-saved-key' } }),
    )

    await wrapper.get('.provider button').trigger('click')
    const settings = wrapper.getComponent(ProviderSettings)
    await settings.get('input[type="checkbox"]').setValue(false)
    expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBeUndefined()
    await settings.get('button').trigger('click')
    await vi.runAllTimersAsync()
    expect(wrapper.get('.manual button').attributes('disabled')).toBeUndefined()
    await wrapper.get('.manual button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledTimes(2)
    expect(computePythonModel).toHaveBeenLastCalledWith({
      inputs: { in: { text: 'test input' } },
      model_id: 'runtime-model',
      dynamic_attributes: { api_key: 'test-saved-key' },
    })
    expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBeUndefined()
  })

  it('uses newly entered session keys and clears credentials when the provider disconnects', async () => {
    const wrapper = await mountRuntime()
    await wrapper.get('.provider button').trigger('click')
    let settings = wrapper.getComponent(ProviderSettings)
    await settings.get('input[type="text"]').setValue('test-session-key')
    await settings.get('button').trigger('click')
    await vi.runAllTimersAsync()
    await wrapper.get('.manual button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ dynamic_attributes: { api_key: 'test-session-key' } }),
    )
    expect(LocalStorageService.get('providersSettings')?.openAi?.apiKey).toBeUndefined()

    await wrapper.get('.provider button').trigger('click')
    settings = wrapper.getComponent(ProviderSettings)
    await settings.get('input[type="text"]').setValue('')
    await settings.get('button').trigger('click')
    await vi.runAllTimersAsync()

    expect(wrapper.get('.manual button').attributes('disabled')).toBeDefined()
    expect(
      wrapper
        .getComponent({ name: 'RuntimeDashboardPromptOptimizationPredict' })
        .props('dynamicAttributes'),
    ).toEqual({ api_key: '' })
  })

  it('uses the current Ollama session base URL when storage is disabled', async () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: false,
      ollama: { apiBase: 'http://localhost:11434' },
    })
    const wrapper = await mountRuntime(ProvidersEnum.ollama)
    await wrapper.get('.provider button').trigger('click')
    const settings = wrapper.getComponent(ProviderSettings)
    await settings.get('input[type="text"]').setValue('http://localhost:11435')
    await settings.get('button').trigger('click')
    await vi.runAllTimersAsync()
    await wrapper.get('.manual button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ dynamic_attributes: { api_base: 'http://localhost:11435' } }),
    )
    expect(LocalStorageService.get('providersSettings')?.ollama?.apiBase).toBe(
      'http://localhost:11434',
    )
  })
})
