import re
from pydantic import create_model, Field
from Engine.state_manager import GameState
from typing import Any, Callable, Literal


class ActionDefinition:
    """
    Defines the structure of an NPC action and provides logic to generate 
    a dynamic Pydantic schema for LLM validation.
    """
    def __init__(self, name: str, fields: dict):
        self.name = name
        self.fields = fields
    
    def build_schema(self, game_state: GameState):
        """
        Constructs a Pydantic model at runtime. 
        Dynamic fields (like interaction targets) are resolved using the current GameState.
        """
        pydantic_fields: dict[str, Any] = {}
        
        # 1. Add the discriminator field to identify the action type.
        pydantic_fields["行动类型"] = (Literal.__getitem__(self.name), Field(description="行动的唯一标识符"))
        
        # 2. Iterate through fields and resolve types/options.
        for field_name, field_def in self.fields.items():
            description = field_def.get("description", "")
            
            if field_def.get("type") == "dynamic":
                # Resolve the list of valid choices from the engine.
                resolver_name = field_def.get("options_from")
                resolver_fn = DYNAMIC_OPTIONS_REGISTRY.get(resolver_name)
                
                if resolver_fn is None:
                    raise KeyError(f"Registry Error: Resolver '{resolver_name}' is not registered.")

                options = resolver_fn(game_state)
                if not options:
                    raise RuntimeError(f"Context Error: Resolver '{resolver_name}' returned no valid options.")

                # Create a Literal type to constrain the LLM to specific engine-provided strings.
                if len(options) == 1:
                    literal_type = Literal.__getitem__(options[0])
                else:
                    literal_type = Literal.__getitem__(tuple(options))
                pydantic_fields[field_name] = (literal_type, Field(description=description))
            else:
                # Standard field (e.g., free text '内心' or '内容').
                field_type = field_def.get("type", str)
                pydantic_fields[field_name] = (field_type, Field(description=description))

        return create_model(f"{self.name}Action", **pydantic_fields)


# Registry for functions that provide dynamic values for Pydantic Literals.
DYNAMIC_OPTIONS_REGISTRY: dict[str, Callable[[GameState], list[str]]] = {
    "get_characters": GameState.get_characters_options,
    "get_locations": GameState.get_location_options,
    "get_directions": GameState.get_direction_options,
    "get_actions": GameState.get_action_options,
    "get_items": GameState.get_items_in_location,
}


# --- Master Action Registry ---
# Defines the vocabulary of actions available to the agents.
# Fields can be static types (str) or dynamic types resolved from the registry above.
ACTION_REGISTRY: dict[str, ActionDefinition] = {
    "开始说话": ActionDefinition(
        name="开始说话",
        fields={
            "目标": {"description": "选择你要对话的对象", "type": "dynamic", "options_from": "get_characters"},
            "内心": {"description": "你此时的真实想法", "type": str}
        }
    ),
    "说话": ActionDefinition(
        name="说话",
        fields={
            "内容": {"description": "你实际说出的话语", "type": str},
            "内心": {"description": "你内心的潜台词", "type": str}
        }
    ),
    "结束说话": ActionDefinition(
        name="结束说话",
        fields={
            "内心": {"description": "对话结束时的心理状态", "type": str}
        }
    ),
    "开始移动": ActionDefinition(
        name="开始移动",
        fields={
            "内心": {"description": "出发前的动机", "type": str}
        }
    ),
    "移动": ActionDefinition(
        name="移动",
        fields={
            "方向": {"description": "移动的方向矢量", "type": "dynamic", "options_from": "get_directions"},
            "内心": {"description": "对这段路程的感受", "type": str}
        }
    ),
    "结束移动": ActionDefinition(
        name="结束移动",
        fields={
            "内心": {"description": "到达目的地后的反馈", "type": str}
        }
    ),
    "查看地图": ActionDefinition(
        name="查看地图",
        fields={
            "内心": {"description": "检索信息时的想法", "type": str}
        }
    ),
    "保持沉默": ActionDefinition(
        name="保持沉默",
        fields={
            "内心": {"description": "为什么选择保持沉默", "type": str}
        }
    ),
    "交易": ActionDefinition(
        name="交易",
        fields={
            "目标": {"description": "与之交易的对象", "type": "dynamic", "options_from": "get_characters"},
            "内容": {"description": "交易的物品或资源", "type": str},
            "内心": {"description": "对这笔交易价值的评估", "type": str}
        }
    ),
    "睡觉": ActionDefinition(
        name="睡觉",
        fields={
            "内心": {"description": "入睡前的最后念头", "type": str}
        }
    ),
    "物品交互": ActionDefinition(
        name="物品交互",
        fields={
            "目标": {"description": "选择要交互的物品", "type": "dynamic", "options_from": "get_items"},
            "内心": {"description": "对这个物品的想法", "type": str}
        }
    ),
}

