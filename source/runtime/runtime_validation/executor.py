"""Select the configured runtime test implementation behind a neutral interface."""


class RuntimeTestExecutor:
    """Dispatch runtime tests without exposing provider decisions to the pipeline."""

    def __init__(self, profile):
        self.mode = profile.runtime_validation_mode

    def execute(self, operation, directory):
        """Return provider results; disabled execution contributes no new evidence."""
        if self.mode == "disabled":
            return {}
        if self.mode == "dummy":
            from runtime.runtime_validation.dummy_executor import DummyRuntimeTestExecutor
            return DummyRuntimeTestExecutor().execute(operation, directory)
        raise ValueError("Runtime test executor implementation is unavailable")
