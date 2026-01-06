"""
Multi-Agent Simulation - World Loader

This module manages the instantiation and bootstrap process of the simulation.
It coordinates the reading of configuration files to build the GameCore,
spawn characters, and initialize the GameState.
"""

import json
from typing import Optional
from Engine.core import GameCore
from Engine.state_manager import GameState
from Engine.character import Character


class WorldLoader:
    """
    Orchestrates the loading of a simulation environment from structured JSON configurations.
    """
    
    def __init__(self, world_config_path: str = "Configs/world_setup.json"):
        """
        Args:
            world_config_path: Path to the master world setup file.
        """
        self.world_config_path = world_config_path
        self.world_config: dict = {}
        self.game_core: Optional[GameCore] = None
        self.game_state: Optional[GameState] = None
        self.characters: list[Character] = []
    
    def load_world_config(self) -> dict:
        """
        Reads the primary configuration file from disk.
        """
        with open(self.world_config_path, 'r', encoding='utf-8') as f:
            self.world_config = json.load(f)
        return self.world_config
    
    def initialize_game_core(self) -> GameCore:
        """
        Instantiates the GameCore and initializes the map geometry.
        """
        map_path = self.world_config.get('map_config', 'Configs/map/map.json')
        self.game_core = GameCore(map_config_path=map_path)
        self.game_core.initialize()
        return self.game_core
    
    def load_characters(self) -> list[Character]:
        """
        Instantiates characters based on the registry in the world config.
        """
        character_configs = self.world_config.get('characters', [])
        self.characters = []
        
        for char_entry in character_configs:
            path = char_entry.get('config_path')
            if not path:
                print(f"Boot Warning: Character entry is missing 'config_path'. Skipping entry: {char_entry}")
                continue
            
            try:
                character = Character(path)
                self.characters.append(character)
                print(f"✓ Character Spawning: {character.name} (UID: {character.id}) at {character.current_location}")
            except Exception as e:
                print(f"❌ Spawning Error: Failed to load character at {path}. Error: {e}")
        
        return self.characters
    
    def setup_game_state(self) -> GameState:
        """
        Finalizes initialization by registering characters with the core and creating the GameState.
        """
        if self.game_core is None:
            raise RuntimeError("Sequence Error: GameCore must be initialized before GameState.")
        
        # Merge characters into the engine's registry
        self.game_core.add_characters(self.characters)
        
        # Instantiate the state manager
        self.game_state = GameState(self.game_core)
        
        return self.game_state
    
    def load_world(self) -> tuple[GameCore, GameState, list[Character]]:
        """
        Executes the full automated boot sequence.
        
        Workflow:
        1. Parse world configuration mapping.
        2. Resolve and load map geometry.
        3. Instantiate and register all characters.
        4. Initialize the interaction state manager.
        
        Returns:
            Tuple: (GameCore, GameState, list[Character])
        """
        print(f"Initiating boot sequence from: {self.world_config_path}")
        
        config = self.load_world_config()
        print(f"Current World: {config.get('world_name', 'Simulation Alpha')}")
        
        game_core = self.initialize_game_core()
        print(f"Map resolution complete. {len(game_core.game_map)} locations indexed.")
        
        characters = self.load_characters()
        print(f"Lifeform population complete. {len(characters)} entities online.")
        
        game_state = self.setup_game_state()
        print("System Phase: GameState operational.")
        
        print("Simulation environment is READY.")
        return game_core, game_state, characters


def load_world(world_config_path: str = "Configs/world_setup.json") -> tuple[GameCore, GameState, list[Character]]:
    """
    Convenience wrapper to quickly boot the simulation using a functional interface.
    """
    loader = WorldLoader(world_config_path)
    return loader.load_world()


# --- CLI Test Interface ---
if __name__ == "__main__":
    game_core, game_state, characters = load_world()
    
    print("\n[ ENVIROMENT STATUS ]")
    print(f"Physical Clusters: {game_core.get_locations()}")
    print("\n[ ENTITY MANIFEST ]")
    for char in characters:
        print(f"  • {char.name:<10} Location: {char.current_location}")
