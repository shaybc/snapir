"""Read manifest arrays incrementally using only Python's standard library."""

import json


class _ManifestJsonReader:
    """Buffer at most one JSON value plus an input chunk, rather than the whole manifest."""

    def __init__(self, stream):
        self.stream = stream
        self.buffer = ''
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def _fill(self):
        chunk = self.stream.read(65536)
        self.buffer = self.buffer[self.position:] + chunk
        self.position = 0
        self.eof = not chunk

    def peek(self):
        """Return the next non-whitespace character, or an empty string at EOF."""
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position] in ' \t\r\n':
                self.position += 1
            if self.position < len(self.buffer):
                return self.buffer[self.position]
            if self.eof:
                return ''
            self._fill()

    def take(self, expected):
        """Consume required JSON punctuation or reject malformed input."""
        if self.peek() != expected:
            raise ValueError('Invalid scoped manifest JSON: expected ' + expected)
        self.position += 1

    def value(self):
        """Decode one value, extending the buffer only when that value spans chunks."""
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self._fill()
                continue
            if end == len(self.buffer) and not self.eof:
                self._fill()
                continue
            if end < len(self.buffer) and self.buffer[end] not in ',]}: \t\r\n':
                if self.eof:
                    raise ValueError('Invalid scoped manifest JSON value')
                self._fill()
                continue
            self.position = end
            return value


def iter_manifest_fields(path):
    """Yield field, event and value; entities/diagnostics arrays yield one item at a time.

    The stream is closed on completion or failure. Invalid/truncated JSON raises ValueError.
    Other fields and individual array items retain their ordinary JSON representation.
    """
    with path.open('r', encoding='utf-8-sig') as stream:
        reader = _ManifestJsonReader(stream)
        reader.take('{')
        if reader.peek() != '}':
            while True:
                name = reader.value()
                if not isinstance(name, str):
                    raise ValueError('Invalid scoped manifest JSON field')
                reader.take(':')
                if name in ('entities', 'diagnostics') and reader.peek() == '[':
                    reader.take('[')
                    yield name, 'array', None
                    if reader.peek() != ']':
                        while True:
                            yield name, 'item', reader.value()
                            if reader.peek() != ',':
                                break
                            reader.take(',')
                    reader.take(']')
                else:
                    yield name, 'value', reader.value()
                if reader.peek() != ',':
                    break
                reader.take(',')
        reader.take('}')
        if reader.peek():
            raise ValueError('Invalid scoped manifest JSON: trailing content')
