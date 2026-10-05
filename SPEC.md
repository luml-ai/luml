# Proposals

## Where the branch stands

The flow tunnels branch, pull request 721, lets a user expose a running Flow instance from any machine as a flow on an orbit's Flow page. The SDK's flow object exposes the flow and serves it through the orbit's relay; the Flow page shows relayed flows as cards; an orbit gets its relay in the orbit settings, reached from the organization's orbits tab; the add-flow dialog points there when the orbit has none. Codie's review of the branch found three correctness bugs and requested changes. Nothing else in the review is open.

A flow is identified by its name within the orbit, and exposing a name that is already exposed replaces the earlier run's session while the flow keeps its identity. That is what lets a rerun after a crash replace its own card. The first bug is in how a run cleans up. When the flow object stops, it removes the flow, and removing a flow ends whatever session the flow has at that moment. So when a second run has taken over the name, the first run's cleanup, whether a stop, an exit of the interpreter or a termination signal, ends the second run's session and takes its card off the page. The second run keeps running with nothing to show for it.

The second bug is a link that goes to the wrong page. The add-flow dialog, when the orbit has no relay, offers a link to the organization's orbits tab. The link names the organization under a parameter the route does not have, so the router drops it and fills the route from the current page instead, which yields an address that treats the orbit as an organization. The user who follows the one hint the dialog gives lands nowhere useful.

The third bug hides a button from everyone. The organization's orbits tab gained a settings button per orbit that opens the orbit editor, where the relay is assigned. The button is shown only when the organization's permissions for orbits include updating. The backend deliberately reports only the create permission for orbits at the organization level, whatever the role, so the condition is never true and no owner or admin ever sees the button. The tests pass because they feed the component a permission answer the backend cannot give.

## What changes

The flow object remembers the session it started and, when it stops, ends that session instead of removing the flow. A session that has already been replaced is already ended, so ending it again changes nothing for the run that replaced it. The add-flow dialog's link names the organization under the route's own parameter. The orbit settings button is shown by the organization role the backend exposes, to owners and admins, and its tests feed the component what the backend sends.

## Why this way

Ending the run's own session is one call that cannot touch another run. The alternative, reading the flow first and removing it only while it still points at the run's session, is two calls with a gap in which a rerun can slip in. The backend already treats a flow whose session has ended as gone: it is left out of every list, and the next flow write deletes it. So the card disappears exactly as it did when the flow was removed.

The orbit settings button follows the role rather than a widened permission answer. The backend grants owners and admins the orbit update permission at the organization level, and the organization the frontend holds carries the member's role. Changing the backend to report more orbit permissions at the organization level would alter what every other reader of that answer sees, for one button.

The link fix follows the orbit dialogs, which link to the buckets and relays tabs with the same route parameter.

## Outside this spec

Codie's report of deviations from the original spec needs no code change; the one check it left open, the flow card on the Flow page of the running dev stack, is handled apart from this spec.

A second run on the same machine finds the first run's Flow instance on the port and exposes it as it is; when the first run stops, it still stops the Flow instance it started, and the second run's flow goes dark. That is the existing rule that a run stops only what it started, and it is left as it is.

# Design

## The flow object's cleanup

The flow object is `RelayedFlow` in the SDK's `luml.flow` module. Today it keeps the flow's identifier from the expose answer and, on stop, removes the flow through the flows resource of the API client. It stops its background serving and the Flow instance it started as before.

The object keeps the identifier of the session the expose answer returned. Cleanup ends that session through the live sessions resource of the API client, which already has an end operation, and no longer removes the flow. The flow's identifier is no longer needed for cleanup; whether the object still keeps it is left to the implementer.

An answer from LUML that the session is gone or already ended counts as ended and is logged as information, as a flow that was already gone is today. Any other failure to reach LUML logs the warning it logs today, and the local parts stop anyway; the session then ends at LUML by silence. The order of the three parts of cleanup, the session, the serving and the Flow instance, stays as it is.

The docstrings that say stopping removes the flow are reworded to say it ends the flow's session, since that is what a reader of the object will now observe.

*Note: the backend already deletes a flow only while it still points at the session named in the removal, so the page's remove action is safe against a rerun. It was the end of the flow's current session inside that removal that reached the other run.*

## The relay-setup link in the add-flow dialog

The dialog in `frontend/src/components/flow/FlowAddDialog.vue` receives the organization's identifier as a property. The route named `organization-orbits` is a child of the organization route, whose path parameter is `id`. The link passes the organization's identifier as `id`, as the orbit creator's links to the buckets and relays tabs do. The existing Flow page test that asserts the link's target is corrected to the right parameter; it currently asserts the wrong one.

