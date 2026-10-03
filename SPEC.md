# Proposals

## Where live sessions stand today

The branch adds a reverse tunnel so that a web service running where nothing can reach it, such as lumlflow next to a training job, can be opened from the LUML app. An agent runs next to the service and keeps one outgoing connection to a relay. The relay has a public address and gives each session its own hostname under a base domain. The LUML backend keeps a live session record per exposed service and signs two kinds of tokens: one lets an agent expose a service, the other lets a viewer reach it. The relay checks tokens offline against keys the backend publishes. A viewer in a browser opens a launch address that exchanges a viewer token for a relay-signed cookie. Every session of the user appears on the Flow page of its orbit, shown in a frame.

Nothing in the branch is shipped. Everything on it may be changed or replaced, and no backward compatibility is owed to any of it, including migrations, API shapes, token formats and the frame protocol.

*Note:* The spec that produced the branch is in git history as SPEC.md at commit 571b78bb. It is the best orientation on what exists and why. The improvements list this spec is built from is the file improvements-list.md in the tunnel directory.

Seven things hurt.

- The relay checks tokens on its own. That needs key rotation and distribution, signing code on both sides, and one-time token state that lives in one relay process and is lost on restart. Revoking anything means waiting for a token to expire. The agent already depends on LUML every few minutes for token renewal, so offline checking bought little.
- Every session lands on the Flow page, because the page lists the orbit's sessions and the backend hardcodes the Flow route as the place a session is opened. Another feature cannot reuse sessions without appearing on that page, and making a flow equal to a session bakes in that tunnels are the only way a flow will ever be exposed.
- One relay per deployment is described in backend settings, and a session records its relay as text. An organization cannot bring its own relay, and nothing can be limited per organization.
- The rule that only the starting user sees a session is spread over the handler and the listing query. Nothing records that it is a choice rather than a fact, so a second visibility later touches every place.
- The Flow page looks out of place next to the other pages. A lumlflow running on the user's own machine has no place on it. Showing a session in a frame needs changes in lumlflow that are not planned yet.
- Exposing a running experiment from training code needs a separate command started next to the job.
- The relay is public and always on, but it bounds neither the number of agents it accepts nor how often an agent makes it check a token.

## What changes

LUML stores tokens as opaque strings and the relay asks LUML about them, with a short cache and a token of its own. Relays become records that an organization owns or that LUML manages, assigned per orbit and counted against two organization limits. A flow becomes an entity of its own, reached through one replaceable session. Visibility becomes an attribute of the session with one rule. The Flow page becomes a card page like the satellites page, knows local flows in the browser, and opens flows in new tabs. The SDK gets an object that exposes a flow from Python and cleans up after itself. The relay gets bounds on connections and renewals.

## Why this way

Asking LUML about tokens makes LUML the single place to revoke a session, a viewer or an agent, and removes the signing code on both sides. The relay already depends on LUML for the agent's renewals, so the new dependency is not new. A short cache and serving what was already validated keep an outage of LUML from dropping open sessions.

Flows and sessions stay two things. Sessions remain the generic record of something exposed into an orbit and never know about flows, so the next feature reuses them the same way. No generic exposure abstraction is built until a second way to expose a flow exists.

Relays are records because bring-your-own needs a relay to be something an organization owns, and managed relays need a quota independent of what a customer runs. Bring-your-own is delivered completely. For managed relays only the record, the ownership rules and the quota are delivered; none is provisioned or operated yet, and nothing is sized for a fleet.

Visibility becomes explicit now, while there is one value, because later values then cost one rule change and nothing in flows or future consumers.

Flows open in a new tab, not in a frame, because embedding needs design changes in lumlflow first. lumlflow's behaviour is not changed in this iteration: no read-only mode, no awareness of being exposed. A viewer sees exactly what the owner sees.

The SDK owns exposing a flow and the tunnel package stays generic, so one code path serves scripts and notebooks, and the tunnel package never learns about flows. A command-line way to expose a flow belongs in the lumlflow command and waits for a later iteration.

Every open point got the simplest answer that is still safe for production. Nothing beyond the improvements list is added unless the list cannot work without it.

## Outside this spec

- Provisioning, rotating, operating and scaling a managed relay, including how its row gets into the database. That is decided when one is offered.
- Showing a flow inside the LUML app in a frame.
- Changes to lumlflow's behaviour, including a command in it that exposes a flow.
- Visibilities other than the owner, and changing a session's visibility.
- Revoking a single viewer or agent without ending the session.
- Usage metering, and more than one relay instance behind one base domain.

# Design

## Parts and where they live

The branch has four parts: the tunnel package, the backend, the API client and the frontend. This iteration changes all four, adds a module to the SDK, adds one docs page and reworks the dev stack. Each part follows a neighbour that exists today.

| Part | Where | Follows |
|---|---|---|
| Relay records, stored tokens, relay-facing API, flows, limits | `backend/` | satellites for records and keys, bucket secrets for organization-owned resources, the organization limits module, the monitoring launch tokens for expiring rows |
| Relay verifier, relay configuration, hardening, agent changes | `tunnel/` | the branch's own package layout and in-process test harness; the satellite kit's platform authorizer as a model for the cache, copied, not imported |
| Relays and flows resources, changed orbit and session operations | `sdk/python/api/` | the bucket secrets and live sessions resources |
| The flow object | `sdk/python/sdk/` | the SDK's other optional extras |
| Flow page, relays tab, relay choice in orbit dialogs | `frontend/` | the satellites page, the buckets tab, the orbit creator and editor |
| How to expose a flow | `docs/` under the Flow app pages | the existing lumlflow pages |
| Relay in the dev stack | `dev/` | the existing relay service and the seed script |

lumlflow's code is not changed. Its dependency pins are widened once, as the section on the flow object explains. The release workflows the branch added stay as they are.

## Relay records

Today one relay per deployment is described by three settings, and a session stores the relay's identifier as text. A relay becomes a row that an organization owns, or a managed row that nobody owns. Several managed relays can exist at once, for example one per region, and nothing may assume there is only one.

A relay record carries a label shown in the UI, a base domain, the address agents connect to, a status of enabled or draining, the hash of its current token, the hash of its previous token with the time that one stops working, the last-seen time and the number of connected agents it last reported, and its owner organization, which is empty for a managed relay. Other columns are the implementer's choice.

The base domain is accepted only as a bare hostname: no scheme, port, path or trailing dot. It is stored lower-case and is unique across all relays of a deployment in that form, because one base domain can be served by one relay process only. The agent address must be a ws or wss address. A session's public address is derived as the handler derives it today, from the relay's base domain and the scheme and port of its agent address.

The relay token follows the satellite API key: random, prefixed `dfsrelay_`, hashed with the keyed hash used for satellite keys, and returned in plain text once by the operation that issued it. Rotation issues a new token, moves the current hash to the previous slot, and sets the previous token's end to now plus `LIVE_SESSION_RELAY_TOKEN_OVERLAP_SECONDS`, a backend setting with a default of 600. Authentication accepts either hash while the previous one has not expired. Only one previous token is kept, so a rotation inside the overlap retires the token before it at once.

A draining relay authenticates, validates and reports as before and keeps serving its connected agents and viewers, including heartbeats and token renewals. It is refused only as the relay of a new session.

Liveness is written by the relay's report operation only. The relay answer carries an online flag computed by the backend, as the satellite status is computed: online when the last report is less than five minutes old.

Removing an own relay is refused while it has sessions that have not ended, with a message that names the count. A disconnected session counts here as much as a live one. Once every session on the relay has ended, the removal succeeds: every orbit assigned to the relay loses the assignment, and the ended sessions keep existing with an empty relay reference so they stay listed. Changing a relay's base domain or agent address is refused by the same rule while the relay has unended sessions, because running sessions derive their addresses from them; the label and the status can change at any time. An organization's relays are deleted with the organization. Managed relays are never removed through the organization API.

Relays join the permission tables as a resource of their own, so the frontend can ask what a role may do. Organization owners and admins get every action. Organization members get list and read, because an orbit admin who is only a member of the organization edits the orbit and needs the list to choose a relay.

| Operation | Who | Behavior |
|---|---|---|
| List | any member of the organization | the organization's own relays and every managed relay, each marked managed or own, with status, online flag, last-seen time and connected agents; never a hash |
| Read one | any member | the same for one relay |
| Create own | owner or admin | validates label, base domain and agent address; refuses a base domain another relay uses with the existing conflict error; stores the record with the hash of a new token; answers the record and the plaintext token, this once |
| Update own | owner or admin | label, base domain, agent address and status may change, under the unended-sessions rule above |
| Rotate own token | owner or admin | issues a new token, keeps the old one for the overlap, answers the plaintext once |
| Remove own | owner or admin | the removal rules above |

Update, rotate and remove of a managed relay through the organization API are refused with a message that says managed relays are read-only. The operations sit under the organization next to bucket secrets.

## Managed relays

A managed relay is a relay record with no owner organization. Every organization can assign it, nobody can edit or delete it through the organization API, and sessions on it count toward the managed limit.

Nothing in this iteration puts a managed relay row into the database or rotates its token. How that happens is decided when a managed relay is offered. The record is ready for it: the repository creates a relay with or without an owner, several managed relays can exist at once and nothing assumes a single one, and the token and rotation mechanism is the same for both kinds. Integration tests create managed rows through the repository. No managed relay is read from settings or kept in memory.

## Orbit relay assignment

An orbit is created and edited through dialogs that choose its bucket. The orbit gets a relay the same way.

The orbit row gains an optional reference to a relay, cleared when the relay is removed. The orbit create and update operations accept it and may clear it, and the orbit answers carry it so the Flow page knows whether the orbit has a relay. The backend accepts only a relay that is managed or owned by the orbit's organization and answers "not found" for any other, the way an unknown bucket secret is refused today. Draining is not checked at assignment; it is enforced at session start. All existing orbits start without a relay.

## Sessions

A live session is the record of something exposed into an orbit, with a status computed when it is read. Today it stores the relay as text, requires a name, and hides itself from everyone but its starter through checks spread over the handler and the listing query.

The record changes in four places. The relay becomes an optional reference to a relay record, kept when the orbit is reassigned and emptied only when the relay is removed. The required name becomes an optional label, for operators and for sessions that have no consumer; it is shown nowhere in the UI. A visibility column is added with the single value `owner`, set at start and not changeable through the API. The time of the last viewer activity LUML observed is stored; what counts as viewer activity is defined in the section Stored tunnel tokens.

