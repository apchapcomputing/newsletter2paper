"""
Memory management utilities for aggressive garbage collection and monitoring
"""

import gc
import psutil
import os
import sys
import logging
import weakref
from typing import Dict, Any, Optional, List, Callable
from contextlib import contextmanager
from functools import wraps
from datetime import datetime
import threading
import time

from config.memory_settings import memory_settings

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """Real-time memory usage monitoring and alerting"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.baseline_memory = self.get_memory_usage()
        self.peak_memory = self.baseline_memory
        self.measurements = []
        self._lock = threading.Lock()
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # Get system memory info
            virtual_memory = psutil.virtual_memory()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),  # Resident Set Size
                'vms_mb': memory_info.vms / (1024 * 1024),  # Virtual Memory Size
                'percent': memory_percent,
                'available_mb': virtual_memory.available / (1024 * 1024),
                'total_mb': virtual_memory.total / (1024 * 1024),
                'system_percent': virtual_memory.percent
            }
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'available_mb': 0, 'total_mb': 0, 'system_percent': 0}
    
    def record_measurement(self, operation: str = "unknown") -> Dict[str, Any]:
        """Record a memory measurement with timestamp"""
        with self._lock:
            measurement = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                **self.get_memory_usage()
            }
            
            # Update peak memory
            if measurement['rss_mb'] > self.peak_memory['rss_mb']:
                self.peak_memory = measurement.copy()
            
            # Keep only last 100 measurements
            self.measurements.append(measurement)
            if len(self.measurements) > 100:
                self.measurements.pop(0)
            
            return measurement
    
    def check_memory_thresholds(self) -> Dict[str, Any]:
        """Check if memory usage exceeds warning/critical thresholds"""
        current = self.get_memory_usage()
        
        warning_threshold = memory_settings.MEMORY_WARNING_THRESHOLD * 100
        critical_threshold = memory_settings.MEMORY_CRITICAL_THRESHOLD * 100
        
        status = "ok"
        if current['system_percent'] >= critical_threshold:
            status = "critical"
        elif current['system_percent'] >= warning_threshold:
            status = "warning"
        
        return {
            'status': status,
            'current_percent': current['system_percent'],
            'warning_threshold': warning_threshold,
            'critical_threshold': critical_threshold,
            'current_rss_mb': current['rss_mb'],
            'message': self._get_status_message(status, current)
        }
    
    def _get_status_message(self, status: str, current: Dict[str, float]) -> str:
        """Generate human-readable status message"""
        if status == "critical":
            return f"CRITICAL: Memory usage at {current['system_percent']:.1f}% ({current['rss_mb']:.1f}MB RSS)"
        elif status == "warning":
            return f"WARNING: Memory usage at {current['system_percent']:.1f}% ({current['rss_mb']:.1f}MB RSS)"
        else:
            return f"OK: Memory usage at {current['system_percent']:.1f}% ({current['rss_mb']:.1f}MB RSS)"
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Generate comprehensive memory report"""
        current = self.get_memory_usage()
        threshold_check = self.check_memory_thresholds()
        
        # Calculate memory growth since baseline
        growth_mb = current['rss_mb'] - self.baseline_memory['rss_mb']
        growth_percent = (growth_mb / self.baseline_memory['rss_mb']) * 100 if self.baseline_memory['rss_mb'] > 0 else 0
        
        return {
            'current': current,
            'baseline': self.baseline_memory,
            'peak': self.peak_memory,
            'growth_mb': growth_mb,
            'growth_percent': growth_percent,
            'status': threshold_check,
            'measurements_count': len(self.measurements),
            'gc_stats': self._get_gc_stats()
        }
    
    def _get_gc_stats(self) -> Dict[str, Any]:
        """Get garbage collection statistics"""
        try:
            return {
                'counts': gc.get_count(),
                'threshold': gc.get_threshold(),
                'stats': gc.get_stats() if hasattr(gc, 'get_stats') else None
            }
        except Exception as e:
            logger.warning(f"Failed to get GC stats: {e}")
            return {}


