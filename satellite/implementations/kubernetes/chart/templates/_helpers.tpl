{{- define "luml.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "luml.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "luml.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "luml.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "luml.componentName" -}}
{{- $suffix := .suffix | trimPrefix "-" -}}
{{- $base := include "luml.fullname" .root -}}
{{- $maxBaseLength := sub 62 (len $suffix) | int -}}
{{- if gt (len $base) $maxBaseLength -}}
{{- $hash := sha256sum $base | trunc 8 -}}
{{- $prefixLength := sub $maxBaseLength 9 | int -}}
{{- $base = printf "%s-%s" ($base | trunc $prefixLength | trimSuffix "-") $hash -}}
{{- end -}}
{{- printf "%s-%s" $base $suffix | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "luml.labels" -}}
helm.sh/chart: {{ include "luml.chart" .root | quote }}
app.kubernetes.io/name: {{ include "luml.name" .root | quote }}
app.kubernetes.io/instance: {{ .root.Release.Name | quote }}
app.kubernetes.io/component: {{ .component | quote }}
app.kubernetes.io/managed-by: {{ .root.Release.Service | quote }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
luml.ai/satellite-id: {{ .root.Release.Name | quote }}
{{- end -}}

{{- define "luml.selectorLabels" -}}
app.kubernetes.io/name: {{ include "luml.name" .root | quote }}
app.kubernetes.io/instance: {{ .root.Release.Name | quote }}
app.kubernetes.io/component: {{ .component | quote }}
luml.ai/satellite-id: {{ .root.Release.Name | quote }}
{{- end -}}

{{- define "luml.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "luml.componentName" (dict "root" . "suffix" "satellite")) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "luml.satelliteName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "satellite") -}}
{{- end -}}

