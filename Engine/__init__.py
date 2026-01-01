"""
Game Engine Package

This package contains the core game engine components:
- GameCore: Main game engine with map and character management
- GameState: State manager for active character and game rules
- Character: Character class for NPCs
- WorldLoader: Utility to load complete game worlds from configuration
"""

from Engine.core import GameCore
from Engine.state_manager import GameState
from Engine.character import Character
from Engine.world_loader import WorldLoader, load_world

__all__ = [
    'GameCore',
    'GameState', 
    'Character',
    'WorldLoader',
    'load_world',
]