| Status | Meaning |
|---|---|
| `live` | the last heartbeat is less than 90 seconds old and the agent reported a working connection |
| `disconnected` | no heartbeat for 90 seconds, or the agent reported no connection |
| `ended` | ended explicitly, or no heartbeat for one hour, or no viewer activity for longer than the viewer-idle period; both silences are counted from the start when nothing has happened yet |

The viewer-idle period is `LIVE_SESSION_VIEWER_IDLE_SECONDS`, a backend setting with a default of seven days. It exists so that a forgotten process whose agent keeps heartbeating does not hold a flow and a limit slot forever. The three ended conditions are one shared rule, applied wherever a session's end is decided: the status computed on a record, the listing query, the guard that refuses heartbeats of ended sessions, the activity of the session's tokens, the counts of unended sessions for the limits and the relay removal check. A heartbeat for an ended session answers the ended status and records nothing.

Every session that has not ended, whether live or disconnected, counts toward the limits and blocks the removal of its relay. A session frees its place only by ending: explicitly, after an hour of silence, or by the viewer-idle rule.

*Note:* Counting only live sessions was considered and rejected. A session is live only after a heartbeat that reports a working connection, so a burst of starts would pass the limit before the first heartbeat, and a crashed run would free its place while it might still reconnect.

Starting a session resolves the orbit's relay and checks it before anything is created.

| Situation at start | Answer |
|---|---|
| The orbit has no relay | refused with status 409 and a message that says to assign a relay in orbit settings |
| The relay is draining | refused with status 409 and a message that names the relay as draining |
| The organization's limit for the relay's kind is reached | the existing limit-reached error, naming the kind of relay |
| Otherwise | the session is created with that relay and the agent's token is issued |

The error that said live sessions are not set up in the deployment disappears with the settings it reported, together with its handling in the clients.

Visibility is decided by one function that takes a session and a user. For the value `owner` it is true for the starting user only. Listing, reading, issuing viewer access and recording heartbeats go through it, and the listing query applies the same rule as its filter so nothing hidden is fetched. A session the user may not see answers "not found". Ending stays limited to the starting user independently of visibility. Where the function lives is left to the implementer.

The operations stay under the orbit and keep their callers, with these changes to their contracts.

| Operation | Change |
|---|---|
| Start | takes an optional label instead of a name; answers the session identifier, its public address, the address agents connect to, the agent's token with its expiry and the heartbeat interval; no longer answers an address in the LUML app, because a bare session appears nowhere in the app |
| Issue viewer access | additionally takes an optional destination; the launch address keeps its shape and the destination is not in it |
| Heartbeat, list, read, end | unchanged |

An ended session is kept for 24 hours as today, so the agent's next heartbeat learns that it ended and the session list shows recent history. After that its row is deleted with the expiring-rows-on-write pattern, whenever a session is started or ended, and its stored tokens and its flow go with it. A session ended by silence or by the viewer-idle rule has no recorded end, so its retention is counted from the moment the shared rule says it ended.

## Organization limits on sessions

Organizations have limit columns for members, orbits, satellites and artifacts, enforced in two layers: a handler pre-check and a row-locked check inside the insert. Two more columns follow them: sessions through managed relays, default 0, and sessions through own relays, default 5. The organization details answer carries both like the existing limits. The limits panel of the organization page is not changed in this iteration; a user who reaches a limit sees the limit-reached message.

A session counts toward exactly one of the two, decided by whether the relay it started on has an owner. It counts from its start until it ends, across all orbits of the organization and all relays of that kind, whether it is live or disconnected. A crashed run therefore holds its place for up to an hour; a user who needs the place sooner ends the session, removes the flow, or re-exposes the same flow, which counts the flow's own session as free.

Enforcement follows the existing two layers: the handler reads the organization and refuses early, and the insert locks the organization row, counts the organization's unended sessions on relays of that kind, and refuses when the count has reached the limit. Both layers answer the existing limit-reached error with a message naming the kind of relay. Limits are changed by operators in the database, as the existing limits are.

*Note:* The managed default of 0 means no organization can use a managed relay until an operator raises its limit. That is intended while no managed relay is offered.

## Stored tunnel tokens

Today the backend signs tokens as JWTs and the relay checks them offline. Tokens become random strings that the backend stores and the relay asks about.

A stored token carries a hash of the token, made with the keyed hash used for API keys and satellite keys, its kind, its session, its user, its expiry, the time a launch consumed it, and for viewer tokens an optional destination. Only the hash is stored, so a copy of the table cannot be replayed. The plaintext is returned once to the caller that asked for it.

There are two kinds, `expose` for the agent and `view` for a viewer. A viewer grant is what a `view` token becomes once a browser has launched with it.

| Kind | Held by | Issued when | Lifetime |
|---|---|---|---|
| `expose` | the agent | a session starts, and a heartbeat finds the current token past half its lifetime | ten minutes, the existing setting |
| `view` | a viewer | the owner asks for viewer access | five minutes, the existing setting |
| viewer grant | a browser, inside the relay's cookie | a launch consumes a `view` token | twelve hours after the launch |

A renewal issues a new `expose` row; the previous row stays valid until its own expiry, so a renewal in flight never cuts a connection. A `view` token is usable in the token header until it expires and at the launch address once. The launch marks the row as launched in one atomic write, so exactly one of two concurrent launches succeeds, and extends its expiry to twelve hours after the launch. From then on the row is the viewer grant that the relay's cookie references, identified by the row's identifier. A launched token is refused everywhere afterwards, at a second launch and in the header alike.

A token or grant is active when it exists, is unexpired, and belongs to a session that is not ended and started on the relay that asks. Ending a session deletes nothing: its tokens and grants become inactive because the session is ended, including a session ended by silence or by the viewer-idle rule. Revoking a single viewer or agent has no API in this iteration; ending the session is the lever, and because grants are rows at LUML, revoking one later needs no change on the relay.

Viewer activity, for the viewer-idle rule in the section Sessions, is what LUML sees of viewers: issuing viewer access for a session, validating one of its `view` tokens for the relay, and checking one of its grants. Each of these records the time on the session. The relay asks about a token or grant at most once per cache window, so an active viewer costs the backend about one write per minute.

Rows past their expiry are deleted whenever a token is issued or launched, following the monitoring launch tokens and the token blacklist. There is no scheduler.

The destination is accepted when it starts with one slash, does not start with two, and contains no scheme or host. Anything else is refused as a validation error when the token is issued. It is stored on the token and handed to the relay at launch.

The signing key setting and the three single-relay settings leave the backend together with the key loading and signing module and the JWKS route.

## The relay-facing API

The relay talks to LUML the way a satellite does: with a key of its own that the authentication backend recognizes by prefix, and routes reserved for it.

The authentication backend dispatches on the relay token prefix, resolves the relay by the hash of its current token or of its previous token within the overlap, and authenticates the request with the scope `relay` and a principal that carries the relay's identifier, the way the satellite principal carries the satellite and its orbit. The relay routes live under the prefix `/relays/v1`, beside the satellite worker routes and outside the organization tree, and require that scope. The scope grants nothing outside those routes.

| Operation | Input | Answer |
|---|---|---|
| Describe self | nothing | the relay's identifier, label, base domain, agent address and status; the origins of the LUML app that may frame sessions, which are the backend's CORS origins; and the address of the LUML app, which the backend already uses for links in emails |
| Validate a token | the token, and whether this is a launch | inactive, or active with the token's kind, session, user and expiry, and for a launch the grant identifier and the destination |
| Check a grant | the grant identifier | inactive, or active with the session, the user and the grant's expiry |
| Report | the number of connected agents | nothing; LUML records the count and the time |

LUML answers about the token itself. Whether the token fits the request, the right kind for an agent handshake or a viewer request and the session the hostname addresses, is checked by the relay against the claims it gets. This keeps one answer per token, which the relay can cache, and a token first presented in the wrong place never poisons its legitimate use.

Invariants:

- Every answer is scoped to the calling relay. A token or grant whose session started on another relay is inactive for this one. A relay can never learn about sessions that are not its own.
- An inactive answer is a normal answer with status 200, never an HTTP error, so the relay can tell a verdict from a failure to answer. A refused relay token answers 401.
- An inactive answer never says why. The reason stays in the server log, so a public relay cannot be used to probe which sessions exist.
- Validation writes nothing except the launch consumption of a `view` token and the viewer activity time on the session.
- A draining relay is served by all four operations. Draining only stops new sessions at session start.

The exact paths and field names are fixed by the backend implementation, which comes first; the tunnel package mirrors them in its client and its test fake.

*Note:* LUML could answer launches with a redirect itself. It does not, because the cookie must be set on the session's hostname, which only the relay serves.

## The relay process

The relay stays one process in one container that serves plain HTTP behind whatever terminates TLS. What changes is where its configuration and its trust come from.

The process is configured by two environment variables: `LUML_BASE_URL`, the same variable the API client reads, for the address of LUML, and `LUML_TUNNEL_RELAY_TOKEN` for its token. The command-line options for the base domain, the relay identifier, the issuer, the issuer's keys and the app origins are removed. The listen host and port and the resource bounds stay options of the process with defaults, and the cookie secret stays as it is today, read from the environment and drawn at random when absent. The container image keeps its entry point and takes the two values from the environment.

At startup the relay fetches its description from LUML and serves no session before it has one, because it needs the base domain to route. While LUML cannot be reached or answers with a server error, it retries with growing pauses capped at half a minute and logs each attempt with its cause, so a relay may start before LUML does. A LUML that refuses the token is a misconfiguration: the process exits with a message that names the cause, since retrying cannot help. The description is read once; a change to the relay's base domain or agent address takes effect when the relay restarts.

The relay checks tokens through the interface the branch already has, asking for a token of a given kind, optionally bound to a session, and getting claims or a refusal. The implementation in this work asks LUML and copies the shape of the satellite kit's platform authorizer: a cache of claims keyed by the hash of the token, and of grant answers keyed by the grant identifier, with a window of 60 seconds by default as a relay setting. The satellite kit is a model only. The tunnel package takes no dependency on it, and its dependencies stay what they are today: a WebSocket client and an HTTP client, with the relay's web server behind the relay extra and the API client behind the LUML extra.

| Outcome of asking LUML | Cached | What the relay does |
|---|---|---|
| active, claims fit the request | yes, until the window or the expiry, whichever is first | serves |
| active, claims do not fit the request | yes, the claims | refuses as it refuses a bad token today, without asking LUML again while the claims are cached |
| inactive | yes, for the window | refuses as it refuses a bad token today |
| no answer: unreachable, timeout, server error, or a refusal of the relay's own token | no | uses the cached answer it has, even past its window, until that token or grant expires on its own; without one, answers "try again" |

