"""
Multi-Agent Simulation - CLI Test Entry Point

This module provides a command-line interface to run the multi-agent simulation
without a web frontend. It is primarily used for testing and debugging the 
agent logic and engine interactions.
"""

import traceback
from Engine import load_world
from Agent.graph import NPCAgent

def main():
    """
    Initializes the game world, creates NPC agents, and runs a test simulation.
    """
    print("=" * 60)
    print("      MULTI-AGENT SIMULATION - CLI DEBUGGER")
    print("=" * 60)
    print()
    
    # --- World Initialization ---
    print("Initializing game world...")
    game_core, game_state, characters = load_world()
    game_core.initialize()
    print("✓ World loaded successfully.\n")
    
    # --- Display Environment Info ---
    print("-" * 60)
    print(" ENVIRONMENT OVERVIEW")
    print("-" * 60)
    print(f"Available Locations : {', '.join(game_core.get_locations())}")
    print(f"Active Characters   : {len(characters)}")
    for char in characters:
        print(f"  • {char.name:<10} (ID: {char.id}) at {char.current_location}")
    print()
    
    # --- Agent Creation ---
    print("-" * 60)
    print(" AGENT INITIALIZATION")
    print("-" * 60)
    agents = {}
    # We create agents for NPC 001 (Xiao Zhang) and NPC 002 (Xiao Hong)
    for character in characters:
        if character.id in ["001", "002"]: 
            agent = NPCAgent(character, game_state)
            agents[character.id] = agent
            print(f"✓ Created IQ agent for {character.name}")
        else:
            print(f"⊘ Skipping IQ agent for {character.name} (NPC Only)")
    print("\nSimulation setup complete. Starting test run...")
    print()
    
    # --- Simulation Execution ---
    print("=" * 60)
    print(" MISSION START: PROJECT ATM")
    print("=" * 60)
    print("Objective: Xiao Zhang must visit Hospital, coordinate with Xiao Hong, then reach ATM.")
    print()
    
    run_test_simulation(game_core, game_state, characters, agents)
    
    return game_core, game_state, characters, agents


def run_test_simulation(game_core, game_state, characters, agents):
    """
    Executes a turn-based simulation loop until an objective or turn limit is reached.
    """

    def _invoke_agent(agent: NPCAgent, label: str) -> None:
        """
        Executes a single workflow turn for a specific agent and prints formatted output.
        """
        print(f"🤖 [NODE: {label}] Character: {agent.character.name}")
        
        # Execute the LangGraph workflow
        result = agent.graph.invoke(
            {},
            {"configurable": {"thread_id": agent.character.id}},
        )

        # Print activity logs from the agent's memory
        messages = result.get("messages", [])
        if messages:
            print("   📜 Execution Trace:")
            for msg in messages:
                role = msg.__class__.__name__.replace("Message", "")
                content = msg.content
                
                if role == "Human":
                    # Display sensory input or environmental updates
                    if "[对话]" in content:
                        dialog = content.split("[对话]")[-1].strip()
                        print(f"      📥 [Received]: {dialog}")
                    else:
                        loc_match = [line for line in content.split("\n") if "当前位置" in line]
                        loc_str = loc_match[0] if loc_match else "Status Update"
                        print(f"      🌐 [System]: {loc_str}")
                
                elif role == "AI":
                    # Display the agent's chosen action and reasoning
                    if hasattr(msg, "additional_kwargs") and "structured_output" in msg.additional_kwargs:
                        struct = msg.additional_kwargs["structured_output"]
                        content = str(struct.model_dump()) if hasattr(struct, "model_dump") else str(struct)
                    print(f"      🚀 [Action]: {content}")
        
        # Display updated status
        c = agent.character
        print(f"   📊 Result: Loc={c.current_location} | Status={c.activity_status}")
        print()

    # Retrieve agents for the simulation loop
    zhang_agent = agents.get("001")
    xiaohong_agent = agents.get("002")
    
    if not zhang_agent or not xiaohong_agent:
        print("Error: Missing primary agents (001 or 002). Aborting.")
        return

    zhang = zhang_agent.character
    max_turns = 30
    success = False

    # Keeps track of events processed by Xiao Hong to avoid duplicate triggers
    xiaohong_wakeup_cursor = 0

    print(f"Initial State: {zhang.name} is starting at {zhang.current_location}")
    print()

    # --- Turn Loop ---
    for turn in range(1, max_turns + 1):
        print(f" [ TURN {turn} ] ".center(60, "="))

        # 1. Proactive Phase: Xiao Zhang (NPC001) always takes an action
        game_state.set_active_character(zhang.name)
        try:
            _invoke_agent(zhang_agent, label="PROACTIVE_AGENT")
        except Exception as e:
            print(f"❌ NPC001 Error: {e}")
            traceback.print_exc()
            break

        # 2. Reactive Phase: Xiao Hong (NPC002) only acts if triggered by a dialogue event
        new_events = game_core.event_log[xiaohong_wakeup_cursor :]
        should_wake_xiaohong = any(
            (ev.get("action") in ["说话", "开始说话", "继续说话", "结束说话"])
            and (
                ev.get("args", {}).get("目标") == xiaohong_agent.character.name or
                ev.get("target_override") == xiaohong_agent.character.name
            )
            for ev in new_events
        )

        if should_wake_xiaohong:
            print(f"🔔 reactive Trigger: {xiaohong_agent.character.name} detected incoming communication.")
            try:
                _invoke_agent(xiaohong_agent, label="REACTIVE_AGENT")
            except Exception as e:
                print(f"❌ NPC002 Error: {e}")
                traceback.print_exc()
                break
        
        # Update cursor to mark events as processed
        xiaohong_wakeup_cursor = len(game_core.event_log)

        # 3. Success Check: Has the target location been reached?
        reached_atm = zhang.current_location == "ATM"
        if reached_atm:
            success = True
            print("\n" + " MISSION ACCOMPLISHED ".center(60, "🎉"))
            print(f"Objective reached in {turn} turns.")
            break

    # --- Post-Simulation Report ---
    print("\n" + "=" * 60)
    print(" SIMULATION SUMMARY ")
    print("=" * 60)
    print(f"Overall Status : {'SUCCESS ✓' if success else 'FAILED ✗'}")
    print(f"Total Duration : {turn} turns")
    print(f"Final Position : {zhang.name} at {zhang.current_location}")
    print(f"Total Actions  : {len(game_core.event_log)}")
    print("-" * 60)
    
    print("Full Action Log History:")
    for i, event in enumerate(game_core.event_log, 1):
        actor = event.get('actor', 'System')
        action = event.get('action', 'Unknown')
        print(f"  {i:02d}. [{actor}] {action}")
    print("=" * 60)


if __name__ == "__main__":
    main()
