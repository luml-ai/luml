### codie review of `05f0bb7` on `draft/OKUA1/feat-lm-764-flow-tunnels` against `origin/main`

**Verdict: changes requested**

This branch adds relay-backed live sessions and named flows, including backend APIs, a relay service, Python clients, and browser access. It also adds relay administration and moves Flow into orbit navigation.

### Correctness bugs

1. **`sdk/python/sdk/luml/flow.py:134` — Cleanup can end a replacement flow.** Re-exposing the same name preserves the flow ID while replacing its session. The older `RelayedFlow` retains that ID, and `_release()` deletes whichever session the flow currently references. Retain the original session ID and make cleanup conditional on it, or end only that session.

   Trigger → consequence: Start a second run under the same name before the first exits, then stop or exit the first run → its cleanup ends the second run’s session and removes its card.

2. **`frontend/src/components/flow/FlowAddDialog.vue:75` — The relay-setup link uses the wrong route parameter.** `organization-orbits` requires `id`, but this link supplies `organizationId`. Vue Router discards that parameter and inherits the current orbit’s `id`, resolving to `/organization/<orbit-id>/orbits-list`. Pass `params: { id: organizationId }`.

   Trigger → consequence: Open “Add flow” on an orbit without a relay and follow “Assign a relay in the orbit settings” → navigation addresses the orbit ID as an organization and fails to open the intended settings.

3. **`frontend/src/components/organizations/OrganizationOrbits.vue:91` — The new settings button is hidden for every actual role.** `PermissionsHandler.get_organization_permissions_by_role()` deliberately returns only `['create']` for organization-level orbit permissions for owners and admins. Consequently, checking that array for `update` always fails. Use permissions or role information that the backend actually exposes; the new tests currently mock an impossible organization permission response.

   Trigger → consequence: An organization owner or admin opens the Orbits tab to configure a relay → no orbit-settings button appears, so the newly added editing path is inaccessible.
