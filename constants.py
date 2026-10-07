APP_NAME = "composer_migration_adk"
RUN_MODE = "single_channel"
ENABLE_GIT = False

# LLM
AGENT_MODEL = "gemini/gemini-2.5-pro"
LITELLM_BASE_URL = "http://enterprise-proxy.internal/v1"
LITELLM_API_KEY = "enterprise-key"

# Retry / parallelism
MAX_AGENT_TASK_RETRIES = 3
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
COMPOSER_ROOT = "./input/composer"
VAULT_ROOT = "./work/vault"
OUTPUT_ROOT = "./generated"
NATIVE_JAVA_ROOT = "./work/native_java"
TEMPLATES_ROOT = "./templates"
GOLDEN_TESTS_ROOT = "./work/golden_tests"
LEGACY_SERVICE_BASE_URL = "http://legacy-wsbcc-host:8080"
DB_PATH = "./work/state/migration.db"

# Composer mapper
COMPOSER_MAPPER_JAR = "./composer-mapper/target/composer-mapper.jar"

# Java
COMMON_LIB_GROUP_ID = "com.company.migration"
COMMON_LIB_ARTIFACT_ID = "composer-common-lib"
JAVA_PACKAGE_BASE = "com.company.generated"
SPRING_BOOT_VERSION = "3.5.16"
JAVA_VERSION = "25"

# Schema
ARTIFACT_SCHEMA_VERSION = "v1"

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
