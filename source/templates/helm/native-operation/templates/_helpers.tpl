{{- define "native-operation.name" -}}
{{- (.Values.service.name | default .Release.Name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