A launch is the exception to the cache. It always asks LUML, never reads the cache, and when it succeeds it evicts the token's cached claims, so a consumed token is refused in the header on its next check even inside the window. A header use never pre-answers a launch, because the launch does not read the cache.

"Try again" is status 503 with a short text for a viewer, and a handshake refused with status 503 for an agent, which the agent already treats as a temporary failure and retries with its growing pauses. Neither is ever answered with 401 or 403, so a client cannot mistake an outage for a revocation. Connected agents and viewers whose claims are cached keep being served; a connected agent is never disconnected because LUML is unreachable, and its connection ends only when its token expires without a renewal, as today. A refusal of the relay's own token during operation is logged at error level on every occurrence and reported by the health check, so the operator restarts the relay with its new token; serving continues as for an outage.

The launch address keeps its shape, the `view` token as a query parameter on the session's hostname. The relay validates the token as a launch, which consumes it at LUML, sets its cookie and redirects to the destination the answer carries, or to the root when there is none. The in-process set of used launch tokens disappears. The cookie keeps its name, its signature and its binding to one session and one user. It carries what the relay needs to decide the idle limit of 30 minutes since the last request and the hard limit of 12 hours since the launch from the cookie alone, and to look the grant up at LUML; the fields are the implementer's choice. On each request with a cookie the relay checks the signature and the two limits, renews the cookie as today, and checks the grant through the cache. A grant that LUML no longer accepts ends the cookie within the cache window, and the viewer gets the access-needed answer. A failed check answers as missing access does today: the access-needed page for a navigation, status 401 otherwise.

Viewer access by the token header, `X-Luml-Tunnel-Token`, is unchanged except for where the token is checked: the header carries a `view` token that the relay validates through the cache and never consumes. A grant identifier is never accepted in the header. This is the path a program uses, and it carries no assumption that a viewer is a browser.

The access-needed page works as a top-level document. It keeps posting its message to a parent frame when it has one, and otherwise says that the flow has to be opened again from the LUML app and links to the app address learned from the relay's description.

The relay reports to LUML on a steady interval, 60 seconds by default as a relay setting, with its number of connected agents. A failed report is logged and tried again at the next interval; it never affects serving.

Hardening adds bounds the relay enforces itself. Each is a setting of the relay command with a default left to the implementer and documented in the command's help.

| Bound | Behavior when reached |
|---|---|
| Agent connections per relay | one more handshake is refused with status 503 and a reason that names the cap; connected agents are untouched |
| Renewal frames per agent connection per unit of time | frames beyond the rate are dropped without validation; the connection and its streams continue, and the token in force keeps its expiry |
| Validations in flight to LUML | further validations wait for a slot, and a wait that outlasts the request's own timeout is answered "try again" |
| Entries in the validation cache | the oldest entries are evicted |
| Streams per connection, request body size, idle time, credit windows | unchanged |

Nothing in this work narrows the door for terminal sessions. The verifier interface takes a token kind and knows nothing about HTTP. Stream kinds remain an open set of frame type codes in the frame protocol, where a terminal would be a new opening frame type, not a special HTTP stream. The relay-facing API carries no assumption that a viewer is a browser or that a stream begins with an HTTP request. The cache data structure, the rate limiter and the handshake refusal text are left to the implementer.

## The agent and the bare-session command

Today the agent reports whether its connection works and its token's expiry, and `luml-tunnel expose` either connects to a relay directly with a token or starts a session at LUML under a required name.

The agent never connects with a token it knows has expired: when the relay closes the connection at the token's expiry, it waits for the heartbeat that renews the token before trying again. This keeps an outage of LUML longer than a token lifetime from ending the command; a handshake refused in the 400 range stays fatal, and a replaced session stays a reason to exit.

The LUML adapter of the tunnel package is split into two steps: starting something at LUML, and serving an already started session until it is stopped or ended. Serving takes what a session start answers, runs the agent, sends heartbeats with the connection state, presents renewed tokens to the relay, and ends the session at LUML on a clean stop. The SDK reuses the second step for flows.

`luml-tunnel expose` keeps both modes. Through LUML it takes the organization, the orbit and an optional label in place of the required name, starts a bare session, prints the session's identifier and public address, and otherwise behaves as today. Direct mode, a relay address and a fixed token without LUML, stays for the package's own tests. The development subcommands that create keys and sign tokens are removed with the signing code, and the relay extra no longer needs a JWT library.

## Flows

A flow is a named entry on an orbit's Flow page that points at a session. Today a session is shown directly on the Flow page and nothing called a flow exists.

A flow carries its orbit, its creator, a name and a reference to its current session. The reference is required: every operation of this iteration creates a flow together with its session. The session knows nothing about the flow. The name is unique per creator within an orbit, guarded by a plain database constraint that is kept true by deleting gone flows before each write. A flow is visible to whoever may see its session, through the session's visibility function.

*Note:* A later feature that creates flows before exposing them relaxes the reference to optional when it exists. The improvements list allows a flow without a session; nothing in this iteration produces one.

A flow is gone when its session's status is ended. Gone flows are not listed, their names are free, and the write paths of the flows handler delete them before they do anything else, following the expiring-rows-on-write pattern.

The flows API lives under the orbit next to the sessions and reuses the live session permission resource; flows get no permission resource of their own.

| Operation | Behavior |
|---|---|
| Expose | takes a name; deletes gone flows; finds the caller's flow of that name in the orbit, if any; checks the start refusals of the section Sessions first, counting the found flow's own session as free in the limit; only then ends the found flow's previous session, starts a session on the orbit's relay with the flow's name as the session label, and creates the flow or points it at the new session; answers the flow, the session start answer and the address of the orbit's Flow page in the LUML app |
| List | the flows the caller may see whose session is not ended, each with its session's identifier, status, start time and last heartbeat |
| Read one | the same for one flow; "not found" for a flow the caller may not see |
| Remove | ends the session when it has not ended, then deletes the flow; the owner of the session only, others answer "not found" |

A refused expose ends nothing and creates nothing, so a re-expose onto an orbit whose relay has since been set to draining leaves the running flow alone. Two concurrent exposes of one name end with one flow; the one that loses the unique constraint reuses the flow the other created. The transaction shape is left to the implementer. The address of a flow in the LUML app is the Flow page of its orbit, built from the app address the backend uses for links in emails; there is no page per flow, since a flow opens in a new tab. Opening a flow uses the session's own viewer access operation.

## The API client

`luml-api` has a live sessions resource with start, list, get, heartbeat, view token and end, an orbits resource whose create and update take a bucket secret, and a bucket secrets resource for a record an organization owns, each in a synchronous and an asynchronous form. The project rule is that anything a user can do in the UI can be done through the client.

A relays resource follows the bucket secrets resource, with list, get by identifier or label, create, update, rotate token and delete in both forms. Create and rotate return the plaintext token once, as the backend answers it, and no answer carries a hash. The list carries managed relays marked as such; the backend refuses changes to them and the client passes the refusal through as it passes other refusals. The orbits resource's create and update take the optional relay reference and may clear it.

The live sessions resource follows the session contract changes: an optional label on start, an optional destination when issuing viewer access, and the start answer without an app address. A flows resource is added with expose, list, read and remove in both forms, following the live sessions resource.

## The flow object

Today exposing anything needs the tunnel package's command and a running service. The SDK gains a `luml.flow` module with a `LiveFlow` object. There is no command for it in this iteration.

The module is importable only with the `flow` extra, which depends on the tunnel package with its LUML extra and on `luml-api`. Importing it without the extra fails with a message naming the extra, as the tunnel's command does for its own extras. lumlflow is not a dependency, because lumlflow depends on the SDK; `LiveFlow` needs the `lumlflow` command on the path only when it has to start one and fails with a message that says to install lumlflow when it is missing. The SDK's development group gets the extra's dependencies with local path sources for the tunnel package and the API client, as lumlflow declares them for the SDK, so the SDK's checks run against the branch.

The extra and lumlflow must install into one environment. lumlflow pins `luml-api` and `luml-sdk` to minors below the ones this work ships, and the tunnel package needs the `luml-api` that carries live sessions and flows. lumlflow's two pins are widened to accept the new minors; nothing else in lumlflow changes. The publish order is `luml-api`, then `luml-tunnel`, then the SDK, then lumlflow.

| Parameter | Default | Meaning |
|---|---|---|
| name | the machine's host name | the flow's name in the orbit; the same name replaces the previous card, so a rerun after a crash replaces its own card |
| organization, orbit | the only one when there is only one | by name or identifier, resolved as the API client's setup resolves them, with its errors passed through |
| store path | lumlflow's default store | passed to lumlflow when it is started |
| port | 5000 | where lumlflow answers, or is started |

`LiveFlow` is a context manager and also has explicit start and stop methods, because a block cannot span notebook cells. Starting probes lumlflow's authentication status path on the loopback port. When lumlflow answers, it is exposed as it is. When nothing listens, `LiveFlow` starts `lumlflow ui` on the store and port without opening a browser and waits until it answers, failing after a timeout. When something answers that is not lumlflow, starting fails at once with a message naming the port as in use. It then exposes the flow through the flows resource, serves the session with the tunnel package's serving step on a background thread with its own event loop, so the caller manages no loop, waits until the agent reports a connection or a timeout passes, and prints the flow's address in the LUML app and keeps it on the object. Starting raises with the cause when a step fails, and starting twice is an error.

Stopping removes the flow through the API, which ends the session, stops the agent thread, and stops lumlflow only when `LiveFlow` started it; a lumlflow it found is left running. Stopping twice is harmless. A stop that cannot reach LUML logs a warning and still stops the local parts; the session then ends at LUML by silence. Start registers an interpreter exit hook and, when running in the main thread, a handler for the termination signal that stops the flow and then chains to the previous handler. No handler is installed for interruption: it unwinds the block or exits the interpreter, which runs the hook, and installing one would let a notebook's interrupt kill a flow started in an earlier cell. Stop removes what it registered. When LUML ends the session, the background serving stops; leaving the block still removes the flow, which may already be gone, and stops lumlflow.

## Organization settings: the relays tab

Organization settings have tabs for members, orbits and buckets, each a child route of the organization page. A fourth tab, Relays, joins them after Buckets, routed and named like its neighbours.

It is built like the buckets tab: a header with the count and an add button, and a table. Each row shows the label, the base domain, the agent address, whether it is managed or the organization's own, enabled or draining, online or offline with the last-seen time, and the connected agents. Own rows have a settings menu with edit, enable or drain, rotate token and remove. Managed rows have no menu and are marked read-only. The add button is shown to users whose organization permissions allow creating relays.

