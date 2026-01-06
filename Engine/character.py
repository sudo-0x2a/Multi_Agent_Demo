import json
import os

class Character:
    """
    Represents an entity within the simulation.
    Handles character-specific configuration, status tracking, and memory management.
    """
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.id: str = "000"
        self.name: str = "Unknown"
        self.background: str = ""
        
        # State tracking
        self.current_location: str | None = None
        self.activity_status: str = "IDLE"  # Valid statuses: IDLE, TALKING, MOVING
        self.activity_data: dict = {}      # Stores contextual data for the current status
        
        self._load_config()

    def _load_config(self):
        """
        Parses the character's JSON configuration and loads the associated background story.
        """
        with open(self.config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)
            self.id = config.get('id', '000')
            self.name = config.get('name', 'Unknown')
            
            # Resolve the background story file path relative to the config file
            bg_filename = config.get('background', 'No background provided.')
            bg_path = os.path.join(os.path.dirname(self.config_path), bg_filename)
            
            if os.path.exists(bg_path):
                with open(bg_path, 'r', encoding='utf-8') as bg_file:
                    self.background = bg_file.read()
            else:
                self.background = 'No background provided.'
            
            # Initialize starting location from config
            self.current_location = config.get('initial_location', None)

    def print_info(self):
        """Debug helper to print character details to the console."""
        print(f"ID: {self.id}\nCharacter Name: {self.name}\nBackground: {self.background}")

    def speak(self, message: str) -> str:
        """Returns the message string (legacy placeholder for expansion)."""
        return message

    def move(self, new_location: str):
        """Updates the character's physical position in the world."""
        self.current_location = new_location
    
    def load_memory(self) -> list[dict]:
        """
        Retrieves recent event summaries or 'memories' for this character.
        If a 'temp_memory.json' file exists in the character's config directory, 
        it is loaded and parsed.
        
        Returns:
            list[dict]: A list of memory entries, each typically containing 'time' and 'content'.
        """
        memory_path = os.path.join(os.path.dirname(self.config_path), "temp_memory.json")
        try:
            with open(memory_path, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                
                # Normalize output to a list
                if isinstance(memory, dict):
                    return [memory]
                elif isinstance(memory, list):
                    return memory
                return []
        except (FileNotFoundError, json.JSONDecodeError):
            # Silence errors for missing files as memories are optional
            return []

# --- Debug Entry Point ---
if __name__ == "__main__":
    # Example usage for testing character loading
    test_character = Character('../Configs/npc_001.json')
    test_character.print_info()