"""
Global lock manager for backend instances to ensure concurrency limits.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict

logger = logging.getLogger(__name__)


class BackendLockManager:
    """
    Manages named locks/semaphores for backend configurations.
    
    This ensures that only N instances of a specific backend configuration 
    run simultaneously across the entire application (all projects).
    """
    
    _semaphores: Dict[str, asyncio.Semaphore] = {}
    _locks: Dict[str, asyncio.Lock] = {}
    _counts: Dict[str, int] = defaultdict(int)

    @classmethod
    def get_lock(cls, key: str, limit: int = 1) -> asyncio.Semaphore | asyncio.Lock:
        """
        Get a concurrency primitive for the given key and limit.
        
        Args:
            key: Unique identifier for the backend configuration
            limit: Maximum concurrent instances (1 = Mutex Lock)
            
        Returns:
            An asyncio.Semaphore or asyncio.Lock
        """
        # If limit is 1, prefer Lock for strict key exclusivity (and potential performance/debugging benefits)
        # But Semaphore(1) is functionally similar. Lock is often reentrant-safe in some frameworks, 
        # but asyncio.Lock is not reentrant.
        
        if limit <= 1:
            if key not in cls._locks:
                logger.debug(f"Creating new backend lock for key: {key}")
                cls._locks[key] = asyncio.Lock()
            return cls._locks[key]
        else:
            if key not in cls._semaphores:
                logger.debug(f"Creating new backend semaphore (limit={limit}) for key: {key}")
                cls._semaphores[key] = asyncio.Semaphore(limit)
            
            # Note: We don't dynamically update the limit of an existing semaphore 
            # if the config changes during runtime. A restart would be needed or 
            # more complex logic. For now, first creation wins.
            return cls._semaphores[key]

    @classmethod
    async def acquire(cls, key: str, limit: int = 1):
        """Helper to acquire lock context."""
        lock = cls.get_lock(key, limit)
        await lock.acquire()
        cls._counts[key] += 1
        logger.debug(f"Acquired backend lock for {key} (Active: {cls._counts[key]})")

    @classmethod
    def release(cls, key: str, limit: int = 1):
        """Helper to release lock."""
        lock = cls.get_lock(key, limit)
        lock.release()
        cls._counts[key] -= 1
        logger.debug(f"Released backend lock for {key} (Active: {cls._counts[key]})")