Adding a relay asks for the label, the base domain and the agent address. On success a second dialog shows the token once with a copy button, in the way the satellite API key dialog does, together with what the relay needs to run: the two environment variables with the LUML API address and the token, and a command that runs the relay image the release workflow publishes with them on its port, plus a note that the base domain needs a wildcard DNS record and a wildcard certificate with TLS terminated in front of the relay. Rotating shows the new token the same way. The settings action of an own relay opens the right-hand dialog used for buckets, with the editable fields, a status toggle, the rotate action and a remove action behind a confirmation. A refused removal or edit shows the backend's message.

## Orbit dialogs: the relay choice

The orbit creator chooses a bucket in a select, and the orbit editor shows it disabled. Both gain a relay select directly under the bucket.

It lists the enabled managed relays and the organization's enabled own relays by label, marks the managed ones, may be left empty, and in the editor is enabled, unlike the bucket, and can be cleared. A relay that is assigned but draining still appears as the current value, marked as draining. When the organization can use no relay, the select is empty with a hint pointing to the relays tab, as the bucket select points to the buckets tab. The orbit payloads carry the relay reference as nullable, and the permissions are those of the dialogs today.

## The Flow page

Today the Flow page lists the user's sessions as rows and opens one in a frame on a page of its own. It becomes a card page like the satellites page and opens flows in new tabs.

The page keeps its route and sidebar entry. The session sub-route, its view, the frame, the message listener for the relay's page and the handling of the not-set-up status are removed, so the old session addresses fall to the not-found page. The Setup page's Flow tab keeps the instructions for running lumlflow locally and points to the docs page for exposing one; the command text that builds a `luml-tunnel` command is removed.

The page follows the satellites page: a header with the title and an add button, skeletons while loading, a grid of cards, and the platform's plus card when there is nothing to show. Cards come from two sources, the browser's local storage for local flows and the flows API for relayed flows. Every card says which of the two it is, with a visible mark for local and for relayed, so the user never has to guess where a flow runs. Local cards come first. The page refreshes both kinds at a steady interval while it is open, as the Prisma pages do; the interval and the copy are left to the implementer.

| Card | Shows | Actions |
|---|---|---|
| Local flow | the name, the address and port, a clear mark that it is local, a reachability dot refreshed on load and on the interval | open its address in a new tab; remove, which drops it from local storage |
| Relayed flow | the name, a status dot for live or disconnected with a tooltip, the time of the last heartbeat, a mark that it is relayed | open in a new tab when the session is live; remove after a confirmation, which calls the flow removal |

A user can add any number of local flows, for example one per lumlflow on different ports. Local flows are kept under one key in local storage, through the existing local storage service, as a list of entries with a name, an address and a port. The address and port together identify an entry: adding the same pair again is refused with a message naming the existing card, and names need not be unique. The store that wraps them never reads the orbit or the user, so the same entries appear on every orbit's Flow page in that browser, for whoever uses it. Relayed flows come from the flows API through a store that follows the satellites store.

The add button and the plus card open a popup with two choices. The local choice shows a form with the address, `localhost` by default, the port, 5000 by default, and a name that defaults to the address and port. Confirming requests lumlflow's authentication status path at that address with a short timeout. lumlflow allows every origin, so the request succeeds from the platform page when the address answers and the browser allows it: browsers that treat localhost as a secure context allow a plain-http localhost from the https page, while other plain-http hosts are blocked as mixed content and read as unreachable. When the check fails nothing is saved and the message says the address did not answer and that only localhost is reliably reachable from the platform page, in a browser that allows it. The same request is the reachability check of a saved card.

The relayed choice explains in two sentences that a relayed flow is exposed from the machine where it runs, with the SDK's flow object, to look into an experiment while it runs inside a job on a cluster or another machine nobody can reach, and links to the docs page at the docs address the frontend already reads from its environment. When the current orbit's details show no relay, the popup says so instead and links to the organization's orbits tab, where an orbit's settings are edited.

Opening a relayed flow asks for viewer access to its session and loads the launch address in a new tab. Because the token arrives after a network round trip, the page opens the tab on the click and sets its address when the token arrives, as the session page does today, so popup blockers allow it.

## The relayed flows docs page

The docs site is Docusaurus with an explicit sidebar; the Flow category under apps lists the lumlflow overview, uploading and the experiment view. A page with the id `apps/lumlflow/relayed_flows` joins the category after the existing pages, in the style of its siblings. The Flow page links to it.

It is written for a user of the platform and explains: what a relayed flow is and when to use it, namely to look into an experiment while it runs inside a job on a cluster or another machine nobody can reach, not to use lumlflow's whole functionality through the relay, even though nothing is blocked; that the orbit needs a relay assigned in orbit settings and that an admin registers one in the relays tab; installing the SDK with the `flow` extra and lumlflow; setting the API key; the flow object in a script and in a notebook, with the block form and the explicit start and stop; what appears on the Flow page; what happens on exit, on a crash and when nobody opens the flow for a long time; and that viewers see exactly what the owner sees. A short section for admins covers what a relay needs to run: the image, the two environment variables, the wildcard DNS record and certificate, TLS in front of the relay, and that the base domain must not share a registered domain with the LUML app.

The page is written in the project's documentation style. It reads like a textbook chapter in a neutral, factual voice: it states what things are and how they work and never sells them, so words such as powerful, elegant, simple, easy, remarkably or importantly do not appear. Sentences are short and direct, one idea each, with no em-dash asides and no nested clauses. The content is continuous prose under a few descriptive, unnumbered headings; there is no introduction that announces what the page covers, no summary at the end, no horizontal rules between sections, and no formulaic subheadings such as "What is X" or "How it works". Lists are kept for genuinely distinct items, kept short, and carry no bold labels. Side information, such as a definition or a rejected alternative, goes in an italic *Note:* line rather than inline. Anything documented elsewhere, such as installing lumlflow or creating an API key, is linked rather than re-explained. Limitations are stated plainly: viewers see everything the owner sees, a crashed run holds its place until the session ends, and a flow nobody opens for a week is ended. Code blocks hold only real commands and real Python; a flow in prose is described in words, and a diagram appears only if it shows something the prose cannot. Tool and library names are formatted in backticks and are current.

## Local development

The dev stack runs the relay as a container with command-line flags, and the backend environment file holds a signing key and the single-relay settings. A seed script creates the dev organization and its sample orbit.

The relay container is configured with the two environment variables, pointing at the backend service, and starts after the seed has completed. The backend environment file drops the signing key and the single-relay settings and gains the dev relay's token, base domain and agent address. The dev seed script registers that relay as the dev organization's own relay with the hash of the token and assigns it to the sample orbit, both only when missing, like the rest of the seed. The base domain under `localhost` and the published ports stay, so sessions are served without DNS or certificates. The dev README names the relay in its table of services.

## Migrations and tests

The branch added one migration for live sessions, and nothing built on it has shipped. Each part is tested the way its neighbours are.

Each backend task rewrites that migration in place rather than adding a migration, so the feature lands as one migration after the current head, and model changes and the migration are kept in step within each task. Developers who applied the old one recreate their dev database, which the dev stack does in one command.

The backend has unit tests for handlers and routes and integration tests for repositories, including the row-locked limit, managed rows and the expiring rows. The tunnel package runs the relay, the agent, a test service and a fake LUML in one process; the fake stores tokens, answers validations, consumes launches, and can be made to refuse, fail or go silent, and the existing forwarding, WebSocket and header tests stay as regression. The API client uses its mocked transport. The SDK tests the flow object with fakes of the flows API and the tunnel's serving step, a stub command in place of lumlflow and a fake local server. The frontend has unit tests beside the new pages and components. The docs page and the dev stack are checked by hand as the tasks describe.

## Trade-offs

Validating through LUML makes the relay depend on LUML for new viewers and agents. The cache, the stale answers and the token lifetime bound that dependency: an outage shorter than a token lifetime drops nothing, and a longer one leaves sessions disconnected until the agent's next renewed token, not ended.

The cache window delays revocation by about a minute, which is accepted for the simplicity of asking LUML. Opaque tokens cost a database write per renewal, about one per session every five minutes, and recording viewer activity costs about one write per active viewer per minute. Both are small while nothing is sized for a fleet.

The viewer-idle rule can end a session that is still wanted but has not been opened for a week. That is accepted because re-exposing is one command and the flow keeps its name, and because the alternative, a forgotten process holding a relay slot forever, has no other remedy without a scheduler.

A relay restart invalidates cookies unless a cookie secret is configured, and a change to a relay's base domain or agent address needs a restart and is refused while the relay has sessions that have not ended. Both are accepted because a relaunch is one click from the Flow page and such changes are rare.

Local flows are shared by everyone who uses the browser, which is accepted because they are only an address. Managed relays exist only as records; how they are provisioned and run is out of scope.

# Scenarios

The scenarios share one setup unless they say otherwise. An organization has an own relay labelled `lab` with the base domain `tunnel.example` and an orbit assigned to it. A managed relay labelled `eu` exists. The limits are 5 sessions through own relays and 0 through managed relays. A session has the identifier `k3f9x2ab` and is served at `k3f9x2ab.tunnel.example`. The owner is the user who started the session. The scenarios are ordered by part: tokens and the relay, relays as records, sessions and limits, flows, the API client and the agent, the SDK, the frontend, docs and the dev stack.

## Scenario: A token is validated by LUML and cached
**Given** a relay configured with the address of LUML and a valid relay token, and a viewer token issued by LUML for a session on that relay
**When** the viewer sends two requests with the token in the header within the cache window
**Then** the relay asks LUML once, serves both requests, and asks again only after the cache window has passed

## Scenario: A refused token is cached too
**Given** a relay whose cache is empty
**When** a viewer sends five requests within the cache window with the same token that LUML does not know
**Then** the relay asks LUML once, answers status 401 to every request, and the service receives no request

## Scenario: LUML is unreachable
**Given** a connected agent and a viewer whose token the relay has validated
**When** LUML becomes unreachable, the viewer keeps sending requests past the cache window, and a second viewer arrives with a token the relay has never seen
**Then** the agent stays connected, the first viewer keeps being served from the stale cache entry, and the second viewer is refused with status 503 and a text that says to try again

## Scenario: An agent meets an unreachable LUML
**Given** a relay that cannot reach LUML
**When** an agent connects with a token the relay has never seen
**Then** the handshake is refused with status 503, the agent retries with growing pauses instead of exiting, and it connects once LUML answers again

