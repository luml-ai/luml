import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TerminalPanel from '../TerminalPanel.vue'

const harness = vi.hoisted(() => ({
  createTerminalWebSocket: vi.fn(),
  getSessionScrollback: vi.fn(),
  close: vi.fn(),
  dispose: vi.fn(),
  fit: vi.fn(),
  disconnect: vi.fn(),
}))

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/lib/api', () => ({
  api: {
    dataAgent: {
      createTerminalWebSocket: harness.createTerminalWebSocket,
      getSessionScrollback: harness.getSessionScrollback,
    },
  },
}))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    loadAddon = vi.fn()
    open = vi.fn()
    write = vi.fn()
    onData = vi.fn()
    dispose = harness.dispose
  },
}))
vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class {
    fit = harness.fit
  },
}))
vi.mock('@xterm/addon-web-links', () => ({ WebLinksAddon: class {} }))

describe('TerminalPanel lifecycle', () => {
  let wrapper: ReturnType<typeof mount> | undefined

  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe = vi.fn()
        disconnect = harness.disconnect
      },
    )
    harness.createTerminalWebSocket.mockReturnValue({ close: harness.close })
    harness.getSessionScrollback.mockResolvedValue(new ArrayBuffer(0))
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it.each([false, true])('cancels delayed initialization on unmount (readonly: %s)', (readonly) => {
    wrapper = mount(TerminalPanel, {
      props: { sessionId: 'session', nodeId: 'node', active: true, taskName: 'task', readonly },
    })
    vi.advanceTimersByTime(199)
    wrapper.unmount()
    wrapper = undefined
    vi.runAllTimers()

    expect(harness.createTerminalWebSocket).not.toHaveBeenCalled()
    expect(harness.getSessionScrollback).not.toHaveBeenCalled()
    expect(harness.fit).not.toHaveBeenCalled()
    expect(harness.dispose).toHaveBeenCalledOnce()
    expect(harness.disconnect).toHaveBeenCalledOnce()
  })

  it('connects while mounted and closes the terminal socket on unmount', () => {
    wrapper = mount(TerminalPanel, {
      props: { sessionId: 'session', active: true, taskName: 'task' },
    })
    vi.advanceTimersByTime(200)
    expect(harness.createTerminalWebSocket).toHaveBeenCalledWith('session')
    wrapper.unmount()
    wrapper = undefined
    expect(harness.close).toHaveBeenCalledOnce()
    expect(harness.dispose).toHaveBeenCalledOnce()
  })
})
