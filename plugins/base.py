from abc import ABC, abstractmethod

class Plugin(ABC):
    """Base class for all plugins in the TextWarp game."""
    
    def __init__(self, game):
        self.game = game
        self.active = False
        
    @property
    def name(self):
        """Return the name of the plugin (class name by default)."""
        return self.__class__.__name__
        
    @abstractmethod
    def update(self, dt):
        """Update the plugin state. Called every game tick.
        
        Args:
            dt: Time delta since last update in seconds.
        """
        pass
        
    @abstractmethod
    def render(self, screen):
        """Render the plugin to the screen.
        
        Args:
            screen: The curses screen object to render to.
        """
        pass
    
    def activate(self):
        """Activate the plugin."""
        self.active = True
        
    def deactivate(self):
        """Deactivate the plugin."""
        self.active = False
