from .core import GameCore
from .character import Character

class GameState:
    def __init__(self, game: GameCore):
        self.game = game
        self._active_character_name: str | None = None

    def set_active_character(self, character_name: str) -> None:
        # Validate existence early (strict behavior).
        self.game.get_character_by_name(character_name)
        self._active_character_name = character_name

    @property
    def active_character(self) -> Character:
        if self._active_character_name is None:
            raise RuntimeError("Active character is not set")
        return self.game.get_character_by_name(self._active_character_name)

    def get_characters_options(self) -> list[str]:
        """Return target character names available to the active character.

        Demo rule: only characters in the same location, excluding self.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError("Active character has no current_location")

        options: list[str] = []
        for c in self.game.get_characters():
            if c.id == actor.id:
                continue
            if c.current_location != actor.current_location:
                continue
            options.append(c.name)
        return options

    def get_location_options(self) -> list[str]:
        """Return destination location names for the active character."""
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError("Active character has no current_location")

        locations = self.game.get_locations()
        options = [loc for loc in locations if loc != actor.current_location]
        return options
    
    def get_direction_options(self) -> list[str]:
        """Return available movement directions based on current location and map boundaries.
        
        Checks which directions (上/下/左/右) have valid locations to move to.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError("Active character has no current_location")
        
        current_coords = self.game.get_location_coordinates(actor.current_location)
        x, y = current_coords[0], current_coords[1]
        
        # Define direction mappings: direction -> coordinate change
        directions = {
            "上": (0, 1),   # Moving up increases y
            "下": (0, -1),  # Moving down decreases y
            "左": (-1, 0),  # Moving left decreases x
            "右": (1, 0),   # Moving right increases x
        }
        
        available_directions = []
        for direction, (dx, dy) in directions.items():
            new_x, new_y = x + dx, y + dy
            # Check if there's a location at the new coordinates
            if self.game.has_location_at_coordinates(new_x, new_y):
                available_directions.append(direction)
        
        return available_directions

    def get_action_options(self) -> list[str]:
        """Return action names allowed given the current state.

        Demo rule: allowed actions are derived solely from the actor's current location.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError("Active character has no current_location")

        return list(self.game.action_rules_by_location[actor.current_location])

    def apply_action(self, structured_output: dict) -> str:
        """Apply a structured action output for the active character.

        Expected shape:
            {"action": <str>, "args": <dict>}
        
        Returns:
            str: Feedback message describing the result of the action
        """
        actor = self.active_character
        if not isinstance(structured_output, dict):
            raise TypeError("structured_output must be a dict")
        action = structured_output["action"]
        args = structured_output["args"]
        if not isinstance(args, dict):
            raise TypeError("structured_output['args'] must be a dict")

        allowed_actions = self.get_action_options()
        if action not in allowed_actions:
            raise ValueError(f"Action not allowed in current state: {action}")

        if action == "移动":
            direction = args["方向"]
            if direction not in self.get_direction_options():
                raise ValueError(f"Invalid move direction: {direction}")
            
            # Calculate new location based on direction
            current_coords = self.game.get_location_coordinates(actor.current_location)
            x, y = current_coords[0], current_coords[1]
            
            direction_mapping = {
                "上": (0, 1),
                "下": (0, -1),
                "左": (-1, 0),
                "右": (1, 0),
            }
            dx, dy = direction_mapping[direction]
            new_x, new_y = x + dx, y + dy
            
            # Find location name at new coordinates
            new_location = self.game.get_location_name_at_coordinates(new_x, new_y)
            if new_location is None:
                raise ValueError(f"No location found at coordinates ({new_x}, {new_y})")
            
            actor.move(new_location)
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "new_location": new_location})
            return f"你成功移动到了{new_location}"

        if action in {"说话", "交易"}:
            target = args["目标"]
            if target not in self.get_characters_options():
                raise ValueError(f"Invalid target character: {target}")
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            if action == "说话":
                content = args.get("内容", "")
                return f"你对{target}说：{content}"
            else:
                return f"你与{target}进行了交易"
        
        if action == "查看地图":
            # Return map information to the actor
            map_info = self.game.get_map_info()
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "map_info": map_info})
            locations_list = ", ".join([f"{name}(坐标{coords})" for name, coords in map_info["locations"].items()])
            return f"地图信息：共有{map_info['total_locations']}个地点 - {locations_list}"

        if action in {"保持沉默", "睡觉"}:
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return "你选择了保持沉默" if action == "保持沉默" else "你睡了一觉"

        raise KeyError(f"Unknown action: {action}")