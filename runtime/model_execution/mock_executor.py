"""Supply explicit canned responses for pipeline integration tests."""


class MockExecutor:
    """Return an injected response without claiming to perform a conversion."""

    def __init__(self, response: str):
        self.response = response

    def execute(self, instruction: str, payload: str) -> str:
        """Return the configured fixture response."""
        return self.response
