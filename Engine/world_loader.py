"""
World Loader - Initializes the game world from configuration files.

This module handles the "boot" process of loading maps, characters,
and setting up the initial game state from config files.
"""

import json
from typing import Optional
from Engine.core import GameCore
from Engine.state_manager import GameState
from Engine.character import Character


class WorldLoader:
    """Loads and initializes a game world from configuration."""
    
    def __init__(self, world_config_path: str = "Configs/world_setup.json"):
        """
        Initialize the world loader.
        
        Args:
            world_config_path: Path to the world setup configuration file
        """
        self.world_config_path = world_config_path
        self.world_config: dict = {}
        self.game_core: Optional[GameCore] = None
        self.game_state: Optional[GameState] = None
        self.characters: list[Character] = []
    
    def load_world_config(self) -> dict:
        """Load the world setup configuration file.
        
        Returns:
            Dictionary containing world configuration
        """
        with open(self.world_config_path, 'r', encoding='utf-8') as f:
            self.world_config = json.load(f)
        return self.world_config
    
    def initialize_game_core(self) -> GameCore:
        """Initialize the game core with the map from config.
        
        Returns:
            Initialized GameCore instance
        """
        map_config_path = self.world_config.get('map_config', 'Configs/map/map.json')
        self.game_core = GameCore(map_config_path=map_config_path)
        self.game_core.initialize()
        return self.game_core
    
    def load_characters(self) -> list[Character]:
        """Load all characters specified in the world config.
        
        Returns:
            List of loaded Character instances
        """
        character_configs = self.world_config.get('characters', [])
        self.characters = []
        
        for char_config in character_configs:
            config_path = char_config.get('config_path')
            if not config_path:
                print(f"Warning: Character config missing 'config_path': {char_config}")
                continue
            
            try:
                character = Character(config_path)
                self.characters.append(character)
                print(f"Loaded character: {character.name} (ID: {character.id}) at {character.current_location}")
            except Exception as e:
                print(f"Error loading character from {config_path}: {e}")
        
        return self.characters
    
    def setup_game_state(self) -> GameState:
        """Create and initialize the game state.
        
        Returns:
            Initialized GameState instance
        """
        if self.game_core is None:
            raise RuntimeError("GameCore must be initialized before setting up GameState")
        
        # Add all loaded characters to the game core
        self.game_core.add_characters(self.characters)
        
        # Create game state
        self.game_state = GameState(self.game_core)
        
        return self.game_state
    
    def load_world(self) -> tuple[GameCore, GameState, list[Character]]:
        """Complete world loading process.
        
        This is the main entry point that handles the full initialization:
        1. Load world configuration
        2. Initialize game core and map
        3. Load and spawn all characters
        4. Set up game state
        
        Returns:
            Tuple of (GameCore, GameState, list of Characters)
        """
        print(f"Loading world from: {self.world_config_path}")
        
        # Step 1: Load world config
        config = self.load_world_config()
        print(f"World: {config.get('world_name', 'Unnamed')}")
        
        # Step 2: Initialize game core with map
        game_core = self.initialize_game_core()
        print(f"Map loaded with {len(game_core.game_map)} locations")
        
        # Step 3: Load characters
        characters = self.load_characters()
        print(f"Loaded {len(characters)} characters")
        
        # Step 4: Setup game state
        game_state = self.setup_game_state()
        print("Game state initialized")
        
        print("World loading complete!")
        return game_core, game_state, characters


def load_world(world_config_path: str = "Configs/world_setup.json") -> tuple[GameCore, GameState, list[Character]]:
    """Convenience function to load a world.
    
    Args:
        world_config_path: Path to the world setup configuration file
        
    Returns:
        Tuple of (GameCore, GameState, list of Characters)
    """
    loader = WorldLoader(world_config_path)
    return loader.load_world()


# Example usage
if __name__ == "__main__":
    game_core, game_state, characters = load_world()
    
    print("\n=== World Status ===")
    print(f"Locations: {game_core.get_locations()}")
    print("\nCharacters:")
    for char in characters:
        print(f"  - {char.name} at {char.current_location}")
