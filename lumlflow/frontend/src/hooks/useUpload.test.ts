import { afterEach, describe, expect, it, vi } from 'vitest'
import { UploadTypeEnum } from '@/components/upload/upload.interface'

vi.mock('@/api/api.service', () => ({
  apiService: {
    uploadArtifact: vi.fn().mockResolvedValue({ job_id: 'upload-job' }),
  },
}))

vi.mock('primevue', () => ({
  useToast: () => ({ add: vi.fn() }),
}))

describe('upload progress URL', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it.each([
    [undefined, '/api/luml/artifact/upload-job/progress'],
    ['', '/api/luml/artifact/upload-job/progress'],
    ['/custom-api', '/custom-api/luml/artifact/upload-job/progress'],
    [
      'https://api.example.test/api',
      'https://api.example.test/api/luml/artifact/upload-job/progress',
    ],
    [
      'https://api.example.test/api/',
      'https://api.example.test/api/luml/artifact/upload-job/progress',
    ],
  ])('opens the progress stream with API URL %s', async (baseURL, expectedURL) => {
    vi.stubEnv('VITE_API_URL', baseURL)
    const eventSource = vi.fn(function () {
      return { close: vi.fn() }
    })
    vi.stubGlobal('EventSource', eventSource)
    const { useUpload } = await import('./useUpload')

    await useUpload().upload({
      upload_type: UploadTypeEnum.EXPERIMENT,
      embed_experiment: false,
      experiment_id: 'experiment-id',
      organization_id: 'organization-id',
      orbit_id: 'orbit-id',
      collection_id: 'collection-id',
      artifact: { name: 'artifact', description: '', tags: [] },
    })

    expect(eventSource).toHaveBeenCalledWith(expectedURL)
  })
})
