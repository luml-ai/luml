# Proposals

## Services that cannot be reached today

Some LUML services run in places that accept no incoming connections. A training job runs in a cluster pod. A satellite runs inside a customer network. Both can open connections to the outside, but nothing outside can open a connection to them.

lumlflow is the experiment tracking interface. It runs on the same machine as the training script and is opened in a browser on that machine. A finished experiment can be uploaded to a collection, where the whole team can see it.

This leaves two problems.

- A run in progress can be watched only from the machine it runs on. To follow it from anywhere else, the user needs access to the cluster, or the job needs its own public address.
- There is no shared way to reach a service that can only connect outward. Each feature that needs one has to solve it again. The satellite monitoring dashboard is an example: it can be opened only when the satellite publishes an address that browsers can load.

*Note:* An earlier plan for live experiment tracking (LM-764) described a tunnel made for lumlflow, with its first relay on Cloudflare. This spec replaces that starting point.

## A reverse tunnel with three parts

The agent is a small program that runs next to the service. It opens one outgoing connection to the relay and keeps it open.

The relay has an address that others can reach. When a request arrives for a service, the relay sends it down the agent's connection. The agent hands it to the service, and the response travels back the same way.

The issuer signs tokens. One kind of token allows an agent to expose a service. Another kind allows someone to view it. The relay checks each token against the issuer's public key and needs no other contact with the issuer.

A session is one exposed service, for as long as its agent stays connected.

The tunnel carries requests and responses without reading them. It knows nothing about the service behind it, so any web app can be exposed without being changed.

## What the proof of concept delivers

A user starts the agent next to a running web app. The app then appears as a live session on the Flow page of the LUML app, inside the orbit the user chose. The user opens it there, in a separate browser tab, or from a script.

The LUML backend is the issuer. It keeps the session records and decides who may view a session. For now that is only the user who started it.

Every part can be self-hosted. The relay is one container, and no hosted service is involved.

The interfaces between the parts are fixed by this work: the protocol between agent and relay, the content of the tokens, and the way a viewer addresses a session. A relay on a hosted platform can later be added beside the self-hosted one without changing the agent or the backend.

## Why build it this way

Existing tunnel tools were considered. They ship as separate programs, which would have to be added to every training image, while an agent written as a Python library installs with the rest of the job's dependencies. Their access rules have no notion of LUML membership. The hosted ones send customer traffic through a third party.

Starting with a relay on Cloudflare was considered. It would shape the protocol around one platform's limits before the protocol is proven. It cannot be self-hosted, which customers with data residency rules require. It is also harder to run in local development and in tests.

A tunnel made for lumlflow was considered. A relay that knows lumlflow's routes has to change whenever lumlflow changes, and it cannot serve anything else. Rules about what a viewer may do belong to the service, which knows its own routes.

One shared hostname for all sessions was considered. An unchanged web app uses absolute paths, its own cookies and its own browser storage, so it works only when it has a hostname to itself. Giving each session its own hostname also lets the browser keep sessions apart by its normal rules.

## Outside this spec

These are built later and are not part of the proof of concept.

- Live mode in the SDK, and the upload of the final experiment when a job ends.
- Changes to lumlflow.
- Sharing a session with other members of the orbit.
- Relays that an organization registers and configures itself.
- Caps on the number of sessions, and usage metering.
- A relay on Cloudflare or any other hosted platform.
- More than one relay instance behind the same address.

# Design

## Parts and where they live

The tunnel is a new package. The backend, the API client and the frontend each gain one feature that follows a feature they already have.

| Part | Where | Follows |
|---|---|---|
| Agent and relay | a new top-level `tunnel/` directory | the satellite kit's layout, tooling and checks |
| Issuer and session records | `backend/` | the satellites feature |
| Client for the session operations | `sdk/python/api/` | the satellites resource |
| Flow page | `frontend/` | the satellites page and the monitoring page |

lumlflow and the SDK are not changed.

## The tunnel package

The package is published as `luml-tunnel` and imported as `luml_tunnel`. It supports Python 3.12 and later. That is the SDK's floor, and the agent runs inside the same training images.

It installs one command, `luml-tunnel`. `luml-tunnel expose` runs the agent and `luml-tunnel relay` runs the relay.

The agent has to stay small to install. It needs a WebSocket client and an HTTP client. The relay's web server sits behind an optional extra, and so does registration with LUML, which depends on `luml-api`.

The package works without LUML. A development command creates a key pair and signs tokens, and the agent accepts a relay address and a token directly. The package's own tests rely on this.

Five things inside the package are interfaces, each with one implementation in this work.

| Interface | Implementation in this work |
|---|---|
| Where the agent sends a request | a port on the loopback address |
| Where the agent gets its token | LUML, or a fixed token |
| How the relay checks a token | the issuer's published keys |
| How the relay finds the session for a request | the hostname |
| Where the relay keeps connected agents | memory |

The names and shapes of these interfaces are left to the implementer.

## Session addresses

A relay is configured with a base domain. Each session is served at its own hostname, made of the session identifier followed by the base domain.

