import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TerminalPanel from '../TerminalPanel.vue'

const harness = vi.hoisted(() => ({
  createTerminalWebSocket: vi.fn(),
  getSessionScrollback: vi.fn(),
  close: vi.fn(),
  write: vi.fn(),
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
    write = harness.write
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

  it('does not write a late scrollback into an unmounted terminal', async () => {
    let resolveScrollback: (buf: ArrayBuffer) => void = () => {}
    harness.getSessionScrollback.mockReturnValue(
      new Promise<ArrayBuffer>((resolve) => {
        resolveScrollback = resolve
      }),
    )
    wrapper = mount(TerminalPanel, {
      props: {
        sessionId: 'session',
        nodeId: 'node',
        active: true,
        taskName: 'task',
        readonly: true,
      },
    })
    vi.advanceTimersByTime(200)
    expect(harness.getSessionScrollback).toHaveBeenCalledWith('node', 'session')
    wrapper.unmount()
    wrapper = undefined
    resolveScrollback(new ArrayBuffer(4))
    await vi.runAllTimersAsync()

    expect(harness.write).not.toHaveBeenCalled()
  })

  it('does not write to the terminal when the socket closes after unmount', () => {
    const socket: { close: typeof harness.close; onclose?: () => void } = { close: harness.close }
    harness.createTerminalWebSocket.mockReturnValue(socket)
    wrapper = mount(TerminalPanel, {
      props: { sessionId: 'session', active: true, taskName: 'task' },
    })
    vi.advanceTimersByTime(200)
    harness.write.mockClear()
    wrapper.unmount()
    wrapper = undefined
    socket.onclose?.()

    expect(harness.write).not.toHaveBeenCalled()
  })

  it('cancels the activation refit on unmount', async () => {
    wrapper = mount(TerminalPanel, {
      props: { sessionId: 'session', active: false, taskName: 'task' },
    })
    vi.advanceTimersByTime(200)
    harness.fit.mockClear()
    await wrapper.setProps({ active: true })
    wrapper.unmount()
    wrapper = undefined
    vi.runAllTimers()

    expect(harness.fit).not.toHaveBeenCalled()
  })
})
