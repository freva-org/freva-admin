{{- define "freva.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "freva.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "freva.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "freva.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "freva.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: freva
{{- end -}}

{{- define "freva.selectorLabels" -}}
app.kubernetes.io/name: {{ include "freva.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "freva.secretName" -}}
{{- default (printf "%s-secrets" (include "freva.fullname" .)) .Values.secrets.existingSecret -}}
{{- end -}}

{{- define "freva.webConfigMapName" -}}
{{- default (printf "%s-web-config" (include "freva.fullname" .)) .Values.web.config.existingConfigMap -}}
{{- end -}}

{{- define "freva.image" -}}
{{- printf "%s:%s" .repository (.tag | toString) -}}
{{- end -}}

{{- define "freva.pvcName" -}}
{{- if .persistence.existingClaim -}}
{{- .persistence.existingClaim -}}
{{- else -}}
{{- printf "%s-%s" (include "freva.fullname" .root) .component -}}
{{- end -}}
{{- end -}}

{{- define "freva.podSettings" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "freva.containerSecurityContext" -}}
{{- with .Values.containerSecurityContext }}
securityContext:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
