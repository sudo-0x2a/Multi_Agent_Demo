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

llm = ChatXAI(model="grok-4-1-fast", temperature=0.8)

class AgentState(MessagesState):
    system_prompt: str

class NPCAgent:
    """
    NPC Agent with 3-stage workflow:
    1. Preprocessing: Get states from engine, prepare schemas, build system prompt
    2. Model Call: Get structured output from LLM
    3. Post Processing: Upload states back to engine
    
    Uses LangGraph's InMemorySaver for conversation memory management.
    Each agent has its own memory thread based on character ID.
    """
    def __init__(self, character: Character, game_state: GameState) :
        self.character = character
        self.game_state = game_state
        # Set this character as active in the game state
        self.game_state.set_active_character(character.name)
        self.system_prompt = character.background
        self.checkpointer = InMemorySaver()  # Memory management for this agent
        # Cursor to avoid repeating old engine events (e.g., old dialogues) in system feedback.
        self._last_event_index_seen: int = 0
        self.graph = self._build_graph()
    
    def _preprocessing_node(self, state: AgentState) -> Command:
        """Prepare system prompt with memory context."""

        # Ensure the engine state is pointing at *this* agent before reading options.
        # GameState is shared across agents.
        self.game_state.set_active_character(self.character.name)
        
        # Load and format system prompt with memory and location context
        memory_data = self.character.load_memory()
        system_prompt = format_system_prompt(
            memory_data=memory_data,
            system_prompt=self.system_prompt,
            current_location=self.character.current_location
        )
        
        # Handle system prompt
        return {
            "system_prompt": system_prompt,
        }

    def _generation_node(self, state: AgentState) -> dict:
        """Call LLM with structured output schema"""
        # Ensure the engine state is pointing at *this* agent before reading options.
        self.game_state.set_active_character(self.character.name)

        # 1. Get available actions for current character state
        available_actions = self.game_state.get_action_options()
        
        # 2. Build dynamic schemas for each available action
        action_schemas = {}
        for action_name in available_actions:
            action_def = ACTION_REGISTRY.get(action_name)
            if action_def:
                try:
                    schema = action_def.build_schema(self.game_state)
                    action_schemas[action_name] = schema
                except RuntimeError:
                    # Skip actions with empty dynamic options (e.g., no characters to talk to)
                    continue
        
        if not action_schemas:
            raise ValueError("No action schemas available")
        
        # Build unified schema with discriminator
        if len(action_schemas) == 1:
            # Single schema - use directly
            union_schema = list(action_schemas.values())[0]
        else:
            # Multiple schemas - create discriminated union
            # The schemas already have the action name embedded in their structure
            # Create a Union of all action schemas
            schema_tuple = tuple(action_schemas.values())
            union_type = Union[schema_tuple]
            
            # Wrap with Annotated for discriminator (the action schemas should have a discriminator field)
            # For our case, we'll create a wrapper model that contains the action
            union_schema = create_model(
                'AgentAction',
                action=(union_type, PydanticField(description="选择要执行的动作"))
            )
        
        # Configure LLM with structured output
        structured_llm = llm.with_structured_output(union_schema)
        
        # Generate system feedback to prompt the agent
        # Use self.game_state instead of state.get('game_state') to avoid serialization issues
        full_event_log = getattr(self.game_state.game, "event_log", None)
        if isinstance(full_event_log, list):
            new_events = full_event_log[self._last_event_index_seen :]
            self._last_event_index_seen = len(full_event_log)
        else:
            new_events = None

        system_feedback = generate_system_feedback(
            self.game_state,
            event_log=new_events,
        )
        
        # Get structured output from LLM using current messages + system feedback
        # Include system prompt as the first message, followed by conversation history and new feedback
        system_prompt = state.get('system_prompt', '')
        messages = [SystemMessage(content=system_prompt)] + list(state.get('messages', [])) + [HumanMessage(content=system_feedback)]
        
        # Get structured output from LLM
        structured_output = structured_llm.invoke(messages)
        
        # If using wrapper model, extract the action
        if hasattr(structured_output, 'action'):
            structured_output = structured_output.action
        
        # Create an AIMessage with the structured output
        ai_message = AIMessage(content=str(structured_output), additional_kwargs={"structured_output": structured_output})
        
        # With add_messages annotation, these messages will be appended to the conversation
        return {"messages": [HumanMessage(content=system_feedback), ai_message]}

    def _postprocessing_node(self, state: AgentState) -> dict:
        """Apply structured output back to game state"""
        # Ensure the engine state is pointing at *this* agent before applying actions.
        self.game_state.set_active_character(self.character.name)

        # Get the last assistant message which contains the structured output
        messages = state.get('messages', [])
        
        # Find the last AIMessage (assistant message)
        last_ai_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        
        if last_ai_message is None:
            raise ValueError("No assistant message found")
        
        # Extract structured output from additional_kwargs
        structured_output = last_ai_message.additional_kwargs.get('structured_output')
        if structured_output is None:
            raise ValueError("No structured output found in assistant message")
        
        # Convert structured output to the expected format for apply_action
        # The structured output should be a Pydantic model with action and args
        action_data = structured_output.model_dump() if hasattr(structured_output, 'model_dump') else structured_output
        
        # Extract action name from the discriminator field "行动类型"
        action_name = action_data.get("行动类型")
        if not action_name:
            raise ValueError(f"No action type found in structured output: {action_data}")
        
        # Extract arguments (all fields except the discriminator)
        args = {k: v for k, v in action_data.items() if k != "行动类型"}
        
        # Format for apply_action: {"action": str, "args": dict}
        formatted_output = {
            "action": action_name,
            "args": args
        }
        
        # Apply action to game state and get feedback
        feedback = self.game_state.apply_action(formatted_output)
        
        # Add feedback as a system feedback to conversation history
        feedback_message = HumanMessage(content=f"系统反馈：{feedback}")
        
        # With add_messages annotation, this feedback will be appended to the conversation
        return {"messages": [feedback_message]}

    def _build_graph(self):
        """Build the 3-stage workflow graph with memory management"""
        builder = StateGraph(AgentState)
        
        builder.add_node("preprocess", self._preprocessing_node)
        builder.add_node("generate", self._generation_node)
        builder.add_node("postprocess", self._postprocessing_node)
        
        builder.add_edge(START, "preprocess")
        builder.add_edge("preprocess", "generate")
        builder.add_edge("generate", "postprocess")
        builder.add_edge("postprocess", END)
        
        # Compile the graph - checkpointer must be passed during compile for persistence
        return builder.compile(checkpointer=self.checkpointer)

    def draw_graph(self) -> str:
        """
        Generate and return the Mermaid graph representation of the agent workflow.

        Returns:
            str: Mermaid diagram text that can be rendered or saved
        """
        try:
            mermaid_graph = self.graph.get_graph().draw_mermaid()
            return mermaid_graph
        except Exception as e:
            return f"Error generating graph: {str(e)}"
