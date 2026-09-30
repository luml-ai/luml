import { Form, type FormInstance } from '@primevue/forms'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import TracksCreator from './TracksCreator.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.unstubAllGlobals())

const mocks = vi.hoisted(() => ({
  createTrack: vi.fn(),
  hideCreator: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/tracks', () => ({
  useTracksStore: () => ({
    creatorVisible: true,
    createTrack: mocks.createTrack,
    hideCreator: mocks.hideCreator,
    showCreator: vi.fn(),
  }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: mocks.toastAdd }) }
})

function mountCreator() {
  return mount(TracksCreator, {
    attachTo: document.body,
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      directives: { tooltip: {} },
      stubs: {
        Dialog: { template: '<div><slot /></div>' },
        Teleport: true,
      },
    },
  })
}

async function fillRequiredFields(wrapper: ReturnType<typeof mountCreator>) {
  await wrapper.get('input[name="name"]').setValue('Release track')
  await wrapper.get('[role="combobox"]').trigger('click')
  await wrapper.get('[role="option"][aria-label="Model"]').trigger('mousedown')
  await flushPromises()
}

describe('TracksCreator validation', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    mocks.createTrack.mockReset()
    mocks.createTrack.mockResolvedValue(undefined)
  })

  it('shows required field errors after Create is clicked with empty fields', async () => {
    const wrapper = mountCreator()
    const createButton = wrapper.get('button[type="submit"]')

    expect(wrapper.text()).not.toContain('Name is required')
    expect(wrapper.text()).not.toContain('Type is required')
    expect(createButton.attributes('disabled')).toBeUndefined()

    await createButton.trigger('click')
    await flushPromises()

    expect(wrapper.get('input[name="name"]').element.closest('.field')?.textContent).toContain(
      'Name is required',
    )
    expect(wrapper.get('[role="combobox"]').element.closest('.field')?.textContent).toContain(
      'Type is required',
    )
    expect(mocks.createTrack).not.toHaveBeenCalled()
    expect(mocks.hideCreator).not.toHaveBeenCalled()
    expect(createButton.attributes('disabled')).toBeUndefined()
  })

  it.each([
    ['name', 'a'.repeat(101), 'Name must be at most 100 characters'],
    ['description', 'a'.repeat(256), 'Description must be at most 255 characters'],
    ['stages', [], 'At least one stage is required'],
    ['stages', [''], 'Stage name is required'],
    ['stages', ['a'.repeat(101)], 'Stage names must be at most 100 characters'],
  ])('shows an inline error for invalid %s', async (field, value, message) => {
    const wrapper = mountCreator()
    await fillRequiredFields(wrapper)
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue(field, value)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get(`label[for="${field}"]`).element.closest('.field')?.textContent).toContain(
      message,
    )
    expect(mocks.createTrack).not.toHaveBeenCalled()
  })

  it('clears errors when corrected and creates a track with an optional empty description', async () => {
    const wrapper = mountCreator()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    await fillRequiredFields(wrapper)
    expect(wrapper.text()).not.toContain('Name is required')
    expect(wrapper.text()).not.toContain('Type is required')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.createTrack).toHaveBeenCalledExactlyOnceWith({
      name: 'Release track',
      description: '',
      artifact_type: ArtifactTypeEnum.model,
      stages: ['Production', 'Pre-Production', 'Staging'],
    })
    expect(mocks.hideCreator).toHaveBeenCalledOnce()
    expect(mocks.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
  })

  it('shows the stage requirement after all default stages are removed', async () => {
    const wrapper = mountCreator()
    await fillRequiredFields(wrapper)
    for (let index = 0; index < 3; index++) {
      await wrapper.get('.remove-icon').trigger('click')
    }

    await wrapper.get('button[type="submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('label[for="stages"]').element.closest('.field')?.textContent).toContain(
      'At least one stage is required',
    )
    expect(mocks.createTrack).not.toHaveBeenCalled()
  })

  it('accepts the maximum name, description and stage lengths', async () => {
    const wrapper = mountCreator()
    await fillRequiredFields(wrapper)
    await wrapper.get('input[name="name"]').setValue('n'.repeat(100))
    await wrapper.get('textarea[name="description"]').setValue('d'.repeat(255))
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stages', ['s'.repeat(100)])

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.createTrack).toHaveBeenCalledExactlyOnceWith({
      name: 'n'.repeat(100),
      description: 'd'.repeat(255),
      artifact_type: ArtifactTypeEnum.model,
      stages: ['s'.repeat(100)],
    })
  })

  it('disables Create while pending and preserves the form when creation fails', async () => {
    let rejectCreation!: (reason: Error) => void
    mocks.createTrack.mockReturnValue(
      new Promise((_, reject) => {
        rejectCreation = reject
      }),
    )
    const wrapper = mountCreator()
    await fillRequiredFields(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    rejectCreation(new Error('Track creation failed'))
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get<HTMLInputElement>('input[name="name"]').element.value).toBe('Release track')
    expect(mocks.hideCreator).not.toHaveBeenCalled()
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Track creation failed' }),
    )
  })
})
