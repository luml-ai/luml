import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ModelUpload from '../ModelUpload.vue'
import ArtifactCreator from '@/components/orbits/tabs/registry/collection/artifact/ArtifactCreator.vue'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'

const harness = vi.hoisted(() => ({
  upload: vi.fn(),
  toastAdd: vi.fn(),
  collection: { type: 'model' },
  progress: null as ReturnType<typeof ref<number | null>> | null,
}))

vi.mock('@/hooks/useArtifactUpload', () => ({
  useArtifactUpload: () => ({ upload: harness.upload, progress: harness.progress }),
}))
vi.mock('@/hooks/useArtifactsTags', () => ({
  useArtifactsTags: () => ({ loadTags: vi.fn(), getTagsByQuery: () => ['suggested'] }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ orbitsList: [], loadOrbitsList: vi.fn() }),
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: { id: 'org' } }),
}))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ currentCollection: harness.collection }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org', id: 'orbit', collectionId: 'collection' } }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: harness.toastAdd }),
}))

describe.each([
  { label: 'ModelUpload', component: ModelUpload, registry: false },
  { label: 'ArtifactCreator', component: ArtifactCreator, registry: true },
])('$label upload lifecycle', ({ component, registry }) => {
  let wrapper: ReturnType<typeof shallowMount>
  let resolveUpload: () => void
  let rejectUpload: (error: Error) => void

  beforeEach(async () => {
    harness.progress = ref(null)
    harness.collection.type = OrbitCollectionTypeEnum.model
    harness.upload.mockReset().mockImplementation(
      () =>
        new Promise<void>((resolve, reject) => {
          resolveUpload = resolve
          rejectUpload = reject
        }),
    )
    wrapper = shallowMount(component, {
      props: { visible: true, modelBlob: new Blob(['model']), fileName: 'model.luml' },
      global: {
        renderStubDefaultSlot: true,
        stubs: {
          Form: {
            name: 'Form',
            props: ['initialValues', 'resolver'],
            template: '<form><slot /></form>',
          },
          InputText: { name: 'InputText', props: ['modelValue'], template: '<input />' },
          Textarea: { name: 'Textarea', props: ['modelValue'], template: '<textarea />' },
          AutoComplete: {
            name: 'AutoComplete',
            props: ['modelValue', 'suggestions'],
            template: '<div />',
          },
          ProgressBar: {
            name: 'ProgressBar',
            props: ['value', 'mode'],
            template: '<div role="progressbar" />',
          },
          Dialog: {
            props: ['visible'],
            emits: ['update:visible'],
            template: '<div v-if="visible"><slot /></div>',
          },
          Button: {
            props: ['type', 'loading', 'disabled'],
            template: '<button :type="type" :disabled="disabled || loading"><slot /></button>',
          },
        },
      },
    })
    await flushPromises()
  })

  afterEach(() => wrapper.unmount())

  async function fillForm() {
    wrapper.getComponent({ name: 'InputText' }).vm.$emit('update:modelValue', 'My model')
    wrapper.getComponent({ name: 'Textarea' }).vm.$emit('update:modelValue', 'Description')
    wrapper.getComponent({ name: 'AutoComplete' }).vm.$emit('update:modelValue', ['tag'])
    wrapper.getComponent({ name: 'AutoComplete' }).vm.$emit('complete', { query: 'tag' })
    if (registry) {
      wrapper
        .getComponent({ name: 'FileInput' })
        .vm.$emit('select-file', new File(['model'], 'model.luml'))
    } else {
      wrapper.getComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'orbit')
      await flushPromises()
      wrapper
        .getComponent({ name: 'ArtifactUploadCollectionSelect' })
        .vm.$emit('update:modelValue', 'collection')
    }
    await flushPromises()
  }

  async function submit(valid = true) {
    wrapper.getComponent({ name: 'Form' }).vm.$emit('submit', { valid })
    await flushPromises()
  }

  function uploadSignal(call = 0): AbortSignal {
    return harness.upload.mock.calls[call][6]
  }

  it('shows upload progress and prevents duplicate uploads', async () => {
    await fillForm()
    await submit()
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)
    harness.progress!.value = 42
    await flushPromises()
    expect(wrapper.getComponent({ name: 'ProgressBar' }).props('value')).toBe(42)
    expect(uploadSignal()).toBeInstanceOf(AbortSignal)
    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Cancel'])
    await submit()
    expect(harness.upload).toHaveBeenCalledTimes(1)
  })

  it('cancels the request without displaying an error and clears the reopened form', async () => {
    await fillForm()
    await submit()
    const cancel = wrapper.findAll('button').find((button) => button.text() === 'Cancel')
    expect(cancel).toBeDefined()
    await cancel!.trigger('click')
    expect(uploadSignal().aborted).toBe(true)
    rejectUpload(new DOMException('Aborted', 'AbortError'))
    await flushPromises()
    expect(harness.toastAdd).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    const defaults = wrapper.getComponent({ name: 'Form' }).props('initialValues')
    expect(defaults).toMatchObject({ name: '', description: '', tags: [] })
    if (registry) expect(defaults).toMatchObject({ file: null, type: ArtifactTypeEnum.model })
    else expect(defaults).toMatchObject({ orbit: null, collection: null })
    expect(wrapper.getComponent({ name: 'AutoComplete' }).props('suggestions')).toEqual([])
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(false)
  })

  it('resets on an ordinary close and aborts when closed during upload', async () => {
    await fillForm()
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    expect(wrapper.getComponent({ name: 'Form' }).props('initialValues')).toMatchObject({
      name: '',
      tags: [],
    })
    await fillForm()
    await submit()
    await wrapper.setProps({ visible: false })
    expect(uploadSignal().aborted).toBe(true)
    rejectUpload(new DOMException('Aborted', 'AbortError'))
    await flushPromises()
    expect(harness.toastAdd).not.toHaveBeenCalled()
  })

  it('reports an upload that completed after the dialog was closed', async () => {
    await fillForm()
    await submit()
    await wrapper.setProps({ visible: false })
    resolveUpload()
    await flushPromises()
    expect(harness.toastAdd).toHaveBeenCalledOnce()
    expect(harness.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        detail: expect.stringContaining('My model has been added'),
      }),
    )
  })

  it('keeps a new upload active when the old cancelled upload settles', async () => {
    await fillForm()
    await submit()
    const resolveOldUpload = resolveUpload
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    await fillForm()
    await submit()
    const visibleEvents = wrapper.emitted('update:visible')?.length ?? 0
    resolveOldUpload()
    await flushPromises()
    expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
    expect(wrapper.emitted('update:visible')?.length ?? 0).toBe(visibleEvents)
    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Cancel'])
    expect(uploadSignal(1).aborted).toBe(false)
  })

  it('aborts when the component is removed', async () => {
    await fillForm()
    await submit()
    wrapper.unmount()
    expect(uploadSignal().aborted).toBe(true)
  })

  it('reports failures and preserves form values for retry', async () => {
    await fillForm()
    await submit()
    rejectUpload(new Error('Network failure'))
    await flushPromises()
    expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    expect(wrapper.getComponent({ name: 'InputText' }).props('modelValue')).toBe('My model')
    await submit()
    expect(harness.upload).toHaveBeenCalledTimes(2)
  })

  it('ignores invalid submissions and resets after success', async () => {
    await fillForm()
    await submit(false)
    expect(harness.upload).not.toHaveBeenCalled()
    await submit()
    resolveUpload()
    await flushPromises()
    expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    expect(wrapper.getComponent({ name: 'Form' }).props('initialValues')).toMatchObject({
      name: '',
      description: '',
      tags: [],
    })
  })

  if (registry) {
    it.each([
      { collectionType: OrbitCollectionTypeEnum.dataset, artifactType: ArtifactTypeEnum.dataset },
      {
        collectionType: OrbitCollectionTypeEnum.experiment,
        artifactType: ArtifactTypeEnum.experiment,
      },
    ])(
      'restores the default type for a $collectionType collection',
      async ({ collectionType, artifactType }) => {
        harness.collection.type = collectionType
        await wrapper.setProps({ visible: false })
        await wrapper.setProps({ visible: true })
        expect(wrapper.getComponent({ name: 'Form' }).props('initialValues').type).toBe(
          artifactType,
        )
      },
    )

    it('clears file validation errors on close', async () => {
      wrapper
        .getComponent({ name: 'FileInput' })
        .vm.$emit('select-file', new File(['invalid'], 'invalid.txt'))
      await flushPromises()
      expect(wrapper.getComponent({ name: 'FileInput' }).props('error')).toBe(true)
      await wrapper.setProps({ visible: false })
      await wrapper.setProps({ visible: true })
      expect(wrapper.getComponent({ name: 'FileInput' }).props('error')).toBe(false)
    })
  }
})