The issuer chooses the session identifier. It is random and consists of lower-case letters and digits, so it is valid as part of a hostname and is never reused.

The relay's own endpoints live on the base domain itself. These are the address agents connect to and a health check.

On a session's hostname, every path that starts with `/.luml-tunnel/` belongs to the relay and is never forwarded to the service.

Running a relay therefore has two requirements.

- A wildcard DNS record and a wildcard certificate for the base domain.
- A base domain that does not share a registered domain with the LUML app. A page served through the tunnel could otherwise set cookies that the LUML app receives.

## Protocol between agent and relay

The agent opens one WebSocket connection to the relay and presents its token. The protocol version is agreed through the WebSocket subprotocol, named `luml-tunnel.v1`.

The relay opens one stream for each request it receives for the session. A stream is either an HTTP request with its response, or a WebSocket connection. Bodies are streamed in both directions and are never held in memory as a whole.

Each stream has a credit window. A sender stops when the window is used up and continues when the receiver grants more. This bounds memory on both sides and keeps one slow viewer from blocking the others.

The connection is kept alive by WebSocket pings. The relay never sends anything else to an idle agent, so a later relay that sleeps between requests remains possible.

Further rules:

- Only the relay opens streams.
- The relay announces its limits when the agent connects.
- The agent can present a renewed token on the open connection. The relay closes a connection whose token has expired.
- The relay can ask the agent to reconnect, which it does before a restart.
- A peer ignores frame types it does not know, so frames can be added within a version.

The byte layout of the frames is left to the implementer. It becomes part of the contract once chosen.

## Tokens

Tokens are signed JWTs with the ES256 algorithm. The relay reads the issuer's public keys from an address or from a local file. It keeps them cached and reads them again when it meets a key it does not know.

There are two kinds, `expose` and `view`. A token states its issuer, the relay it is for, the session, its kind, the user and its expiry. The relay refuses a token when any of these does not fit the request, and it never accepts one kind in place of the other.

| Kind | Held by | Lifetime | Renewal |
|---|---|---|---|
| `expose` | the agent | ten minutes | through the agent's heartbeat |
| `view` | the viewer | five minutes | a new one is requested |

The lifetimes are issuer settings with these defaults.

## How a viewer reaches a session

A viewer reaches a session in one of three ways. All three end at the same hostname and differ only in how access is proven.

| Way | How access is proven | Typical use |
|---|---|---|
| From a script | the `view` token in the `X-Luml-Tunnel-Token` header of every request | tests, other services |
| In a browser tab | the launch address, which exchanges the token for a cookie | "open in new tab" |
| Inside the LUML app | the same launch address, loaded in a frame | the Flow page |

The launch address is `/.luml-tunnel/launch` on the session's hostname, with the token as a query parameter. The relay checks the token, sets a cookie and redirects to the root of the service. It accepts each token at this address once.

The cookie is signed by the relay and bound to one session and one user. It follows the rules of the monitoring dashboard's session: it ends after 30 minutes without requests and after 12 hours in any case. It is marked so that browsers send it inside a frame on another site.

*Note:* The token travels in its own header because a service may use the `Authorization` header itself.

Further rules:

- A request authenticated by cookie is accepted only when it comes from the session's own pages or is a plain navigation. Requests started by other sites are refused.
- Without valid access, a page navigation gets a relay page that says access is needed. Any other request gets status 401.
- When the cookie ends while the session is shown in the LUML app, the relay page tells the embedding page, which requests a new token and loads the frame again.

## What the relay and the agent change in a request and a response

The tunnel forwards bodies untouched. It changes a small, fixed set of headers.

On the way in, the relay removes its own cookie and token, so the service never sees them. It adds the usual forwarding headers and the viewer's user identifier in `X-Luml-Tunnel-User`. It removes that header when a viewer sends it.

On the way out, the relay removes the service's restrictions on being shown in a frame and sets its own, which allow only the origins configured as the LUML app. With no origin configured, framing is forbidden. It also removes the domain from cookies the service sets, so they stay on the session's hostname.

The agent keeps the public hostname in the request by default. An option makes it present the loopback address instead, for services that refuse an unexpected hostname.

The agent only ever connects to the loopback address. There is no option for another host, so the agent cannot be used to reach other machines in the cluster.

## Relay operation

The relay is one process in one container. It keeps connected agents in memory, so only one instance can serve a base domain.

It serves plain HTTP. TLS ends at whatever sits in front of it.

| Situation | Behavior |
|---|---|
| A second agent connects for the same session | the new connection replaces the old one |
| A request arrives for a session with no connected agent | status 502 and a relay page that says the session is not connected |
| The service behind the agent does not answer | status 502 from the agent, and the tunnel stays open |
| The relay restarts | agents reconnect on their own, with growing pauses between attempts |

The relay enforces limits on concurrent streams, request body size and idle time. They are settings, and the defaults are left to the implementer.

## LUML backend as issuer

