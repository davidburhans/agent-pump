"""System utilities."""

import shutil
from functools import lru_cache

# Cache up to 32 lookups
cached_which = lru_cache(maxsize=32)(shutil.which)
