import { describe, expect, it, vi } from 'vitest'
import { toExperimentReadError } from '../../metric-buckets/errors'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import { redactSecrets } from '../snapshot-source/errors'
import {
  createSyncRangeReader,
  downloadSnapshotMember,
  HttpRangeFile,
  probeSnapshotHeader,
  type SnapshotTransport,
} from '../snapshot-source/httpSource'
import { toSourceLocation } from '../snapshot-source/sourceLocation'

const SIGNED = 'https://bucket.example/o/run.tar?X-Amz-Signature=SECRET&X-Amz-Credential=KEY'
const TOKEN = { Authorization: 'Bearer SECRET-TOKEN' }

function networkError(): DOMException {
  return new DOMException(
    `Failed to execute 'send' on 'XMLHttpRequest': Failed to load '${SIGNED}'.`,
    'NetworkError',
  )
}

function messageOf(action: () => unknown): string {
  try {
    action()
  } catch (error) {
    return (error as Error).message
  }
  throw new Error('expected a throw')
}

async function asyncMessageOf(action: () => Promise<unknown>): Promise<string> {
  try {
    await action()
  } catch (error) {
    return (error as Error).message
  }
  throw new Error('expected a rejection')
}

describe('redactSecrets', () => {
  it('cuts URLs to their origin and drops query strings and credentials', () => {
    const text = redactSecrets(
      `Failed to load '${SIGNED}', then /o/x?sig=SECRET with Bearer SECRET-TOKEN`,
    )
    expect(text).toBe(
      "Failed to load 'https://bucket.example', then /o/x?[redacted] with Bearer [redacted]",
    )
  })

  it('drops signatures, SAS tokens, JWTs and storage token headers outside a URL', () => {
    const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJTRUNSRVQifQ.c2lnU0VDUkVU'
    const text = redactSecrets(
      [
        'sr=b&sig=SECRET1&se=2030',
        'SharedAccessSignature sr=x&sig=SECRET2',
        `jwt ${jwt}`,
        'x-amz-security-token: SECRET3',
        'x-ms-blob-key=SECRET4',
        'signature=SECRET5',
      ].join('; '),
    )
    expect(text).not.toMatch(/SECRET|eyJ/)
    expect(text).toContain('SharedAccessSignature [redacted]')
    expect(text).toContain('x-amz-security-token: [redacted]')
  })

  it('is applied to every read error message', () => {
    expect(toExperimentReadError(networkError()).message).not.toMatch(/SECRET|\?/)
    expect(toExperimentReadError(`plain ${SIGNED}`).message).not.toMatch(/SECRET/)
  })
})

describe('transport errors name no URL or credential', () => {
  it('for a failed sync range read', () => {
    const file = new HttpRangeFile('m', { url: SIGNED, headers: TOKEN }, 0, 1 << 20, () => {
      throw networkError()
    })
    const message = messageOf(() => file.read(0, 10))
    expect(message).toBe('Snapshot range read failed: NetworkError')
  })

  it('for a range read that failed after a redirect to another origin', () => {
    const read = createSyncRangeReader(() => ({
      status: 401,
      url: 'https://other.example/o/run.tar?sig=SECRET',
      contentRange: null,
      body: new Uint8Array(0),
    }))
    const file = new HttpRangeFile('m', { url: SIGNED, headers: TOKEN }, 0, 1 << 20, read)
    expect(messageOf(() => file.read(0, 10))).not.toMatch(/SECRET|\?|other\.example/)
  })

  it('for a failed or redirected fetch at open', async () => {
    const thrown: SnapshotTransport = {
      readRangeSync: () => new Uint8Array(0),
      fetch: async () => {
        throw new TypeError(`Failed to fetch ${SIGNED}`)
      },
    }
    const redirected: SnapshotTransport = {
      readRangeSync: () => new Uint8Array(0),
      fetch: async () => {
        const response = new Response('denied', { status: 403 })
        Object.defineProperty(response, 'redirected', { value: true })
        Object.defineProperty(response, 'url', { value: 'https://other.example/x?sig=SECRET' })
        return response
      },
    }
    const location = { url: SIGNED, headers: TOKEN }
    for (const transport of [thrown, redirected]) {
      const probe = await asyncMessageOf(() =>
        probeSnapshotHeader(transport, 'm', location, 0, 4096),
      )
      const download = await asyncMessageOf(() =>
        downloadSnapshotMember(transport, 'm', location, 0, 4096, 1 << 20),
      )
      for (const message of [probe, download]) {
        expect(message).not.toMatch(/SECRET|\?|other\.example|bucket\.example/)
      }
    }
  })

  it('for a web page answered instead of the data', async () => {
    const page: SnapshotTransport = {
      readRangeSync: () => new Uint8Array(0),
      fetch: async () =>
        new Response('<html>sign in</html>', { headers: { 'Content-Type': 'text/html' } }),
    }
    await expect(probeSnapshotHeader(page, 'm', SIGNED, 0, 4096)).rejects.toMatchObject({
      code: 'snapshot-source-page',
    })
    const read = createSyncRangeReader(() => ({
      status: 200,
      url: SIGNED,
      contentRange: null,
      contentType: 'text/html; charset=utf-8',
      body: new Uint8Array(10),
    }))
    const file = new HttpRangeFile('m', SIGNED, 0, 1 << 20, read)
    expect(() => file.read(0, 10)).toThrow(
      expect.objectContaining({ code: 'snapshot-source-page' }),
    )
    expect(file.failure).toMatchObject({ code: 'snapshot-source-page' })
  })
})

describe('source location headers', () => {
  it('allow Authorization only, as browsers drop only it on a cross-origin redirect', () => {
    expect(toSourceLocation({ url: SIGNED, headers: { authorization: 'Bearer t' } })).toBeTruthy()
    expect(() => toSourceLocation({ url: SIGNED, headers: { 'X-Api-Key': 'SECRET' } })).toThrow(
      /'X-Api-Key' is not allowed; only Authorization is/,
    )
    expect(
      messageOf(() => toSourceLocation({ url: SIGNED, headers: { 'X-Key': 'SECRET' } })),
    ).not.toContain('SECRET')
  })
})

describe('the log of a failed open', () => {
  it('holds the error message once, without URL, query string or token', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    try {
      const provider = new ExperimentSnapshotDatabaseProvider()
      const message = `Failed to load '${SIGNED}' with Bearer SECRET-TOKEN`
      await provider.init({
        modelsInfo: [{ modelId: 'm', error: { code: 'read-failed', message } }],
      })
      expect(warn).toHaveBeenCalledOnce()
      const logged = warn.mock.calls[0]!.map(String).join(' ')
      expect(logged).toContain("Failed to load 'https://bucket.example'")
      expect(logged).not.toMatch(/SECRET|X-Amz|\?/)
    } finally {
      warn.mockRestore()
    }
  })
})
