#!/bin/sh
# Run only the server JAR beside this verified tool wrapper.
set -eu
tool_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${JAVA_HOME:-}" ]; then java_exe="$JAVA_HOME/bin/java"; else java_exe=java; fi
exec "$java_exe" -jar "$tool_dir/../server/fixture-server.jar" "$@"
