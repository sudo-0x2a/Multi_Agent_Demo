"""
Multi-Agent Game Demo - Main Entry Point

This demonstrates how to load a game world and create NPC agents.
"""

import traceback
from Engine import load_world
from Agent.graph import NPCAgent


def main():
    """Main entry point for the game."""
    print("=" * 50)
    print("Multi-Agent Game Demo")
    print("=" * 50)
    print()
    
    # Load the game world from configuration
    print("Loading game world...")
    game_core, game_state, characters = load_world()
    print()
    
    # Display world information
    print("=" * 50)
    print("World Information")
    print("=" * 50)
    print(f"Map Locations: {', '.join(game_core.get_locations())}")
    print(f"Total Characters: {len(characters)}")
    print()
    
    # Display character information
    print("Characters:")
    for char in characters:
        print(f"  - {char.name} (ID: {char.id}) at {char.current_location}")
    print()
    
    # Create NPC agents for each character
    print("=" * 50)
    print("Creating NPC Agents")
    print("=" * 50)
    agents = {}
    # Create agents for both npc_001 and npc_002
    for character in characters:
        if character.id in ["001", "002"]:  # 小张 and 小红
            agent = NPCAgent(character, game_state)
            agents[character.id] = agent
            print(f"✓ Created agent for {character.name}")
        else:
            print(f"⊘ Skipped agent for {character.name}")
    print()
    
    print("=" * 50)
    print("Game Setup Complete!")
    print("=" * 50)
    print(f"Total agents: {len(agents)}")
    print()
    
    # Run test simulation for 小张
    print("=" * 50)
    print("Starting Test Simulation")
    print("=" * 50)
    print("Goal: 小张 should go to 医院 and speak with 小红")
    print()
    
    run_test_simulation(game_core, game_state, characters, agents)
    
    return game_core, game_state, characters, agents


def run_test_simulation(game_core, game_state, characters, agents):
    """Run a test simulation for 小张 to reach 医院 and speak with 小红."""

    def _invoke_agent(agent: NPCAgent, label: str) -> None:
        """Invoke one agent once and print its messages + last engine event."""
        initial_state = {}
        print(f"🤖 Running agent workflow: {label} ({agent.character.name}) ...")
        result = agent.graph.invoke(
            initial_state,
            {"configurable": {"thread_id": agent.character.id}},
        )

        # Display all messages
        print("\n📝 Conversation Log:")
        print("-" * 50)
        for i, msg in enumerate(result.get("messages", []), 1):
            msg_type = msg.__class__.__name__
            content = msg.content if hasattr(msg, "content") else str(msg)
            print(f"[{i}] {msg_type}:")
            print(f"    {content[:200]}{'...' if len(str(content)) > 200 else ''}")

            # Check for structured output in AIMessage
            if hasattr(msg, "additional_kwargs") and "structured_output" in msg.additional_kwargs:
                structured = msg.additional_kwargs["structured_output"]
                if hasattr(structured, "model_dump"):
                    print(f"    Structured: {structured.model_dump()}")
        print("-" * 50)
        print()

        # Display the last action taken from event log
        if game_core.event_log:
            last_event = game_core.event_log[-1]
            print("✅ Last Engine Event:")
            print(f"   Actor: {last_event.get('actor')}")
            print(f"   Action: {last_event.get('action')}")
            print(f"   Args: {last_event.get('args')}")
            if "new_location" in last_event:
                print(f"   New Location: {last_event.get('new_location')}")
            if "map_info" in last_event:
                print(f"   Map Info: {last_event.get('map_info')}")
            print()

    # Agents
    zhang_agent = agents.get("001")
    if not zhang_agent:
        print("Error: Could not find agent for 小张 (001)")
        return
    xiaohong_agent = agents.get("002")
    if not xiaohong_agent:
        print("Error: Could not find agent for 小红 (002)")
        return

    zhang = zhang_agent.character
    max_turns = 10
    success = False

    # Standby cursor: npc002 only acts if there is a *new* dialogue addressed to her.
    xiaohong_wakeup_cursor = 0

    print(f"Initial state: {zhang.name} at {zhang.current_location}")
    print()

    for turn in range(1, max_turns + 1):
        print("=" * 50)
        print(f"Turn {turn}")
        print("=" * 50)

        # ---- NPC001 acts every turn ----
        game_state.set_active_character(zhang.name)
        print(f"[NPC001] Current location: {zhang.current_location}")
        print(f"[NPC001] Available actions: {game_state.get_action_options()}")
        print()

        try:
            _invoke_agent(zhang_agent, label="NPC001")
        except Exception as e:
            print(f"❌ Error during NPC001 execution: {e}")
            traceback.print_exc()
            break

        # ---- NPC002 standby: only act if NPC001 spoke to her ----
        new_events = game_core.event_log[xiaohong_wakeup_cursor :]
        should_wake_xiaohong = any(
            (ev.get("action") == "说话")
            and (ev.get("args", {}).get("目标") == xiaohong_agent.character.name)
            for ev in new_events
        )

        if should_wake_xiaohong:
            print("[NPC002] Wake condition met: received a dialogue event. Acting once...")
            try:
                _invoke_agent(xiaohong_agent, label="NPC002")
            except Exception as e:
                print(f"❌ Error during NPC002 execution: {e}")
                traceback.print_exc()
                break
        else:
            print("[NPC002] Standby: no incoming dialogue addressed to 小红.")

        # Move cursor forward regardless (prevents waking again on same old event)
        xiaohong_wakeup_cursor = len(game_core.event_log)

        # ---- Success criteria ----
        print("\n🎯 Checking Success Criteria:")
        print(f"   Location: {zhang.current_location} (need: 医院)")

        at_hospital = zhang.current_location == "医院"
        spoke_with_xiaohong = False

        for event in game_core.event_log:
            if (
                event.get("actor") == zhang.name
                and event.get("action") == "说话"
                and event.get("args", {}).get("目标") == "小红"
            ):
                spoke_with_xiaohong = True
                break

        print(f"   At Hospital: {'✓' if at_hospital else '✗'}")
        print(f"   Spoke with 小红: {'✓' if spoke_with_xiaohong else '✗'}")
        print()

        if at_hospital and spoke_with_xiaohong:
            success = True
            print("🎉 SUCCESS! Test completed successfully!")
            print(f"   小张 reached 医院 and spoke with 小红 in {turn} turns")
            break

        print()
    
    # Final summary
    print("=" * 50)
    print("Test Summary")
    print("=" * 50)
    print(f"Status: {'SUCCESS ✓' if success else 'INCOMPLETE ✗'}")
    print(f"Total turns: {turn}")
    print(f"Final location: {zhang.current_location}")
    print(f"Total actions taken: {len(game_core.event_log)}")
    print()
    
    print("Full Event Log:")
    print("-" * 50)
    for i, event in enumerate(game_core.event_log, 1):
        print(f"{i}. {event}")
    print("-" * 50)


if __name__ == "__main__":
    main()