# --- Context Engineering ---

def format_system_prompt(memory_data: list[dict], system_prompt: str = "", current_location: str | None = None) -> str:
    """
    Enriches the character's base personality with dynamic world context.
    - Injects specific memories into marked <memory> tags.
    - Appends current spatial status.
    """
    if not system_prompt:
        return ""
    
    # 1. Memory Injection
    if memory_data:
        memory_lines = []
        for entry in memory_data:
            time = entry.get("time", "某个时刻")
            content = entry.get("content", "")
            if content:
                memory_lines.append(f"【{time}】{content}")
        
        formatted_memories = "\n".join(memory_lines)
        
        # Replace or insert into the <memory> block if it exists in the prompt template.
        if "<memory>" in system_prompt:
            match = re.search(r"<memory>(.*?)</memory>", system_prompt, flags=re.DOTALL)
            if match:
                existing = match.group(1).strip()
                combined = f"{existing}\n{formatted_memories}" if existing else formatted_memories
            else:
                combined = formatted_memories
            
            replacement = f"<memory>\n{combined}\n</memory>"
            system_prompt = re.sub(r"<memory>.*?</memory>", replacement, system_prompt, flags=re.DOTALL)
    
    # 2. Spatial Status Append
    if current_location:
        status_info = f"\n\n--- 空间定位 ---\n你目前所在地点：{current_location}\n"
        system_prompt += status_info
    
    return system_prompt


def generate_system_feedback(game_state: GameState, event_log: list[dict] | None = None) -> str:
    """
    Constructs a 'Sensory Input' report for the agent based on the world state.
    Provides the LLM with information about their surroundings and any direct interactions.
    """
    actor = game_state.active_character
    
    # Segment 1: Environmental Sensing
    nearby = game_state.get_characters_options()
    nearby_str = "、".join(nearby) if nearby else "None"
    
    items = game_state.get_items_in_location()
    items_str = "、".join(items) if items else "None"
    
    feedback = [
        "### 环境感知",
        f"- **当前位置**: {actor.current_location}",
        f"- **附近人物**: {nearby_str}",
        f"- **周围物品**: {items_str}"
    ]
    
    # Segment 2: Dialogue Sensing (Parsing direct mentions in the event log)
    incoming = []
    if event_log:
        for event in event_log:
            action = event.get("action", "")
            actor_name = event.get("actor")
            args = event.get("args", {}) or {}
            target = args.get("目标") or event.get("target_override")
            
            if action in ["说话", "开始说话", "继续说话"] and target == actor.name:
                content = args.get("内容", "（对你发起了对话）")
                incoming.append(f"> **{actor_name}** 对你说: {content}")
            
            elif action == "结束说话" and target == actor.name:
                incoming.append(f"> **系统提示**: {actor_name} 结束了与你的对话。")
    
    if incoming:
        feedback.append("\n### 实时通信")
        feedback.extend(incoming)
        
    return "\n".join(feedback)
