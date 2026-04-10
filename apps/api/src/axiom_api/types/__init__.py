"""Shared static types for the API layer."""

from axiom_api.types.errors import ErrorDetailBody, ErrorEnvelope
from axiom_api.types.json import JSONValue
from axiom_api.types.jwt import AccessTokenClaims

__all__ = [
    "AccessTokenClaims",
    "ErrorDetailBody",
    "ErrorEnvelope",
    "JSONValue",
]
