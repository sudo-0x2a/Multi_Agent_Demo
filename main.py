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
    print("Goal: 小张 should go to 医院 to check on 小明's situation, then go to ATM")
    print()
    
    run_test_simulation(game_core, game_state, characters, agents)
    
    return game_core, game_state, characters, agents


def run_test_simulation(game_core, game_state, characters, agents):
    """Run a test simulation for 小张 to reach 医院 and speak with 小红."""

    def _invoke_agent(agent: NPCAgent, label: str) -> None:
        """Invoke one agent once and print simplified logs."""
        print(f"🤖 Action: {label} ({agent.character.name})")
        
        result = agent.graph.invoke(
            {},
            {"configurable": {"thread_id": agent.character.id}},
        )

        # Simplified Message Log
        messages = result.get("messages", [])
        if messages:
            print("   📜 Activity:")
            for msg in messages:
                role = msg.__class__.__name__.replace("Message", "")
                content = msg.content
                
                if role == "Human":
                    # For system feedback, maybe just show the [对话] if it exists
                    # or a summary to keep it clean.
                    if "[对话]" in content:
                        # Extract the dialog part
                        dialog = content.split("[对话]")[-1].strip()
                        print(f"      [Incoming]: {dialog}")
                    else:
                        # Environment update
                        loc_match = [line for line in content.split("\n") if "当前位置" in line]
                        loc_str = loc_match[0] if loc_match else "Status Update"
                        print(f"      [System]: {loc_str}")
                
                elif role == "AI":
                    if hasattr(msg, "additional_kwargs") and "structured_output" in msg.additional_kwargs:
                        struct = msg.additional_kwargs["structured_output"]
                        content = str(struct.model_dump()) if hasattr(struct, "model_dump") else str(struct)
                    print(f"      [Action]: {content}")
        
        # State Summary
        c = agent.character
        print(f"   📊 State: Loc={c.current_location} | Status={c.activity_status} | Data={c.activity_data}")
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
    max_turns = 30
    success = False
    success_reported = False

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
            (ev.get("action") in ["说话", "开始说话", "继续说话", "结束说话"])
            and (
                ev.get("args", {}).get("目标") == xiaohong_agent.character.name or
                ev.get("target_override") == xiaohong_agent.character.name
            )
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
        print(f"   Location: {zhang.current_location} (need: ATM)")

        reached_atm = zhang.current_location == "ATM"
        
        print(f"   Reached ATM: {'✓' if reached_atm else '✗'}")
        print()

        if reached_atm:
            success = True
            print("🎉 SUCCESS! Test completed successfully!")
            print(f"   小张 reached ATM in {turn} turns")
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
