import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBackendStatus } from '@/hooks/useBackendStatus'

const healthMock = vi.fn()

vi.mock('@/lib/api', () => ({
  api: {
    dataAgent: {
      health: (...args: unknown[]) => healthMock(...args),
    },
  },
}))

describe('useBackendStatus', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('sets isOffline on network error', async () => {
    healthMock.mockRejectedValue(new Error('Network Error'))
    const { isOffline, isLoading, check } = useBackendStatus()

    await check()

    expect(isOffline.value).toBe(true)
    expect(isLoading.value).toBe(false)
  })

  it('clears isOffline on successful response', async () => {
    healthMock.mockResolvedValue({ service: 'luml-agent', version: '0.2.0' })
    const { isOffline, isLoading, check } = useBackendStatus()

    const ok = await check()

    expect(ok).toBe(true)
    expect(isOffline.value).toBe(false)
    expect(isLoading.value).toBe(false)
  })

  it('sets versionMismatch on wrong major version', async () => {
    healthMock.mockResolvedValue({ service: 'luml-agent', version: '1.0.0' })
    const { versionMismatch, isOffline, check } = useBackendStatus()

    const ok = await check()

    expect(ok).toBe(false)
    expect(versionMismatch.value).toBe(true)
    expect(isOffline.value).toBe(false)
  })

  it('sets isOffline on wrong service name', async () => {
    healthMock.mockResolvedValue({ service: 'other-service', version: '0.2.0' })
    const { isOffline, versionMismatch, check } = useBackendStatus()

    const ok = await check()

    expect(ok).toBe(false)
    expect(isOffline.value).toBe(true)
    expect(versionMismatch.value).toBe(false)
  })

  it('resets state between checks', async () => {
    healthMock.mockRejectedValueOnce(new Error('Network Error'))
    const { isOffline, check } = useBackendStatus()

    await check()
    expect(isOffline.value).toBe(true)

    healthMock.mockResolvedValueOnce({ service: 'luml-agent', version: '0.2.0' })
    await check()
    expect(isOffline.value).toBe(false)
  })
})
