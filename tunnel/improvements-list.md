# Tunnel: planned changes

Direction for the next iteration of live sessions and the relay. Input for a
detailed spec. Each section gives the decision, why, the constraints a spec
must respect, what it touches, and what is still open.

## 1. Tokens are validated by LUML, not by signatures

The relay asks LUML whether a token is valid, with a short cache, like the
satellite asks the platform. Tokens are opaque and stored by LUML, which
becomes the single place to revoke a session, a viewer or an agent. The relay
authenticates to LUML with a relay token of its own.

Why: offline verification bought little, since the agent already depends on
LUML every few minutes for token renewal. It cost key rotation and
distribution, signing code on both sides, and one-time-token state stuck in a
single relay process.

- An unreachable LUML must not drop open sessions. The relay keeps serving
  what it already validated.
- Stored tokens clean themselves up with the backend's existing pattern of
  expiring rows on write. There is no scheduler and none should be added.
- The relay's frame protocol, streams and forwarding do not change.

Touches: backend token storage and a validation endpoint, the relay's
verifier, the launch and cookie flow, removal of the signing code.

Open: static relay token on both sides or a pairing flow like the satellite's.
Viewer idle timeout enforced by the relay or by LUML.

## 2. Flows are their own entity

A flow exists on its own. A tunnel session is one optional, replaceable way to
reach it. Sessions stay the generic record of something exposed into an orbit
and never know about flows, so other features reuse them the same way.

Why: today every session lands on the Flow page, because the page lists the
orbit's sessions and the backend hardcodes the Flow route as the place a
session is opened. Making a flow equal to a session would also bake in that
tunnels are the only way a flow will ever be exposed.

- A flow can exist without a session and be re-exposed by a new one.
- Nothing in the session machinery references flows.
- No generic exposure abstraction until a second way to expose exists.
- A flow has no visibility of its own. It is seen by whoever may see its
  session, see section 4.
- For now the Flow page opens a flow in a new tab, never in an iframe.
  Embedding needs design changes in lumlflow first. The relay keeps its
  embedding support, since it is generic, but the access-needed page must
  work as a top-level tab, where there is no parent to notify.
- No changes to lumlflow itself in this iteration. No read-only mode, no
  awareness of being exposed. A viewer sees exactly what the owner sees.
- Opening a session can carry a destination: a path with query arguments that
  the viewer lands on after launch, instead of the root. After launch every
  request already reaches the local service with its path and query intact,
  so this only concerns the first hop. The destination must be a relative
  path on the session's own host, never a full address, and must not carry
  anything secret, since it travels in a URL. It is session machinery, so
  flows and future consumers all get it.

Touches: a flows entity and its API, the Flow page, the SDK, the tunnel's
LUML adapter.

Open: whether a session keeps a name of its own once flows carry one. When
embedding comes back.

## 3. Relays are records: bring your own, managed, limits

Organizations register their own relays and assign one per orbit. LUML offers
managed relays that any organization can assign but nobody can edit or delete.
Every organization has two independent limits on active sessions, both always
enforced: one for sessions through managed relays and one for sessions through
its own relays. The two have different values. Both are organization-wide
totals across all of its orbits and all relays of that kind, not limits per
relay.

Scope: bring-your-own relays are delivered completely, from registration to
running sessions through them. For managed relays this iteration delivers only
the way to have one: the record, the ownership rules, the quota and the
provisioning path. No managed relay is operated or offered yet, and nothing
here should be sized for a fleet.

Why: today one relay per deployment lives in settings, and a session only
records its id as a string. Bring-your-own needs a relay to be something an
organization owns, and managed relays need a quota that is independent of what
a customer runs.

- A session keeps the relay it started on, even if the orbit is reassigned.
  Whether that relay is managed or the organization's own decides which of
  the two organization limits the session counts toward.
- A session stops counting against a limit once its heartbeats lapse, not
  only when it is ended explicitly.
- There can be several managed relays at once, for example one per region,
  from the first version on. Nothing may assume a single managed relay: not
  the provisioning path, not the assignment UI, not the quota, which counts
  across all of them.
- Managed relays are provisioned by operators, not through the organization
  API. A seed from settings is enough to start, as long as it can describe
  more than one relay.
- Independent of section 1. With section 1, the relay token lives on the
  relay record.
- An orbit without an assigned relay refuses to start sessions, with a clear
  message to assign one in orbit settings. No fallback to a managed relay.
- Every relay record has a status, enabled or draining. A draining relay keeps
  its sessions but takes no new ones, so it can be taken out of rotation
  without being deleted. Applies to own and managed relays alike.
- A relay token can be rotated: a new one is issued and the old one retired
  after a short overlap. Same path for own and managed relays. Goes with
  section 1.
- The relay reports to LUML periodically using its token, at least a
  last-seen time and its number of connected agents, so admins and operators
  see whether a relay is alive. Direction only, the first version can be
  minimal.
- Every relay record carries a free-text label shown in the UI, so choosing
  among several relays later needs no schema change.
