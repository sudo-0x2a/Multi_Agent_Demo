import json
import os
from .character import Character
from .item import Item

class GameCore:
    """
    The central authority for the simulation world state and rules.
    
    Responsibilities:
    - Managing the world map and location coordinates.
    - Maintaining the list of active characters.
    - Managing items placed at locations.
    - Governing action availability based on environmental rules.
    - Providing a central event log for all world activities.
    """
    
    def __init__(self, map_config_path: str = "Configs/map/map.json"):
        self.initialized = False
        self.characters: list[Character] = []
        self.items: list[Item] = []
        
        # World Map: A mapping of location names to their [x, y] grid coordinates.
        self.game_map: dict[str, list[int]] = {}
        self.map_config_path = map_config_path

        # Action Availability Rules:
        # Defines which actions are theoretically possible at each location.
        # This is a static world rule set used to filter agent options.
        self.action_rules_by_location: dict[str, list[str]] = {
            "家": ["说话", "移动", "保持沉默", "睡觉", "查看地图"],
            "医院": ["说话", "移动", "保持沉默", "查看地图"],
            "小明家": ["说话", "移动", "保持沉默", "查看地图"],
            "超市": ["说话", "移动", "保持沉默", "交易", "查看地图"],
            "ATM": ["说话", "移动", "保持沉默", "查看地图"],
        }

        # Central Event log: A chronologically ordered list of every action taken in the world.
        self.event_log: list[dict] = []

    def load_map_from_config(self):
        """
        Loads the map geometry from a JSON configuration file.
        Resolves the path relative to the project root.
        """
        if os.path.isabs(self.map_config_path):
            config_path = self.map_config_path
        else:
            # Resolved relative to the parent directory of this file (Engine/)
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.map_config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.game_map = json.load(f)

    def set_map(self):
        """Deprecated: Retained for backward compatibility. Use load_map_from_config()."""
        self.load_map_from_config()

    def add_characters(self, characters: list[Character]):
        """Registers a list of character instances with the game engine."""
        self.characters.extend(characters)

    def add_items(self, items: list[Item]):
        """Registers a list of item instances with the game engine."""
        self.items.extend(items)

    def get_items_at_location(self, location: str) -> list[Item]:
        """Returns all items placed at the specified location."""
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        return [item for item in self.items if item.location == location]

    def get_locations(self) -> list[str]:
        """Returns a list of all defined location names in the world."""
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        return list(self.game_map.keys())
    
    def get_location_coordinates(self, location_name: str) -> list[int]:
        """
        Retrieves the [x, y] coordinates for a given location name.
        """
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        if location_name not in self.game_map:
            raise KeyError(f"Location '{location_name}' is not defined in the world map.")
        return self.game_map[location_name]
    
    def has_location_at_coordinates(self, x: int, y: int) -> bool:
        """
        Checks if any location exists at the specified grid coordinates.
        """
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        for coords in self.game_map.values():
            if coords[0] == x and coords[1] == y:
                return True
        return False
    
    def get_location_name_at_coordinates(self, x: int, y: int) -> str | None:
        """
        Returns the name of the location at the given coordinates, or None if empty.
        """
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        for name, coords in self.game_map.items():
            if coords[0] == x and coords[1] == y:
                return name
        return None
    
    def get_map_info(self) -> dict:
        """
        Provides a comprehensive summary of the world map structure.
        """
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        return {
            "locations": dict(self.game_map),
            "total_locations": len(self.game_map)
        }

    def get_characters(self) -> list[Character]:
        """Returns all characters currently active in the simulation."""
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        return list(self.characters)

    def get_character_by_id(self, character_id: str) -> Character:
        """Locates a character by their unique ID."""
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        for c in self.characters:
            if c.id == character_id:
                return c
        raise KeyError(f"No character found with ID: {character_id}")

    def get_character_by_name(self, character_name: str) -> Character:
        """Locates a character by their display name."""
        if not self.initialized:
            raise RuntimeError("GameCore must be initialized before accessing world data.")
        for c in self.characters:
            if c.name == character_name:
                return c
        raise KeyError(f"No character found with name: {character_name}")

    def initialize(self):
        """
        Perform internal setup required to make the GameCore operational.
        """
        self.load_map_from_config()
        self.initialized = True