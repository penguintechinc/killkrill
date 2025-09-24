{{/*
Expand the name of the chart.
*/}}
{{- define "killkrill.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "killkrill.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "killkrill.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "killkrill.labels" -}}
helm.sh/chart: {{ include "killkrill.chart" . }}
{{ include "killkrill.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "killkrill.selectorLabels" -}}
app.kubernetes.io/name: {{ include "killkrill.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "killkrill.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "killkrill.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create a default fully qualified postgresql name.
*/}}
{{- define "killkrill.postgresql.fullname" -}}
{{- include "killkrill.fullname" . }}-postgresql
{{- end }}

{{/*
Create a default fully qualified redis name.
*/}}
{{- define "killkrill.redis.fullname" -}}
{{- include "killkrill.fullname" . }}-redis
{{- end }}

{{/*
Create a default fully qualified elasticsearch name.
*/}}
{{- define "killkrill.elasticsearch.fullname" -}}
{{- include "killkrill.fullname" . }}-elasticsearch
{{- end }}

{{/*
Create a default fully qualified prometheus name.
*/}}
{{- define "killkrill.prometheus.fullname" -}}
{{- include "killkrill.fullname" . }}-prometheus
{{- end }}

{{/*
Create a default fully qualified grafana name.
*/}}
{{- define "killkrill.grafana.fullname" -}}
{{- include "killkrill.fullname" . }}-grafana
{{- end }}

{{/*
Create the license key secret name
*/}}
{{- define "killkrill.license.secretName" -}}
{{- if .Values.license.existingSecret }}
{{- .Values.license.existingSecret }}
{{- else }}
{{- include "killkrill.fullname" . }}-license
{{- end }}
{{- end }}

{{/*
Generate postgresql connection string
*/}}
{{- define "killkrill.postgresql.connectionString" -}}
{{- printf "postgresql://%s:%s@%s:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "killkrill.postgresql.fullname" .) .Values.postgresql.auth.database }}
{{- end }}

{{/*
Generate redis connection string
*/}}
{{- define "killkrill.redis.connectionString" -}}
{{- if .Values.redis.auth.enabled }}
{{- printf "redis://:%s@%s:6379" .Values.redis.auth.password (include "killkrill.redis.fullname" .) }}
{{- else }}
{{- printf "redis://%s:6379" (include "killkrill.redis.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Generate infrastructure URLs for manager
*/}}
{{- define "killkrill.infrastructure.urls" -}}
PROMETHEUS_URL: "http://{{ include "killkrill.prometheus.fullname" . }}:9090"
ELASTICSEARCH_URL: "http://{{ include "killkrill.elasticsearch.fullname" . }}:9200"
KIBANA_URL: "http://{{ include "killkrill.fullname" . }}-kibana:5601"
GRAFANA_URL: "http://{{ include "killkrill.grafana.fullname" . }}:3000"
ALERTMANAGER_URL: "http://{{ include "killkrill.fullname" . }}-alertmanager:9093"
{{- end }}

{{/*
Validate required values
*/}}
{{- define "killkrill.validateValues" -}}
{{- if not .Values.license.key }}
{{- fail "A valid license key is required. Please set .Values.license.key" }}
{{- end }}
{{- end }}

{{/*
Generate common environment variables
*/}}
{{- define "killkrill.commonEnv" -}}
- name: DATABASE_URL
  value: {{ include "killkrill.postgresql.connectionString" . }}
- name: REDIS_URL
  value: {{ include "killkrill.redis.connectionString" . }}
- name: LICENSE_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "killkrill.license.secretName" . }}
      key: license-key
- name: PRODUCT_NAME
  value: {{ .Values.license.product | quote }}
- name: LICENSE_SERVER_URL
  value: {{ .Values.license.server | quote }}
{{- end }}

{{/*
Generate XDP security context
*/}}
{{- define "killkrill.xdpSecurityContext" -}}
{{- if .Values.killkrill.logReceiver.xdp.enabled }}
privileged: true
allowPrivilegeEscalation: true
capabilities:
  add:
    - NET_ADMIN
    - SYS_ADMIN
    - NET_RAW
runAsUser: 0
{{- else }}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end }}
{{- end }}