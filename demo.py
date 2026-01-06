"""
Multi-Agent Demo - FastAPI Web Interface
Serves the graphical frontend and provides API endpoints for simulation control.
"""
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from Engine import load_world
from Agent.graph import NPCAgent

# FastAPI App
app = FastAPI(title="Multi-Agent Demo")

# Serve static files from Graphics folder
graphics_path = Path(__file__).parent / "Graphics"
app.mount("/Graphics", StaticFiles(directory=graphics_path), name="graphics")


# ============================================================
# Simulation State (module-level singleton)
# ============================================================
class SimulationState:
    def __init__(self):
        self.game_core = None
        self.game_state = None
        self.characters = None
        self.agents = {}
        self.turn = 0
        self.max_turns = 30
        self.complete = False
        self.xiaohong_wakeup_cursor = 0
        self.initialized = False
    
    def initialize(self):
        """Load the game world and create agents."""
        self.game_core, self.game_state, self.characters = load_world()
        self.agents = {}
        
        for character in self.characters:
            if character.id in ["001", "002"]:
                agent = NPCAgent(character, self.game_state)
                self.agents[character.id] = agent
        
        self.turn = 0
        self.complete = False
        self.xiaohong_wakeup_cursor = 0
        self.initialized = True
    
    def get_state_dict(self) -> dict:
        """Return current state as JSON-serializable dict."""
        if not self.initialized:
            self.initialize()
        
        return {
            "map": {name: list(coords) for name, coords in self.game_core.game_map.items()},
            "characters": [
                {"id": c.id, "name": c.name, "location": c.current_location}
                for c in self.characters
            ],
            "events": list(self.game_core.event_log),
            "turn": self.turn,
            "complete": self.complete
        }
    
    def step(self) -> dict:
        """Advance simulation by one turn."""
        if not self.initialized:
            self.initialize()
        
        if self.complete:
            return {"success": False, "message": "Simulation already complete", "complete": True}
        
        self.turn += 1
        
        zhang_agent = self.agents.get("001")
        xiaohong_agent = self.agents.get("002")
        
        if not zhang_agent:
            return {"success": False, "message": "Agent 001 not found"}
        
        zhang = zhang_agent.character
        
        # Run NPC001 (小张)
        self.game_state.set_active_character(zhang.name)
        try:
            zhang_agent.graph.invoke(
                {},
                {"configurable": {"thread_id": zhang.id}}
            )
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "message": f"NPC001 error: {str(e)}"}
        
        # Check if NPC002 (小红) should wake up
        if xiaohong_agent:
            new_events = self.game_core.event_log[self.xiaohong_wakeup_cursor:]
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
                    xiaohong_agent.graph.invoke(
                        {},
                        {"configurable": {"thread_id": xiaohong_agent.character.id}}
                    )
                except Exception as e:
                    traceback.print_exc()
            
            self.xiaohong_wakeup_cursor = len(self.game_core.event_log)
        
        # Check completion criteria
        if zhang.current_location == "ATM":
            self.complete = True
        elif self.turn >= self.max_turns:
            self.complete = True
        
        return {"success": True, "turn": self.turn, "complete": self.complete}
    
    def reset(self):
        """Reset the simulation to initial state."""
        self.initialized = False
        self.initialize()


# Global simulation state
sim = SimulationState()


# ============================================================
# API Routes
# ============================================================
@app.get("/")
async def root():
    """Serve the main HTML page."""
    return FileResponse(graphics_path / "index.html")


@app.get("/api/state")
async def get_state():
    """Get current simulation state."""
    return JSONResponse(sim.get_state_dict())


@app.post("/api/step")
async def step_simulation():
    """Advance simulation by one turn."""
    result = sim.step()
    return JSONResponse(result)


@app.post("/api/reset")
async def reset_simulation():
    """Reset the simulation."""
    sim.reset()
    return JSONResponse({"success": True, "message": "Simulation reset"})


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
