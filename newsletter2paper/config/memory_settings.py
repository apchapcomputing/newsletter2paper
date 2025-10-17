"""
Memory optimization configuration settings
"""

import os
from typing import Optional

class MemorySettings:
    """Configuration for memory optimization features"""
    
    # Image processing limits
    MAX_IMAGE_SIZE_MB: float = float(os.getenv('MAX_IMAGE_SIZE_MB', '2.0'))
    MAX_IMAGE_WIDTH: int = int(os.getenv('MAX_IMAGE_WIDTH', '800'))
    MAX_IMAGE_HEIGHT: int = int(os.getenv('MAX_IMAGE_HEIGHT', '600'))
    IMAGE_QUALITY: int = int(os.getenv('IMAGE_QUALITY', '80'))
    
    # Cache settings
    MAX_CACHE_SIZE_MB: float = float(os.getenv('MAX_CACHE_SIZE_MB', '100.0'))
    MAX_CACHED_IMAGES: int = int(os.getenv('MAX_CACHED_IMAGES', '50'))
    CACHE_CLEANUP_THRESHOLD: float = float(os.getenv('CACHE_CLEANUP_THRESHOLD', '0.8'))
    
    # Memory monitoring
    MEMORY_WARNING_THRESHOLD: float = float(os.getenv('MEMORY_WARNING_THRESHOLD', '0.8'))
    MEMORY_CRITICAL_THRESHOLD: float = float(os.getenv('MEMORY_CRITICAL_THRESHOLD', '0.9'))
    
    # Processing limits
    MAX_ARTICLE_LENGTH: int = int(os.getenv('MAX_ARTICLE_LENGTH', '50000'))
    ENABLE_IMAGE_COMPRESSION: bool = os.getenv('ENABLE_IMAGE_COMPRESSION', 'true').lower() == 'true'
    ENABLE_WEBP_CONVERSION: bool = os.getenv('ENABLE_WEBP_CONVERSION', 'true').lower() == 'true'
    
    @classmethod
    def get_max_image_size_bytes(cls) -> int:
        """Get maximum image size in bytes"""
        return int(cls.MAX_IMAGE_SIZE_MB * 1024 * 1024)
    
    @classmethod
    def get_max_cache_size_bytes(cls) -> int:
        """Get maximum cache size in bytes"""
        return int(cls.MAX_CACHE_SIZE_MB * 1024 * 1024)

# Global settings instance
memory_settings = MemorySettings()