The backend gains a signing key and the description of one relay: its identifier, its base domain and the address agents connect to. These are deployment settings. When they are absent the feature is off, and starting a session fails with a message that says so.

The backend publishes its public keys without authentication at `/.well-known/jwks.json`. Each key carries an identifier, so keys can be replaced later.

*Note:* All signing in the backend today uses one shared secret. The relay must not hold a secret that can sign, so this is the first use of a key pair.

A live session record holds the session identifier, the orbit, the user who started it, a name, the relay identifier, the time it started, the time of the last heartbeat, whether the agent reported a working connection, and the time it ended. The relay identifier is stored so that relays registered by organizations can be added later.

The status is computed when a session is read, as the satellite status is. The backend has no scheduler.

| Status | Meaning |
|---|---|
| `live` | the last heartbeat is recent and the agent reported a working connection |
| `disconnected` | no heartbeat for 90 seconds, or the agent reported no connection |
| `ended` | the session was ended, or no heartbeat arrived for one hour |

Ended sessions stay in the list for 24 hours.

The operations sit under the orbit, next to the satellites operations, and accept a signed-in user or an API key.

| Operation | Who may call it |
|---|---|
| Start a session | any member of the orbit |
| Send a heartbeat | the user who started the session |
| List sessions, read one | the user who started them |
| Issue a `view` token | the user who started the session |
| End a session | the user who started the session |

Starting a session returns the session identifier, its public address, its address in the LUML app, the address the agent connects to, an `expose` token and the heartbeat interval, which is 30 seconds. The address in the LUML app is built from the app address the backend already uses for links in emails.

A heartbeat reports whether the agent's connection works. The answer carries a renewed token when the current one is about to expire, and it says when the session has been ended.

Once a session is ended, the backend issues no further tokens for it. The agent learns this from its next heartbeat and exits. An agent that ignores it loses its connection when its token expires.

Live sessions become a resource in the permission tables, so the frontend can ask what a role may do. The rule that only the starting user sees a session is checked in one place, because it is expected to become configurable.

## The agent command

`luml-tunnel expose` takes the port of the local service, a name for the session, and the organization and orbit. It reads the API key and the address of LUML from the environment variables the API client already uses.

The agent starts a session, connects to the relay, and prints the address of the session in the LUML app. It then sends heartbeats until it stops.

| Event | Behavior |
|---|---|
| The connection to the relay drops | the agent reconnects, and reports the state in its heartbeats |
| LUML cannot be reached for a heartbeat | the agent keeps the tunnel open and retries |
| The user interrupts the agent, or it receives a termination signal | the agent ends the session at LUML and exits |
| LUML reports the session as ended | the agent exits |
| The API key is missing or refused | the agent exits with a message that names the cause |

## The API client

`luml-api` gains a live sessions resource with the operations listed above. It follows the satellites resource and has a synchronous and an asynchronous form.

## The Flow page

Today the Flow entry in the sidebar opens a static page with instructions for running lumlflow locally. The page belongs to no organization or orbit and needs no sign-in.

The page becomes part of an orbit and requires sign-in. The sidebar entry stays where it is and keeps its name. The old address is removed.

The list is at `/organization/<organization>/orbit/<orbit>/flow`. A session is at the same address followed by the session identifier. The backend builds this address when a session starts, so both sides have to agree on it.

The page lists the user's sessions in the orbit with name, start time and status. With no sessions, it shows the existing instructions and, next to them, how to expose a running service.

Opening a session shows it in a frame that fills the page. The frame loads the launch address with a new `view` token. Two actions sit above the frame: open in a new tab, and stop the session.

| State | What the user sees |
|---|---|
| `live` | the session in the frame |
| `disconnected` | a notice with the time of the last heartbeat, and no frame |
| `ended` | a notice, and no frame |
| The feature is off in this deployment | a notice in place of the list |

Browsers that block cookies in frames from other sites cannot show the embedded view. "Open in new tab" works in every browser and is offered in that case.

## Local development

The relay joins the development stack in `dev/`. Browsers resolve every name under `localhost` to the local machine, so session hostnames work there without DNS or certificates.

## Tests

Each part is tested the way its neighbours are. The tunnel package runs the relay, the agent and a small test service in one process, without containers. The backend has unit tests for handlers and routes and integration tests for the repository. The frontend has unit tests for the new pages.

# Scenarios

The scenarios share one setup. A relay has the base domain `tunnel.example`. A session has the identifier `k3f9x2ab` and is served at `k3f9x2ab.tunnel.example`. The service is a small web app on a loopback port. The starting user is the user who started the session.

They are ordered by part: tokens, forwarding, relay operation, viewer access, headers, backend, agent command, API client, Flow page, local development.

## Scenario: The package works without LUML
**Given** a key pair created by the development command, a relay that reads the public key from a local file, and an `expose` and a `view` token for the session signed by the same command
**When** the agent is started with the relay address and the `expose` token, and a script requests `/` on the session's hostname with the `view` token in the `X-Luml-Tunnel-Token` header
**Then** the script receives the response of the service

