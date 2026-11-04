import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Select } from 'primevue'
import ModelSelect from './ModelSelect.vue'

const mocks = vi.hoisted(() => ({
  getArtifact: vi.fn(),
  getOrbitArtifacts: vi.fn(),
  toast: vi.fn(),
}))

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ getArtifact: mocks.getArtifact }),
}))
vi.mock('@/lib/api', () => ({
  api: { artifacts: { getOrbitArtifacts: mocks.getOrbitArtifacts } },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))

enableAutoUnmount(afterEach)
beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
})
afterEach(() => vi.unstubAllGlobals())

const initialModel = { id: 'selected-model', name: 'Selected model' }
const firstPage = Array.from({ length: 20 }, (_, index) => ({
  id: `model-${index}`,
  name: `Model ${index}`,
}))

function mountSelect(collectionId: string | null = 'collection') {
  mocks.getArtifact.mockResolvedValue(initialModel)
  return mount(ModelSelect, {
    props: {
      disabled: true,
      organizationId: 'org',
      orbitId: 'orbit',
      collectionId,
      initialModelId: initialModel.id,
      modelValue: initialModel.id,
    },
    global: { plugins: [PrimeVue] },
  })
}

it('displays the initial model when it is outside the first page', async () => {
  mocks.getOrbitArtifacts.mockResolvedValue({ items: firstPage, cursor: 'next' })
  const wrapper = mountSelect()
  await flushPromises()

  expect(mocks.getOrbitArtifacts).toHaveBeenCalled()
  expect(wrapper.getComponent(Select).props('options')).toEqual([...firstPage, initialModel])
  expect(wrapper.get('[data-pc-section="label"]').text()).toBe(initialModel.name)
})

it('does not duplicate an initial model already in the first page', async () => {
  mocks.getOrbitArtifacts.mockResolvedValue({ items: [initialModel], cursor: null })
  const wrapper = mountSelect()
  await flushPromises()

  expect(wrapper.getComponent(Select).props('options')).toEqual([initialModel])
  expect(wrapper.get('[data-pc-section="label"]').text()).toBe(initialModel.name)
})

it('displays the initial model without a collection', async () => {
  const wrapper = mountSelect(null)
  await flushPromises()

  expect(mocks.getOrbitArtifacts).not.toHaveBeenCalled()
  expect(wrapper.get('[data-pc-section="label"]').text()).toBe(initialModel.name)
})

it('keeps the initial model and reports a failed first page load', async () => {
  mocks.getOrbitArtifacts.mockRejectedValue(new Error('Models unavailable'))
  const wrapper = mountSelect()
  await flushPromises()

  expect(wrapper.get('[data-pc-section="label"]').text()).toBe(initialModel.name)
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ severity: 'error', detail: 'Models unavailable' }),
  )
})
