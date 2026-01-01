import json
import os

class Character:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.id: str
        self.name: str
        self.background: str
        self.current_location: str | None = None
        self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)
            self.id = config.get('id', '000')
            self.name = config.get('name', 'Unknown')
            # Load background from the same directory as the config file
            bg_filename = config.get('background', 'No background provided.')
            bg_path = os.path.join(os.path.dirname(self.config_path), bg_filename)
            if os.path.exists(bg_path):
                with open(bg_path, 'r', encoding='utf-8') as bg_file:
                    self.background = bg_file.read()
            else:
                self.background = 'No background provided.'
            
            # Set initial location
            self.current_location = config.get('initial_location', None)

    def print_info(self):
        print(f"ID: {self.id}\nCharacter Name: {self.name}\nBackground: {self.background}")


    def speak(self, message: str):
        return message

    def move(self, new_location: str):
        self.current_location = new_location
    
    def load_memory(self) -> list[dict]:
        """Load recent memories from temp_memory.json.
        
        Returns:
            List of memory entries with 'time' and 'content' fields
        """
        memory_path = os.path.join(os.path.dirname(self.config_path), "temp_memory.json")
        try:
            with open(memory_path, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                # Handle both single dict and list of dicts
                if isinstance(memory, dict):
                    return [memory]
                elif isinstance(memory, list):
                    return memory
                return []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

# test
if __name__ == "__main__":
    character = Character('../Configs/npc_001.json')
    character.print_info()