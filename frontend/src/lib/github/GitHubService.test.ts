import axios from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { GitHubService } from './GitHubService'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

describe('GitHubService', () => {
  it('reads the star count of the luml repository', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { stargazers_count: 274 } })

    await expect(GitHubService.getStarsCount()).resolves.toBe(274)
    expect(axios.get).toHaveBeenCalledExactlyOnceWith('https://api.github.com/repos/luml-ai/luml')
  })
})
