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

        Demo rule: allowed actions are derived from the actor's current location,
        but modified by their current activity status.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError("Active character has no current_location")

        # If actor is busy, they have specific options
        if actor.activity_status == "TALKING":
            return ["说话", "结束说话", "查看地图"]
        elif actor.activity_status == "MOVING":
            return ["移动", "结束移动", "查看地图"]

        # Default options from location
        base_actions = list(self.game.action_rules_by_location[actor.current_location])
        
        # Remap legacy names to start/stop variants
        remapped_actions = []
        for action in base_actions:
            if action == "说话":
                remapped_actions.append("开始说话")
            elif action == "移动":
                remapped_actions.append("开始移动")
            else:
                remapped_actions.append(action)
        return remapped_actions

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
            # Fallback for legacy actions if they were somehow triggered
            if action == "说话": action = "开始说话"
            elif action == "移动": action = "开始移动"
            
            if action not in allowed_actions:
                raise ValueError(f"Action not allowed in current state: {action}")

        # --- Continuous Action Handlers ---
        
        if action == "开始说话":
            target = args["目标"]
            if target not in self.get_characters_options():
                raise ValueError(f"Invalid target character: {target}")
            
            actor.activity_status = "TALKING"
            actor.activity_data = {"target": target}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你进入了与{target}的对话模式。请等待对方回应，或使用'说话'继续发送。"

        if action == "说话":
            target = actor.activity_data.get("target")
            content = args.get("内容", "")
            # Log with target_override so system feedback can pick it up
            self.game.event_log.append({
                "actor": actor.name, 
                "action": action, 
                "args": args,
                "target_override": target
            })
            return ""

        if action == "结束说话":
            target = actor.activity_data.get("target")
            actor.activity_status = "IDLE"
            actor.activity_data = {}
            self.game.event_log.append({
                "actor": actor.name, 
                "action": action, 
                "args": args,
                "target_override": target
            })
            return f"你结束了与{target}的对话"

        if action == "开始移动":
            actor.activity_status = "MOVING"
            actor.activity_data = {}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你进入了移动模式。请使用'移动'指令进行移动，或使'结束移动'退出模式。"

        if action == "移动":
            direction = args["方向"]
            if direction not in self.get_direction_options():
                raise ValueError(f"Invalid move direction: {direction}")
            
            # Calculate new location based on direction and move immediately
            current_coords = self.game.get_location_coordinates(actor.current_location)
            x, y = current_coords[0], current_coords[1]
            
            direction_mapping = {"上": (0, 1), "下": (0, -1), "左": (-1, 0), "右": (1, 0)}
            dx, dy = direction_mapping[direction]
            new_x, new_y = x + dx, y + dy
            
            new_location = self.game.get_location_name_at_coordinates(new_x, new_y)
            if new_location is None:
                raise ValueError(f"No location found at coordinates ({new_x}, {new_y})")
            
            # Move the character immediately
            actor.move(new_location)
            # Update destination in activity data so we can report it on exit if needed (optional)
            actor.activity_data["last_destination"] = new_location
            
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "new_location": new_location})
            return f"你向{direction}移动，到达了{new_location}"

        if action == "结束移动":
            last_destination = actor.activity_data.get("last_destination", actor.current_location)
            actor.activity_status = "IDLE"
            actor.activity_data = {}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你结束了移动模式，当前位置：{last_destination}"

        # --- Discrete Action Handlers ---

        if action == "交易":
            target = args["目标"]
            if target not in self.get_characters_options():
                raise ValueError(f"Invalid target character: {target}")
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你与{target}进行了交易"
        
        if action == "查看地图":
            map_info = self.game.get_map_info()
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "map_info": map_info})
            locations_list = ", ".join([f"{name}(坐标{coords})" for name, coords in map_info["locations"].items()])
            return f"地图信息：共有{map_info['total_locations']}个地点 - {locations_list}"

        if action in {"保持沉默", "睡觉"}:
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return "你选择了保持沉默" if action == "保持沉默" else "你睡了一觉"

        raise KeyError(f"Unknown action: {action}")