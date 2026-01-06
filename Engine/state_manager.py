from .core import GameCore
from .character import Character

class GameState:
    """
    Manages transient state and interaction logic for characters within the GameCore.
    Acts as the primary interface for agents to perceive and interact with the world.
    """
    
    def __init__(self, game: GameCore):
        self.game = game
        self._active_character_name: str | None = None

    def set_active_character(self, character_name: str) -> None:
        """Sets the context for subsequent queries and actions."""
        # Verification ensures only valid characters are targeted.
        self.game.get_character_by_name(character_name)
        self._active_character_name = character_name

    @property
    def active_character(self) -> Character:
        """Returns the character object currently in focus."""
        if self._active_character_name is None:
            raise RuntimeError("Context Error: No active character has been set for the GameState.")
        return self.game.get_character_by_name(self._active_character_name)

    def get_characters_options(self) -> list[str]:
        """
        Calculates a list of other characters present at the active character's location.
        Used to populate dialogue or interaction targets.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError(f"State Error: Character {actor.name} has no valid location.")

        # Logic: Characters must be in the same physical space to interact.
        options: list[str] = []
        for c in self.game.get_characters():
            if c.id == actor.id:
                continue
            if c.current_location == actor.current_location:
                options.append(c.name)
        return options

    def get_location_options(self) -> list[str]:
        """
        Returns all valid travel destinations excluding the character's current position.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError(f"State Error: Character {actor.name} has no valid location.")

        locations = self.game.get_locations()
        return [loc for loc in locations if loc != actor.current_location]
    
    def get_direction_options(self) -> list[str]:
        """
        Calculates valid movement directions (UP/DOWN/LEFT/RIGHT) based on grid geometry.
        Verifies if an adjacent cell on the map contains a registered location.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError(f"State Error: Character {actor.name} has no valid location.")
        
        current_coords = self.game.get_location_coordinates(actor.current_location)
        x, y = current_coords
        
        # Grid direction vector mapping
        directions = {
            "上": (0, 1),   # North (+Y)
            "下": (0, -1),  # South (-Y)
            "左": (-1, 0),  # West (-X)
            "右": (1, 0),   # East (+X)
        }
        
        available = []
        for label, (dx, dy) in directions.items():
            if self.game.has_location_at_coordinates(x + dx, y + dy):
                available.append(label)
        
        return available

    def get_action_options(self) -> list[str]:
        """
        Dynamic action resolution.
        The available actions fluctuate based on the character's current 'activity_status'.
        This implements a simple finite state machine for character behavior.
        """
        actor = self.active_character
        if actor.current_location is None:
            raise ValueError(f"State Error: Character {actor.name} has no valid location.")

        # 1. Status-based overrides (Busy states)
        if actor.activity_status == "TALKING":
            # While in a conversation, the character can only talk, leave, or look at their map.
            return ["说话", "结束说话", "查看地图"]
        elif actor.activity_status == "MOVING":
            # While in movement mode, the character can move further or stop.
            return ["移动", "结束移动", "查看地图"]

        # 2. Location-based defaults (Idle states)
        base_actions = list(self.game.action_rules_by_location.get(actor.current_location, []))
        
        # Remap entry-point actions to their specific "Start" variants for the UI/LLM.
        remapped = []
        for action in base_actions:
            if action == "说话":
                remapped.append("开始说话")
            elif action == "移动":
                remapped.append("开始移动")
            else:
                remapped.append(action)
        return remapped

    def apply_action(self, structured_output: dict) -> str:
        """
        The main state transition function.
        Parses structured input from an agent and updates the world/character state.
        
        Args:
            structured_output: dict in format {"action": str, "args": dict}
            
        Returns:
            str: Natural language feedback for the agent/user.
        """
        actor = self.active_character
        if not isinstance(structured_output, dict):
            raise TypeError("System Error: Action input must be a dictionary.")
            
        action = structured_output["action"]
        args = structured_output.get("args", {})

        # Validation: Verify the action is legally permissible in the current state.
        allowed = self.get_action_options()
        if action not in allowed:
            # Legacy/Shortcut mapping for robust handling
            if action == "说话": action = "开始说话"
            elif action == "移动": action = "开始移动"
            
            if action not in allowed:
                raise ValueError(f"Rule Violation: Action '{action}' is not permitted for {actor.name} right now.")

        # --- Continuous State Transitions (FSM) ---
        
        if action == "开始说话":
            target = args["目标"]
            if target not in self.get_characters_options():
                raise ValueError(f"Target Error: {target} is not present at this location.")
            
            actor.activity_status = "TALKING"
            actor.activity_data = {"target": target}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你进入了与 {target} 的对话模式。你可以开始‘说话’，或在完成后‘结束说话’。"

        if action == "说话":
            target = actor.activity_data.get("target")
            # Ensure context for the event log
            if target and "目标" not in args:
                args["目标"] = target
                
            self.game.event_log.append({
                "actor": actor.name, 
                "action": action, 
                "args": args,
                "target_override": target
            })
            return "" # Transparent action (no direct system feedback needed)

        if action == "结束说话":
            target = actor.activity_data.get("target")
            if target and "目标" not in args:
                args["目标"] = target
                
            actor.activity_status = "IDLE"
            actor.activity_data = {}
            self.game.event_log.append({
                "actor": actor.name, 
                "action": action, 
                "args": args,
                "target_override": target
            })
            return f"你结束了与 {target} 的对话。"

        if action == "开始移动":
            actor.activity_status = "MOVING"
            actor.activity_data = {}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return "你进入了移动模式。请指定方向（上/下/左/右）进行移动。"

        if action == "移动":
            direction = args["方向"]
            if direction not in self.get_direction_options():
                raise ValueError(f"Movement Error: Cannot move '{direction}' from here.")
            
            # Retrieve coordinates and resolve destination
            coords = self.game.get_location_coordinates(actor.current_location)
            delta = {"上": (0, 1), "下": (0, -1), "左": (-1, 0), "右": (1, 0)}[direction]
            new_loc_name = self.game.get_location_name_at_coordinates(coords[0] + delta[0], coords[1] + delta[1])
            
            if new_loc_name is None:
                raise ValueError("Engine Error: Destination does not exist in world map.")
            
            actor.move(new_loc_name)
            actor.activity_data["last_destination"] = new_loc_name
            
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "new_location": new_loc_name})
            return f"你向 {direction} 移动，到达了 {new_loc_name}。"

        if action == "结束移动":
            final_loc = actor.activity_data.get("last_destination", actor.current_location)
            actor.activity_status = "IDLE"
            actor.activity_data = {}
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你停止了移动，目前的所在地是：{final_loc}。"

        # --- Discrete Action Handlers ---

        if action == "交易":
            target = args["目标"]
            if target not in self.get_characters_options():
                raise ValueError(f"Target Error: {target} is not here.")
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args})
            return f"你与 {target} 成功发起了交易。"
        
        if action == "查看地图":
            info = self.game.get_map_info()
            self.game.event_log.append({"actor": actor.name, "action": action, "args": args, "map_info": info})
            loc_list = ", ".join([f"{n} ({c})" for n, c in info["locations"].items()])
            return f"【卫星地图】目前已感知的地点：{loc_list}"

        if action in {"保持沉默", "睡觉"}:
            self.game_core_event = {"actor": actor.name, "action": action, "args": args}
            self.game.event_log.append(self.game_core_event)
            return "你默默地观察着周围。" if action == "保持沉默" else "你休息了一段时间。"

        raise KeyError(f"Fatal Error: Action handler for '{action}' is not implemented.")