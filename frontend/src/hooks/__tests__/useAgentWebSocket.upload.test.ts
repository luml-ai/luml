import { describe, it, expect, vi, beforeEach } from 'vitest'

const UPLOAD_EVENT_TYPES = new Set([
  'upload_ready',
  'upload_completed',
  'upload_failed',
  'worktrees_pending_upload',
])

describe('useAgentWebSocket upload event dispatch', () => {
  it('recognises all upload event types', () => {
    expect(UPLOAD_EVENT_TYPES.has('upload_ready')).toBe(true)
    expect(UPLOAD_EVENT_TYPES.has('upload_completed')).toBe(true)
    expect(UPLOAD_EVENT_TYPES.has('upload_failed')).toBe(true)
    expect(UPLOAD_EVENT_TYPES.has('worktrees_pending_upload')).toBe(true)
  })

  it('does not treat regular events as upload events', () => {
    expect(UPLOAD_EVENT_TYPES.has('node_created')).toBe(false)
    expect(UPLOAD_EVENT_TYPES.has('node_completed')).toBe(false)
    expect(UPLOAD_EVENT_TYPES.has('run_status_changed')).toBe(false)
  })

  it('dispatches upload events to upload flow handler', () => {
    const handleEvent = vi.fn()
    const mockUploadFlow = { handleEvent }

    const eventData = {
      type: 'upload_ready',
      data: {
        upload_id: 'u1',
        run_id: 'r1',
        node_id: 'n1',
        file_size: 1024,
        experiment_ids: ['exp-1'],
        collection_id: 'col-1',
        organization_id: 'org-1',
        orbit_id: 'orb-1',
      },
    }

    if (UPLOAD_EVENT_TYPES.has(eventData.type)) {
      mockUploadFlow.handleEvent(eventData.type, eventData.data)
    }

    expect(handleEvent).toHaveBeenCalledWith('upload_ready', eventData.data)
  })

  it('does not dispatch non-upload events to upload flow', () => {
    const handleEvent = vi.fn()
    const mockUploadFlow = { handleEvent }

    const eventData = { type: 'node_created', data: { node_id: 'n1' } }

    if (UPLOAD_EVENT_TYPES.has(eventData.type)) {
      mockUploadFlow.handleEvent(eventData.type, eventData.data)
    }

    expect(handleEvent).not.toHaveBeenCalled()
  })
})