class MemoryManager:
    """Aggressive memory management with garbage collection"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self._cleanup_callbacks: List[Callable] = []
        self._weak_refs: List[weakref.ref] = []
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a callback to be called during memory cleanup"""
        self._cleanup_callbacks.append(callback)
    
    def add_weak_reference(self, obj: Any) -> weakref.ref:
        """Add weak reference for tracking object lifecycle"""
        weak_ref = weakref.ref(obj)
        self._weak_refs.append(weak_ref)
        return weak_ref
    
    def force_garbage_collection(self, reason: str = "manual") -> Dict[str, Any]:
        """Force aggressive garbage collection"""
        before_memory = self.monitor.get_memory_usage()
        
        # Clear dead weak references
        self._weak_refs = [ref for ref in self._weak_refs if ref() is not None]
        
        # Force garbage collection for all generations
        collected = []
        for generation in range(3):
            collected.append(gc.collect(generation))
        
        # Additional cleanup
        gc.collect()
        
        after_memory = self.monitor.get_memory_usage()
        freed_mb = before_memory['rss_mb'] - after_memory['rss_mb']
        
        result = {
            'reason': reason,
            'before_mb': before_memory['rss_mb'],
            'after_mb': after_memory['rss_mb'],
            'freed_mb': freed_mb,
            'collected_objects': sum(collected),
            'generation_counts': collected,
            'timestamp': datetime.now().isoformat()
        }
        
        if freed_mb > 1.0:  # Log if significant memory freed
            logger.info(f"GC freed {freed_mb:.1f}MB (reason: {reason})")
        
        return result
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """Perform emergency memory cleanup when critically low"""
        logger.warning("Performing emergency memory cleanup")
        
        cleanup_results = []
        
        # Call registered cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                result = callback()
                cleanup_results.append(result)
            except Exception as e:
                logger.error(f"Cleanup callback failed: {e}")
        
        # Force aggressive GC
        gc_result = self.force_garbage_collection("emergency")
        
        # Clear weak references to help with cleanup
        dead_refs = sum(1 for ref in self._weak_refs if ref() is None)
        self._weak_refs = [ref for ref in self._weak_refs if ref() is not None]
        
        return {
            'gc_result': gc_result,
            'cleanup_callbacks': len(cleanup_results),
            'dead_refs_cleared': dead_refs,
            'total_cleanup_results': cleanup_results
        }
    
    def check_and_cleanup_if_needed(self) -> Optional[Dict[str, Any]]:
        """Check memory usage and cleanup if thresholds exceeded"""
        threshold_check = self.monitor.check_memory_thresholds()
        
        if threshold_check['status'] == 'critical':
            return self.emergency_cleanup()
        elif threshold_check['status'] == 'warning':
            return self.force_garbage_collection("threshold_warning")
        
        return None


# Global memory manager instance
memory_manager = MemoryManager()


@contextmanager
def memory_managed_operation(operation_name: str = "operation", force_gc_after: bool = True):
    """
    Context manager for memory-managed operations
    
    Args:
        operation_name: Name of the operation for tracking
        force_gc_after: Whether to force garbage collection after operation
    """
    # Record memory before operation
    before_measurement = memory_manager.monitor.record_measurement(f"{operation_name}_start")
    
    try:
        yield memory_manager
    finally:
        # Clean up and record memory after operation
        if force_gc_after:
            memory_manager.force_garbage_collection(f"{operation_name}_end")
        
        after_measurement = memory_manager.monitor.record_measurement(f"{operation_name}_end")
        
        # Log if significant memory change
        memory_diff = after_measurement['rss_mb'] - before_measurement['rss_mb']
        if abs(memory_diff) > 10:  # More than 10MB change
            logger.info(f"Operation '{operation_name}' memory change: {memory_diff:+.1f}MB")


def memory_tracked(operation_name: Optional[str] = None, force_gc: bool = True):
    """
    Decorator for automatic memory tracking and cleanup
    
    Args:
        operation_name: Name for tracking (defaults to function name)
        force_gc: Whether to force garbage collection after function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with memory_managed_operation(op_name, force_gc):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class MemoryEfficientProcessor:
    """Base class for memory-efficient processing with automatic cleanup"""
    
    def __init__(self):
        self._temp_objects = []
        self.memory_manager = memory_manager
    
    def add_temp_object(self, obj: Any):
        """Add object to be cleaned up later"""
        self._temp_objects.append(obj)
    
    def cleanup_temp_objects(self):
        """Clean up temporary objects"""
        cleaned_count = 0
        for obj in self._temp_objects:
            try:
                if hasattr(obj, 'close'):
                    obj.close()
                elif hasattr(obj, 'cleanup'):
                    obj.cleanup()
                del obj
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup object: {e}")
        
        self._temp_objects.clear()
        return cleaned_count
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_temp_objects()
        self.memory_manager.force_garbage_collection("processor_cleanup")


def get_memory_stats() -> Dict[str, Any]:
    """Get comprehensive memory statistics"""
    return memory_manager.monitor.get_memory_report()


def cleanup_memory(force: bool = False) -> Dict[str, Any]:
    """Manual memory cleanup function"""
    if force:
        return memory_manager.emergency_cleanup()
    else:
        return memory_manager.force_garbage_collection("manual_cleanup")