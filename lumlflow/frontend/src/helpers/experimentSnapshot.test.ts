import { afterEach, describe, expect, it, vi } from 'vitest'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { findSnapshotMember, loadSnapshotSource } from './experimentSnapshot'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('findSnapshotMember', () => {
  const manifest = { name: 'manifest.json', size: 10 }
  const raw = { name: 'exp.db', size: 4096 }
  const zipped = { name: 'exp.db.zip', size: 512 }

  it('finds the database of either generation', () => {
    expect(findSnapshotMember([manifest, raw])).toBe(raw)
    expect(findSnapshotMember([manifest, zipped])).toBe(zipped)
  })

  it('prefers the raw generation 2 database, as the SDK does', () => {
    expect(findSnapshotMember([zipped, raw])).toBe(raw)
  })

  it('finds nothing in an archive without a database', () => {
    expect(findSnapshotMember([manifest, { name: 'attachments/exp.db', size: 1 }])).toBe(undefined)
  })
})

describe('loadSnapshotSource', () => {
  const signal = new AbortController().signal

  it('reads a raw database by range from its member, without downloading it', async () => {
    vi.spyOn(workspaceApi, 'fileUrl').mockResolvedValue('/api/flow/file/entry?name=exp.db')
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(
      loadSnapshotSource('/work/run.luml', { name: 'exp.db', size: 4096 }, signal),
    ).resolves.toEqual({
      kind: 'range',
      url: '/api/flow/file/entry?name=exp.db',
      offset: 0,
      size: 4096,
    })
    expect(workspaceApi.fileUrl).toHaveBeenCalledWith('/work/run.luml', 'exp.db')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('downloads a zipped database whole', async () => {
    vi.spyOn(workspaceApi, 'fileUrl').mockResolvedValue('/member')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2]))))
    const source = await loadSnapshotSource(
      '/work/run.luml',
      { name: 'exp.db.zip', size: 2 },
      signal,
    )
    expect(source.kind).toBe('zip')
    expect(source.kind === 'zip' && new Uint8Array(source.buffer)).toEqual(new Uint8Array([1, 2]))
  })

  it('reports a zipped database the daemon cannot serve', async () => {
    vi.spyOn(workspaceApi, 'fileUrl').mockResolvedValue('/member')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 404 })))
    await expect(
      loadSnapshotSource('/work/run.luml', { name: 'exp.db.zip', size: 2 }, signal),
    ).rejects.toThrow('Could not read the experiment database (404)')
  })
})
