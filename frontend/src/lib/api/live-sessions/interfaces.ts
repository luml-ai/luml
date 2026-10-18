export enum LiveSessionStatusEnum {
  live = 'live',
  disconnected = 'disconnected',
  ended = 'ended',
}

export interface LiveSessionViewToken {
  token: string
  launch_url: string
  expires_at: string
}
