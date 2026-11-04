import type { LiveSessionStatusEnum } from '../live-sessions/interfaces'

export interface FlowSession {
  id: string
  status: LiveSessionStatusEnum
  started_at: string
  last_heartbeat_at: string | null
}

export interface Flow {
  id: string
  orbit_id: string
  user_id: string
  name: string
  session: FlowSession
  created_at: string
}
