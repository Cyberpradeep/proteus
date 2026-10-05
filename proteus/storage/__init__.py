"""Storage layer for PROTEUS artifacts."""

from proteus.storage.database import Database
from proteus.storage.schema import SCHEMA_DDL

__all__ = ["Database", "SCHEMA_DDL"]
