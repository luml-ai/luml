import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAgentWebSocket } from '../useAgentWebSocket'

const harness = vi.hoisted(() => ({
  store: null as unknown as {
    selectedRunId: string | null
    lastSeq: number
    applySnapshot: ReturnType<typeof vi.fn>
    applyEvent: ReturnType<typeof vi.fn>
  },
  createRunWebSocket: vi.fn(),
  getRunEvents: vi.fn(),
}))

vi.mock('@/stores/prisma', () => ({ usePrismaStore: () => harness.store }))
vi.mock('@/lib/api', () => ({
  api: {
    dataAgent: {
      createRunWebSocket: harness.createRunWebSocket,
      getRunEvents: harness.getRunEvents,
    },
  },
}))

class FakeSocket {
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  close = vi.fn(() => {
    setTimeout(() => this.onclose?.(), 0)
  })
}

describe('useAgentWebSocket lifecycle', () => {
  let wrapper: ReturnType<typeof mount> | undefined
  let state: ReturnType<typeof useAgentWebSocket>
  let sockets: FakeSocket[]

  beforeEach(() => {
    vi.useFakeTimers()
    harness.store = reactive({
      selectedRunId: 'A',
      lastSeq: 0,
      applySnapshot: vi.fn(),
      applyEvent: vi.fn(),
    })
    sockets = []
    harness.getRunEvents.mockResolvedValue([])
    harness.createRunWebSocket.mockImplementation(() => {
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket
    })
    wrapper = mount(
      defineComponent({
        setup() {
          state = useAgentWebSocket()
          return () => null
        },
      }),
    )
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('closes the live socket on unmount after an old socket closes asynchronously', async () => {
    harness.store.selectedRunId = 'B'
    await nextTick()
    expect(sockets[0].close).toHaveBeenCalledOnce()
    sockets[1].onopen?.()
    vi.advanceTimersByTime(0)

    const connectedAfterOldClose = state.connected.value
    wrapper!.unmount()
    wrapper = undefined
    expect(sockets[1].close).toHaveBeenCalledOnce()
    expect(connectedAfterOldClose).toBe(true)
    await vi.runAllTimersAsync()
    expect(harness.createRunWebSocket).toHaveBeenCalledTimes(2)
    expect(harness.getRunEvents).not.toHaveBeenCalled()
  })

  it('ignores late callbacks from a replaced socket when returning to the same run', async () => {
    harness.store.selectedRunId = 'B'
    await nextTick()
    harness.store.selectedRunId = 'A'
    await nextTick()
    sockets[2].onopen?.()
    vi.advanceTimersByTime(0)

    expect(state.connected.value).toBe(true)
    expect(harness.getRunEvents).not.toHaveBeenCalled()
    await vi.runAllTimersAsync()
    expect(harness.createRunWebSocket).toHaveBeenCalledTimes(3)
  })

  it('reconnects after an unexpected close and closes the replacement on unmount', async () => {
    sockets[0].onopen?.()
    sockets[0].onclose?.()
    expect(state.connected.value).toBe(false)
    expect(state.reconnecting.value).toBe(true)
    expect(harness.getRunEvents).toHaveBeenCalledWith('A', 0)
    await vi.advanceTimersByTimeAsync(1000)
    expect(harness.createRunWebSocket).toHaveBeenCalledTimes(2)
    sockets[1].onopen?.()
    expect(state.connected.value).toBe(true)
    expect(state.reconnecting.value).toBe(false)

    wrapper!.unmount()
    wrapper = undefined
    expect(sockets[1].close).toHaveBeenCalledOnce()
    await vi.runAllTimersAsync()
    expect(harness.createRunWebSocket).toHaveBeenCalledTimes(2)
  })

  it('cancels a pending reconnect when unmounted', async () => {
    sockets[0].onclose?.()
    wrapper!.unmount()
    wrapper = undefined
    await vi.runAllTimersAsync()
    expect(harness.createRunWebSocket).toHaveBeenCalledOnce()
  })

  it('closes the live socket when the run is deselected after a late close', async () => {
    harness.store.selectedRunId = 'B'
    await nextTick()
    vi.advanceTimersByTime(0)
    harness.store.selectedRunId = null
    await nextTick()
    expect(sockets[1].close).toHaveBeenCalledOnce()
    await vi.runAllTimersAsync()
    expect(harness.createRunWebSocket).toHaveBeenCalledTimes(2)
  })
})
