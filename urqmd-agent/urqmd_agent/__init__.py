"""UrQMD-Agent: deterministic microscopic reaction-history layer for UrQMD 4.0.

This package parses UrQMD file15 collision-history output into a temporal
bipartite reaction graph (particle-state -> interaction -> particle-state).
It contains no physics model assumptions of its own: the ground truth is the
UrQMD 4.0 source-verified file15 format (see docs/history_format.md and
phase0/source_map.md).
"""

__version__ = "0.0.0-phase0b"
