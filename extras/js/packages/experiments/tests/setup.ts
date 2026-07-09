import { vi, beforeEach } from 'vitest'

// jsdom has no ResizeObserver; components that observe element resizes need it.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub)

beforeEach(() => {
  vi.clearAllMocks()
})