## Scenario: A token that does not fit is refused
**Given** a relay that knows the issuer's public keys
**When** an agent connects, or a viewer sends a request, with a token that is one of these
- signed by a key the issuer does not publish
- issued by another issuer
- made for another relay
- made for another session
- expired

**Then** the relay refuses the agent's connection, and answers the viewer's request with status 401

## Scenario: One kind of token is never accepted as the other
**Given** a valid `expose` token and a valid `view` token for the same session
**When** an agent connects with the `view` token, and a viewer sends a request with the `expose` token
**Then** the relay refuses both

## Scenario: The relay learns a new issuer key
**Given** a relay that has cached the issuer's keys, and an issuer that then publishes a second key
**When** a token signed with the second key arrives
**Then** the relay reads the issuer's keys again and accepts the token

## Scenario: A request and its response pass through the tunnel
**Given** a connected agent
**When** a viewer sends a `POST` with a query string, its own headers and a body to a path on the session's hostname
**Then** the service receives the same method, path, query string, headers and body, and the viewer receives the status, headers and body the service returned

## Scenario: A large body does not block other viewers
**Given** a connected agent and a service that returns a body many times larger than the credit window
**When** one viewer reads that body slowly, and a second viewer requests a small page from the same session
**Then** the agent stops sending the large body when its window is used up, and the second viewer receives the page while the first download is still running

## Scenario: A WebSocket connection passes through the tunnel
**Given** a connected agent and a service with a WebSocket endpoint
**When** a viewer opens a WebSocket connection to that endpoint on the session's hostname, and both sides send messages
**Then** each side receives the other's messages in order, and closing on one side closes the other

## Scenario: An unknown frame type is ignored
**Given** an open connection between agent and relay with a running stream
**When** one peer sends a frame of a type the other does not know
**Then** the connection stays open and the running stream completes

## Scenario: An agent with another protocol version is refused
**Given** an agent that offers only a subprotocol other than `luml-tunnel.v1`
**When** it connects to the relay
**Then** the relay refuses the connection

## Scenario: Relay paths are not forwarded
**Given** a connected agent and a service that answers every path
**When** a viewer requests a path that starts with `/.luml-tunnel/` on the session's hostname
**Then** the relay answers, and the service receives no request

## Scenario: The agent reaches only the loopback address
**Given** the `luml-tunnel expose` command
**When** it is given a host together with the port
**Then** it exits with a usage error, because it accepts only a port

## Scenario: The service sees the public hostname unless told otherwise
**Given** a connected agent
**When** a viewer requests a page, first with the agent's default settings and then with the option that presents the loopback address
**Then** the service sees `k3f9x2ab.tunnel.example` as the host in the first case and the loopback address in the second

## Scenario: A session without a connected agent
**Given** no agent is connected for the session
**When** a viewer with valid access requests a page
**Then** the viewer receives status 502 and the relay page that says the session is not connected

## Scenario: The service does not answer
**Given** a connected agent and nothing listening on the service's port
**When** a viewer requests a page
**Then** the viewer receives status 502, the agent's connection stays open, and a request made after the service has started succeeds

## Scenario: A second agent replaces the first
**Given** an agent connected for the session
**When** a second agent connects with a valid `expose` token for the same session
**Then** the relay closes the first connection, and new requests reach the service behind the second agent

## Scenario: The relay restarts
**Given** a connected agent
**When** the relay asks the agent to reconnect and then restarts
**Then** the agent reconnects on its own, with growing pauses between failed attempts, and the session is served again

## Scenario: A token expires on an open connection
**Given** a connected agent whose `expose` token expires in one minute
**When** the agent presents no renewed token
**Then** the relay closes the connection when the token expires

## Scenario: A renewed token keeps the connection open
**Given** a connected agent whose `expose` token expires in one minute
**When** the agent presents a renewed token on the open connection before that
**Then** the connection stays open after the first token has expired

## Scenario: A request over a limit is refused
**Given** a relay with limits on request body size, concurrent streams and idle time
**When** a viewer sends a body over the size limit, opens more streams than allowed, or leaves a stream idle for longer than the idle time
**Then** the relay refuses or closes that stream, and the other streams of the session continue

## Scenario: A script reaches a session with the token header
**Given** a valid `view` token
**When** a script sends several requests, each with the token in the `X-Luml-Tunnel-Token` header
**Then** each request is served

## Scenario: A browser tab opens a session through the launch address
**Given** a valid `view` token
**When** a browser opens `/.luml-tunnel/launch` on the session's hostname with the token as a query parameter
**Then** the relay sets its cookie and redirects to `/`, and the following requests from that browser are served without the token

## Scenario: A launch token is accepted once
**Given** a `view` token that has already been used at the launch address
**When** the same launch address is opened again
**Then** the relay refuses it and sets no cookie

## Scenario: The cookie ends after 30 minutes without requests
**Given** a browser that holds the relay's cookie for the session
**When** it sends no request for 30 minutes and then navigates to a page of the session
**Then** it gets the relay page that says access is needed

