import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { useUploadFlow } from '@/hooks/useUploadFlow'
import type { UploadReadyEvent } from '@/lib/api/prisma/prisma.interfaces'
import RunDetailView from '../RunDetailView.vue'

const harness = vi.hoisted(() => ({
  flow: null as ReturnType<typeof useUploadFlow> | null,
  createArtifact: vi.fn(),
  postUploadUrl: vi.fn().mockResolvedValue(202),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/lib/api', () => ({
  api: {
    artifacts: { create: harness.createArtifact },
    dataAgent: { postUploadUrl: harness.postUploadUrl },
  },
}))
vi.mock('@/stores/prisma', () => ({
  usePrismaStore: () => ({
    selectedRun: {
      id: 'run-1',
      name: 'Training run',
      status: 'failed',
      config: {
        luml_collection_id: 'col-1',
        luml_organization_id: 'org-1',
        luml_orbit_id: 'orb-1',
      },
    },
    selectRun: vi.fn(),
  }),
}))
vi.mock('@/hooks/useAgentWebSocket', () => ({
  useAgentWebSocket: (flow: ReturnType<typeof useUploadFlow>) => {
    harness.flow = flow
  },
}))
vi.mock('@/components/prisma/RunGraph.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/prisma/NodeDetail.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/prisma/TerminalPanel.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/prisma/MergeDialog.vue', () => ({ default: { template: '<div />' } }))

describe('RunDetailView upload retry', () => {
  let wrapper: ReturnType<typeof shallowMount> | undefined
  afterEach(() => wrapper?.unmount())

  it('registers the original artifact metadata when the Retry button is clicked', async () => {
    harness.createArtifact.mockRejectedValueOnce(new Error('Network error'))
    wrapper = shallowMount(RunDetailView, {
      global: {
        stubs: {
          Message: { template: '<div><slot /></div>' },
          Button: { template: '<button><slot /></button>' },
        },
      },
    })
    const event: UploadReadyEvent = {
      upload_id: 'upload-1',
      run_id: 'run-1',
      node_id: 'node-1',
      file_size: 12345,
      experiment_ids: ['exp-1'],
      collection_id: 'col-1',
      organization_id: 'org-1',
      orbit_id: 'orb-1',
      manifest: {
        variant: 'pyfunc',
        producer_name: 'luml.ai',
        producer_version: '0.3.0',
        producer_tags: ['training'],
        inputs: [],
        outputs: [],
        dynamic_attributes: [],
        env_vars: [],
      },
      file_index: { 'manifest.json': [0, 128], 'model.pkl': [128, 12217] },
    }
    harness.flow!.handleUploadReady(event)
    await flushPromises()
    harness.createArtifact.mockResolvedValue({
      artifact: { id: 'artifact-1' },
      upload_details: { url: 'https://presigned.example.com/upload' },
    })

    const retry = wrapper.findAll('button').find((button) => button.text() === 'Retry')
    expect(retry).toBeDefined()
    await retry!.trigger('click')
    await flushPromises()

    expect(harness.createArtifact).toHaveBeenCalledTimes(2)
    expect(harness.createArtifact).toHaveBeenLastCalledWith(
      'org-1',
      'orb-1',
      'col-1',
      expect.objectContaining({
        manifest: event.manifest,
        file_index: event.file_index,
        size: event.file_size,
        extra_values: { experiment_ids: event.experiment_ids },
      }),
    )
  })
})
