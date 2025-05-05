import pygame
import curses
import json
import os

# Default key bindings for terminal
DEFAULT_TERMINAL_KEYS = {
    "move_up": curses.KEY_UP,
    "move_down": curses.KEY_DOWN,
    "move_left": curses.KEY_LEFT,
    "move_right": curses.KEY_RIGHT,
    "move_up_left": ord('7'),
    "move_up_right": ord('9'),
    "move_down_left": ord('1'),
    "move_down_right": ord('3'),
    "rotate_ccw": ord('q'),
    "rotate_cw": ord('e'),
}

# Default key bindings for 3D GUI
DEFAULT_GUI_KEYS = {
    "move_forward": pygame.K_UP,
    "move_backward": pygame.K_DOWN,
    "strafe_left": pygame.K_LEFT,
    "strafe_right": pygame.K_RIGHT,
    "rotate_ccw": pygame.K_q,
    "rotate_cw": pygame.K_e,
}

# Key name mappings for display
KEY_DISPLAY_NAMES = {
    # Terminal keys
    curses.KEY_UP: "UP ARROW",
    curses.KEY_DOWN: "DOWN ARROW",
    curses.KEY_LEFT: "LEFT ARROW",
    curses.KEY_RIGHT: "RIGHT ARROW",
    ord('7'): "7",
    ord('9'): "9",
    ord('1'): "1",
    ord('3'): "3",
    ord('q'): "Q",
    ord('e'): "E",
    ord('w'): "W",
    ord('a'): "A",
    ord('s'): "S",
    ord('d'): "D",
    
    # Pygame keys
    pygame.K_UP: "UP ARROW",
    pygame.K_DOWN: "DOWN ARROW",
    pygame.K_LEFT: "LEFT ARROW",
    pygame.K_RIGHT: "RIGHT ARROW",
    pygame.K_w: "W",
    pygame.K_a: "A",
    pygame.K_s: "S",
    pygame.K_d: "D",
    pygame.K_q: "Q",
    pygame.K_e: "E",
}

# Action descriptions for the menu
ACTION_DESCRIPTIONS = {
    "move_up": "Move Up",
    "move_down": "Move Down",
    "move_left": "Move Left",
    "move_right": "Move Right",
    "move_up_left": "Move Diagonally Up-Left",
    "move_up_right": "Move Diagonally Up-Right",
    "move_down_left": "Move Diagonally Down-Left",
    "move_down_right": "Move Diagonally Down-Right",
    "rotate_ccw": "Rotate Counter-Clockwise",
    "rotate_cw": "Rotate Clockwise",
    "move_forward": "Move Forward",
    "move_backward": "Move Backward",
    "strafe_left": "Strafe Left",
    "strafe_right": "Strafe Right",
}

class KeyBindings:
    """Class to manage key bindings for the game."""
    
    def __init__(self):
        """Initialize key bindings with defaults."""
        self.terminal_keys = DEFAULT_TERMINAL_KEYS.copy()
        self.gui_keys = DEFAULT_GUI_KEYS.copy()
        self.load_bindings()
        
    def load_bindings(self):
        """Load key bindings from file."""
        try:
            if os.path.exists("keybindings.json"):
                with open("keybindings.json", "r") as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    if "terminal_keys" in data:
                        self.terminal_keys = {k: int(v) for k, v in data["terminal_keys"].items()}
                    if "gui_keys" in data:
                        self.gui_keys = {k: int(v) for k, v in data["gui_keys"].items()}
        except Exception as e:
            print(f"Error loading key bindings: {e}")
            # Fallback to defaults
            self.terminal_keys = DEFAULT_TERMINAL_KEYS.copy()
            self.gui_keys = DEFAULT_GUI_KEYS.copy()
            
    def save_bindings(self):
        """Save key bindings to file."""
        try:
            # Convert all keys to strings for JSON serialization
            data = {
                "terminal_keys": {k: str(v) for k, v in self.terminal_keys.items()},
                "gui_keys": {k: str(v) for k, v in self.gui_keys.items()}
            }
            with open("keybindings.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving key bindings: {e}")
            
    def reset_to_defaults(self):
        """Reset key bindings to defaults."""
        self.terminal_keys = DEFAULT_TERMINAL_KEYS.copy()
        self.gui_keys = DEFAULT_GUI_KEYS.copy()
        self.save_bindings()
        
    def get_key_name(self, key_code):
        """Get a display name for a key code."""
        if key_code in KEY_DISPLAY_NAMES:
            return KEY_DISPLAY_NAMES[key_code]
        else:
            # Try to convert to a character
            try:
                if 32 <= key_code <= 126:  # Printable ASCII
                    return chr(key_code)
                else:
                    return f"KEY {key_code}"
            except:
                return f"KEY {key_code}"
                
    def get_action_description(self, action):
        """Get a description for an action."""
        return ACTION_DESCRIPTIONS.get(action, action.replace("_", " ").title())
        
    def wait_for_key_press(self, screen):
        """Wait for a key press and return the key code."""
        # Disable normal key handling
        curses.cbreak()
        screen.nodelay(False)
        
        # Wait for a key press
        key = screen.getch()
        
        # Restore normal key handling
        screen.nodelay(True)
        
        return key