## Scenario: The cookie ends after 12 hours in any case
**Given** a browser that holds the relay's cookie and sends a request every ten minutes
**When** 12 hours have passed since the launch
**Then** the next navigation gets the relay page that says access is needed

## Scenario: A cookie is valid for one session only
**Given** a cookie the relay issued for the session `k3f9x2ab`
**When** it is presented on the hostname of another session
**Then** the relay refuses the request

## Scenario: Requests started by other sites are refused
**Given** a browser that holds a valid cookie for the session
**When** a page on another site sends a request to the session's hostname, as a form post or from a script
**Then** the relay refuses it, while a plain navigation to the session and requests from the session's own pages are served

## Scenario: A request without access
**Given** a viewer with no token and no cookie
**When** the viewer navigates to a page of the session, and when a script requests the same address
**Then** the navigation gets the relay page that says access is needed, and the script gets status 401

## Scenario: What the service sees of the viewer
**Given** a viewer whose token names the user `U`, and who sends an `X-Luml-Tunnel-User` header with another value
**When** the request is forwarded
**Then** the service receives the usual forwarding headers and `X-Luml-Tunnel-User` with `U`, and it receives neither the viewer's value, nor the relay's cookie, nor the token

## Scenario: Framing is limited to the LUML app
**Given** a service whose responses forbid being shown in a frame
**When** a viewer loads a page through a relay configured with the origin of the LUML app, and through a relay with no origin configured
**Then** the first response allows framing by that origin only and carries none of the service's restrictions, and the second forbids framing

## Scenario: Cookies of the service stay on the session's hostname
**Given** a service that sets a cookie with a domain
**When** the response passes through the relay
**Then** the cookie reaches the browser without the domain

## Scenario: A member starts a session
**Given** a deployment with a signing key and a relay description, and a member of an orbit with an API key
**When** the member starts a session named `training run`
**Then** the answer carries the session identifier, its public address, its address in the LUML app, the address the agent connects to, an `expose` token that lasts ten minutes, and a heartbeat interval of 30 seconds
**And** the identifier consists of lower-case letters and digits only

## Scenario: Starting a session when the feature is off
**Given** a deployment without a signing key or without a relay description
**When** a member starts a session
**Then** the operation fails with a message that says live sessions are not set up in this deployment, and no record is created

## Scenario: Someone outside the orbit cannot start a session
**Given** a user who is not a member of the orbit
**When** the user starts a session in it
**Then** the operation is refused for lack of permission, and no record is created

## Scenario: The status follows the heartbeats
**Given** a started session
**When** it is read in each of these situations
- a heartbeat that reported a working connection arrived less than 90 seconds ago
- the last heartbeat reported no connection
- the last heartbeat arrived more than 90 seconds ago
- the last heartbeat arrived more than one hour ago

**Then** the status is `live`, `disconnected`, `disconnected` and `ended`, in that order

## Scenario: A heartbeat renews the token
**Given** an agent whose `expose` token is about to expire
**When** it sends a heartbeat
**Then** the answer carries a new `expose` token for the same session
**And** a heartbeat sent well before the expiry carries none

## Scenario: An ended session gets no tokens
**Given** a session that the starting user has ended
**When** the agent sends a heartbeat, and the user asks for a `view` token
**Then** the heartbeat answer says that the session has ended and carries no token, and the request for a `view` token is refused

## Scenario: A session that was silent for an hour cannot return
**Given** a session whose last heartbeat arrived more than one hour ago
**When** the agent sends a heartbeat
**Then** the answer says that the session has ended

## Scenario: Only the starting user sees a session
**Given** a session started by one member, and a second user who is an admin of the same orbit
**When** the second user lists the sessions, reads the session, sends a heartbeat, asks for a `view` token, or ends the session
**Then** the list does not contain the session, and every other operation answers that the session is not found

## Scenario: A view token fits one viewer and one session
**Given** a live session
**When** the starting user asks for a `view` token
**Then** the token is of the kind `view`, names the session, the relay and the user, and lasts five minutes

## Scenario: Ended sessions leave the list after 24 hours
**Given** one session that ended 23 hours ago and one that ended 25 hours ago
**When** the starting user lists the sessions
**Then** the list contains the first and not the second

## Scenario: The public keys are published
**Given** a deployment with a signing key
**When** someone who is not signed in requests `/.well-known/jwks.json`
**Then** the answer lists the public keys, each with an identifier, and a token issued by the backend passes a check against them

## Scenario: A user exposes a service through LUML
**Given** an API key and the address of LUML in the environment, and a web app on port 5000
**When** the user runs `luml-tunnel expose` with the port, a name, the organization and the orbit
**Then** the agent starts a session, connects to the relay and prints the address of the session in the LUML app
**And** the session is `live` after the first heartbeat

## Scenario: The connection to the relay drops
**Given** a running agent with a `live` session
**When** the connection to the relay drops and returns a few minutes later
**Then** the agent reconnects on its own, its heartbeats report no connection in between, and the session shows `disconnected` and then `live` again

