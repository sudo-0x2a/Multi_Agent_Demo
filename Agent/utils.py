import re
from pydantic import create_model, Field
from Engine.state_manager import GameState
from typing import Any, Callable, Literal


class ActionDefinition:
    def __init__(self, name: str, fields: dict):
        self.name = name
        self.fields = fields
    
    def build_schema(self, game_state: GameState):
        """Build a Pydantic model with dynamic options resolved from engine state."""
        # NOTE: use `Any` here to avoid fighting create_model's type stubs.
        pydantic_fields: dict[str, Any] = {}
        
        # Add discriminator field first - this is used to distinguish between different actions
        # Use __getitem__ for single value Literal
        pydantic_fields["行动类型"] = (Literal.__getitem__(self.name), Field(description="行动类型"))
        
        for field_name, field_def in self.fields.items():
            description = field_def.get("description", "")
            
            if field_def.get("type") == "dynamic":
                # Get options from engine state using the registered function
                options_from = field_def.get("options_from")
                options_fn = DYNAMIC_OPTIONS_REGISTRY.get(options_from)
                if options_fn is None:
                    raise KeyError(f"Unknown dynamic options resolver: {options_from}")

                options = options_fn(game_state)
                if not options:
                    raise RuntimeError(
                        f"Dynamic options resolver returned empty list: {options_from}"
                    )

                # Use Literal for dynamic options - compatible with structured output
                # Need to use __getitem__ since options are runtime values
                if len(options) == 1:
                    literal_type = Literal.__getitem__(options[0])
                else:
                    literal_type = Literal.__getitem__(tuple(options))
                pydantic_fields[field_name] = (literal_type, Field(description=description))
            else:
                field_type = field_def.get("type", str)
                pydantic_fields[field_name] = (field_type, Field(description=description))

        return create_model(f"{self.name}Action", **pydantic_fields)


DYNAMIC_OPTIONS_REGISTRY: dict[str, Callable[[GameState], list[str]]] = {
    "get_characters": GameState.get_characters_options,
    "get_locations": GameState.get_location_options,
    "get_directions": GameState.get_direction_options,
    "get_actions": GameState.get_action_options,
}


# Master Action Registry - all possible actions NPCs can use
ACTION_REGISTRY: dict[str, ActionDefinition] = {
    "说话": ActionDefinition(
        name="说话",
        fields={
            "目标": {
                "description": "选择你要对话的对象",
                "type": "dynamic",
                "options_from": "get_characters",
            },
            "内容": {
                "description": "你说话的内容",
                "type": str,
            },
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
    "移动": ActionDefinition(
        name="移动",
        fields={
            "方向": {
                "description": "选择你要移动的方向（上/下/左/右）",
                "type": "dynamic",
                "options_from": "get_directions",
            },
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
    "查看地图": ActionDefinition(
        name="查看地图",
        fields={
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
    "保持沉默": ActionDefinition(
        name="保持沉默",
        fields={
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
    "交易": ActionDefinition(
        name="交易",
        fields={
            "目标": {
                "description": "选择你要交易的对象",
                "type": "dynamic",
                "options_from": "get_characters",
            },
            "内容": {
                "description": "描述交易的具体内容",
                "type": str,
            },
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
    "睡觉": ActionDefinition(
        name="睡觉",
        fields={
            "内心": {
                "description": "你此时的内心想法",
                "type": str,
            }
        }
    ),
}

# Context engineering: Format system prompt with memory and current status
def format_system_prompt(memory_data: list[dict], system_prompt: str = "", current_location: str | None = None) -> str:
    """Format system prompt with memory data and current location status.
    
    Args:
        memory_data: List of memory entries with 'time' and 'content' fields
        system_prompt: The base system prompt to enhance (optional)
        current_location: Current location of the character (optional)
        
    Returns:
        The formatted system prompt with memory and location info injected.
    """
    if not system_prompt:
        return ""
    
    # Format new memory entries if provided
    if memory_data:
        memory_lines = []
        for entry in memory_data:
            time = entry.get("time", "某个时候")
            content = entry.get("content", "")
            if content:
                memory_lines.append(f"{time}：{content}")
        
        formatted_new_memory = "\n".join(memory_lines)
        
        # Inject memory into system prompt if <memory> tags exist
        if "<memory>" in system_prompt:
            # Extract existing memory content from within <memory> tags
            memory_match = re.search(r"<memory>(.*?)</memory>", system_prompt, flags=re.DOTALL)
            if memory_match:
                existing_memory = memory_match.group(1).strip()
                # Combine existing and new memories
                if existing_memory:
                    combined_memory = f"{existing_memory}\n{formatted_new_memory}"
                else:
                    combined_memory = formatted_new_memory
            else:
                combined_memory = formatted_new_memory
            
            # Replace the memory section with combined content
            memory_section = f"<memory>\n{combined_memory}\n</memory>"
            system_prompt = re.sub(
                r"<memory>.*?</memory>",
                memory_section,
                system_prompt,
                flags=re.DOTALL
            )
    
    # Add current location status if provided
    if current_location:
        location_info = f"\n\n<current_status>\nYou are currently at: {current_location}\n</current_status>"
        system_prompt = system_prompt + location_info
    
    return system_prompt


# Auto generate feedback from the system
def generate_system_feedback(game_state: GameState, event_log: list[dict] | None = None) -> str:
    """Generate automated system feedback to prompt the agent.
    
    This feedback is sent as a user message and informs the agent
    about their current state, prompting them to take action.
    
    Args:
        game_state: Current game state
        event_log: Optional event log to extract recent dialogue
        
    Returns:
        Formatted system feedback string
    """
    actor = game_state.active_character
    if actor.current_location is None:
        return "系统：你需要选择一个起始位置"
    
    # Get nearby characters at the same location
    nearby_characters = game_state.get_characters_options()
    
    # Build feedback message with location and nearby characters
    feedback = f"系统：你当前在{actor.current_location}"
    
    if nearby_characters:
        characters_list = "、".join(nearby_characters)
        feedback += f"，附近有{characters_list}"
    
    # Append incoming dialogue if event_log is provided.
    # Format requested: "{character}: {content}".
    if event_log:
        incoming_lines: list[str] = []
        # Collect up to the last 5 messages addressed to this actor.
        for event in reversed(event_log):
            if event.get("action") != "说话":
                continue
            actor_name = event.get("actor")
            args = event.get("args", {}) or {}
            target = args.get("目标")
            content = args.get("内容", "")
            if not (actor_name and target and content):
                continue
            if target != actor.name:
                continue
            if actor_name == actor.name:
                continue
            incoming_lines.append(f"{actor_name}: {content}")
            if len(incoming_lines) >= 5:
                break

        if incoming_lines:
            feedback += "\n\n系统：你刚刚收到消息\n" + "\n".join(reversed(incoming_lines))

    return feedback
