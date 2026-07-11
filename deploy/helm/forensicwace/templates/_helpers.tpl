{{- define "fw.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "fw.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "fw.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "fw.imageTag" -}}
{{- .Values.image.tag | default .Chart.AppVersion -}}
{{- end -}}

{{- define "fw.databaseUrl" -}}
{{- if .Values.postgresql.enabled -}}
postgresql+psycopg2://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "fw.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else -}}
{{- required "postgresql.externalUrl is required when postgresql.enabled=false" .Values.postgresql.externalUrl -}}
{{- end -}}
{{- end -}}

{{- define "fw.brokerUrl" -}}
{{- if .Values.rabbitmq.enabled -}}
amqp://{{ .Values.rabbitmq.auth.username }}:{{ .Values.rabbitmq.auth.password }}@{{ include "fw.fullname" . }}-rabbitmq:5672//
{{- else -}}
{{- required "rabbitmq.externalUrl is required when rabbitmq.enabled=false" .Values.rabbitmq.externalUrl -}}
{{- end -}}
{{- end -}}

{{/* KEDA rabbitmq scaler host: single trailing slash selects the default vhost */}}
{{- define "fw.brokerKedaHost" -}}
{{- if .Values.rabbitmq.enabled -}}
amqp://{{ .Values.rabbitmq.auth.username }}:{{ .Values.rabbitmq.auth.password }}@{{ include "fw.fullname" . }}-rabbitmq:5672/
{{- else -}}
{{- .Values.rabbitmq.externalKedaHost | default .Values.rabbitmq.externalUrl -}}
{{- end -}}
{{- end -}}

{{/* Object storage (projects uploads): in-cluster MinIO or external S3 */}}
{{- define "fw.s3Enabled" -}}
{{- if or .Values.minio.enabled .Values.minio.externalEndpoint -}}true{{- end -}}
{{- end -}}

{{- define "fw.s3Endpoint" -}}
{{- if .Values.minio.enabled -}}
http://{{ include "fw.fullname" . }}-minio:9000
{{- else -}}
{{- .Values.minio.externalEndpoint -}}
{{- end -}}
{{- end -}}

{{- define "fw.s3AccessKey" -}}
{{- if .Values.minio.enabled -}}
{{- .Values.minio.auth.rootUser -}}
{{- else -}}
{{- required "minio.externalAccessKey is required with minio.externalEndpoint" .Values.minio.externalAccessKey -}}
{{- end -}}
{{- end -}}

{{- define "fw.s3SecretKey" -}}
{{- if .Values.minio.enabled -}}
{{- .Values.minio.auth.rootPassword -}}
{{- else -}}
{{- required "minio.externalSecretKey is required with minio.externalEndpoint" .Values.minio.externalSecretKey -}}
{{- end -}}
{{- end -}}

{{/* Environment shared by api and worker */}}
{{- define "fw.sharedEnv" -}}
- name: FW_DATA_DIR
  value: /data
- name: FW_COOKIE_SECURE
  value: {{ .Values.auth.cookieSecure | quote }}
{{- if include "fw.s3Enabled" . }}
- name: FW_S3_ENDPOINT
  value: {{ include "fw.s3Endpoint" . | quote }}
- name: FW_S3_BUCKET
  value: {{ .Values.minio.bucket | quote }}
{{- with .Values.minio.region }}
- name: FW_S3_REGION
  value: {{ . | quote }}
{{- end }}
{{- end }}
{{- range $name, $value := .Values.extraEnv }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}
{{- end -}}

{{- define "fw.evidenceClaim" -}}
{{- .Values.evidence.existingClaim | default (printf "%s-evidence" (include "fw.fullname" .)) -}}
{{- end -}}