## Scenario: LUML cannot be reached for a heartbeat
**Given** a running agent with a connected tunnel
**When** LUML does not answer a heartbeat
**Then** the tunnel stays open, viewers with valid access are still served, and the agent tries the heartbeat again

## Scenario: The user stops the agent
**Given** a running agent
**When** the user interrupts it, or it receives a termination signal
**Then** the agent ends the session at LUML and exits, and the session shows `ended`

## Scenario: The session is ended elsewhere
**Given** a running agent
**When** the starting user stops the session on the Flow page
**Then** the agent learns it from its next heartbeat and exits

## Scenario: The API key is missing or refused
**Given** no API key in the environment, or one that LUML refuses
**When** the user runs `luml-tunnel expose`
**Then** the agent exits with a message that names the cause, and no session is started

## Scenario: The API client covers the session operations
**Given** a client with an organization and an orbit
**When** each session operation is called, in the synchronous and in the asynchronous form
**Then** each call sends the matching request and returns the answer as a typed object

## Scenario: The Flow entry opens the page of the current orbit
**Given** a signed-in user with a current orbit
**When** the user selects Flow in the sidebar
**Then** the Flow page of that orbit opens

## Scenario: Flow without sign-in
**Given** a user who is not signed in
**When** the user selects Flow in the sidebar
**Then** the user is sent to the setup page, as for the other orbit pages, and sees the instructions for running lumlflow locally

## Scenario: The old address is gone
**Given** the app after this change
**When** a browser opens `/flow`
**Then** the not-found page is shown

## Scenario: The Flow page lists the user's sessions
**Given** a user with one `live` and one `ended` session in the orbit, and a session of another member in the same orbit
**When** the user opens the Flow page
**Then** the list shows the user's two sessions with name, start time and status, and not the other member's session

## Scenario: The Flow page without sessions
**Given** a user with no sessions in the orbit
**When** the user opens the Flow page
**Then** the page shows the instructions for running lumlflow locally and, next to them, how to expose a running service

## Scenario: The Flow page when the feature is off
**Given** a deployment without a signing key or without a relay description
**When** a user opens the Flow page
**Then** a notice says that live sessions are not set up in this deployment, in place of the list

## Scenario: Opening a live session
**Given** a `live` session in the list
**When** the user opens it
**Then** the page requests a new `view` token and shows the session in a frame that loads the launch address, with the actions to open in a new tab and to stop the session above it

## Scenario: Opening a session in a new tab
**Given** an open `live` session
**When** the user chooses to open it in a new tab
**Then** the page requests another `view` token, and the new tab loads the launch address with it

## Scenario: Stopping a session from the page
**Given** an open `live` session
**When** the user stops it
**Then** the session is ended at the backend, the frame is removed, and the page shows the notice for an ended session

## Scenario: A session that is not live
**Given** a `disconnected` session and an `ended` session
**When** the user opens each of them
**Then** the first shows a notice with the time of the last heartbeat, the second shows a notice that it has ended, and neither shows a frame

## Scenario: The cookie ends while the session is embedded
**Given** a session shown in the frame
**When** the relay's cookie ends, and the relay page in the frame tells the embedding page
**Then** the page requests a new `view` token and loads the frame again, without an action by the user

## Scenario: The browser does not keep the cookie in a frame
**Given** a browser that blocks cookies in frames from other sites
**When** the user opens a `live` session, and the frame reports missing access again right after a new launch
**Then** the page stops loading the frame again and shows a notice that offers to open the session in a new tab

## Scenario: A session in the dev stack
**Given** the running dev stack, and a web app on the developer's machine
**When** the developer runs `luml-tunnel expose` against the local backend
**Then** the session appears on the Flow page of the local app and opens in the frame, at a hostname under `localhost`, without DNS or certificates

# Tasks

Tasks one to six build the tunnel package, which runs without LUML. The backend, the API client and the LUML side of the agent follow. The frontend comes last, because it needs all of them.

- [x] Add luml-tunnel package with tunnel tokens
  - [x] Create `tunnel/` with a `pyproject.toml` that follows `satellite/kit/pyproject.toml`: package `luml-tunnel`, import name `luml_tunnel`, Python 3.12 as the floor, the same ruff, mypy and pytest settings with 3.12 as the target
  - [x] Keep the core dependencies to a WebSocket client and an HTTP client; declare one extra for the relay and one for registration with LUML; keep the libraries for signing and checking tokens out of the core install
  - [x] Add the `luml-tunnel` command with the development subcommand that creates a key pair and signs `expose` and `view` tokens
  - [x] Add signing and checking of tokens as described in the Design section Tokens, behind the interface for how the relay checks a token
  - [x] Read the issuer's keys from an address or from a local file, cache them, and read them again on an unknown key identifier
  - [x] Add tests in `tunnel/tests/` for the token scenarios: a token that does not fit, one kind in place of the other, a new issuer key
  - [x] Add `.github/workflows/[tunnel] tests-and-linters.yml`, following the satellite kit workflow, on Python 3.12
  - [x] Run ruff, mypy and pytest in `tunnel/`

