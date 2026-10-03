import type { Relay, RelayCreatePayload, RelayUpdatePayload } from '@/lib/api/relays/interfaces'
import { api } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useRelaysStore = defineStore('relays', () => {
  const relays = ref<Relay[]>([])

  function replaceRelay(relay: Relay) {
    const index = relays.value.findIndex((item) => item.id === relay.id)
    if (index !== -1) relays.value[index] = relay
  }

  async function getRelays(organizationId: string) {
    relays.value = await api.relays.getRelays(organizationId)
  }

  async function createRelay(organizationId: string, payload: RelayCreatePayload) {
    const { relay, token } = await api.relays.createRelay(organizationId, payload)
    relays.value.push(relay)
    return token
  }

  async function updateRelay(organizationId: string, relayId: string, payload: RelayUpdatePayload) {
    const relay = await api.relays.updateRelay(organizationId, relayId, payload)
    replaceRelay(relay)
    return relay
  }

  async function rotateRelayToken(organizationId: string, relayId: string) {
    const { relay, token } = await api.relays.rotateRelayToken(organizationId, relayId)
    replaceRelay(relay)
    return token
  }

  async function deleteRelay(organizationId: string, relayId: string) {
    await api.relays.deleteRelay(organizationId, relayId)
    relays.value = relays.value.filter((relay) => relay.id !== relayId)
  }

  return { relays, getRelays, createRelay, updateRelay, rotateRelayToken, deleteRelay }
})
