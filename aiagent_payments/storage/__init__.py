from aiagent_payments.config import ENABLED_STORAGE

from .base import StorageBackend
from .database import DatabaseStorage
from .file import FileStorage
from .memory import MemoryStorage

__all__ = ["StorageBackend"]

if "memory" in ENABLED_STORAGE:
    __all__.append("MemoryStorage")
if "file" in ENABLED_STORAGE:
    __all__.append("FileStorage")
if "database" in ENABLED_STORAGE:
    __all__.append("DatabaseStorage")

# Remove disabled backends from module namespace
globals_ = globals()
if "memory" not in ENABLED_STORAGE and "MemoryStorage" in globals_:
    del globals_["MemoryStorage"]
if "file" not in ENABLED_STORAGE and "FileStorage" in globals_:
    del globals_["FileStorage"]
if "database" not in ENABLED_STORAGE and "DatabaseStorage" in globals_:
    del globals_["DatabaseStorage"]