- [x] Add tunnel protocol frames and flow control
  - [x] Choose the byte layout of the frames and implement encoding and decoding in `tunnel/luml_tunnel/`
  - [x] Implement streams for an HTTP request with its response and for a WebSocket connection, opened by the relay only
  - [x] Implement the credit window per stream, with a sender that stops when the window is used up
  - [x] Add the frames for the relay's limits, a renewed token and the request to reconnect
  - [x] Ignore frame types that are not known
  - [x] Test the protocol in memory, without a network: round trips of every frame, the credit window, unknown frame types

- [x] Add relay and agent with HTTP forwarding
  - [x] Add the relay's web server behind the relay extra, and the `luml-tunnel relay` subcommand with settings for the base domain, the relay identifier, the issuer and the location of its keys
  - [x] Serve the address agents connect to and a health check on the base domain; agree the version through the subprotocol `luml-tunnel.v1`
  - [x] Find the session for a request by its hostname, keep connected agents in memory, and put both behind the interfaces listed in the Design section The tunnel package
  - [x] Accept viewers by the `X-Luml-Tunnel-Token` header; browser access comes in a later task
  - [x] Add the agent and the `luml-tunnel expose` subcommand with a relay address and a token given directly; forward to a port on the loopback address only; add the option that presents the loopback address as the host
  - [x] Apply the changes to incoming requests from the Design section on what the relay and the agent change
  - [x] Answer with status 502 when no agent is connected and when the service does not answer; never forward paths under `/.luml-tunnel/`
  - [x] Build the test setup that runs the relay, the agent and a small test service in one process, in `tunnel/tests/`
  - [x] Cover the scenarios: the package works without LUML, a request and its response, a large body, relay paths, loopback only, the public hostname, no connected agent, the service does not answer, what the service sees of the viewer

- [ ] Add limits, reconnection and token renewal to the tunnel
  - [ ] Enforce the limits on concurrent streams, request body size and idle time as relay settings, and announce them to the agent when it connects
  - [ ] Replace the old connection when a second agent connects for the same session
  - [ ] Close a connection whose token has expired; accept a renewed token on the open connection
  - [ ] Ask agents to reconnect before the relay shuts down
  - [ ] Reconnect from the agent with growing pauses between failed attempts
  - [ ] Cover the scenarios: a second agent, the relay restarts, a token expires, a renewed token, a request over a limit

- [ ] Forward WebSocket connections through the tunnel
  - [ ] Accept WebSocket connections from viewers on a session's hostname and open a stream for each
  - [ ] Connect from the agent to the service's WebSocket endpoint and pass messages in both directions under the credit window
  - [ ] Pass a close from either side to the other
  - [ ] Cover the scenario for a WebSocket connection, and a request for a WebSocket when the service refuses it

- [ ] Add browser access to tunnel sessions
  - [ ] Add the launch address, which checks the `view` token, accepts it once, sets the cookie and redirects to the root of the service
  - [ ] Sign the cookie in the relay and bind it to one session and one user, with the lifetimes of the monitoring dashboard's session in `satellite/kit/luml_satellite/monitoring/dashboard/session.py`
  - [ ] Accept a request authenticated by cookie only from the session's own pages or as a plain navigation
  - [ ] Add the two relay pages: access is needed, and the session is not connected
  - [ ] Make the relay page for missing access tell an embedding page, so the LUML app can launch again
  - [ ] Apply the changes to responses from the Design section on what the relay and the agent change, with a relay setting for the origins of the LUML app
  - [ ] Cover the scenarios: the launch address, a launch token accepted once, both ends of the cookie, a cookie for one session only, requests started by other sites, a request without access, framing, cookies of the service

- [ ] Add live session records to the backend
  - [ ] Add the model in `backend/luml/models/` with the fields from the Design section LUML backend as issuer, and register it in `backend/luml/models/__init__.py`
  - [ ] Add the migration `042` in `backend/migrations/versions/`
  - [ ] Add the schemas in `backend/luml/schemas/` with the status computed on read, as `Satellite.status` is in `backend/luml/schemas/satellite.py`
  - [ ] Add the repository in `backend/luml/repositories/`: create, read, list for one user and orbit without sessions that ended more than 24 hours ago, record a heartbeat, end
  - [ ] Create session identifiers that are random, made of lower-case letters and digits, and never reused
  - [ ] Add live sessions as a resource in `backend/luml/schemas/permissions.py` for every role that may work in an orbit, and to the resource lists in `backend/luml/handlers/permissions.py` that the frontend reads
  - [ ] Add integration tests in `backend/tests/integration/repository/` and unit tests for the status and the permissions
  - [ ] Run ruff, mypy and pytest in `backend/`

