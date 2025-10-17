"""
Image optimization utilities for memory-efficient processing
"""

import io
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from PIL import Image, ImageOps
import logging
from config.memory_settings import memory_settings

logger = logging.getLogger(__name__)

class ImageOptimizer:
    """Handles image compression, resizing, and format conversion"""
    
    def __init__(self):
        self.max_size = (memory_settings.MAX_IMAGE_WIDTH, memory_settings.MAX_IMAGE_HEIGHT)
        self.quality = memory_settings.IMAGE_QUALITY
        self.max_file_size = memory_settings.get_max_image_size_bytes()
    
    def should_process_image(self, content_length: Optional[int] = None, url: str = "") -> bool:
        """
        Determine if an image should be processed based on size and type
        
        Args:
            content_length: Size of image in bytes
            url: Image URL for format detection
            
        Returns:
            bool: True if image should be processed
        """
        # Skip if too large
        if content_length and content_length > self.max_file_size:
            logger.warning(f"Skipping large image ({content_length} bytes): {url}")
            return False
        
        # Skip data URLs and already processed images
        if url.startswith('data:') or url.startswith('file:'):
            return False
        
        return True
    
    def optimize_image_stream(self, image_data: bytes, original_format: str = 'JPEG') -> Tuple[bytes, str]:
        """
        Optimize image data in memory without saving to disk
        
        Args:
            image_data: Raw image bytes
            original_format: Original image format
            
        Returns:
            Tuple of (optimized_bytes, format_used)
        """
        if not memory_settings.ENABLE_IMAGE_COMPRESSION:
            return image_data, original_format
        
        try:
            # Load image from bytes
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if needed (for WebP/JPEG compatibility)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if necessary
                if img.size[0] > self.max_size[0] or img.size[1] > self.max_size[1]:
                    img = ImageOps.fit(img, self.max_size, Image.Resampling.LANCZOS)
                    logger.debug(f"Resized image to {img.size}")
                
                # Determine output format
                output_format = 'WebP' if memory_settings.ENABLE_WEBP_CONVERSION else 'JPEG'
                
                # Save to bytes
                output_buffer = io.BytesIO()
                save_kwargs = {'format': output_format}
                
                if output_format == 'WebP':
                    save_kwargs['quality'] = self.quality
                    save_kwargs['method'] = 6  # Better compression
                elif output_format == 'JPEG':
                    save_kwargs['quality'] = self.quality
                    save_kwargs['optimize'] = True
                
                img.save(output_buffer, **save_kwargs)
                optimized_data = output_buffer.getvalue()
                
                # Log compression results
                original_size = len(image_data)
                optimized_size = len(optimized_data)
                compression_ratio = (1 - optimized_size / original_size) * 100
                
                logger.debug(f"Image compressed: {original_size} -> {optimized_size} bytes "
                           f"({compression_ratio:.1f}% reduction)")
                
                return optimized_data, output_format.lower()
                
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")
            return image_data, original_format.lower()
    
    def get_file_extension(self, format_name: str) -> str:
        """Get appropriate file extension for image format"""
        format_extensions = {
            'jpeg': '.jpg',
            'jpg': '.jpg',
            'png': '.png',
            'webp': '.webp',
            'gif': '.gif',
            'bmp': '.bmp'
        }
        return format_extensions.get(format_name.lower(), '.jpg')


class MemoryEfficientCache:
    """LRU cache with memory limits and automatic cleanup"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.cache_info = {}  # url_hash -> {'path': Path, 'size': int, 'access_time': float}
        self.total_size = 0
        self.max_size = memory_settings.get_max_cache_size_bytes()
        self.max_items = memory_settings.MAX_CACHED_IMAGES
        
    def _calculate_current_size(self) -> int:
        """Recalculate total cache size by scanning files"""
        total = 0
        valid_items = {}
        
        for url_hash, info in list(self.cache_info.items()):
            if info['path'].exists():
                size = info['path'].stat().st_size
                valid_items[url_hash] = info
                valid_items[url_hash]['size'] = size
                total += size
            else:
                # File was deleted externally
                logger.debug(f"Cache file missing: {info['path']}")
        
        self.cache_info = valid_items
        self.total_size = total
        return total
    
    def _cleanup_cache(self, target_size: Optional[int] = None):
        """Remove least recently used items to free space"""
        if not target_size:
            target_size = int(self.max_size * memory_settings.CACHE_CLEANUP_THRESHOLD)
        
        # Sort by access time (oldest first)
        items_by_access = sorted(
            self.cache_info.items(),
            key=lambda x: x[1]['access_time']
        )
        
        removed_count = 0
        removed_size = 0
        
        while (self.total_size > target_size or len(self.cache_info) > self.max_items) and items_by_access:
            url_hash, info = items_by_access.pop(0)
            
            try:
                if info['path'].exists():
                    info['path'].unlink()
                    removed_size += info['size']
                    self.total_size -= info['size']
                
                del self.cache_info[url_hash]
                removed_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to remove cached file {info['path']}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cache cleanup: removed {removed_count} files, freed {removed_size} bytes")
    
    def get_cached_path(self, url: str) -> Optional[Path]:
        """Get cached file path if exists, update access time"""
        import time
        
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        if url_hash in self.cache_info:
            info = self.cache_info[url_hash]
            if info['path'].exists():
                # Update access time
                info['access_time'] = time.time()
                return info['path']
            else:
                # File was deleted, remove from cache info
                del self.cache_info[url_hash]
        
        return None
    
    def cache_image(self, url: str, image_data: bytes, format_ext: str) -> Path:
        """Cache image data and return path"""
        import time
        
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.base_dir / f"{url_hash}{format_ext}"
        
        # Check if we need to cleanup before adding
        new_size = len(image_data)
        if self.total_size + new_size > self.max_size or len(self.cache_info) >= self.max_items:
            self._cleanup_cache()
        
        try:
            # Write to temporary file first, then move (atomic operation)
            with tempfile.NamedTemporaryFile(dir=self.base_dir, delete=False) as temp_file:
                temp_file.write(image_data)
                temp_path = Path(temp_file.name)
            
            # Move to final location
            temp_path.rename(cache_path)
            
            # Update cache info
            self.cache_info[url_hash] = {
                'path': cache_path,
                'size': new_size,
                'access_time': time.time()
            }
            self.total_size += new_size
            
            logger.debug(f"Cached image: {url_hash}{format_ext} ({new_size} bytes)")
            return cache_path
            
        except Exception as e:
            logger.error(f"Failed to cache image {url}: {e}")
            # Clean up temp file if it exists
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
            raise
    
    def clear_all(self):
        """Clear entire cache"""
        removed_count = 0
        for url_hash, info in list(self.cache_info.items()):
            try:
                if info['path'].exists():
                    info['path'].unlink()
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove cached file {info['path']}: {e}")
        
        self.cache_info.clear()
        self.total_size = 0
        logger.info(f"Cache cleared: removed {removed_count} files")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        # Recalculate to ensure accuracy
        actual_size = self._calculate_current_size()
        
        return {
            'total_files': len(self.cache_info),
            'total_size_bytes': self.total_size,
            'total_size_mb': self.total_size / (1024 * 1024),
            'max_size_mb': self.max_size / (1024 * 1024),
            'usage_percentage': (self.total_size / self.max_size) * 100 if self.max_size > 0 else 0,
            'max_files': self.max_items
        }