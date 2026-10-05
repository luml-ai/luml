### codie review of `eee7760` on `draft/OKUA1/feat-lm-764-flow-tunnels` against `origin/main`

**Verdict: changes requested**

This branch adds relay-backed live sessions and named flows across the backend, Python clients, and browser UI. It also adds organization relay management and orbit relay assignment.

### Correctness bugs

1. **`frontend/src/components/organizations/OrganizationOrbits.vue:101` — Load relay options when the editor first opens.** Setting `editedOrbit` and `editorVisible` together mounts `OrbitEditor` already visible. Its non-immediate visibility watcher never calls `getRelays()`, leaving the selector empty on a fresh page even when registered relays exist. Initialize the editor’s data when mounted visible and cover this path without preloading the relay store.

   Trigger → consequence: An organization owner or admin opens orbit settings from the Orbits tab on a fresh page → existing relays are unavailable for selection until the editor is closed and reopened.
