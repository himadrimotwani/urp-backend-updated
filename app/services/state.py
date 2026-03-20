"""
Shared game state storage.
"""

from typing import Dict
from simulation.core import GameState

# Global session storage - all game sessions are stored here
SESSIONS: Dict[str, GameState] = {}