## Scenario: An agent waits for a fresh token after an outage
**Given** a connected agent whose token expires during an outage of LUML longer than the token's lifetime
**When** the relay closes the connection at the expiry and LUML becomes reachable again
**Then** the agent makes no connection attempt with the expired token and does not exit, its next answered heartbeat renews the token, and it reconnects with the new one so the session is live again

## Scenario: Claims that do not fit are refused by the relay alone
**Given** a valid `view` token for `k3f9x2ab` that the relay has not seen
**When** an agent connects with it, then a viewer presents it on the hostname of another session, then a viewer presents it on `k3f9x2ab.tunnel.example`, all within the cache window
**Then** LUML is asked once and answers the token's claims, the first two are refused by the relay, and the third is served

## Scenario: Ending a session revokes its viewers and its agent
**Given** a session with a connected agent and a viewer served through a cookie
**When** the owner ends the session at LUML
**Then** within the cache window the viewer's requests are refused, and the agent learns from its next heartbeat that the session has ended and exits

## Scenario: A relay validates only its own sessions
**Given** a `view` token and an `expose` token for a session on `lab`
**When** the relay `eu` asks LUML to validate either, and `lab` asks the same
**Then** LUML answers inactive to `eu` without a reason and active to `lab`

## Scenario: A relay fetches its description from LUML
**Given** a relay process started with only the address of LUML and a relay token, while LUML is still starting
**When** LUML becomes reachable
**Then** the relay has retried, learned its base domain and the app origins, and serves sessions on that base domain

## Scenario: A relay with a refused token exits at startup
**Given** a relay process started with a token LUML does not know
**When** it fetches its description
**Then** LUML answers 401, the relay exits with a message that names the refused token and does not retry, while a relay that cannot reach LUML keeps retrying

## Scenario: A relay token is refused during operation
**Given** a running relay with a connected agent and a cached viewer, whose token was rotated and whose overlap has passed
**When** the relay asks LUML about a token it has never seen, and reports
**Then** both calls are refused, the relay logs an error each time and its health check reports the refused token, the connected agent and the cached viewer keep being served, and new viewers and agents get "try again"

## Scenario: A browser launches and is served through a grant
**Given** a valid `view` token
**When** a browser opens the launch address with it
**Then** LUML consumes the token and the relay sets a cookie that refers to the grant and redirects to the root, and the following requests from that browser are served after one grant check per cache window

## Scenario: A launch token is accepted once
**Given** a `view` token that was first used in the token header, so its claims are cached, and then used at the launch address
**When** the same launch address is opened again, and the token is sent in the header of a request, both inside the cache window
**Then** both are refused, the second launch sets no cookie and shows the access-needed page, and the browser that holds the cookie from the first launch is still served; because the one-time state is at LUML, a second relay process would refuse it too

## Scenario: A grant outlives the view token's lifetime
**Given** a browser that launched with a `view` token ten minutes ago and sent a request a minute ago
**When** it sends another request with the cookie
**Then** it is served, although the token it launched with has passed its five minutes

## Scenario: The cookie ends by idleness and by age
**Given** a browser that holds the relay's cookie for the session
**When** it sends no request for 30 minutes and then navigates to a page, or sends a request every ten minutes until 12 hours have passed since the launch
**Then** in both cases the next navigation gets the access-needed page, decided from the cookie without a call to LUML

## Scenario: Opening a session with a destination
**Given** a valid viewer token issued with the destination `/experiments/42?tab=metrics`
**When** a browser opens the launch address
**Then** the relay sets its cookie and redirects to that path and query on the session's hostname

## Scenario: A destination that is not a relative path is refused
**Given** a live session
**When** the owner asks for viewer access with a destination that is a full address, starts with two slashes, or does not start with a slash
**Then** the request is refused with a validation error and no token is issued

## Scenario: The access-needed page in a top-level tab
**Given** a browser with no cookie
**When** it navigates to a page of the session as a top-level document
**Then** it gets the page that says to open the flow again from the LUML app, with a link to the app address, and no message is posted because there is no parent

## Scenario: Viewer access by header survives
**Given** a valid `view` token and a grant identifier from a launch
**When** a script sends several requests with the token in the token header, and one request with the grant identifier in that header
**Then** the token requests are served and the grant request is refused

## Scenario: The relay reports and is shown online
**Given** a relay that reports every minute with three connected agents
**When** an admin opens the relays tab, and again after the relay has been silent for ten minutes
**Then** the first time the relay is shown online with three agents and a recent last-seen time, and the second time it is shown offline

## Scenario: Agent connections are capped
**Given** a relay with a cap on agent connections that is reached
**When** one more agent connects with a valid token
**Then** the relay refuses it with status 503 and a reason that names the cap, and the connected agents are unaffected

## Scenario: Token renewals are rate limited
**Given** a connected agent
**When** it sends renewal frames far faster than the allowed rate
**Then** the relay stops validating them beyond the rate, and the connection and its streams continue

## Scenario: A flood of unknown tokens is bounded
**Given** a relay with a bound on validations in flight
**When** many requests with distinct unknown tokens arrive at once
**Then** LUML never has more validations open than the bound, and requests that cannot get a slot in time are answered with "try again"

## Scenario: Relay tokens authenticate as relays
**Given** a relay token with the relay prefix and a user API key
**When** each is presented as a bearer token on a relay-facing route and on an organization route
**Then** the relay token is accepted on the relay-facing route with the relay scope and refused on the organization route, and the user API key is refused on the relay-facing route for lack of that scope

## Scenario: The relay token is rotated
**Given** a relay connected with its token
**When** an admin rotates the token, and the relay keeps using the old token for a few minutes before being restarted with the new one
**Then** validations with the old token succeed during the overlap, the new token works at once, and the old token is refused once the overlap has passed

## Scenario: The relay token is rotated twice within the overlap
**Given** a relay whose token was rotated a minute ago, so the first token still works
**When** an admin rotates the token again
**Then** the first token is refused at once, the second token works until its own overlap passes, and the third works at once

## Scenario: An organization registers its own relay
**Given** an organization admin on the relays tab
**When** the admin adds a relay with a label, a base domain and a ws address
**Then** the relay is listed as own, enabled and offline, the token with its prefix is shown once together with the LUML address and the run command, and reading the relay afterwards returns no token or hash

## Scenario: A relay with an invalid address or a taken base domain is refused
**Given** an organization admin
**When** the admin creates a relay with an agent address that is not a ws or wss address, with a base domain that carries a scheme, a port or a trailing dot, or with the base domain `Tunnel.Example`
**Then** each creation is refused with a message naming the problem, and nothing is created

## Scenario: Changing a relay's address with unended sessions is refused
**Given** the own relay `lab` with one disconnected session
**When** an admin changes its label, then its base domain
**Then** the label change succeeds and the base domain change is refused with a message naming the session; after the session has ended the base domain change succeeds

## Scenario: Members may list relays but not change them
**Given** a member of the organization who is not an admin
**When** the member lists relays, then tries to create, update, rotate or remove one
**Then** the list succeeds with managed relays marked, and every other call is refused for lack of permission

## Scenario: A managed relay is read-only for organizations
**Given** the managed relay `eu`
**When** an organization admin tries to update it, rotate its token or remove it
**Then** each call is refused with a message that managed relays are read-only, and the relay stays listed as managed for every organization

## Scenario: Several managed relays coexist
**Given** two managed relay rows with different labels and base domains, one enabled and one draining
**When** an admin of any organization lists relays, opens the orbit relay choice, and starts sessions in orbits assigned to each
**Then** both are listed as managed and read-only, only the enabled one is offered in the choice, the draining one refuses new sessions, and sessions on either count toward the one managed limit

## Scenario: An orbit is assigned a relay
**Given** the own relay `lab`, the managed relay `eu`, and an own relay of another organization
**When** an orbit admin updates an orbit with each of the three, then clears the relay
**Then** the first two assignments succeed, the third answers "not found" and leaves the orbit unchanged, and the cleared orbit has no relay

## Scenario: The orbit dialogs offer relays
**Given** an organization with the own relay `lab` enabled, an own relay `old` draining, and the managed relay `eu` enabled
**When** an admin opens the orbit creator and the orbit editor of an orbit assigned to `old`
**Then** the creator lists `lab` and `eu` by label with `eu` marked as managed and may be left empty, and the editor additionally shows `old` as the current value marked as draining and can be cleared

## Scenario: The relays tab
**Given** an organization owner on the organization settings page
**When** the owner opens the Relays tab, adds a relay, rotates its token, sets it to draining and removes it
**Then** the table lists own and managed relays with kind, status, last seen and connected agents, the token is shown once after adding and once after rotating, managed rows have no menu, and a refused removal shows the backend's message

## Scenario: Removing a relay with unended sessions is refused
**Given** an organization's own relay with one live session and one session silent for five minutes
**When** an admin removes it
**Then** the removal is refused with a message naming two sessions; after the admin sets the relay to draining and both sessions end, the removal succeeds and the orbits that used it have no relay assigned

## Scenario: Removing a relay keeps its ended sessions
**Given** an organization's own relay whose only sessions have ended
**When** an admin removes the relay
**Then** the removal succeeds, the sessions still answer ended and stay listed for their retention, and neither references a relay

## Scenario: A draining relay takes no new sessions
**Given** a relay set to draining with one live session
**When** a user starts a session in an orbit assigned to that relay, and the live session's agent sends a heartbeat and receives a renewed token
**Then** the start is refused with a message that names the relay as draining, and the live session continues with the renewed token

## Scenario: An orbit without a relay
**Given** an orbit with no relay assigned
**When** a user tries to start a session or expose a flow in it
**Then** the start is refused with a message that says to assign a relay in orbit settings, and nothing is created

## Scenario: The organization limit for own relays is reached
**Given** an organization with 5 unended sessions on its own relays, one of them disconnected
**When** a member starts a sixth session on an own relay
**Then** the start is refused with the organization's limit-reached error naming the own-relay limit, and the five sessions are untouched

## Scenario: The managed limit is independent and zero by default
**Given** an orbit assigned to the managed relay `eu`
**When** a member starts a session in that orbit, first with the default managed limit of 0 and again after an operator raises it to 2
**Then** the first start is refused with the limit-reached error naming managed relays although the own-relay limit has free places, and the second succeeds and counts toward the managed limit only

## Scenario: A disconnected session keeps its place in the limit
**Given** an organization at its limit for own relays, one of whose sessions has had no heartbeat for two minutes
**When** a member starts a new session on an own relay, then the owner of the disconnected session ends it and the member tries again
**Then** the first start is refused with the limit-reached error and the second succeeds

