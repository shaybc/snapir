"""Stream prepared-unit metadata without materializing embedded Java source strings."""

import json


FIELDS = {'unit_id', 'kind', 'logical_id', 'occurrence_id', 'source_definition_id',
          'effective_configuration', 'attributes', 'id', 'implClass',
          'resolved_implementation', 'implementation_mapping_key'}


class UnitReader:
    """Project selected unit fields from a JSON stream using bounded read buffers."""

    def __init__(self, stream, wanted):
        self.stream, self.wanted = stream, wanted
        self.buffer, self.position, self.units = '', 0, {}

    def peek(self):
        if self.position == len(self.buffer):
            self.buffer, self.position = self.stream.read(65536), 0
        return self.buffer[self.position:self.position + 1]

    def take(self):
        character = self.peek()
        self.position += bool(character)
        return character

    def whitespace(self):
        while self.peek() and self.peek().isspace():
            self.take()

    def string(self, keep):
        if self.take() != '"':
            raise ValueError('Expected JSON string')
        parts, escaped = ['"'] if keep else [], False
        while True:
            character = self.take()
            if not character:
                raise ValueError('Truncated JSON string')
            if keep:
                parts.append(character)
            if character == '"' and not escaped:
                return json.loads(''.join(parts)) if keep else None
            escaped = character == '\\' and not escaped

    def value(self, keep=False, depth=0):
        if depth > 160:
            raise ValueError('JSON nesting exceeds diagnostic limit')
        self.whitespace()
        character = self.peek()
        if character == '"':
            return self.string(keep)
        if character in ('{', '['):
            self.take()
            closing = '}' if character == '{' else ']'
            result = {}
            self.whitespace()
            if self.peek() == closing:
                self.take()
                return result if character == '{' else None
            while True:
                self.whitespace()
                if character == '{':
                    key = self.string(True)
                    self.whitespace()
                    if self.take() != ':':
                        raise ValueError('Expected JSON colon')
                    value = self.value(key in FIELDS, depth + 1)
                    if key in FIELDS:
                        result[key] = value
                else:
                    self.value(False, depth + 1)
                self.whitespace()
                delimiter = self.take()
                if delimiter == closing:
                    break
                if delimiter != ',':
                    raise ValueError('Incomplete JSON container')
            if character == '{' and result.get('unit_id') in self.wanted and 'effective_configuration' in result:
                identity = result['unit_id']
                if identity in self.units and self.units[identity] != result:
                    raise ValueError('Conflicting prepared records for one unit')
                self.units[identity] = result
            return result if keep else None
        parts = []
        while self.peek() and self.peek() not in ',]} \r\n\t':
            character = self.take()
            if keep:
                parts.append(character)
        if not parts and keep or not character:
            raise ValueError('Missing JSON value')
        return json.loads(''.join(parts)) if keep else None


def read_prepared_units(path, wanted):
    """Read only diagnostic unit metadata; never return source or configuration values."""
    with path.open(encoding='utf-8-sig') as stream:
        reader = UnitReader(stream, set(wanted))
        reader.value()
        reader.whitespace()
        if reader.peek():
            raise ValueError('Unexpected trailing JSON data')
        return reader.units
