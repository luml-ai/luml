export enum LiveSessionStatusEnum {
  live = 'live',
  disconnected = 'disconnected',
  ended = 'ended',
}

export interface LiveSession {
  id: string
  orbit_id: string
  user_id: string
  name: string
  relay_id: string
  started_at: string
  last_heartbeat_at: string | null
  connected: boolean
  ended_at: string | null
  status: LiveSessionStatusEnum
}

export interface LiveSessionViewToken {
  token: string
  launch_url: string
  expires_at: string
}