- [ ] Add live session operations and token issuing to the backend
  - [ ] Add the optional settings to `backend/luml/settings.py`: the signing key, the relay identifier, its base domain, the address agents connect to, and the two token lifetimes; add them to `backend/.env.example` and `backend/.env.test`
  - [ ] Publish the public keys at `/.well-known/jwks.json` without authentication, registered in `backend/luml/service.py` outside the `/v1` prefix
  - [ ] Add the handler in `backend/luml/handlers/` with the operations from the Design table, signing tokens with ES256 and the claims that `tunnel/luml_tunnel` checks
  - [ ] Check the rule that only the starting user may see or change a session in one place, and answer not found for everyone else
  - [ ] Fail every operation in the same way when the feature is off, with an error the frontend can tell apart from other failures
  - [ ] Add the routes in `backend/luml/api/orbits/`, following `orbit_satellites.py`, and register them in `backend/luml/api/organization_routes.py`
  - [ ] Add unit tests in `backend/tests/unit/handlers/` and `backend/tests/unit/api/` for the backend scenarios
  - [ ] Run ruff, mypy and pytest in `backend/`

- [ ] Add live sessions resource to the API client
  - [ ] Add the resource in `sdk/python/api/luml_api/resources/` in a synchronous and an asynchronous form, following `satellites.py`
  - [ ] Add the types to `sdk/python/api/luml_api/_types.py`
  - [ ] Add the resource to the base client and to both clients in `sdk/python/api/luml_api/_client.py`
  - [ ] Add tests in `sdk/python/api/tests/unit/`, following `test_satellite_resources.py`
  - [ ] Run ruff, mypy and pytest in `sdk/python/api/`

- [ ] Add LUML registration to the expose command
  - [ ] Make the LUML extra in `tunnel/pyproject.toml` depend on `luml-api`, with a local source for development as in `lumlflow/pyproject.toml`
  - [ ] Add LUML as a second implementation of where the agent gets its token
  - [ ] Let `luml-tunnel expose` take a name, the organization and the orbit, and read the API key and the address of LUML from the environment variables the API client uses
  - [ ] Start the session, connect, print the address of the session in the LUML app, and send heartbeats that report the state of the connection
  - [ ] Present a renewed token to the relay when a heartbeat returns one
  - [ ] Implement the behavior for every event in the Design table of the section The agent command
  - [ ] Test against a faked LUML and the relay in one process, covering the agent command scenarios

- [ ] Add the relay to the dev stack
  - [ ] Add `tunnel/Dockerfile` for the relay, following `satellite/kit/Dockerfile.monitoring`
  - [ ] Add the relay as a service in `dev/docker-compose.yml`, with a base domain under `localhost`, the backend as issuer and the local frontend as the origin of the LUML app
  - [ ] Add a signing key for development and the relay description to `dev/backend.env`
  - [ ] Check the compose file with `docker compose config`, then run the stack and walk through the scenario for a session in the dev stack up to the point where the session is served with a token header

- [ ] List live sessions on the Flow page
  - [ ] Add the API module in `frontend/src/lib/api/`, following `satellites/`, and register it in `frontend/src/lib/api/api.ts`
  - [ ] Add a store in `frontend/src/stores/`, following `satellites.ts`
  - [ ] Remove the `/flow` route from `frontend/src/router/index.ts` and add the list and the session page under the orbit route; the session identifier is not a UUID, so it stays out of the checks in `RouteIdsMiddleware.ts`
  - [ ] Make the sidebar entry resolve the organization and the orbit like the other orbit entries, in `frontend/src/constants/orbit-navigation.ts`, `frontend/src/constants/constants.ts` and `frontend/src/components/layout/LayoutSidebar.vue`
  - [ ] Add a Flow tab to `frontend/src/pages/orbits/SetupPage.vue` that keeps the instructions for running lumlflow locally
  - [ ] Replace `frontend/src/pages/FlowPage.vue` with a view in `frontend/src/pages/orbits/` that shows the list, the empty state with both sets of instructions, and the notice for a deployment with the feature off
  - [ ] Add unit tests next to the new files for the scenarios about the sidebar entry, sign-in, the old address, the list, the empty state and the feature being off
  - [ ] Run the type check, the linter and the unit tests in `frontend/`

- [ ] Show a live session on the Flow page
  - [ ] Add the session page, following `frontend/src/pages/DeploymentMonitoringPage.vue`, with the frame that loads the launch address with a new `view` token
  - [ ] Keep the `credentialless` attribute on the frame, which the app needs because it is cross-origin isolated
  - [ ] Add the actions to open in a new tab, with a token of its own, and to stop the session
  - [ ] Show the notices for the `disconnected` and the `ended` state in place of the frame
  - [ ] Listen for the message of the relay page and launch again, with the guard against repeated launches that the monitoring page has; when the guard stops a launch, offer to open the session in a new tab
  - [ ] Add unit tests for the scenarios from opening a live session to the browser that does not keep the cookie
  - [ ] Run the type check, the linter and the unit tests in `frontend/`

- [ ] Add release workflows for the tunnel package and relay image
  - [ ] Add a tag for `luml-tunnel` to `.github/workflows/publish-sdk-python.yml`
  - [ ] Add a workflow that publishes the relay image, following `.github/workflows/publish-monitoring-image.yml`
