import json
import os
from .character import Character

class GameCore:
    def __init__(self, map_config_path: str = "Configs/map/map.json"):
        self.initialized = False
        self.characters: list[Character] = []
        # Map is now a dict: location_name -> [x, y] coordinates
        self.game_map: dict[str, list[int]] = {}
        self.map_config_path = map_config_path

        # Demo-only: state-driven action availability.
        # Actions are not character skills; they are derived from current world state.
        # Key: location name -> list of allowed action names.
        # 查看地图 is available everywhere
        self.action_rules_by_location: dict[str, list[str]] = {
            "家": ["说话", "移动", "保持沉默", "睡觉", "查看地图"],
            "医院": ["说话", "移动", "保持沉默", "查看地图"],
            "小明家": ["说话", "移动", "保持沉默", "查看地图"],
            "超市": ["说话", "移动", "保持沉默", "交易", "查看地图"],
            "ATM": ["说话", "移动", "保持沉默", "查看地图"],
        }

        # Demo-only: a simple event log for postprocess results.
        self.event_log: list[dict] = []

    def load_map_from_config(self):
        """Load map from JSON config file with 2D coordinates."""
        if os.path.isabs(self.map_config_path):
            config_path = self.map_config_path
        else:
            # Relative to the project root
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.map_config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.game_map = json.load(f)

    def set_map(self):
        """Deprecated: Use load_map_from_config() instead."""
        self.load_map_from_config()

    def add_characters(self, characters: list[Character]):
        self.characters.extend(characters)

    def get_locations(self) -> list[str]:
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        return list(self.game_map.keys())
    
    def get_location_coordinates(self, location_name: str) -> list[int]:
        """Get 2D coordinates for a location.
        
        Args:
            location_name: Name of the location
            
        Returns:
            [x, y] coordinates
        """
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        if location_name not in self.game_map:
            raise KeyError(f"Location not found: {location_name}")
        return self.game_map[location_name]
    
    def has_location_at_coordinates(self, x: int, y: int) -> bool:
        """Check if a location exists at given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if a location exists at the coordinates
        """
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        for coords in self.game_map.values():
            if coords[0] == x and coords[1] == y:
                return True
        return False
    
    def get_location_name_at_coordinates(self, x: int, y: int) -> str | None:
        """Get location name at given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Location name if found, None otherwise
        """
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        for name, coords in self.game_map.items():
            if coords[0] == x and coords[1] == y:
                return name
        return None
    
    def get_map_info(self) -> dict:
        """Get map information including all locations and their coordinates.
        
        Returns:
            Dictionary with map data
        """
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        return {
            "locations": dict(self.game_map),
            "total_locations": len(self.game_map)
        }

    def get_characters(self) -> list[Character]:
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        return list(self.characters)

    def get_character_by_id(self, character_id: str) -> Character:
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        for c in self.characters:
            if c.id == character_id:
                return c
        raise KeyError(f"Character id not found: {character_id}")

    def get_character_by_name(self, character_name: str) -> Character:
        if not self.initialized:
            raise RuntimeError("GameCore is not initialized")
        for c in self.characters:
            if c.name == character_name:
                return c
        raise KeyError(f"Character name not found: {character_name}")

    def initialize(self):
        self.load_map_from_config()
        self.initialized = True