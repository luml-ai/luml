import axios from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { GitHubService } from '../GitHubService'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

describe('GitHubService', () => {
  it.each([42, 0])('fetches the canonical repository star count of %i', async (count) => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { stargazers_count: count } })

    await expect(GitHubService.getStarsCount()).resolves.toBe(count)
    expect(axios.get).toHaveBeenCalledExactlyOnceWith('https://api.github.com/repos/luml-ai/luml')
  })

  it('propagates API failures to the caller', async () => {
    const error = new Error('GitHub unavailable')
    vi.mocked(axios.get).mockRejectedValueOnce(error)

    await expect(GitHubService.getStarsCount()).rejects.toBe(error)
  })
})
