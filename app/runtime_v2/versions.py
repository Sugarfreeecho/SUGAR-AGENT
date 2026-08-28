"""Persistent Runtime V2 format and projection versions.

Changing a fact schema requires an explicit compatibility decision in
``RuntimeEvent.from_dict``.  Projection/index versions may be bumped whenever
their derived representation changes; stale caches will then rebuild from the
event log.
"""

EVENT_SCHEMA_VERSION = 1
PROJECTOR_VERSION = 6
UI_PROJECTION_INDEX_VERSION = 5
SEQ_OFFSET_INDEX_VERSION = 2
