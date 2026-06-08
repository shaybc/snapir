# Prompt 23 — `JavaDeploymentManifestAgent`

## Context
Stage 6. JavaServiceGenerationAgent (22) has produced a compiled service.
This agent generates Kubernetes / OpenShift deployment manifests using
Jinja2 templates. The LLM only provides service-specific values — it does not
write YAML directly.

## Reference
`Implementation_plan_V8.md` section 5 Phase 7,
`models/deployment_models/`.

## Files to create
```
agents/java_deployment_manifest/
├── __init__.py
└── agent.py
tools/deployment_tools/
├── __init__.py
└── template_renderer.py
templates/deployment/
├── deployment.yaml.j2
├── service.yaml.j2
├── configmap.yaml.j2
└── route.yaml.j2
```

## `template_renderer.py`

```python
def render_manifest(
    template_dir: str,
    spec: DeploymentSpec
) -> RenderedManifest:
    """
    Renders Jinja2 templates using spec values.
    Returns RenderedManifest with rendered YAML strings per file.
    Validates rendered YAML is parseable before returning.
    """
```

## LLM instruction (values only, not YAML)

```
You are providing configuration values for a deployment manifest.
Do NOT write YAML. Output ONLY a JSON object with these keys:

OPERATION_ID: {operation_id}
SERVICE_CLASS: {service_class_name}
SPRING_PORT: {port}  (inferred from application.properties)
DB_LOOKUPS: {db_lookup_count}  (indicates DB connectivity needed)
IMAGE_NAME_HINT: {operation_id.lower().replace('_','-')}-service

Output JSON:
{
  "service_name": "...",
  "image_name": "...",
  "container_port": 8080,
  "env_vars": {"SPRING_PROFILES_ACTIVE": "prod"},
  "health_paths": {"liveness": "/actuator/health", "readiness": "/actuator/health"},
  "requires_db": true|false,
  "replicas": 1
}
```

## Templates (Jinja2)
`deployment.yaml.j2`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ spec.service_name }}
  namespace: {{ defaults.namespace }}
spec:
  replicas: {{ spec.replicas }}
  ...
```

## Validation
After rendering, run `kubectl --dry-run=client apply -f` on each file.
If `kubectl` is unavailable: validate YAML parse only (no k8s schema check).

## Tests
`tests/test_deployment_manifest.py`:
- Rendered deployment.yaml contains service_name from LLM values.
- Invalid YAML in template raises before delivery.
- LLM JSON parse failure retries.
