"""Report Excel export phases and throttle note/operation progress messages."""

from datetime import datetime
from time import monotonic


class ExportProgress:
    """Print timestamped progress and elapsed time without changing export results."""

    def __init__(self):
        self.started = monotonic()
        self.last_update = self.started

    def elapsed(self):
        """Return total runtime in hours, minutes and seconds."""
        seconds = int(monotonic() - self.started)
        return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'

    def phase(self, message):
        """Print a phase immediately and flush redirected or interactive console output."""
        self.last_update = monotonic()
        print(f'[{datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")}] '
              f'{message} | elapsed={self.elapsed()}', flush=True)

    def update(self, message):
        """Print ongoing work at most once every five seconds."""
        if monotonic() - self.last_update >= 5:
            self.phase(message)
