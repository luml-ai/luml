import { RelayKindEnum, RelayStatusEnum, type Relay } from '@/lib/api/relays/interfaces'

export interface RelayOption {
  id: string
  name: string
}

function relayOptionName(relay: Relay): string {
  const marks = [
    relay.kind === RelayKindEnum.managed ? 'managed' : null,
    relay.status === RelayStatusEnum.draining ? 'draining' : null,
  ].filter(Boolean)
  return marks.length ? `${relay.label} (${marks.join(', ')})` : relay.label
}

export function getRelayOptions(
  relays: Relay[],
  currentRelayId: string | null = null,
): RelayOption[] {
  return relays
    .filter((relay) => relay.status === RelayStatusEnum.enabled || relay.id === currentRelayId)
    .map((relay) => ({ id: relay.id, name: relayOptionName(relay) }))
}
