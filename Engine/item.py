import json

class Item:
    """
    Represents an interactable object in the game world.
    Items are static environmental props that agents can perceive and interact with.
    """
    
    def __init__(self, config_path: str, location: str = None):
        self.config_path = config_path
        self.location = location
        self.id = None
        self.name = None
        self.description = None
        
        # Auto-load configuration on instantiation
        self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)
            self.id = config.get('id', '000')
            self.name = config.get('name', 'Unknown')
            self.description = config.get('description', 'No description provided.')

    def print_info(self):
        print(f"ID: {self.id}\nItem Name: {self.name}\nLocation: {self.location}\nDescription: {self.description}")
