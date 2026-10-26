APP_NAME = "composer_migration_adk"
RUN_MODE = "single_channel"
ENABLE_GIT = False

# LLM
AGENT_MODEL = "gemini/gemini-3.5-flash-lite"
LITELLM_BASE_URL = ""
MODEL_PROVIDER = "gemini"
MODEL_API_KEY_ENVIRONMENT = "GOOGLE_API_KEY"
MODEL_TIMEOUT_SECONDS = 180
MAX_MODEL_ATTEMPTS = 4

# Retry / parallelism
MAX_AGENT_TASK_RETRIES = 4
MAX_PARALLEL_CONVERSION_WORKERS = 4
MAX_PARALLEL_LLM_TASKS = 2
MAX_PARALLEL_BUILD_TASKS = 2
MAX_OPERATIONS_PER_BATCH = 5
MAX_SOURCE_CHARS_PER_CONVERSION = 32000
MAX_CONTEXT_CHARS_PER_CONVERSION = 48000
RUNNER_HEARTBEAT_TIMEOUT_SECONDS = 300
INTER_BATCH_DELAY_SECS = 1

# Target channels and languages
TARGET_CHANNELS = ["INTERNET"]
TARGET_LANGUAGES = ["java"]

# Operation filters
INCLUDE_OPERATIONS: list[str] | None = None
EXCLUDE_OPERATIONS: list[str] | None = None

# Paths
COMPOSER_ROOT = "./bank-demo/composer/Workspace"
VAULT_ROOT = "./work/vault"
OUTPUT_ROOT = "./work/migration_runs"
NATIVE_JAVA_ROOT = "./work/native_java"
TEMPLATES_ROOT = "./source/templates"
GOLDEN_TESTS_ROOT = "./work/golden_tests"
LEGACY_SERVICE_BASE_URL = "http://legacy-wsbcc-host:8080"
DB_PATH = "./work/state/migration.db"

# Composer mapper
COMPOSER_MAPPER_JAR = "./source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar"
COMPOSER_MAPPER_VAULT_LAYOUT = "legacy"

# Java
COMMON_LIB_GROUP_ID = "com.company.migration"
COMMON_LIB_ARTIFACT_ID = "composer-common-lib"
JAVA_PACKAGE_BASE = "com.company.generated"
SPRING_BOOT_VERSION = "3.5.16"
JAVA_VERSION = "25"
JAVA_HOME = None
MAPPER_JAVA_VERSION = "25"

# Schema
ARTIFACT_SCHEMA_VERSION = "v1"

# Composer runtime boundaries; available application source still takes priority.
COMPOSER_FRAMEWORK_PACKAGES = [
    "com.ibm.dse.base",
    "com.ibm.il.dse.cc.format",
    "com.ibm.il.dse.cc.decorator",
    "com.ibm.il.dse.cc.service.database",
    "com.ibm.dse.services.jdbc",
]

# IBM guard
FORBIDDEN_DEPENDENCIES = [
    "com.ibm",
    "com.ibm.websphere",
    "com.ibm.wsbcc",
    "com.ibm.ws",
    "javax.ejb",
    "javax.rmi",
    "javax.resource",
    "javax.transaction.UserTransaction",
    "org.omg.CORBA",
    "websphere",
    "wsbcc",
    "Business Component Composer",
]

# Project profile defaults (credentials are always process environment values).
SOURCE_WORKSPACE_ID = None
SHARED_LIBRARY_MIN_USAGE = 5
BROAD_LIBRARY_USAGE_THRESHOLD = 10
AUTO_RERUN_IMPACTED_OPERATIONS = True
CLASSPATH_JARS = []
MAVEN_SETTINGS_PATH = None
APPROVED_MAVEN_REPOSITORY_URLS = []
MAVEN_LOCAL_REPOSITORY = None
ALLOWED_IBM_ARTIFACTS = []
ALLOWED_IBM_CLASSES = []
DEPLOYMENT_TEMPLATE_DIR = None
DEPLOYMENT_VALUES = {}
RUNTIME_VALIDATION_MODE = "disabled"
ECLIPSE_CLASSPATH_VARIABLES = {}
GATE_POLICIES = {str(number): "human" for number in range(1, 5)}

# Implemented capabilities, distinct from the default selection.
SUPPORTED_TARGET_LANGUAGES = ("java",)

# Deployment fallback values, merged before writing a run snapshot.
DEPLOYMENT_PLATFORM = "openshift"
# Approved driver replacement proposals keyed by driver_class and java_versions.
# Empty by default: workspace versions are preferred and vendor versions are not guessed.
SERVICE_DRIVER_DEPENDENCY_CANDIDATES = []
DEPLOYMENT_ENVIRONMENT = "prod"
DEPLOYMENT_CONTAINER_PORT = 8080
DEPLOYMENT_HEALTH_PATHS = {"liveness": "/actuator/health", "readiness": "/actuator/health"}
DEPLOYMENT_ENV_VARS = {"SPRING_PROFILES_ACTIVE": "prod"}
DEPLOYMENT_DEFAULTS = {
    "namespace": "default", "replicas": 1, "image_pull_policy": "IfNotPresent",
    "container_port": DEPLOYMENT_CONTAINER_PORT,
    "cpu_request": "100m", "cpu_limit": "500m",
    "memory_request": "256Mi", "memory_limit": "512Mi",
    "liveness_path": DEPLOYMENT_HEALTH_PATHS["liveness"],
    "readiness_path": DEPLOYMENT_HEALTH_PATHS["readiness"], "managed_by_label": "snapir",
}

# Connection settings for testing manually deployed OpenShift services.
TEST_DEPLOYMENT_DEFAULTS = {
    "service_base_url": "https://openshift/microservices/", # externally accessible base URL for test requests, including http:// or https://
    "service_external_port": None, # external router port; None means no explicit override of the URL or protocol default port
    "service_route_pattern": "ms_${ms_name}", # hostname or path pattern used to construct each microservice's test URL
}
