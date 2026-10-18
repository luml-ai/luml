export enum RelayStatusEnum {
  enabled = 'enabled',
  draining = 'draining',
}

export enum RelayKindEnum {
  managed = 'managed',
  own = 'own',
}

export interface Relay {
  id: string
  organization_id: string | null
  label: string
  base_domain: string
  agent_url: string
  status: RelayStatusEnum
  kind: RelayKindEnum
  online: boolean
  last_seen_at: string | null
  connected_agents: number
  capabilities: Record<string, Record<string, unknown>>
  present_capabilities: string[]
  created_at: string
  updated_at: string | null
}

export interface RelayWithToken {
  relay: Relay
  token: string
}

export interface RelayCreatePayload {
  label: string
  base_domain: string
  agent_url: string
}

export interface RelayUpdatePayload {
  label?: string
  base_domain?: string
  agent_url?: string
  status?: RelayStatusEnum
}