## Scenario: Concurrent starts cannot exceed the limit
**Given** an organization one below its own-relay limit
**When** two members start a session each at the same moment, before either agent has sent a heartbeat
**Then** exactly one start succeeds and the other is refused with the limit-reached error

## Scenario: A session keeps its relay when the orbit is reassigned
**Given** a live session on `lab`
**When** the orbit is reassigned to `eu`
**Then** the session still answers viewer access through `lab`, still counts toward the own-relay limit, its agent's heartbeats and renewals continue, and the next session starts on `eu`

## Scenario: The status follows heartbeats and viewer idleness
**Given** a started session
**When** it is read in each of these situations: a heartbeat with a working connection less than 90 seconds ago; the last heartbeat reported no connection; the last heartbeat is more than 90 seconds old; the last heartbeat is more than an hour old; heartbeats are fresh but LUML has seen no viewer activity for longer than the viewer-idle period since the start
**Then** the status is `live`, `disconnected`, `disconnected`, `ended` and `ended`, in that order

## Scenario: A session nobody looks at is ended
**Given** a session whose agent heartbeats every 30 seconds, and no viewer access issued, token validated or grant checked for it for longer than the viewer-idle period since it started
**When** the agent sends its next heartbeat
**Then** the answer says the session has ended and records nothing, the agent exits, the session's tokens are inactive, it counts toward no limit, and its flow disappears from the Flow page

## Scenario: Viewer activity resets the idle clock
**Given** a session started eight days ago whose grant the relay checked yesterday
**When** its status is computed
**Then** the session is not ended by the idle rule

## Scenario: A heartbeat renews the token at LUML
**Given** an agent whose `expose` token is past half its lifetime
**When** it sends a heartbeat and presents the renewed token on its connection
**Then** the answer carries a new opaque token that the relay validates at LUML, the connection stays open past the first token's expiry, the first token is still accepted until its own expiry, and a heartbeat sent well before the expiry carries no token

## Scenario: An ended session gets no credentials
**Given** a session the owner has ended
**When** the agent sends a heartbeat, the owner asks for viewer access, and the relay asks LUML to validate the session's old `expose` token
**Then** the heartbeat answers ended without a token, the viewer access is refused, and the validation answers inactive

## Scenario: Expired tokens are removed on write
**Given** stored tokens whose validity ended an hour ago
**When** any new token is issued
**Then** no plaintext credential exists in the database, the expired rows are gone, and no scheduler was involved

## Scenario: Ended sessions are removed after their retention
**Given** a session ended by its owner two days ago, a session silent for 26 hours, and a session ended ten minutes ago
**When** another session is started in the organization
**Then** the first two rows are gone with their stored tokens and their flows, the third is still listed as ended, and no scheduler was involved

## Scenario: An invisible session answers not found
**Given** a session started by one user with the visibility `owner`
**When** another member of the orbit, who is also an orbit admin, lists sessions, opens that session, asks for viewer access to it, sends a heartbeat for it, or ends it
**Then** the session is absent from the list, the other four calls answer "not found", and no operation accepts another visibility value

## Scenario: A flow is exposed
**Given** a member of the orbit with an API key
**When** the member exposes a flow named `training`
**Then** a flow and a session labelled `training` exist, the flow references the session, the answer carries the flow, the session start answer and the address of the orbit's Flow page, the session start answer alone carries no address in the app, and the session counts toward the own-relay limit

## Scenario: Exposing a flow when the session cannot start
**Given** an organization at its limit for own relays
**When** a member exposes a flow with a new name
**Then** the start is refused with the limit-reached error and no flow is created

## Scenario: A flow is re-exposed under the same name after a crash
**Given** a flow named `training` whose agent died a minute ago, so its session is disconnected
**When** the same user starts a `LiveFlow` with the name `training` in the same orbit
**Then** no second flow is created, the flow gets a new session, the previous session is ended, and the Flow page shows one card named `training` that is live

## Scenario: Re-exposing replaces a running agent
**Given** a flow named `training` with a live session and a running agent
**When** the same user exposes `training` again from another machine
**Then** the flow gets the new session, the first agent learns from its next heartbeat that its session has ended and exits, and the card shows the new session

## Scenario: Re-exposing onto a draining relay leaves the flow alone
**Given** a flow named `training` with a live session, whose orbit's relay has since been set to draining
**When** the same user exposes `training` again
**Then** the expose is refused with the draining message, the running session is not ended, and the card is unchanged

## Scenario: Re-exposing at the limit counts the flow's own session as free
**Given** an organization at its limit for own relays, one of whose sessions belongs to the flow `training`
**When** the same user exposes `training` again
**Then** the expose succeeds, the previous session is ended, and the organization is still at its limit, not over it

## Scenario: Two users share a flow name
**Given** two members of the orbit
**When** each exposes a flow named `training`
**Then** two flows exist, and each user's Flow page shows only their own

## Scenario: A flow is gone when its session ends by silence
**Given** a flow whose session has had no heartbeat for more than an hour
**When** the user lists flows in the orbit, then exposes a flow with the same name
**Then** the flow is not listed, the gone row is deleted on the way, and the new flow is created

## Scenario: Removing a flow ends its session
**Given** a flow with a live session and a connected agent
**When** the creator removes the flow, on the Flow page or through the API
**Then** the flow is deleted, the session is ended, the card disappears, and the agent exits after its next heartbeat; another member who removes it answers "not found"

## Scenario: A flow is seen only through its session
**Given** a flow exposed by one user
**When** another member of the orbit lists flows, reads that flow or removes it
**Then** the flow is absent from the list and the other two calls answer "not found"

## Scenario: A bare session appears nowhere
**Given** an API key in the environment and an orbit with a relay
**When** the user runs `luml-tunnel expose` with a port, the organization, the orbit and a label, then opens the Flow page
**Then** a session with that label starts without a flow, the command prints the session's identifier and public address, a script reaches the service with a `view` token in the header, the session is listed by the sessions API, and the Flow page shows no card for it

## Scenario: The API client covers flows and the changed session operations
**Given** a client with an organization and an orbit
**When** each flow operation and each session operation is called in the synchronous and the asynchronous form
**Then** each call sends the matching request, including the label and the destination where they apply, and returns the answer as a typed object

## Scenario: The API client manages relays
**Given** a client with an organization and an admin's API key
**When** it lists relays, creates one, updates its label, rotates its token, assigns it to an orbit through the orbits resource, clears the assignment and deletes the relay, in the synchronous and the asynchronous form
**Then** each call sends the matching request and returns a typed answer, the plaintext token appears only in the create and rotate answers and never a hash, the list marks the managed relay `eu`, and an update of `eu` surfaces the backend's read-only refusal as an error

## Scenario: LiveFlow in a script
**Given** a script with valid API credentials in the environment, an orbit with a relay, and nothing listening on port 5000
**When** the script enters a `LiveFlow` block, does some work, and leaves the block
**Then** lumlflow is started on the default store, a flow and its session exist while the block runs, the address in the LUML app is printed and returned, and on leaving the block the flow is removed, so the session is ended, and lumlflow is stopped

## Scenario: LiveFlow finds a running lumlflow
**Given** lumlflow already answering on port 5000
**When** a `LiveFlow` block runs and exits
**Then** the running lumlflow is exposed as it is and is still running after the block

## Scenario: LiveFlow meets a port in use
**Given** a server that is not lumlflow answering on port 5000
**When** a `LiveFlow` block is entered
**Then** it raises at once with a message naming the port as in use, does not start lumlflow, and nothing is created at LUML

## Scenario: LiveFlow without lumlflow installed
**Given** nothing listening on the port and no `lumlflow` command on the path
**When** a `LiveFlow` block is entered
**Then** it raises with a message that says to install lumlflow, and nothing is created at LUML

## Scenario: LiveFlow is cleaned up on termination
**Given** a running `LiveFlow` started from the main thread of a script
**When** the process receives a termination signal, or exits through an unhandled error
**Then** the flow is removed at LUML and the lumlflow it started is stopped before the process ends, and the cleanup runs once

## Scenario: LiveFlow in a notebook
**Given** a notebook with valid API credentials in the environment and an orbit with a relay
**When** one cell starts a `LiveFlow` explicitly, a later cell is interrupted by the user, and a later cell stops it
**Then** the flow exists and is live between the first and the last cell, the interruption does not touch it, and it is gone after the last

## Scenario: LiveFlow uses the default name
**Given** a `LiveFlow` built without a name
**When** it starts twice in a row on the same machine, the second time after the first was killed
**Then** both runs expose a flow named after the machine's host name, and the second replaces the first's card

## Scenario: The flow extra gates the module
**Given** the SDK installed without the `flow` extra
**When** the flow module is imported
**Then** the import fails with a message naming the extra, and the rest of the SDK imports as before

## Scenario: The SDK with the flow extra installs beside lumlflow
**Given** the published `luml-api`, `luml-tunnel`, SDK and lumlflow of this work
**When** a user installs the SDK with the `flow` extra and lumlflow into one environment
**Then** the installer resolves the set without a conflict

## Scenario: The Flow page without flows
**Given** a user with no relayed flows in the orbit and no local flows in the browser
**When** the user opens the Flow page
**Then** the page shows the plus card and the header's add button, and either opens the popup with the local and the relayed choice

## Scenario: Several local flows coexist with relayed ones
**Given** a browser with two saved local flows on ports 5000 and 5001 and an orbit with one relayed flow
**When** the user opens the Flow page and adds a third local flow on port 5002, then tries to add port 5000 again
**Then** four cards are shown, the three local ones marked local and the relayed one marked relayed, the fourth add succeeds, and the repeat of port 5000 is refused with a message naming the existing card

## Scenario: A local flow is added
**Given** lumlflow running on the user's machine on port 5000 and the Flow page open in the same browser
**When** the user chooses the local option, enters the address and port, and confirms
**Then** the page checks that lumlflow answers, saves the entry in local storage, and shows a card marked as local that opens lumlflow in a new tab; the card is present on every orbit's Flow page in that browser

## Scenario: A local flow is not reachable
**Given** nothing listening on the entered address and port
**When** the user confirms the local option
**Then** nothing is saved and the message says the address did not answer, noting that only localhost is reliably reachable from the platform page

## Scenario: A local flow goes offline
**Given** a saved local flow whose lumlflow has been stopped
**When** the Flow page loads or refreshes reachability
**Then** the card stays, marked local and shown as not answering right now, and is shown as reachable again once lumlflow is restarted

