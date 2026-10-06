"""Share managed build policy between converter and generation executors."""

from dataclasses import dataclass
from pathlib import Path

from models.maven_dependency import JavaConversionOutput
from tools.maven_dependency_tools.conversion_submission import submit_managed_conversion


@dataclass
class ManagedBuildContext:
    """Own one canonical POM and its trusted dependency verification policy."""

    pom_path: str
    verifier: object
    allowed_ibm_artifacts: tuple[str, ...] = ()
    allowed_ibm_classes: tuple[str, ...] = ()

    def submit(self, source: str, output_path: str, task_id: str, dependencies=()):
        """Verify proposals and compile with the same approved repository policy."""
        return submit_managed_conversion(
            JavaConversionOutput(java_source=source, dependencies=list(dependencies)), output_path,
            self.pom_path, self.verifier, allowed_ibm_artifacts=self.allowed_ibm_artifacts,
            allowed_ibm_classes=self.allowed_ibm_classes, task_id=task_id,
            settings_path=getattr(self.verifier, "settings_path", None),
        )

    @property
    def source_root(self) -> Path:
        """Return the project's production Java source directory."""
        return Path(self.pom_path).parent / "src/main/java"
