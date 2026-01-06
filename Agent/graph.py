from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Union
from pydantic import create_model, Field as PydanticField
from Engine.character import Character
from Engine.state_manager import GameState
from Agent.utils import ACTION_REGISTRY, format_system_prompt, generate_system_feedback

# --- Global LLM Configuration ---
# Using Grok-4-1-fast for high-performance agent reasoning.
llm = ChatXAI(model="grok-4-1-fast", temperature=0.8)

class AgentState(MessagesState):
    """Extends the base MessagesState to include the dynamic system prompt."""
    system_prompt: str

class NPCAgent:
    """
    Implements a cognitive controller for an NPC using a 3-stage LangGraph workflow.
    
    Stages:
    1. Preprocessing: Syncs with the game engine, prepares environmental context, 
       and builds the dynamic system prompt including character memories.
    2. Generation: Constrains the LLM to provide structured output based on 
       actions currently available to the character in their specific context.
    3. Postprocessing: Executes the LLM's chosen action in the game engine 
       and handles secondary feedback loops.
    """
    
    def __init__(self, character: Character, game_state: GameState):
        self.character = character
        self.game_state = game_state
        
        # Initial context synchronization
        self.game_state.set_active_character(character.name)
        self.system_prompt = character.background
        
        # Memory persistence across calls
        self.checkpointer = InMemorySaver()
        
        # Tracks the last processed event index to ensure system feedback only includes NEW sensory data.
        self._last_event_index_seen: int = 0
        
        # Compile the state machine
        self.graph = self._build_graph()
    
    def _preprocessing_node(self, state: AgentState) -> dict:
        """
        Gathers environmental data and memory to construct a comprehensive system prompt.
        """
        # Ensure thread safety by asserting the character context in the shared game_state.
        self.game_state.set_active_character(self.character.name)
        
        # Combine static background with dynamic memories and location status.
        memory_data = self.character.load_memory()
        system_prompt = format_system_prompt(
            memory_data=memory_data,
            system_prompt=self.system_prompt,
            current_location=self.character.current_location
        )
        
        return {"system_prompt": system_prompt}

    def _generation_node(self, state: AgentState) -> dict:
        """
        Resolves valid actions, builds a dynamic schema, and calls the LLM.
        """
        self.game_state.set_active_character(self.character.name)

        # 1. Identify which actions are legally possible in the current world state.
        available_actions = self.game_state.get_action_options()
        
        # 2. Build dynamic Pydantic models for the LLM's structured output.
        # This handles dynamic options (e.g., list of characters nearby).
        action_schemas = {}
        for action_name in available_actions:
            action_def = ACTION_REGISTRY.get(action_name)
            if action_def:
                try:
                    schema = action_def.build_schema(self.game_state)
                    action_schemas[action_name] = schema
                except RuntimeError:
                    # Occurs if an action target list is empty (e.g., no one to talk to).
                    continue
        
        if not action_schemas:
            raise ValueError(f"State Error: {self.character.name} has no valid action schemas at this moment.")
        
        # 3. Construct a Discriminated Union of all possible action schemas.
        if len(action_schemas) == 1:
            union_schema = list(action_schemas.values())[0]
        else:
            schema_tuple = tuple(action_schemas.values())
            union_type = Union[schema_tuple]
            
            # Wrap the union in a selection model for the LLM.
            union_schema = create_model(
                'AgentActionSelection',
                action=(union_type, PydanticField(description="选择当前环境下最合理的行动"))
            )
        
        # 4. Configure LLM for structured output targeting our dynamic schema.
        structured_llm = llm.with_structured_output(union_schema)
        
        # 5. Generate sensory feedback (System Notify) from the engine's event log.
        full_event_log = getattr(self.game_state.game, "event_log", [])
        new_events = full_event_log[self._last_event_index_seen :]
        self._last_event_index_seen = len(full_event_log)

        system_feedback = generate_system_feedback(self.game_state, event_log=new_events)
        
        # 6. Compose the message history and invoke the LLM.
        system_prompt = state.get('system_prompt', '')
        feedback_message = HumanMessage(content=system_feedback)
        
        messages = [SystemMessage(content=system_prompt)] + list(state.get('messages', [])) + [feedback_message]
        
        structured_output = structured_llm.invoke(messages)
        
        # Unwrap the selection model if necessary.
        if hasattr(structured_output, 'action'):
            structured_output = structured_output.action
        
        # Encapsulate the structured choice in an AIMessage for history tracking.
        ai_message = AIMessage(
            content=str(structured_output), 
            additional_kwargs={"structured_output": structured_output}
        )
        
        return {"messages": [feedback_message, ai_message]}

    def _postprocessing_node(self, state: AgentState) -> dict:
        """
        Translates the LLM's structured intention into engine commands.
        """
        self.game_state.set_active_character(self.character.name)

        messages = state.get('messages', [])
        
        # Retrieve the latest decision from the AI.
        last_ai_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        
        if last_ai_message is None or 'structured_output' not in last_ai_message.additional_kwargs:
            raise ValueError("Logic Error: Missing structured AI output in state history.")
        
        structured_output = last_ai_message.additional_kwargs['structured_output']
        
        # Format the Pydantic model back into a raw dictionary for the GameState.
        action_data = structured_output.model_dump() if hasattr(structured_output, 'model_dump') else structured_output
        action_name = action_data.get("行动类型")
        args = {k: v for k, v in action_data.items() if k != "行动类型"}
        
        formatted_output = {"action": action_name, "args": args}
        
        # Commit the action to the world engine.
        feedback = self.game_state.apply_action(formatted_output)
        
        if not feedback:
            return {"messages": []}

        # Record the outcome as system feedback in the character's cognitive history.
        outcome_message = HumanMessage(content=f"系统反馈：{feedback}")
        return {"messages": [outcome_message]}

    def _build_graph(self):
        """
        Constructs the cyclic state machine for the agent workflow.
        """
        builder = StateGraph(AgentState)
        
        builder.add_node("preprocess", self._preprocessing_node)
        builder.add_node("generate", self._generation_node)
        builder.add_node("postprocess", self._postprocessing_node)
        
        builder.add_edge(START, "preprocess")
        builder.add_edge("preprocess", "generate")
        builder.add_edge("generate", "postprocess")
        builder.add_edge("postprocess", END)
        
        return builder.compile(checkpointer=self.checkpointer)

    def draw_graph(self) -> str:
        """
        Returns a Mermaid diagram representation of the internal cognitive architecture.
        """
        try:
            return self.graph.get_graph().draw_mermaid()
        except Exception as e:
            return f"Mermaid Generation Error: {str(e)}"