## Scenario: The relayed choice points to the docs or to orbit settings
**Given** the popup open in an orbit with a relay, and then in an orbit whose details show no relay
**When** the user picks the relayed choice in each
**Then** the first explains that a relayed flow is exposed from the machine where it runs and links to the docs page, and the second says the orbit has no relay and links to the organization's orbits tab

## Scenario: A relayed flow is opened and removed
**Given** a live relayed flow on the Flow page
**When** the user opens it, then removes it and confirms
**Then** a tab opened on the click loads the launch address of its session with a fresh token, and after the removal the card is gone and the session is ended; a disconnected card offers no open action and shows when the last heartbeat arrived

## Scenario: The old session route is gone
**Given** the app after this change
**When** a browser opens the Flow page address followed by a session identifier
**Then** the not-found page is shown, and the sidebar still highlights Flow on the Flow page

## Scenario: The docs page exists and is linked
**Given** the docs site and the Flow page
**When** a user follows the relayed choice's link
**Then** the page under the Flow app pages opens from the sidebar and explains the flow object, assigning a relay to an orbit and running a relay

## Scenario: A flow in the dev stack
**Given** the running dev stack and lumlflow on the developer's machine
**When** the developer runs a script with a `LiveFlow` block against the local backend in the sample orbit
**Then** the seed has registered the dev relay as the dev organization's own and assigned it to the sample orbit, the relay has fetched its description from the local backend, the flow appears as a card on the Flow page of the local app, and it opens in a new tab at a hostname under `localhost` without DNS or certificates

# Tasks

The backend goes first and fixes the routes of the relay-facing API, so the tunnel package's fake can mirror them. The API client and the agent follow, so the tunnel's LUML adapter and its tests track the changed session contracts at once. The relay, the SDK, the dev stack, the frontend and the docs page come after. Between the backend task that stores tokens and the relay task that validates through LUML, the backend issues opaque tokens while the relay still verifies signatures; each package's own tests pass throughout, and a dev stack built from the branch does not work end to end until the dev stack task. The backend tasks rewrite the branch's migration `042` in place, as the Design section Migrations and tests says.

- [x] Add relay records and the organization relay API
  - [x] Add the relay model in `backend/luml/models/` with the fields from the Design section Relay records, the unique normalized base domain, the optional owner organization deleted with it, and the two token hashes with the previous token's end; register it in `backend/luml/models/__init__.py` and rewrite `backend/migrations/versions/042_live_sessions.py` to create it
  - [x] Add the schemas in `backend/luml/schemas/`, with the kind derived from the owner, the online flag computed as `Satellite.status` is in `backend/luml/schemas/satellite.py`, and no hash in any answer; add the repository in `backend/luml/repositories/`: list usable by an organization, read, create, update, rotate with the overlap end, record a report, look up by current or unexpired previous hash, remove
  - [x] Generate and hash relay tokens with the relay prefix as `backend/luml/handlers/satellites.py` does for satellite keys; add the overlap setting to `backend/luml/settings.py`, `backend/.env.example` and `backend/.env.test`
  - [x] Add a relay principal next to `AuthSatellite` in `backend/luml/models/auth.py` and dispatch the prefix in `backend/luml/infra/security.py` to a relay lookup that grants the relay scope
  - [x] Add the relay resource to `backend/luml/schemas/permissions.py` with every action for owners and admins and list and read for members, and to the resource lists in `backend/luml/handlers/permissions.py`
  - [x] Add the handler in `backend/luml/handlers/` with the operations from the Design table, the read-only refusal for managed relays and the conflict for a taken base domain; in this task removal and address changes are plain, since sessions reference relays only from the next task; add the routes in `backend/luml/api/organization/` following `organization_bucket_secrets.py`, registered in `backend/luml/api/organization_routes.py`
  - [x] Add unit tests in `backend/tests/unit/handlers/` and `backend/tests/unit/api/`, a test for the prefix dispatch beside `backend/tests/unit/test_security.py`, and integration tests in `backend/tests/integration/repository/` for the relay operations, the roles, the base domain rules, the rotation overlap including two rotations, and managed rows created without an owner
  - [x] Run ruff, mypy and pytest in `backend/`

- [x] Assign relays to orbits and enforce organization session limits
  - [x] Add the nullable relay reference to `OrbitOrm` in `backend/luml/models/orbit.py`, cleared on relay removal, and to the schemas in `backend/luml/schemas/orbit.py`; accept it on create and update in `backend/luml/handlers/orbits.py`, refusing a relay the organization cannot use the way `_validate_bucket_secret` refuses a foreign bucket secret
  - [x] Add the two limit columns to `OrganizationOrm` in `backend/luml/models/organization.py` with defaults 0 and 5 and to `OrganizationDetails` in `backend/luml/schemas/organization.py`; extend `backend/luml/repositories/limits.py` with the two resources, their usage queries over unended sessions by the owner of their relay, and their messages
  - [x] Replace the session's relay string in `backend/luml/models/live_session.py` with a nullable reference to the relay row; implement the relay removal and address-change rules of the Design section Relay records: refuse while unended sessions exist with the count in the message, otherwise clear the relay reference of the ended sessions
  - [x] Resolve the orbit's relay at session start in `backend/luml/handlers/live_sessions.py` with the refusals from the Design table in Sessions, build the public address from the relay record, reserve the limit slot in the handler and inside the insert in `backend/luml/repositories/live_sessions.py`; remove the three single-relay settings; keep the signing key setting and the not-configured error until the next task, with the tests supplying a key as they do today
  - [x] Update the migration; update `backend/tests/unit/handlers/test_live_sessions.py`, `backend/tests/unit/api/test_orbit_live_sessions.py` and `backend/tests/integration/repository/test_live_sessions.py`, and add a concurrent-start check to `backend/tests/integration/repository/test_concurrency_guards.py`, covering the start refusals, both limits, the disconnected session that keeps its place, the orbit assignment, and relay removal and address changes with live, disconnected and ended sessions
  - [x] Run ruff, mypy and pytest in `backend/`

- [x] Store tunnel tokens at LUML and add the relay-facing API
  - [x] Add the stored token model with the fields from the Design section Stored tunnel tokens, register it and add it to the migration
  - [x] Replace `backend/luml/infra/live_session_tokens.py` with a repository that issues opaque tokens hashed as API keys are, looks them up by hash, launches a `view` token once atomically with the twelve-hour extension, checks grants, and deletes expired rows on every issue and launch as `backend/luml/repositories/monitoring.py` does
  - [x] Issue opaque tokens in `backend/luml/handlers/live_sessions.py` for the start, the heartbeat renewal and viewer access; accept and validate the optional destination with the rule from the Design and store it on the token
  - [x] Remove the signing key setting from the settings and both env files, the not-configured error from `backend/luml/infra/exceptions.py`, and `backend/luml/api/well_known.py` with its registration in `backend/luml/service.py`
  - [x] Add the relay-facing router in `backend/luml/api/`, following `satellites.py` and requiring the relay scope, with describe, validate, check grant and report as in the Design table in The relay-facing API, each scoped to the calling relay, answering verdicts with status 200 and the token's own claims, and recording the viewer activity time on the session
  - [x] Add unit tests for issue, validate, launch once including two concurrent launches, the grant after the token's lifetime, the other relay, the ended session, the destination rule, the viewer activity time and the expiring rows, and route tests for the scope and a refused relay token
  - [x] Run ruff, mypy and pytest in `backend/`

- [x] Make session visibility explicit and end idle sessions
  - [x] Rename the session's name to an optional label in the model, the schemas in `backend/luml/schemas/live_session.py` and the start input, and add the visibility column with its single value and the viewer activity time; update the migration
  - [x] Implement visibility as one function used by list, read, viewer access and heartbeat, with the listing query in `backend/luml/repositories/live_sessions.py` filtering by the same rule; keep ending owner-only in the same place
  - [x] Add the viewer-idle setting with a seven-day default and apply the shared ended rule of the Design section Sessions in the computed status, the listing query, the heartbeat guard, token activity, the limit counts and the relay removal check
  - [x] Delete sessions ended more than 24 hours ago, with an end recorded or implied by the shared rule, whenever a session is started or ended, cascading to their stored tokens and flows
  - [x] Remove the app address from the session start answer
  - [x] Update `backend/tests/unit/test_live_session_status.py` and the handler, route and repository tests for the status table, the idle rule and the activity reset, the invisible session, the label and the removal of ended sessions after their retention
  - [x] Run ruff, mypy and pytest in `backend/`

- [x] Add flows to the backend
  - [x] Add the flow model with orbit, creator, name and required session reference, the unique name per creator and orbit, register it and add it to the migration
  - [x] Add schemas and a repository: delete gone flows, find by name for a creator and orbit, create with its session, point at a new session, list visible flows whose session is not ended with the session summary, read, delete
  - [x] Add the handler implementing expose, list, read and remove as in the Design table in Flows, with the start refusals checked before anything is ended or created and the found flow's own session counted as free, reusing the live session handler for starting and ending sessions and the live session permission resource, and building the Flow page address from `APP_EMAIL_URL`
  - [x] Add the routes in `backend/luml/api/orbits/` next to `orbit_live_sessions.py` and register them in `backend/luml/api/organization_routes.py`
  - [x] Add unit and integration tests for the flow scenarios: exposed, refused with nothing created, re-exposed after a crash, over a running agent, onto a draining relay and at the limit, two users with one name, concurrent exposes of one name, gone by silence, removed, seen only through its session
  - [x] Run ruff, mypy and pytest in `backend/`

- [x] Update the API client for relays, flows and the changed operations
  - [x] Add a relays resource in `sdk/python/api/luml_api/resources/` following `bucket_secrets.py`, with list, get by identifier or label, create, update, rotate token and delete in both forms, the plaintext token only in the create and rotate answers; add its types to `sdk/python/api/luml_api/_types.py` and register it in `sdk/python/api/luml_api/_client.py`
  - [x] Let create and update in `sdk/python/api/luml_api/resources/orbits.py` take the optional relay reference and clear it
  - [x] Change `sdk/python/api/luml_api/resources/live_sessions.py` and the types for the optional label, the destination in viewer access and the start answer without an app address
  - [x] Add a flows resource with expose, list, read and remove in both forms, following `live_sessions.py`, and register it in the client
  - [x] Add a relays test following the bucket secrets resource test, extend the orbits test for the relay reference, update `sdk/python/api/tests/unit/test_live_session_resources.py` and add a flows test following it
  - [x] Run ruff, mypy and pytest in `sdk/python/api/`