{{- define "luml.dashboardName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "dashboard") -}}
{{- end -}}

{{- define "luml.workerName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "worker") -}}
{{- end -}}

{{- define "luml.collectorName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "collector") -}}
{{- end -}}

{{- define "luml.storeName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "store") -}}
{{- end -}}

{{- define "luml.sharedCacheClaimName" -}}
{{- if .Values.sharedCache.existingClaim -}}
{{- .Values.sharedCache.existingClaim -}}
{{- else -}}
{{- include "luml.componentName" (dict "root" . "suffix" "model-cache") -}}
{{- end -}}
{{- end -}}

{{- define "luml.tokenSecretName" -}}
{{- default (include "luml.componentName" (dict "root" . "suffix" "token")) .Values.satellite.existingSecret -}}
{{- end -}}

{{- define "luml.tokenSecretKey" -}}
{{- if .Values.satellite.existingSecret -}}
{{- .Values.satellite.existingSecretKey -}}
{{- else -}}
satellite-token
{{- end -}}
{{- end -}}

{{- define "luml.derivationSecretName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "derivation-key") -}}
{{- end -}}

{{- define "luml.derivationKey" -}}
{{- if hasKey .Values "_lumlDerivationKey" -}}
{{- get .Values "_lumlDerivationKey" -}}
{{- else -}}
{{- $key := .Values.satellite.derivationKey -}}
{{- if not $key -}}
{{- $current := lookup "v1" "Secret" .Release.Namespace (include "luml.derivationSecretName" .) -}}
{{- if and $current $current.data (hasKey $current.data "derivation-key") -}}
{{- $key = index $current.data "derivation-key" | b64dec -}}
{{- else -}}
{{- $key = randAlphaNum 64 -}}
{{- end -}}
{{- end -}}
{{- $_ := set .Values "_lumlDerivationKey" $key -}}
{{- $key -}}
{{- end -}}
{{- end -}}

{{- define "luml.tokenChecksum" -}}
{{- if .Values.satellite.existingSecret -}}
{{- printf "external:%s:%s" .Values.satellite.existingSecret .Values.satellite.existingSecretKey | sha256sum -}}
{{- else -}}
{{- .Values.satellite.token | sha256sum -}}
{{- end -}}
{{- end -}}

{{- define "luml.derivationChecksum" -}}
{{- include "luml.derivationKey" . | sha256sum -}}
{{- end -}}

{{- define "luml.monitoringSecretName" -}}
{{- include "luml.componentName" (dict "root" . "suffix" "monitoring") -}}
{{- end -}}

{{- define "luml.storeCredentialsConfigured" -}}
{{- if or .Values.monitoring.store.existingSecret .Values.monitoring.store.username .Values.monitoring.store.password -}}true{{- end -}}
{{- end -}}

{{- define "luml.storeSecretName" -}}
{{- default (include "luml.componentName" (dict "root" . "suffix" "store-credentials")) .Values.monitoring.store.existingSecret -}}
{{- end -}}

{{- define "luml.storeUsernameKey" -}}
{{- if .Values.monitoring.store.existingSecret -}}
{{- .Values.monitoring.store.existingSecretUsernameKey -}}
{{- else -}}
username
{{- end -}}
{{- end -}}

{{- define "luml.storePasswordKey" -}}
{{- if .Values.monitoring.store.existingSecret -}}
{{- .Values.monitoring.store.existingSecretPasswordKey -}}
{{- else -}}
password
{{- end -}}
{{- end -}}

{{- define "luml.objectStorageSecretName" -}}
{{- default (include "luml.componentName" (dict "root" . "suffix" "object-storage")) .Values.monitoring.store.objectStorage.existingSecret -}}
{{- end -}}

{{- define "luml.objectStorageAccessKey" -}}
{{- if .Values.monitoring.store.objectStorage.existingSecret -}}
{{- .Values.monitoring.store.objectStorage.existingSecretAccessKeyKey -}}
{{- else -}}
access-key
{{- end -}}
{{- end -}}

{{- define "luml.objectStorageSecretKey" -}}
{{- if .Values.monitoring.store.objectStorage.existingSecret -}}
{{- .Values.monitoring.store.objectStorage.existingSecretSecretKeyKey -}}
{{- else -}}
secret-key
{{- end -}}
{{- end -}}

{{- define "luml.storeHost" -}}
{{- if eq .Values.monitoring.store.mode "external" -}}
{{- required "monitoring.store.host is required in external mode" .Values.monitoring.store.host -}}
{{- else -}}
{{- include "luml.storeName" . -}}
{{- end -}}
{{- end -}}

{{- define "luml.baseUrl" -}}
{{- if .Values.satellite.baseUrl -}}
{{- .Values.satellite.baseUrl | trimSuffix "/" -}}
{{- else -}}
{{- $https := or (not (empty .Values.ingress.tls.secretName)) (eq .Values.podSecurity.preset "openshift") -}}
{{- printf "%s://%s" (ternary "https" "http" $https) .Values.satellite.host -}}
{{- end -}}
{{- end -}}

{{- define "luml.ingressClassName" -}}
{{- if .Values.ingress.className -}}
{{- .Values.ingress.className -}}
{{- else if eq .Values.podSecurity.preset "openshift" -}}
openshift-default
{{- end -}}
{{- end -}}

{{- define "luml.ingressAnnotations" -}}
{{- $annotations := deepCopy .Values.ingress.annotations -}}
{{- if eq .Values.podSecurity.preset "openshift" -}}
{{- if not (hasKey $annotations "route.openshift.io/termination") -}}
{{- $_ := set $annotations "route.openshift.io/termination" "edge" -}}
{{- end -}}
{{- end -}}
{{- toYaml $annotations -}}
{{- end -}}

{{- define "luml.podSecurityContext" -}}
{{- $context := dict "runAsNonRoot" true "seccompProfile" (dict "type" "RuntimeDefault") -}}
{{- if eq .Values.podSecurity.preset "vanilla" -}}
{{- $_ := set $context "runAsUser" 10001 -}}
{{- $_ := set $context "runAsGroup" 0 -}}
{{- $_ := set $context "fsGroup" 10001 -}}
{{- end -}}
{{- $context = mergeOverwrite $context (deepCopy .Values.podSecurity.podContext) -}}
{{- toYaml $context -}}
{{- end -}}

{{- define "luml.containerSecurityContext" -}}
{{- $context := dict
    "runAsNonRoot" true
    "allowPrivilegeEscalation" false
    "capabilities" (dict "drop" (list "ALL"))
-}}
{{- $context = mergeOverwrite $context (deepCopy .Values.podSecurity.containerContext) -}}
{{- toYaml $context -}}
{{- end -}}

{{- define "luml.image" -}}
{{- printf "%s:%s" .repository .tag -}}
{{- end -}}

{{- define "luml.imagePullSecrets" -}}
{{- range .Values.satellite.imagePullSecrets }}
- name: {{ . | quote }}
{{- end -}}
{{- end -}}

{{- define "luml.tokenEnv" -}}
- name: SATELLITE_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "luml.tokenSecretName" . | quote }}
      key: {{ include "luml.tokenSecretKey" . | quote }}
{{- end -}}

{{- define "luml.derivationEnv" -}}
- name: DERIVATION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "luml.derivationSecretName" . | quote }}
      key: derivation-key
{{- end -}}

{{- define "luml.storeCredentialEnv" -}}
{{- if include "luml.storeCredentialsConfigured" . }}
- name: GREPTIMEDB_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "luml.storeSecretName" . | quote }}
      key: {{ include "luml.storeUsernameKey" . | quote }}
- name: GREPTIMEDB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "luml.storeSecretName" . | quote }}
      key: {{ include "luml.storePasswordKey" . | quote }}
{{- end -}}
{{- end -}}

{{- define "luml.monitoringEnv" -}}
{{ include "luml.tokenEnv" . }}
{{ include "luml.derivationEnv" . }}
- name: PLATFORM_URL
  value: {{ .Values.satellite.platformUrl | quote }}
- name: GREPTIMEDB_HOST
  value: {{ include "luml.storeHost" . | quote }}
- name: GREPTIMEDB_HTTP_PORT
  value: {{ .Values.monitoring.store.port | quote }}
- name: GREPTIMEDB_DATABASE
  value: {{ .Values.monitoring.store.database | quote }}
{{ include "luml.storeCredentialEnv" . }}
- name: SIDECAR_INTERNAL_URL_TEMPLATE
  value: "http://luml-dep-{deployment_id}:8001"
- name: MONITORING_FRAME_ANCESTORS
  value: {{ .Values.monitoring.frameAncestors | quote }}
- name: MONITORING_SESSION_TTL_SECONDS
  value: {{ .Values.monitoring.sessionTtlSeconds | quote }}
- name: MONITORING_DEPLOYMENTS_REFRESH_SEC
  value: {{ .Values.monitoring.worker.deploymentsRefreshSeconds | quote }}
- name: MONITORING_INTERVAL_SEC
  value: {{ .Values.monitoring.worker.intervalSeconds | quote }}
- name: MONITORING_WINDOW_SEC
  value: {{ .Values.monitoring.worker.windowSeconds | quote }}
- name: MONITORING_BACKFILL_MAX_WINDOWS
  value: {{ .Values.monitoring.worker.maxBackfillWindows | quote }}
- name: MONITORING_EVENTS_TTL
  value: {{ .Values.monitoring.store.retention.events | quote }}
- name: MONITORING_RESULTS_TTL
  value: {{ .Values.monitoring.store.retention.results | quote }}
- name: MONITORING_ALERTS_TTL
  value: {{ .Values.monitoring.store.retention.alerts | quote }}
- name: MONITORING_TRACES_TTL
  value: {{ .Values.monitoring.store.retention.traces | quote }}
- name: MONITORING_METRICS_TTL
  value: {{ .Values.monitoring.store.retention.metrics | quote }}
- name: LOG_LEVEL
  value: {{ .Values.monitoring.logLevel | quote }}
{{- if .Values.monitoring.sessionSecret }}
- name: MONITORING_SESSION_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "luml.monitoringSecretName" . | quote }}
      key: session-secret
{{- end }}
{{- end -}}

{{- define "luml.probeTimeout" -}}
{{- (.Values.probes | default dict).timeoutSeconds | default 5 -}}
{{- end -}}

{{- define "luml.probeFailureThreshold" -}}
{{- (.Values.probes | default dict).failureThreshold | default 3 -}}
{{- end -}}

{{- define "luml.probeTuning" -}}
timeoutSeconds: {{ include "luml.probeTimeout" . }}
failureThreshold: {{ include "luml.probeFailureThreshold" . }}
{{- end -}}