## The orbit settings button in the organization's orbits tab

The tab in `frontend/src/components/organizations/OrganizationOrbits.vue` shows a settings button on each orbit row that loads the orbit's details and opens the orbit editor. It is gated on the organization's orbit permissions including update, which the backend never sends.

The button is shown when the current organization's role is owner or admin, the two roles whose organization-level orbit permissions include update in the backend's permission table. Members do not see it. The create button keeps its gate, since the create permission is the one the backend does send.

The component's tests set the organization's role to drive the button and no longer put an update permission into the organization's orbit permissions. A member case is added.

## Dependencies

None beyond what the branch already uses.

## Trade-offs

Ending the session rather than removing the flow leaves the flow's row at LUML until the next flow write deletes it. The row is invisible in the meantime, and this is the same path a flow takes when its session ends by silence.

Gating the orbit settings button on the role hides it from an organization member who is an admin of that orbit. Such a member edits the orbit from the orbit's own pages, where orbit-level permissions are known; the organization's orbits tab is organization administration.

# Scenarios

## Scenario: A second run takes over the name and the first run stops
**Given** a flow exposed by a first run, then exposed under the same name by a second run that is still running
**When** the first run stops, leaves its block, exits the interpreter or receives the termination signal
**Then** the first run ends only its own session, which is already ended, the second run's session stays live, and the second run's card stays on the Flow page

## Scenario: A run stops while it still owns the flow
**Given** a flow exposed by one run and not replaced
**When** the run stops
**Then** its session is ended at LUML, the flow is left out of the flows list from then on, and the card disappears on the page's next refresh

## Scenario: Stopping after LUML ended the session
**Given** a run whose session LUML has ended, so its serving has stopped
**When** the run stops
**Then** the answer that the session is gone or already ended is logged as information, nothing is raised, and the serving thread and the Flow instance the run started are stopped

## Scenario: Stopping when LUML cannot be reached
**Given** a running flow and a LUML that does not answer
**When** the run stops
**Then** a warning says the session ends by silence, nothing is raised, and the local parts are stopped

## Scenario: Removing a flow from the Flow page is unchanged
**Given** a live relayed card
**When** the card's remove action is confirmed
**Then** the flow is removed and its session ended, as before

## Scenario: The relay-setup link reaches the orbits tab
**Given** the add-flow dialog open on an orbit without a relay
**When** the relayed choice is shown
**Then** its link targets the route named `organization-orbits` with the organization's identifier under the `id` parameter, and following it opens that organization's orbits tab

## Scenario: Owners and admins see the orbit settings button
**Given** the organization's orbits tab with the current organization's role set to owner, and again to admin
**When** the tab renders its orbit rows
**Then** each row shows the settings button, and using it loads the orbit's details and opens the editor

## Scenario: Members do not see the orbit settings button
**Given** the organization's orbits tab with the current organization's role set to member
**When** the tab renders its orbit rows
**Then** no row shows the settings button, and the create button follows the create permission as before

# Tasks

- [x] Make the flow object end only its own session
  - [x] Keep the started session's identifier in `RelayedFlow` in `sdk/python/sdk/luml/flow.py` and end that session in cleanup through the API client's live sessions resource, treating gone or already ended as ended and other failures with the existing warning
  - [x] Reword the docstrings of the object and its stop to say the session is ended
  - [x] Extend the fakes in `sdk/python/sdk/tests/flow/fakes.py` with the session end operation and add tests in `sdk/python/sdk/tests/flow/test_relayed_flow.py` for the scenarios: the second run outlives the first, the run that still owns the flow, stopping after LUML ended the session, stopping when LUML cannot be reached
  - [x] Run ruff, mypy and pytest in `sdk/python/sdk/`

- [ ] Fix the relay-setup link's route parameter in the add-flow dialog
  - [ ] Pass the organization's identifier as the `id` parameter of the `organization-orbits` route in `frontend/src/components/flow/FlowAddDialog.vue`
  - [ ] Correct the assertion on the link's target in `frontend/src/pages/orbits/__tests__/OrbitFlowView.test.ts`
  - [ ] Run the type check, the linter and the unit tests in `frontend/`

- [ ] Show the orbit settings button to organization owners and admins
  - [ ] Gate the settings button in `frontend/src/components/organizations/OrganizationOrbits.vue` on the current organization's role being owner or admin, leaving the create button's gate as it is
  - [ ] Rewrite `frontend/src/components/organizations/OrganizationOrbits.test.ts` to set the role instead of an update permission, covering owner, admin and member
  - [ ] Run the type check, the linter and the unit tests in `frontend/`
