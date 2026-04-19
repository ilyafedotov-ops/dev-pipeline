"""
DevGodzilla Priority Queue Utilities

Priority levels for orchestration queue ordering.
Higher priority values are executed first.
"""

from enum import IntEnum
from typing import List, Any

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class Priority(IntEnum):
    """
    Priority levels for step execution ordering.
    
    Higher values indicate higher priority (executed first).
    Default priority is NORMAL (0).
    """
    LOW = -10      # Background tasks, non-urgent
    NORMAL = 0     # Default priority
    HIGH = 10      # Important tasks
    CRITICAL = 20  # Urgent, blocking issues
    URGENT = 30    # Emergency, immediate attention


DEFAULT_PRIORITY = Priority.NORMAL


def parse_priority(value: Any) -> Priority:
    """
    Parse a priority value from various input types.
    
    Args:
        value: Input value (str, int, Priority, or None)
        
    Returns:
        Priority enum value
    """
    if value is None:
        return DEFAULT_PRIORITY
    
    if isinstance(value, Priority):
        return value
    
    if isinstance(value, int):
        # Find closest priority or return custom value
        for priority in Priority:
            if priority.value == value:
                return priority
        # Return as-is for custom priority values
        return value
    
    if isinstance(value, str):
        upper_value = value.upper()
        try:
            return Priority[upper_value]
        except KeyError:
            # Try parsing as integer
            try:
                return parse_priority(int(value))
            except ValueError:
                pass
    
    return DEFAULT_PRIORITY


def sort_by_priority(items: List[Any], priority_attr: str = "priority") -> List[Any]:
    """
    Sort items by priority in descending order (highest first).
    
    Args:
        items: List of items with priority attribute
        priority_attr: Name of the priority attribute
        
    Returns:
        Sorted list (highest priority first)
    """
    def get_priority_value(item: Any) -> int:
        priority = getattr(item, priority_attr, DEFAULT_PRIORITY)
        if isinstance(priority, Priority):
            return priority.value
        if isinstance(priority, int):
            return priority
        return DEFAULT_PRIORITY
    
    return sorted(items, key=get_priority_value, reverse=True)


def sort_dicts_by_priority(
    items: List[dict],
    priority_key: str = "priority",
) -> List[dict]:
    """
    Sort dictionaries by priority in descending order (highest first).
    
    Args:
        items: List of dictionaries with priority key
        priority_key: Key for the priority value
        
    Returns:
        Sorted list (highest priority first)
    """
    def get_priority_value(item: dict) -> int:
        priority = item.get(priority_key, DEFAULT_PRIORITY)
        if isinstance(priority, Priority):
            return priority.value
        if isinstance(priority, int):
            return priority
        return DEFAULT_PRIORITY
    
    return sorted(items, key=get_priority_value, reverse=True)