- Organization settings get a relays page next to members, orbits and
  buckets: it lists the relays the organization can use, with managed ones
  marked as such and read-only, and lets admins add, edit and remove the
  organization's own, and rotate their tokens. Adding one shows what the
  relay needs to run, and with section 1 shows its token once.
- Assigning a relay to an orbit happens where an orbit's bucket is chosen
  today, with the same permissions as other orbit settings. The choice lists
  every enabled managed relay and the organization's own, by label.

Touches: a relays entity with organization and orbit API, organization
limits, the session start path, the relay's configuration, organization
settings and orbit settings in the frontend.

Open: how a managed relay is run and scaled, decided when one is offered,
not now.

## 4. Session visibility is a property of the session

A session is visible to the user who started it, and to nobody else. That
stays the only visibility for now, but it becomes an explicit attribute of the
session with a single rule that decides who may list, open and view it. Later
visibilities, such as all members of the orbit, are then a new value of that
attribute, and flows and any future tunnel-based feature inherit it without
work of their own.

Why: today the owner-only rule is right, but it is spread over the handler and
the listing query, and nothing records that it is a choice rather than a fact.

- Visibility lives on the session, not on the flow or any other consumer. A
  consumer is visible exactly to those who may see its session, so an
  invisible session hides its flow too. A flow with no session is visible to
  its creator only.
- One rule decides visibility everywhere: listing, opening, issuing viewer
  access. Sessions a user may not see keep answering "not found".
- Only the owner can end a session, whatever its visibility.

Touches: the session record and its handler and repository. No API or
frontend change until a second visibility exists.

Open: whether visibility is fixed at start or can be changed afterwards, and
by whom.

## 5. The Flow page is redesigned

The page is rebuilt to feel like a native platform page. Today it looks out of
place. The spec writer analyses how existing pages, the satellites page above
all, are built and follows the same patterns.

- Landing on the page needs nothing beyond being in the platform. Opening a
  flow needs no sign-in of its own.
- Flows are big cards like satellites. With no flows, the page shows a card
  with a plus sign, in whatever way the platform already does this.
- The plus opens a popup with two choices: connect a local flow, or a remote
  one through a relay.
- Local flow: the user enters address and port, the page checks that
  something is up there, and the entry is stored in the browser's local
  storage only. It is bound to neither orbit nor user, so it shows on every
  orbit's Flow page in that browser and for whoever uses it. The card must
  make it obvious that the flow is local.
- Remote flow: the popup sends the user to the docs that explain how to expose
  one through a relay. Nothing is created from the page.
- Removing a flow: a local one is dropped from local storage, a remote one has
  its tunnel session ended.
- Opening a flow opens a new tab, see section 2.

The reachability check runs in the browser, so it has to cope with CORS and
mixed content: a plain-http localhost is reachable from the platform page,
other plain-http hosts may not be.

Touches: frontend only.

Open: whether a local flow gets a name.

## 6. Temporary flows from code

Training and experiment code can spawn a relayed flow with one object, for
example a `LiveFlow` class in the SDK used as a context manager, and have it
destroyed when the block or the process ends. The building blocks exist: the
tunnel package already starts a session at LUML, serves it and ends it on
stop. This wraps them for use from ordinary Python.

- Works from synchronous code, scripts and notebooks alike, so the tunnel runs
  in the background without the caller managing an event loop.
- Prints or returns the address where the flow can be opened.
- Destroys on exit: the session is ended and the flow removed, so nothing
  lingers on the Flow page. Cleanup also runs when the process ends without
  reaching the exit, as far as Python allows.
- Uses the same credentials and organization and orbit selection as the rest
  of the SDK.
- Launches lumlflow itself when none is running yet, and exposes the running
  one otherwise. A lumlflow it launched is stopped on exit, one it found is
  left alone.
- Lives in the SDK, which takes the tunnel package as a dependency, optional
  if that keeps the base install light.

Touches: the SDK, possibly the tunnel package's LUML adapter.

## 7. Keep the door open for terminal sessions

Today the relay carries web UIs. Relaying terminal sessions may come later.
Nothing is built for it now, but nothing in this iteration may make it hard.

- Stream kinds stay extensible. Today there are HTTP and WebSocket streams,
  and a terminal would be a third kind, not a special case of HTTP.
- Nothing in the relay, the protocol or the token design assumes that every
  viewer is a browser or that every stream begins with an HTTP request. The
  existing header-based viewer access, as opposed to the cookie, is the path
  a non-browser client would use and must survive section 1.
- A web terminal served by a local service over WebSocket already works and
  needs nothing from the relay.

## 8. Relay hardening

The relay is a public, always-on component, so it should be reasonably
hardened: not the first priority of this iteration, but part of it. Every
resource an agent or a viewer can make the relay spend must have a bound the
relay enforces itself, without relying on LUML to issue few tokens.

- Rate-limit token renewal frames per agent connection, since each one costs
  a verification.
- Cap the number of agent connections a relay accepts, with a clear refusal.
- The existing bounds stay: streams per connection, request body size, idle
  timeout, credit windows per stream.
