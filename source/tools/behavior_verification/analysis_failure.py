"""Carry underlying batch-analysis failures without disguising them as missing application methods."""
class BoundaryAnalysisFailure(ValueError):
    """An analyzer execution failure with machine-readable diagnostic context."""
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = dict(kind='boundary_analysis_inactivity', message=message, **details)
