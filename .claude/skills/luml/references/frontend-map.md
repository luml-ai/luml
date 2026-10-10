# Frontend map (`frontend/src`) and Flow UI (`lumlflow/frontend/src`)

Where features live, so a bug in "Deployments → gear → Save" can be read in
the right file without grepping the whole tree. Vue 3 + Pinia + PrimeVue
(`d-*` components are PrimeVue wrappers; forms use `@primevue/forms` with zod
resolvers in `utils/forms/resolvers.ts`).

## Routes (`router/index.ts`)

| Path | Page |
| --- | --- |
| `/sign-in`, `/sign-up`, `/forgot-password`, `/change-password?token=` | `pages/*Page.vue`; reset flow in `ChangePasswordPage.vue` |
| `/organization/:organizationId/orbits` | orbit list |
| `/organization/:organizationId/orbit/:id` | orbit root = Registry (Collections / Tracks tabs); children `tracks`, `deployments`, `satellites`, `secrets` |
| `…/orbit/:id/collection/:collectionId` | artifact table; child `artifacts/:artifactId` with `data`, `card`, `experiment-snapshot`, `attachments`, `lineage`, `compare` |
| `…/orbit/:id/tracks/:trackId` | track entries |
| `…/orbit/:id/deployments/:deploymentId/schema` \| `/monitoring` | deployment pages |
| `/classification`, `/regression`, `/forecasting`, `/prompt-fusion`, `/runtime` | in-browser tasks (wasm worker) |
| `/notebooks`, `/flow`, `/prisma` | Jupyter, Flow embed, Prisma agent |

Route guards: `router/middlewares/` — `AuthMiddleware.ts` (calls
`checkIsLoggedIn` on every navigation while unauthenticated),
`OrbitMiddleware.ts`, `LoadLayoutMiddleware.ts`. Page-level leave guards use
`onBeforeRouteLeave` (e.g. `pages/collection/artifact/LineageView.vue`) or
`hooks/useRouteLeaveConfirm.ts`. Organization is chosen from the route param in
`pages/organization/index.vue` → `organizationStore.setCurrentOrganizationId`,
persisted in localStorage `currentOrganizationId`.

## Feature → files

| Feature | Components | State / data |
| --- | --- | --- |
| Registry: collections | `components/orbits/tabs/registry/` (`CollectionsList`, `CollectionCard`, `CollectionCreator`, `CollectionEditor`) | `hooks/useCollectionsList.ts`, `stores/collections.ts` |
| Artifact table | `…/registry/collection/artifacts-table/` (`ArtifactsTable`, `TagsList`, `MetricsSelect`), `…/collection/artifact/` (`ArtifactsList`, `ArtifactCard`, `ArtifactDetails`) | `hooks/useArtifactsList.ts` (cursor paging, `limit = 20`, PrimeVue VirtualScroller lazy load), `stores/artifacts/index.ts` |
| Artifact upload | `components/model-upload/ModelUpload.vue` | `hooks/useArtifactUpload.ts` (initiate → PUT to bucket → confirm), `lib/bucket-service/` |
| Tracks | `components/tracks/` (`TracksCreator`, `TracksList`, `LinkArtifactToTrack`, `StageSelect`, `StageWarning`, `LinksToolbar`) ; page `pages/orbits/TracksView.vue` | `hooks/useTracksList.ts`, `hooks/useTrackEntriesList.ts`, `stores/tracks/` |
| Deployments | `components/deployments/create/DeploymentsCreateModal.vue`, `edit/DeploymentsEditor.vue`, `form/*` (`DeploymentsFormSatelliteSettings`, `SecretsSelect`), `table/DeploymentsTable.vue` | `stores/deployments.ts`, `stores/orbit-secrets.ts`, `stores/satellites.ts` |
| Satellites | `components/satellites/` (`SatellitesCreateModal`, `SatellitesEditModal`, `SatellitesApiKeyModal`, `SatellitesCard`) | `stores/satellites.ts`, `hooks/satellites/` |
| Organization settings | `components/organizations/` (`OrganizationMembers`, `OrganizationInviteManager`, `OrganizationLeavePopover`, `registry/OrganizationRegistryTable.vue` = buckets) | `stores/organization.ts`, `stores/invitations.ts`, `stores/buckets.ts` |
| Orbit header / popover | `components/orbits/OrbitManagePopover.vue`, `OrbitsList.vue`, `creator/`, `editor/` | `stores/orbits.ts` (`getCurrentOrbitPermissions` is the permission gate used by toolbars) |
| User / account | `components/user/` (`UserSettings`, `UserChangePassword`, `UserToolbar`) | `stores/user.ts`, `stores/auth.ts` |
| Theme | — | `stores/theme.ts` |
| Experiment snapshots / compare | `pages/collection/artifact/SnapshotView.vue`, `pages/collection/compare/CompareView.vue` | `hooks/useExperimentSnapshotsDatabaseProvider.ts` → `workers/experiment-snapshot` (Web Worker), package `@luml/experiments` in `extras/js/packages/experiments` |
| Lineage | `components/lineage/`, `pages/collection/artifact/LineageView.vue` | `stores/lineage/` |
| In-browser training | `components/express-tasks/`, `lib/data-processing/DataProcessingWorker.ts` (singleton `window.pyodideWorker` from `public/webworker.js`) | Python side in `wasm/packages/dfs_webworker/` |
| Notebooks | `components/notebooks/` (`NotebooksList`, `NotebooksModelsTable`) | `stores/notebooks.ts`; Jupyter reached via the Vite `/jupyter` proxy |

Shared bits: `lib/api/api.ts` (all REST calls, one class), `lib/api/api.interceptors.ts`,
`lib/primevue/data/toasts.ts` (`simpleErrorToast` / `simpleSuccessToast`),
`helpers/helpers.ts` (`getSizeText`, `getErrorMessage`), `utils/forms/initialValues.ts`
(module-level objects — anything bound with v-model to them persists across
dialog opens).

Things to check first when reading a UI bug:

- Modals with a submit button outside the `<form>` use `form="<id>"`; two
  components mounted at once with the same form id submit the wrong one.
- Async init in `onBeforeMount` that fills `initialValues`: is Save disabled
  while it runs?
- A "create" hook that appends to the currently loaded store list regardless of
  which collection/orbit the request targeted.
- Permission gates are per toolbar (`getCurrentOrbitPermissions?.<resource>.includes(PermissionEnum.x)`), not per route; a missing gate means the button shows for viewers.

## Flow UI (`lumlflow/frontend/src`)

| Area | Files |
| --- | --- |
| Experiment list, search tooltip | `components/experiments/experiment/ExperimentTable.vue`, `ExperimentToolbar.vue`, `experiment.const.ts` (`AUTOCOMPLETE_TOOLTIP`) |
| Experiment details | `pages/details/ExperimentDetailsPage.vue` (heading), `OverviewView.vue`, `MetricsView.vue` (metric list derived from `experiment.dynamic_params`) |
| Metrics card / charts | `table-cards/MetricsCard.vue` |
| Stores | `store/experiments`, `store/experiment`, `store/groups` (`deleteGroups` → toast), `store/model-card` |
| Formatting | `helpers/date.ts` (`durationToText` expects milliseconds; API sends seconds) |
| API | `api/` |

Backend for the Flow UI is `lumlflow/lumlflow/api/*.py` (`experiment_groups.py`
for the list/search routes, `experiments.py` for details and metrics).
