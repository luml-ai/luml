import { describe, it, expect, beforeEach } from 'vitest'
import { getStoredBackendUrl, setStoredBackendUrl } from '@/lib/api/prisma'

const STORAGE_KEY = 'luml-agent-backend-url'

beforeEach(() => {
  localStorage.removeItem(STORAGE_KEY)
})

describe('getStoredBackendUrl', () => {
  it('returns default when nothing is stored', () => {
    expect(getStoredBackendUrl()).toBe('http://localhost:8420')
  })

  it('returns stored value', () => {
    localStorage.setItem(STORAGE_KEY, 'http://myhost:9000')
    expect(getStoredBackendUrl()).toBe('http://myhost:9000')
  })
})

describe('setStoredBackendUrl', () => {
  it('stores and retrieves correctly', () => {
    setStoredBackendUrl('http://myhost:9000')
    expect(getStoredBackendUrl()).toBe('http://myhost:9000')
  })

  it('strips trailing slashes', () => {
    setStoredBackendUrl('http://myhost:9000/')
    expect(getStoredBackendUrl()).toBe('http://myhost:9000')
  })

  it('strips multiple trailing slashes', () => {
    setStoredBackendUrl('http://myhost:9000///')
    expect(getStoredBackendUrl()).toBe('http://myhost:9000')
  })
})
