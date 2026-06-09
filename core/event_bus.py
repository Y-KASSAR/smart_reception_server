"""
Event Bus
=========
Simple synchronous pub/sub event system for decoupled module communication.

Usage:
    from core.event_bus import event_bus

    # Subscribe
    event_bus.subscribe("face_recognized", my_handler)

    # Publish
    event_bus.publish("face_recognized", guest_id=1, confidence=0.95)
"""
from typing import Callable, Dict, List, Any, Optional
from config.logging_config import get_logger

logger = get_logger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    def publish(self, event_type: str, **kwargs: Any) -> None:
        handlers = self._subscribers.get(event_type, [])
        logger.debug(f"Publishing '{event_type}' to {len(handlers)} subscriber(s)")
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f"Handler {handler.__name__} failed for event '{event_type}': {e}", exc_info=True)

    def clear(self, event_type: Optional[str] = None) -> None:
        if event_type:
            self._subscribers.pop(event_type, None)
        else:
            self._subscribers.clear()


event_bus = EventBus()
