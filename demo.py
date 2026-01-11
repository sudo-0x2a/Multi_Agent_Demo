"""
Multi-Agent Simulation - FastAPI Web Server

This module serves as the web interface for the multi-agent simulation.
It provides:
1. Static file serving for the graphical frontend (HTML/JS/CSS).
2. REST API endpoints to control and monitor the simulation state.
3. Integration between the simulation engine and the agent logic.
"""

import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from Engine import load_world
from Agent.graph import NPCAgent

# --- Application Setup ---

app = FastAPI(title="Multi-Agent Simulation Interface")

# Direct the server to serve visual assets and frontend logic from the Graphics directory.
graphics_path = Path(__file__).parent / "Graphics"
app.mount("/Graphics", StaticFiles(directory=graphics_path), name="graphics")


# --- Simulation Management ---

class SimulationState:
    """
    Manages the lifecycle and state of the multi-agent simulation.
    Acts as a bridge between the GameEngine and the FastAPI application.
    """
    
    def __init__(self):
        # Core simulation components
        self.game_core = None      # The underlying world model
        self.game_state = None     # Current state of the world (who is where, what can they do)
        self.characters = None     # List of all character objects
        
        # Agent management
        self.agents = {}           # Maps character IDs to their NPCAgent controllers
        
        # Simulation progress tracking
        self.turn = 0
        self.max_turns = 30
        self.complete = False
        self.initialized = False
        
        # Wake-up logic state: tracks which events have been processed for NPC002
        self.xiaohong_wakeup_cursor = 0
    
    def initialize(self):
        """
        Initializes the simulation by loading the world configuration
        and instantiating agents for the primary characters.
        """
        # Load world data (map, characters, starting positions)
        self.game_core, self.game_state, self.characters = load_world()
        self.agents = {}
        
        # Instantiate agents for the specific NPCs we want to control (小张 and 小红)
        for character in self.characters:
            if character.id in ["001", "002"]:
                agent = NPCAgent(character, self.game_state)
                self.agents[character.id] = agent
        
        # Reset progress counters
        self.turn = 0
        self.complete = False
        self.xiaohong_wakeup_cursor = 0
        self.initialized = True
    
    def get_state_dict(self) -> dict:
        """
        Gathers current simulation data and returns it in a format suitable for JSON serialization.
        
        Returns:
            dict: The current world state including map, characters, event log, and turn info.
        """
        if not self.initialized:
            self.initialize()
        
        return {
            "map": {name: list(coords) for name, coords in self.game_core.game_map.items()},
            "characters": [
                {
                    "id": c.id, 
                    "name": c.name, 
                    "location": c.current_location,
                    "status": c.activity_status
                }
                for c in self.characters
            ],
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location
                }
                for item in self.game_core.items
            ],
            "events": list(self.game_core.event_log),
            "turn": self.turn,
            "complete": self.complete
        }
    
    def step(self) -> dict:
        """
        Advances the simulation by one full turn.
        In each turn:
        1. NPC001 (Xiao Zhang) takes an action based on their internal logic.
        2. NPC002 (Xiao Hong) checks if they were addressed and responds if necessary.
        3. Completion criteria are evaluated.
        
        Returns:
            dict: Success status and metadata about the turn.
        """
        if not self.initialized:
            self.initialize()
        
        if self.complete:
            return {"success": False, "message": "Simulation already complete", "complete": True}
        
        self.turn += 1
        
        # Retrieve primary agents
        zhang_agent = self.agents.get("001")
        xiaohong_agent = self.agents.get("002")
        
        if not zhang_agent:
            return {"success": False, "message": "Primary agent (001) not found"}
        
        zhang = zhang_agent.character
        
        # Step 1: Execute NPC001 (Xiao Zhang) logic
        # We set the active character in game_state so the agent operates on its own context.
        self.game_state.set_active_character(zhang.name)
        try:
            # Invoke the LangGraph workflow for 小张
            zhang_agent.graph.invoke(
                {},
                {"configurable": {"thread_id": zhang.id}}
            )
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "message": f"NPC001 error: {str(e)}"}
        
        # Step 2: Reactive Logic for NPC002 (Xiao Hong)
        # Xiao Hong only wakes up if someone spoke to her in the events that occurred since her last check.
        if xiaohong_agent:
            new_events = self.game_core.event_log[self.xiaohong_wakeup_cursor:]
            
            # Check if any event involves speaking to Xiao Hong
            should_wake = any(
                (ev.get("action") in ["说话", "开始说话", "继续说话", "结束说话"])
                and (
                    ev.get("args", {}).get("目标") == xiaohong_agent.character.name or
                    ev.get("target_override") == xiaohong_agent.character.name
                )
                for ev in new_events
            )
            
            if should_wake:
                self.game_state.set_active_character(xiaohong_agent.character.name)
                try:
                    # Invoke the LangGraph workflow for 小红
                    xiaohong_agent.graph.invoke(
                        {},
                        {"configurable": {"thread_id": xiaohong_agent.character.id}}
                    )
                except Exception as e:
                    traceback.print_exc()
            
            # Update the event cursor so we don't process the same messages twice
            self.xiaohong_wakeup_cursor = len(self.game_core.event_log)
        
        # Step 3: Evaluate termination conditions
        # The demo ends if Xiao Zhang reaches the ATM or the turn limit is hit.
        if zhang.current_location == "ATM":
            self.complete = True
        elif self.turn >= self.max_turns:
            self.complete = True
        
        return {"success": True, "turn": self.turn, "complete": self.complete}
    
    def reset(self):
        """Resets the simulation to its starting conditions."""
        self.initialized = False
        self.initialize()


# Global singleton for the simulation state
sim = SimulationState()


# --- API Endpoints ---

@app.get("/")
async def root():
    """Serves the main graphical user interface."""
    return FileResponse(graphics_path / "index.html")


@app.get("/api/state")
async def get_state():
    """Returns the current state of the simulation for the frontend to render."""
    return JSONResponse(sim.get_state_dict())


@app.post("/api/step")
async def step_simulation():
    """Triggers a single turn progression in the simulation."""
    result = sim.step()
    return JSONResponse(result)


@app.post("/api/reset")
async def reset_simulation():
    """Resets the simulation state to initial values."""
    sim.reset()
    return JSONResponse({"success": True, "message": "Simulation reset successfully"})


# --- Server Entry Point ---

if __name__ == "__main__":
    import uvicorn
    # Start the FastAPI server using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