- [x] Adapt the agent and the expose command to the changed session contracts
  - [x] Split `tunnel/luml_tunnel/luml.py` into starting a bare session and serving a started session with heartbeats, renewed tokens and the clean end, so the SDK can reuse the second part
  - [x] Never connect with a token known to be expired in `tunnel/luml_tunnel/agent.py`; wait for the heartbeat that renews it, keeping a 400-range handshake refusal fatal
  - [x] Turn the name flag of `luml-tunnel expose` in `tunnel/luml_tunnel/cli.py` into an optional label and print the session's identifier and public address on start
  - [x] Update the fake LUML in `tunnel/tests/test_luml.py` for the changed session contracts, still signing tokens until the next task, and cover the scenarios: the bare session, the renewed token, the agent after an outage, the ended answer
  - [x] Run ruff format, ruff check, mypy and pytest in `tunnel/`

- [x] Validate tunnel tokens through LUML in the relay
  - [x] Remove `tunnel/luml_tunnel/signing.py`, the JWKS verifier in `tunnel/luml_tunnel/verification.py`, the `dev` subcommands in `tunnel/luml_tunnel/cli.py` and the JWT dependency from the relay extra in `tunnel/pyproject.toml`; adjust `tunnel/tests/test_imports.py`
  - [x] Implement the verifier interface in `tunnel/luml_tunnel/tokens.py` with a client of the relay-facing API: claims cached by token as in the Design table in The relay process, fit checked locally, stale answers while LUML cannot answer, a distinct "try again" error, and the error log and health report for a refused relay token, written in the tunnel package after the model of `satellite/kit/luml_satellite/authorization.py` without importing it
  - [x] Configure the relay command from the two environment variables of the Design section The relay process, fetch the description at startup with growing pauses before serving, exit on a refused token, take the base domain and app origins from the description, and remove the replaced command-line options; keep `tunnel/Dockerfile` with its entry point
  - [x] Answer "try again" with status 503 for viewers and for agent handshakes in `tunnel/luml_tunnel/relay.py`
  - [x] Replace the signer fixtures in `tunnel/tests/harness.py` and `tunnel/tests/conftest.py` with an in-process fake of the relay-facing API that mirrors the backend's routes, issues tokens, consumes launches and can refuse, fail or go silent; make the fake LUML in `tunnel/tests/test_luml.py` issue tokens through it; adapt every test to issue tokens through it
  - [x] Rewrite `tunnel/tests/test_tokens.py` and adjust `tunnel/tests/test_cli.py` for the scenarios: validated and cached, refused and cached, LUML unreachable for viewers and agents, claims that do not fit refused by the relay alone, another relay's session, the description fetched with retries, a refused token at startup and during operation
  - [x] Run ruff format, ruff check, mypy and pytest in `tunnel/`

- [x] Move viewer launch and grants to LUML in the relay
  - [x] Launch through the validate operation with the launch flag, bypassing the cache and evicting the token's cached claims on success, remove the in-memory set of used launch tokens from `tunnel/luml_tunnel/relay.py`, and redirect to the destination from the answer or to the root
  - [x] Make the cookie in `tunnel/luml_tunnel/cookies.py` carry what the relay needs to decide the 30-minute idle and 12-hour limits from the cookie alone and to look the grant up, and check the grant through the cache on cookie requests
  - [x] Accept only `view` tokens in the header and only grant references through the cookie
  - [x] Make the access-needed page in `tunnel/luml_tunnel/pages.py` work as a top-level document with a link to the app address from the description, posting its message only when framed
  - [x] Update `tunnel/tests/test_browser_access.py` for the scenarios: launch and grant, launch accepted once including header use after launch inside the cache window, the grant after the token's lifetime, idleness and age, the destination, the access-needed page top-level, viewer access by header survives, viewers revoked when the session ends
  - [x] Run ruff format, ruff check, mypy and pytest in `tunnel/`

- [x] Add relay reporting and hardening bounds
  - [x] Report connected agents to LUML on the report interval, logging and retrying failed reports without affecting serving
  - [x] Add the bounds from the Design table in The relay process as settings of the relay command with defaults documented in its help: the agent connection cap with a 503 refusal naming the cap, the renewal rate per connection with dropped frames in the token expiry watcher, validations in flight, and the cache size with eviction
  - [x] Add tests in `tunnel/tests/test_relay_operation.py` for the cap, the rate, the flood of unknown tokens and the report
  - [x] Run ruff format, ruff check, mypy and pytest in `tunnel/`

- [x] Add LiveFlow to the SDK
  - [x] Add the `flow` extra to `sdk/python/sdk/pyproject.toml` depending on the tunnel package with its LUML extra and on `luml-api`, with local path sources for development as `lumlflow/pyproject.toml` declares them, and the extra's dependencies in the dev group so `.github/workflows/[sdk] tests-and-linters.yml` installs them
  - [x] Widen the `luml-api` and `luml-sdk` pins in `lumlflow/pyproject.toml` to accept the minors this work ships, changing nothing else in lumlflow, and note the publish order from the Design section The flow object in the pull request
  - [x] Add the `luml.flow` module under `sdk/python/sdk/luml/` with `LiveFlow` as the Design section The flow object describes: the defaults, start and stop, the context manager, the background thread with its own loop, the lumlflow probe with the port-in-use failure and the start through the `lumlflow` command, the exit hook and the termination handler only, the printed and kept address
  - [x] Fail clearly when the extra or the `lumlflow` command is missing
  - [x] Add tests in `sdk/python/sdk/tests/` with fakes of the flows API and the tunnel's serving step, a stub command in place of lumlflow and a fake local server: started lumlflow stopped, found lumlflow left running, port in use, missing lumlflow, explicit start and stop, the default name, cleanup on termination, no interruption handler, the gated import
  - [x] Run ruff, mypy and pytest in `sdk/python/sdk/`

- [x] Register the dev relay in the dev stack
  - [x] Configure the relay service in `dev/docker-compose.yml` with the two environment variables pointing at the backend service, drop its old command-line options, and start it after the seed completes
  - [x] Replace the signing key and single-relay settings in `dev/backend.env` with the dev relay's token, base domain and agent address
  - [x] Extend `dev/seed.py` to register the relay as the dev organization's own with the hash of the token and assign it to the sample orbit, both only when missing
  - [x] Name the relay in the services table of `dev/README.md`, check the compose file with `docker compose config`, run the stack and walk through the scenario for a flow in the dev stack

- [x] Add a relays tab to organization settings
  - [x] Add a relays API module in `frontend/src/lib/api/` following `bucket-secrets/`, register it in `frontend/src/lib/api/api.ts`, and add a store in `frontend/src/stores/` following `buckets.ts`
  - [x] Add the child route in `frontend/src/router/index.ts` and the tab in `frontend/src/components/organizations/OrganizationTabs.vue`, named like the buckets route and tab
  - [x] Build the tab under `frontend/src/components/organizations/` following `registry/OrganizationRegistry.vue` and `registry/OrganizationRegistryTable.vue`, with the columns and menus from the Design section Organization settings: the relays tab
  - [x] Build the create dialog, the token dialog following `frontend/src/components/satellites/SatellitesApiKeyModal.vue` with the environment variables and the run command, and the settings dialog following `registry/BucketSettings.vue` with edit, status toggle, rotate and remove
  - [x] Add unit tests beside the components for the list with managed and own rows, the add dialog, the token shown once, rotation and a refused removal shown with its message
  - [x] Run the type check, the linter and the unit tests in `frontend/`

- [x] Add the relay choice to the orbit dialogs
  - [x] Add the nullable relay reference to the orbit interfaces and payloads in `frontend/src/lib/api/api.interfaces.ts` and the two limits to the organization interface
  - [x] Add the relay select under the bucket select in `frontend/src/components/orbits/creator/OrbitCreator.vue` and `frontend/src/components/orbits/editor/OrbitEditor.vue`: enabled relays by label from the relays store, managed ones marked, may be left empty, clearable in the editor, the current draining relay shown marked, a hint pointing to the relays tab when there is none
  - [x] Extend `frontend/src/components/orbits/creator/OrbitCreator.test.ts` and `frontend/src/components/orbits/editor/OrbitEditor.test.ts` for the scenario about the orbit dialogs
  - [x] Run the type check, the linter and the unit tests in `frontend/`

- [ ] Rebuild the Flow page with flow cards
  - [ ] Add a flows API module in `frontend/src/lib/api/` and a store in `frontend/src/stores/` following `satellites.ts`; add a local flows store over one key in `frontend/src/utils/services/LocalStorageService.ts` that reads neither orbit nor user; keep `frontend/src/lib/api/live-sessions/` for viewer access and remove `frontend/src/stores/live-sessions.ts` with its test, since nothing lists sessions any more
  - [ ] Remove `frontend/src/pages/orbits/OrbitFlowSessionView.vue` and its test, its route in `frontend/src/router/index.ts`, its entries in `frontend/src/constants/orbit-navigation.ts` and `frontend/src/components/layout/LayoutSidebar.vue`, and the expose commands in `frontend/src/components/flow/flow-commands.ts`; point the Flow tab of `frontend/src/pages/orbits/SetupPage.vue` to the docs page
  - [ ] Rebuild `frontend/src/pages/orbits/OrbitFlowView.vue` after `frontend/src/pages/orbits/OrbitSatellitesView.vue`: header with add button, skeletons, card grid, `frontend/src/components/ui/UiCardAdd.vue` when empty, periodic refresh
  - [ ] Add the components under `frontend/src/components/flow/` following `frontend/src/components/satellites/SatellitesCard.vue`: the local card with its mark and reachability, the relayed card with the session state, the add popup with the local form and its reachability check and the relayed choice linking to the docs page or to the organization's orbits tab
  - [ ] Open flows in a new tab with the tab opened on the click, and remove flows as the Design section The Flow page describes
  - [ ] Rewrite `frontend/src/pages/orbits/__tests__/OrbitFlowView.test.ts`, update `frontend/src/router/__tests__/flow-routes.test.ts`, `frontend/src/components/layout/__tests__/LayoutSidebar.test.ts` and `frontend/src/pages/orbits/__tests__/SetupPage.test.ts`, and add tests for the empty page, the local flow added, not reachable and offline, the relayed choice with and without a relay, opening and removing a relayed flow, and the old route gone
  - [ ] Run the type check, the linter and the unit tests in `frontend/`

- [ ] Document relayed flows
  - [ ] Write `docs/docs/apps/lumlflow/relayed_flows.md` with the content and in the style of the Design section The relayed flows docs page, with the front matter of `docs/docs/apps/lumlflow/uploading.md`
  - [ ] Read the page once against the style paragraph of that section and remove every sentence that can go without losing meaning
  - [ ] Add the page to the Flow category in `docs/sidebars.ts` after the existing pages
