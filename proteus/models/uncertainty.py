"""Explicit uncertainty and epistemic status representations.

Architecture invariant (Contract Section 3):
The system must explicitly represent:
- UNKNOWN
- UNAVAILABLE
- AMBIGUOUS
- NOT_OBSERVED
- CANNOT_SAFELY_DETERMINE
These must never be silently converted into false, zero, or unchanged.
"""

from enum import StrEnum


class UncertaintyState(StrEnum):
    """Explicit epistemological states for unresolved or ambiguous evidence."""

    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_OBSERVED = "NOT_OBSERVED"
    CANNOT_SAFELY_DETERMINE = "CANNOT_SAFELY_DETERMINE"
