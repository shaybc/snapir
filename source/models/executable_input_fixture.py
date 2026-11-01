"""Unit-scoped controlled inputs/replays; no business-output expectations are accepted."""
from pydantic import field_validator
from models.boundary_case import BoundaryCase


class ExecutableInputFixture(BoundaryCase):
    """Reuse the same logical input, clock, seed and replay responses on both JVM sides."""
    @field_validator('clock_millis','random_seed')
    @classmethod
    def validate_runtime_long(cls,value):
        if not -(2**63)<=value<2**63:raise ValueError('Runtime controls require a Java long value')
        return value

    @field_validator('external_responses')
    @classmethod
    def validate_replays(cls,responses):
        for response in responses:
            allowed={'target','arguments','value','exception_type','message'}
            if (set(response)-allowed or not isinstance(response.get('target'),str) or not response['target']
                or not isinstance(response.get('arguments'),list)
                or ('value' in response)==('exception_type' in response)):
                raise ValueError('Replay needs target, arguments and exactly one value or exception_type')
            if 'exception_type' in response and (not isinstance(response['exception_type'],str) or not response['exception_type'].strip()):raise ValueError('Replay exception_type must be a nonblank string')
            if 'message' in response and ('exception_type' not in response or not isinstance(response['message'],str)):
                raise ValueError('Replay messages require an exception_type and string content')
        return responses
