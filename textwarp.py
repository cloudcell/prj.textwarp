#!/usr/bin/env python3
import curses
import time
import random
import math
import json
import hashlib
import os
import signal
from plugins.base import Plugin
from plugins.snake import SnakePlugin
from plugins.graph_classifier import GraphClassifierPlugin
from plugins.polygraph_3d import Polygraph3DPlugin
from plugins.gui_3d import GUI3DPlugin
from plugins.audio import AudioPlugin
from plugins.network import NetworkPlugin
from keybindings import KeyBindings
import copy

class TextAdventure:
    """A text-based adventure game."""

    def __init__(self, screen):
        """Initialize the game."""
        # Initialize variables
        self.screen = screen
        self.curses = __import__('curses')  # Store curses module reference for plugins
        self.running = True
        self.world_x = 0
        self.world_y = 0
        self.dx = 0
        self.dy = 0
        self.player_char = 'X'
        self.player_color = None
        self.background_color = None
        self.at_symbol_color = None
        self.zero_color = None
        self.panel_color = None
        self.menu_color = None
        self.snake_color = None
        self.fuel_color = None
        self.snake_indicator_color = None
        self.fps_color = None
        self.dot_color = None
        self.max_y = 0
        self.max_x = 0
        self.last_update = time.time()
        self.move_speed = 5  # Integer cells per second
        # World coordinates (player is always at center of screen)
        # Accumulated movement that hasn't been applied yet
        self.acc_x = 0
        self.acc_y = 0
        # Debug info
        self.last_key = 0
        # Flag to indicate if redraw is needed
        self.needs_redraw = True
        # Flag to check for window resize
        self.check_resize = True
        # FPS tracking
        self.frame_times = []
        self.current_fps = 0
        self.fps_update_timer = 0
        # Location settings
        self.start_at_last_location = True  # Whether to start at the last saved location
        self.load_location_settings()  # Load location settings
        # Key state tracking for diagonal movement
        self.key_states = {
            curses.KEY_UP: False,
            curses.KEY_DOWN: False,
            curses.KEY_LEFT: False,
            curses.KEY_RIGHT: False,
            ord('w'): False,
            ord('s'): False,
            ord('a'): False,
            ord('d'): False,
            # Numeric keypad
            ord('7'): False,  # NW
            ord('8'): False,  # N
            ord('9'): False,  # NE
            ord('4'): False,  # W
            ord('6'): False,  # E
            ord('1'): False,  # SW
            ord('2'): False,  # S
            ord('3'): False   # SE
        }
        # Track when keys were last pressed
        self.key_press_time = {}
        for key in self.key_states:
            self.key_press_time[key] = 0
        # Key timeout (how long a key remains "pressed" after it's released)
        self.key_timeout = 0.1  # seconds
        # Direction mapping for numeric keypad
        self.numpad_directions = {
            ord('7'): (-1, -1),  # NW
            ord('8'): (0, -1),   # N
            ord('9'): (1, -1),   # NE
            ord('4'): (-1, 0),   # W
            ord('5'): (0, 0),    # Center (no movement)
            ord('6'): (1, 0),    # E
            ord('1'): (-1, 1),   # SW
            ord('2'): (0, 1),    # S
            ord('3'): (1, 1)     # SE
        }
        # Store spaces created by the user
        self.spaces = self.load_spaces()
        # Message to display
        self.message = ""
        self.message_timeout = 0
        
        # Fuel system
        self.fuel = 0
        self.fuel_collected = {}  # Dictionary to track collected fuel positions
        
        # Menu system
        self.in_menu = False
        self.current_menu = "main"
        self.menu_selection = 0
        self.menus = {
            "main": ["Resume Game", "Plugin Management", "Color Settings", "Key Bindings", "Location Settings", "Audio Settings", "3D Settings", "Network", "Quit"],
            "plugins": [],  # Will be populated with plugin names
            "location": ["Start at Last Location: " + ("Yes" if self.start_at_last_location else "No"), 
                         "Save Current Location", 
                         "Reset to Origin", 
                         "Back to Main Menu"]
        }
        
        # Plugins
        self.plugins = []
        self.initialize_plugins()
        self.load_plugin_config()

        # Character cache to improve performance
        self.char_cache = {}
        self.last_player_x = 0
        self.last_player_y = 0
        self.cache_valid = False
        
        # Initialize key bindings
        self.key_bindings = KeyBindings()

    def initialize_plugins(self):
        # Add plugins here
        self.plugins.append(SnakePlugin(self))
        self.plugins.append(GraphClassifierPlugin(self))
        self.plugins.append(NetworkPlugin(self))
        self.plugins.append(GUI3DPlugin(self))
        self.plugins.append(Polygraph3DPlugin(self))
        self.plugins.append(AudioPlugin(self))  # Add the new AudioPlugin
        
        # Update plugin menu
        self.menus["plugins"] = [p.name + (" [Active]" if p.active else " [Inactive]") for p in self.plugins] + ["Back"]

    def load_plugin_config(self):
        try:
            if os.path.exists('plugins.json'):
                with open('plugins.json', 'r') as f:
                    config = json.load(f)
                    for plugin in self.plugins:
                        if plugin.name in config and config[plugin.name]:
                            plugin.activate()
                        else:
                            plugin.deactivate()
        except Exception as e:
            print(f"Error loading plugin config: {e}")
        
        # Update plugin menu
        self.menus["plugins"] = [p.name + (" [Active]" if p.active else " [Inactive]") for p in self.plugins] + ["Back"]

    def save_plugin_config(self):
        try:
            config = {plugin.name: plugin.active for plugin in self.plugins}
            with open('plugins.json', 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving plugin config: {e}")

    def setup(self):
        """Setup curses and colors."""
        curses.start_color()
        curses.use_default_colors()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.screen.keypad(True)
        
        # Initialize colors
        self.initialize_colors()
        
        # Get screen dimensions
        self.max_y, self.max_x = self.screen.getmaxyx()
        
        # Setup colors
        self.screen.timeout(50)  # Non-blocking input with 50ms timeout
        
    def initialize_colors(self):
        """Initialize color pairs for the game."""
        # Define colors
        curses.start_color()
        curses.use_default_colors()
        
        # Define color pairs
        self.background_color = curses.color_pair(0)  # Default (usually white on black)
        
        # Player color (red)
        curses.init_pair(1, curses.COLOR_RED, -1)
        self.player_color = curses.color_pair(1)
        
        # Menu color (white on blue)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.menu_color = curses.color_pair(2)
        
        # Selected menu item color (yellow on blue)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLUE)
        self.selected_menu_color = curses.color_pair(3)
        
        # Panel color (white on green)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_GREEN)
        self.panel_color = curses.color_pair(4)
        
        # @ symbol color (green)
        curses.init_pair(5, curses.COLOR_GREEN, -1)
        self.at_symbol_color = curses.color_pair(5)
        
        # Snake indicator color (white on black)
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)
        self.snake_indicator_color = curses.color_pair(6)
        
        # FPS counter color (yellow on black)
        curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        self.fps_color = curses.color_pair(7)
        
        # Snake color (dark blue)
        curses.init_pair(8, curses.COLOR_BLUE, -1)
        self.snake_color = curses.color_pair(8)
        
        # Fuel color (magenta)
        curses.init_pair(9, curses.COLOR_MAGENTA, -1)
        self.fuel_color = curses.color_pair(9)
        
        # Zero color (orange - approximated with yellow)
        curses.init_pair(10, curses.COLOR_YELLOW, -1)
        self.zero_color = curses.color_pair(10)
        
        # Dot color (brown - approximated with red+black background)
        curses.init_pair(11, curses.COLOR_RED, curses.COLOR_BLACK)
        self.dot_color = curses.color_pair(11)
        
        # Store color settings for the color menu
        self.color_settings = {
            "Player": {"color_id": 1, "fg": curses.COLOR_RED, "bg": -1, "attr": curses.A_NORMAL},
            "Menu": {"color_id": 2, "fg": curses.COLOR_WHITE, "bg": curses.COLOR_BLUE, "attr": curses.A_NORMAL},
            "Selected Menu": {"color_id": 3, "fg": curses.COLOR_YELLOW, "bg": curses.COLOR_BLUE, "attr": curses.A_NORMAL},
            "Panel": {"color_id": 4, "fg": curses.COLOR_WHITE, "bg": curses.COLOR_GREEN, "attr": curses.A_NORMAL},
            "@ Symbol": {"color_id": 5, "fg": curses.COLOR_GREEN, "bg": -1, "attr": curses.A_NORMAL},
            "Snake Indicator": {"color_id": 6, "fg": curses.COLOR_WHITE, "bg": curses.COLOR_BLACK, "attr": curses.A_NORMAL},
            "FPS Counter": {"color_id": 7, "fg": curses.COLOR_YELLOW, "bg": curses.COLOR_BLACK, "attr": curses.A_NORMAL},
            "Snake": {"color_id": 8, "fg": curses.COLOR_BLUE, "bg": -1, "attr": curses.A_NORMAL},
            "Fuel": {"color_id": 9, "fg": curses.COLOR_MAGENTA, "bg": -1, "attr": curses.A_NORMAL},
            "Egg": {"color_id": 10, "fg": curses.COLOR_YELLOW, "bg": -1, "attr": curses.A_NORMAL},
            "Dot": {"color_id": 11, "fg": curses.COLOR_RED, "bg": curses.COLOR_BLACK, "attr": curses.A_NORMAL},
            "Coordinate Notches": {"color_id": 12, "fg": curses.COLOR_WHITE, "bg": -1, "attr": curses.A_NORMAL}
        }
        
        # Initialize the coordinate notches color
        curses.init_pair(12, curses.COLOR_WHITE, -1)
        self.coordinate_notches_color = curses.color_pair(12)
        
        # Save the original color settings
        self.original_color_settings = copy.deepcopy(self.color_settings)
        
        # Load color settings from file
        self.load_color_settings()

    def handle_input(self):
        # Get input
        try:
            key = self.screen.getch()
        except:
            # Handle any errors with getch()
            key = -1
        
        # Skip input handling if in menu
        if self.in_menu:
            if key != -1:
                self.handle_menu_input(key)
            return
            
        # Store last key for debugging
        if key != -1:
            self.last_key = key
            
        # Handle special keys
        if key == 27:  # ESC key
            # Open menu
            self.in_menu = True
            self.menu_selection = 0
            self.needs_redraw = True
            # Clear movement when entering menu
            self.dx = 0
            self.dy = 0
            # Clear key states
            for k in self.key_states:
                self.key_states[k] = False
        elif key == ord(' '):  # Space key
            # Create a space at the current position
            space_key = self.get_space_key(self.world_x, self.world_y)
            self.spaces[space_key] = (self.world_x, self.world_y)
            self.save_spaces()
            self.message = f"Space created at ({self.world_x}, {self.world_y})"
            self.message_timeout = 2.0
            self.needs_redraw = True
        elif key in self.key_states:
            # Update key state (pressed)
            self.key_states[key] = True
            self.key_press_time[key] = time.time()
        
        # Calculate movement direction based on key states
        self.dx = 0
        self.dy = 0
        
        # Use key bindings for movement
        if self.key_states.get(self.key_bindings.terminal_keys["move_up"], False):
            self.dy = -1
        if self.key_states.get(self.key_bindings.terminal_keys["move_down"], False):
            self.dy = 1
        if self.key_states.get(self.key_bindings.terminal_keys["move_left"], False):
            self.dx = -1
        if self.key_states.get(self.key_bindings.terminal_keys["move_right"], False):
            self.dx = 1
        
        # Diagonal movement
        if self.key_states.get(self.key_bindings.terminal_keys["move_up_left"], False):
            self.dx = -1
            self.dy = -1
        if self.key_states.get(self.key_bindings.terminal_keys["move_up_right"], False):
            self.dx = 1
            self.dy = -1
        if self.key_states.get(self.key_bindings.terminal_keys["move_down_left"], False):
            self.dx = -1
            self.dy = 1
        if self.key_states.get(self.key_bindings.terminal_keys["move_down_right"], False):
            self.dx = 1
            self.dy = 1
            
        # Rotation
        if self.key_states.get(self.key_bindings.terminal_keys["rotate_ccw"], False):
            # Find the GUI3D plugin and rotate counter-clockwise
            for plugin in self.plugins:
                if isinstance(plugin, GUI3DPlugin) and plugin.active:
                    plugin.rotation_y += plugin.rotation_speed
                    break
        if self.key_states.get(self.key_bindings.terminal_keys["rotate_cw"], False):
            # Find the GUI3D plugin and rotate clockwise
            for plugin in self.plugins:
                if isinstance(plugin, GUI3DPlugin) and plugin.active:
                    plugin.rotation_y -= plugin.rotation_speed
                    break
            
        # Normalize diagonal movement
        if self.dx != 0 and self.dy != 0:
            self.dx *= 0.7071  # 1/sqrt(2)
            self.dy *= 0.7071
        
        # Check for key timeouts
        current_time = time.time()
        for key in list(self.key_states.keys()):
            if self.key_states[key] and current_time - self.key_press_time.get(key, 0) > self.key_timeout:
                self.key_states[key] = False

    def handle_menu_input(self, key):
        current_menu = self.menus[self.current_menu]
        
        if key == curses.KEY_UP:
            self.menu_selection = (self.menu_selection - 1) % len(current_menu)
            self.needs_redraw = True
        elif key == curses.KEY_DOWN:
            self.menu_selection = (self.menu_selection + 1) % len(current_menu)
            self.needs_redraw = True
        elif key == 10 or key == 13:  # Enter key
            self.handle_menu_selection()
        elif key == 27:  # ESC key
            if self.current_menu == "main":
                self.in_menu = False
            else:
                self.current_menu = "main"
                self.menu_selection = 0
            self.needs_redraw = True

    def handle_menu_selection(self):
        """Handle menu item selection."""
        if self.current_menu == "main":
            if self.menu_selection == 0:  # Resume Game
                self.in_menu = False
                self.needs_redraw = True
            elif self.menu_selection == 1:  # Plugin Management
                self.current_menu = "plugins"
                self.menu_selection = 0
            elif self.menu_selection == 2:  # Color Settings
                # Temporarily exit menu mode
                self.in_menu = False
                self.needs_redraw = True
                
                # Show color settings menu
                self.show_color_settings_menu()
                
                # Return to menu mode
                self.in_menu = True
                self.needs_redraw = True
            elif self.menu_selection == 3:  # Key Bindings
                # Temporarily exit menu mode
                self.in_menu = False
                self.needs_redraw = True
                
                # Show key bindings menu
                self.show_key_bindings_menu()
                
                # Return to menu mode
                self.in_menu = True
                self.needs_redraw = True
            elif self.menu_selection == 4:  # Location Settings
                self.current_menu = "location"
                self.menu_selection = 0
            elif self.menu_selection == 5:  # Audio Settings
                # Temporarily exit menu mode
                self.in_menu = False
                self.needs_redraw = True
                
                # Show audio settings menu
                self.show_audio_settings_menu()
                
                # Return to menu mode
                self.in_menu = True
                self.needs_redraw = True
            elif self.menu_selection == 6:  # 3D Settings
                # Temporarily exit menu mode
                self.in_menu = False
                self.needs_redraw = True
                
                # Show 3D settings menu
                self.show_3d_settings_menu()
                
                # Return to menu mode
                self.in_menu = True
                self.needs_redraw = True
            elif self.menu_selection == 7:  # Network
                # Temporarily exit menu mode
                self.in_menu = False
                self.needs_redraw = True
                
                # Show network menu
                self.show_network_menu()
                
                # Return to menu mode
                self.in_menu = True
                self.needs_redraw = True
            elif self.menu_selection == 8:  # Quit
                self.running = False
        elif self.current_menu == "plugins":
            if self.menu_selection < len(self.plugins):
                # Toggle plugin active state
                plugin = self.plugins[self.menu_selection]
                if plugin.active:
                    plugin.deactivate()
                else:
                    plugin.activate()
                # Update menu text
                self.menus["plugins"][self.menu_selection] = f"{plugin.name} {'[Active]' if plugin.active else '[Inactive]'}"
                self.needs_redraw = True
                # Save plugin config
                self.save_plugin_config()
            else:
                # Back to main menu
                self.current_menu = "main"
                self.menu_selection = 0
        elif self.current_menu == "location":
            if self.menu_selection == 0:  # Start at Last Location
                self.start_at_last_location = not self.start_at_last_location
                self.menus["location"][0] = "Start at Last Location: " + ("Yes" if self.start_at_last_location else "No")
                self.save_location_settings()
                self.needs_redraw = True
            elif self.menu_selection == 1:  # Save Current Location
                self.save_current_location()
                self.message = "Current location saved"
                self.message_timeout = 2.0
                self.in_menu = False
                self.needs_redraw = True
            elif self.menu_selection == 2:  # Reset to Origin
                self.world_x = 0
                self.world_y = 0
                self.save_current_location()
                self.message = "Reset to origin"
                self.message_timeout = 2.0
                self.in_menu = False
                self.needs_redraw = True
            elif self.menu_selection == 3:  # Back to Main Menu
                self.current_menu = "main"
                self.menu_selection = 0

    def update(self):
        """Update the game state."""
        # Calculate time since last update
        current_time = time.time()
        dt = current_time - self.last_update
        
        # Update FPS counter
        self.update_fps(dt)
        
        # Update message timeout
        if self.message_timeout > 0:
            self.message_timeout -= dt
            if self.message_timeout <= 0:
                self.message = ""
                self.needs_redraw = True
        
        # Update all active plugins
        for plugin in self.plugins:
            if plugin.active:
                plugin.update(dt)
                
        # Update direction string for status display
        self.direction = ""
        if self.dy < 0:
            self.direction += "N"
        elif self.dy > 0:
            self.direction += "S"
        if self.dx > 0:
            self.direction += "E"
        elif self.dx < 0:
            self.direction += "W"

    def handle_movement(self):
        """Handle player movement."""
        # Calculate time since last update
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Calculate movement based on speed and time
        move_amount = self.move_speed * dt
        
        # Apply movement if direction keys are pressed
        if self.dx != 0 or self.dy != 0:
            # Accumulate movement
            self.acc_x += self.dx * move_amount
            self.acc_y += self.dy * move_amount
            
            # Apply accumulated movement
            dx_int = int(self.acc_x)
            dy_int = int(self.acc_y)
            
            if dx_int != 0 or dy_int != 0:
                # Update world coordinates
                self.world_x += dx_int
                self.world_y += dy_int
                
                # Subtract applied movement from accumulator
                self.acc_x -= dx_int
                self.acc_y -= dy_int
                
                # Mark for redraw
                self.needs_redraw = True
                
                # Check if we moved over a fuel ('&') character
                self.check_for_fuel()
                
                # Update character cache
                self.update_char_cache()
        
        # Update all active plugins
        for plugin in self.plugins:
            if plugin.active:
                plugin.update(dt)

    def update_fps(self, dt):
        """Update the FPS calculation."""
        # Add the current frame time to the list
        self.frame_times.append(dt)
        
        # Keep only the last 60 frames for the calculation
        if len(self.frame_times) > 60:
            self.frame_times.pop(0)
            
        # Update the FPS value every 0.5 seconds
        self.fps_update_timer += dt
        if self.fps_update_timer >= 0.5:
            self.fps_update_timer = 0
            
            # Calculate average frame time and convert to FPS
            if self.frame_times:
                avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                if avg_frame_time > 0:
                    self.current_fps = 1.0 / avg_frame_time
                else:
                    self.current_fps = 0
            
            # Force redraw to update the FPS display
            self.needs_redraw = True

    def check_for_fuel(self):
        """Check if the player is on a fuel ('&') character and collect it."""
        # Get the character at the player's position
        char = self.get_char_at(self.world_x, self.world_y)
        
        # If it's a fuel character and we haven't collected it before
        if char == '&':
            fuel_key = self.get_space_key(self.world_x, self.world_y)
            if fuel_key not in self.fuel_collected:
                # Collect the fuel
                self.fuel += 1
                self.fuel_collected[fuel_key] = True
                
                # Create a space where the fuel was
                self.spaces[fuel_key] = (self.world_x, self.world_y)
                self.save_spaces()
                
                # Show a message
                self.message = f"Fuel collected! Total: {self.fuel}"
                self.message_timeout = 2.0  # Show message for 2 seconds
                self.needs_redraw = True

    def render(self):
        """Render the game."""
        if not self.needs_redraw:
            return
            
        self.screen.clear()
        
        if self.in_menu:
            self.render_menu()
        else:
            # Render the game world
            self.render_game_world()
            
            # Render coordinate notches on top of the game world
            self.render_coordinate_notches()
            
            # Render UI elements
            self.render_ui()
            
            # Force a refresh to ensure all terminal drawing is complete
            # before any plugins (like 3D GUI) start reading from the screen
            self.screen.refresh()
            
            # Render plugins
            for plugin in self.plugins:
                if plugin.active:
                    plugin.render(self.screen)
        
        self.screen.refresh()
        self.needs_redraw = False

    def render_coordinate_notches(self):
        """Render coordinate notches on the left and top of the game world."""
        # Calculate the world coordinates for the visible area
        # Convert to integers to avoid float issues
        start_x = int(round(self.world_x)) - self.max_x // 2
        start_y = int(round(self.world_y)) - self.max_y // 2
        end_x = start_x + self.max_x
        end_y = start_y + self.max_y
        
        # Find the nearest multiples of 10 for the visible area
        notch_start_x = (start_x // 10) * 10
        notch_start_y = (start_y // 10) * 10
        
        # Define the rendering boundaries (same as in render_game_world)
        notch_left_margin = 3
        notch_top_margin = 6
        bottom_margin = 10
        render_bottom = self.max_y - bottom_margin
        
        # Render horizontal notches (on top)
        for x in range(notch_start_x, end_x + 10, 10):
            # Calculate screen position
            screen_x = x - start_x
            
            # Skip if out of bounds
            if screen_x < 3 or screen_x >= self.max_x:
                continue
                
            # Get the tens digit (second digit from the right)
            tens_digit = (abs(x) // 10) % 10
            
            # Determine sign
            sign = '+' if x >= 0 else '-'
            
            # Draw the notch
            try:
                # Line 3: Vertical line
                self.screen.addch(3, screen_x, '|', self.coordinate_notches_color)
                
                # Line 4: Sign
                self.screen.addch(4, screen_x, sign, self.coordinate_notches_color)
                
                # Line 5: Tens digit
                self.screen.addch(5, screen_x, str(tens_digit), self.coordinate_notches_color)
            except:
                pass  # Ignore errors from writing to the bottom-right corner
        
        # Render vertical notches (on left)
        for y in range(notch_start_y, end_y + 10, 10):
            # Calculate screen position
            screen_y = y - start_y
            
            # Skip if out of bounds or in the notch area or below the rendering area
            if screen_y < notch_top_margin or screen_y >= render_bottom:
                continue
                
            # Get the tens digit (second digit from the right)
            tens_digit = (abs(y) // 10) % 10
            
            # Determine sign
            sign = '+' if y >= 0 else '-'
            
            # Draw the notch
            try:
                # Column 0: Horizontal line
                self.screen.addch(screen_y, 0, '-', self.coordinate_notches_color)
                
                # Column 1: Sign
                self.screen.addch(screen_y, 1, sign, self.coordinate_notches_color)
                
                # Column 2: Tens digit
                self.screen.addch(screen_y, 2, str(tens_digit), self.coordinate_notches_color)
            except:
                pass  # Ignore errors from writing to the bottom-right corner

    def render_game_world(self):
        # Draw the background
        half_width = self.max_x // 2
        half_height = self.max_y // 2
        
        # Leave space for coordinate notches (3 columns on left, 6 rows at top)
        notch_left_margin = 3
        notch_top_margin = 6
        
        # Calculate the bottom margin to ensure we don't draw outside valid area
        bottom_margin = 12  # Increased to 12 to ensure we don't draw outside valid area
        
        # Calculate the actual rendering area
        render_top = notch_top_margin
        render_bottom = self.max_y - bottom_margin
        render_left = notch_left_margin
        render_right = self.max_x - 2  # Leave 2 columns on the right
        
        # Draw a very visible border around the rendering area
        # Top border with '#' at corners
        try:
            self.screen.addch(render_top - 1, render_left - 1, '#')
            for x in range(render_left, render_right):
                self.screen.addch(render_top - 1, x, '#')
            self.screen.addch(render_top - 1, render_right, '#')
        except:
            pass
        
        # Bottom border with '#' at corners
        try:
            self.screen.addch(render_bottom, render_left - 1, '#')
            bottom_border = '#' * (render_right - render_left)
            self.screen.addstr(render_bottom, render_left, bottom_border)
            self.screen.addch(render_bottom, render_right, '#')
        except:
            pass
        
        # Left and right borders
        for y in range(render_top, render_bottom):
            try:
                self.screen.addch(y, render_left - 1, '#')
                self.screen.addch(y, render_right, '#')
            except:
                pass
        
        # Add a debug message at the bottom of the border
        try:
            debug_msg = f"Border: {render_top}-{render_bottom}, {render_left}-{render_right}"
            self.screen.addstr(render_bottom + 1, render_left, debug_msg)
        except:
            pass
        
        # Adjust visible area to account for notch margins and ensure we stay within the border
        for y in range(render_top, render_bottom):
            for x in range(render_left, render_right):
                # Calculate world coordinates
                world_x = x - half_width + self.world_x
                world_y = y - half_height + self.world_y
                
                # Get the character at this position
                char = self.get_char_at(world_x, world_y)
                
                # Determine color based on character
                color = self.background_color
                # Don't apply player color to 'X' characters in the background
                # Only the main player 'X' will get the player color
                if char == '@':
                    color = self.at_symbol_color
                elif char == '0':
                    color = self.zero_color
                elif char == '&':
                    color = self.fuel_color
                elif char == '.':
                    color = self.dot_color
                
                # Draw the character
                try:
                    self.screen.addch(y, x, char, color)
                except:
                    pass  # Ignore errors from writing to the bottom-right corner
        
        # Draw player at center of screen
        player_y = self.max_y // 2
        player_x = self.max_x // 2
        
        try:
            self.screen.addch(player_y, player_x, self.player_char, self.player_color | curses.A_BOLD)
        except:
            pass  # Ignore errors from writing to the bottom-right corner
        
        # Draw player position and fuel info at the bottom
        status_line = f"Top-Left: ({self.world_x - half_width + notch_left_margin}, {self.world_y - half_height + notch_top_margin}) | X: ({self.world_x}, {self.world_y}) | Dir: {self.dx},{self.dy} | Fuel: {self.fuel}"
        try:
            self.screen.addstr(self.max_y - 1, 0, status_line)
        except:
            pass  # Ignore errors from writing to the bottom-right corner
        
        # Display message if there is one
        if self.message and self.message_timeout > 0:
            try:
                self.screen.addstr(self.max_y - 2, 0, self.message)
            except:
                pass  # Ignore errors from writing to the bottom-right corner
        
        # Display snake count on the second line with a black background
        snake_count = 0
        for plugin in self.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                snake_count = len(plugin.snakes)
                break
        
        try:
            snake_indicator = f"Snakes Detected: {snake_count}"
            self.screen.addstr(1, 0, snake_indicator, curses.color_pair(0) | curses.A_BOLD)
        except:
            pass  # Ignore errors

    def render_menu(self):
        # Draw semi-transparent overlay
        for y in range(1, self.max_y - 2):
            for x in range(self.max_x - 1):
                # Get current character at this position
                try:
                    char = chr(self.screen.inch(y, x) & 0xFF)
                    # Draw a semi-transparent overlay (darken the background)
                    if char != ' ':
                        self.screen.addch(y, x, char, curses.A_DIM)
                except:
                    pass
        
        # Draw menu background
        menu_width = 40
        menu_height = len(self.menus[self.current_menu]) + 4
        menu_x = (self.max_x - menu_width) // 2
        menu_y = (self.max_y - menu_height) // 2
        
        # Draw border
        for y in range(menu_y, menu_y + menu_height):
            for x in range(menu_x, menu_x + menu_width):
                if (y == menu_y or y == menu_y + menu_height - 1 or 
                    x == menu_x or x == menu_x + menu_width - 1):
                    self.screen.addch(y, x, '#', self.menu_color)
                else:
                    self.screen.addch(y, x, ' ', self.menu_color)
        
        # Draw title
        title = "Menu" if self.current_menu == "main" else "Plugin Management"
        self.screen.addstr(menu_y + 1, menu_x + (menu_width - len(title)) // 2, title, self.menu_color)
        
        # Draw menu items
        for i, item in enumerate(self.menus[self.current_menu]):
            if i == self.menu_selection:
                # Highlight selected item
                self.screen.addstr(menu_y + i + 3, menu_x + 2, "> " + item + " <", self.menu_color | curses.A_BOLD)
            else:
                self.screen.addstr(menu_y + i + 3, menu_x + 4, item, self.menu_color)

    def render_ui(self):
        # Draw top menu bar
        self.screen.addstr(0, 0, " " * (self.max_x - 1), self.menu_color)
        menu_text = "TextWarp Adventure | Press ESC for Menu"
        self.screen.addstr(0, (self.max_x - len(menu_text)) // 2, menu_text, self.menu_color)
        
        # Draw snake indicator on second line
        snake_count = sum(1 for plugin in self.plugins if isinstance(plugin, SnakePlugin) and plugin.active for _ in plugin.snakes)
        snake_indicator = f"Snakes Detected: {snake_count}"
        # Fill the entire line with black background
        self.screen.addstr(1, 0, " " * (self.max_x - 1), self.snake_indicator_color)
        # Draw the indicator text
        self.screen.addstr(1, 2, snake_indicator, self.snake_indicator_color)
        
        # Draw FPS counter
        fps_text = f"FPS: {self.current_fps:.2f}"
        self.screen.addstr(1, self.max_x - len(fps_text) - 2, fps_text, self.fps_color)

    def cleanup(self):
        # Clean up curses
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()

    def get_char_at(self, x, y):
        """Get the character at world coordinates (x, y)"""
        # Convert coordinates to integers if they are floats
        if isinstance(x, float):
            x = int(round(x))
        if isinstance(y, float):
            y = int(round(y))
            
        # Check if we have this character in the cache
        cache_key = f"{x},{y}"
        if cache_key in self.char_cache:
            return self.char_cache[cache_key]
            
        # Calculate character if not in cache
        # Check if there's a space at this location
        space_key = self.get_space_key(x, y)
        if space_key in self.spaces:
            char = ' '
        else:
            # Calculate character based on location ID
            location_id = (x + y * 1000) % 127
            char = chr(location_id)
            
        # Store in cache
        self.char_cache[cache_key] = char
        return char
        
    def update_char_cache(self):
        """Update the character cache when player moves."""
        # Only update if player has moved
        if self.world_x != self.last_player_x or self.world_y != self.last_player_y:
            # Clear the cache
            self.char_cache = {}
            # Update last position
            self.last_player_x = self.world_x
            self.last_player_y = self.world_y
            # Mark cache as valid
            self.cache_valid = True

    def get_space_key(self, x, y):
        """Generate a hash key for a space at coordinates (x, y)"""
        # Create a string representation of the coordinates
        coord_str = f"{x},{y}"
        # Hash the coordinates to create a unique key
        return hashlib.md5(coord_str.encode()).hexdigest()

    def load_spaces(self):
        """Load spaces from file"""
        spaces = {}
        try:
            if os.path.exists('spaces.json'):
                with open('spaces.json', 'r') as f:
                    spaces = json.load(f)
        except Exception as e:
            print(f"Error loading spaces: {e}")
        return spaces

    def save_spaces(self):
        """Save spaces to file"""
        try:
            with open('spaces.json', 'w') as f:
                json.dump(self.spaces, f)
        except Exception as e:
            print(f"Error saving spaces: {e}")

    def check_window_resize(self):
        """Check if the terminal window has been resized and update accordingly."""
        # Get current terminal dimensions
        new_y, new_x = self.screen.getmaxyx()
        
        # Check if dimensions have changed
        if new_y != self.max_y or new_x != self.max_x:
            # Update dimensions
            self.max_y = new_y
            self.max_x = new_x
            
            # Clear screen and force redraw
            self.screen.clear()
            self.needs_redraw = True
            
            # Resize the curses window
            curses.resizeterm(new_y, new_x)
            
            # Show a message about the resize
            self.message = f"Window resized to {new_x}x{new_y}"
            self.message_timeout = 2.0
            
            # Return True if resized
            return True
            
        # Return False if not resized
        return False

    def run(self):
        try:
            self.setup()
            
            # Set up signal handler for window resize
            signal.signal(signal.SIGWINCH, self.handle_resize_signal)
            
            # Load last saved location
            if self.start_at_last_location:
                try:
                    with open('last_location.json', 'r') as f:
                        last_location = json.load(f)
                        self.world_x = last_location['x']
                        self.world_y = last_location['y']
                except:
                    pass  # Ignore errors if the file doesn't exist or is invalid
            
            while self.running:
                # Check for window resize
                if self.check_resize:
                    self.check_window_resize()
                    self.check_resize = False
                
                self.handle_input()
                self.handle_movement()
                self.update()
                self.render()
                
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
                
        except Exception as e:
            self.cleanup()
            print(f"An error occurred: {e}")
            # Print stack trace for debugging
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
            # Save last location
            try:
                with open('last_location.json', 'w') as f:
                    json.dump({'x': self.world_x, 'y': self.world_y}, f)
            except:
                pass  # Ignore errors if the file doesn't exist or is invalid

    def handle_resize_signal(self, signum, frame):
        """Signal handler for SIGWINCH (window resize)."""
        self.check_resize = True

    def show_color_settings_menu(self):
        """Show the color settings menu."""
        # Variables for menu navigation
        current_selection = 0
        color_names = list(self.color_settings.keys())
        in_color_menu = True
        
        # Color options
        color_options = {
            0: {"name": "Black", "value": curses.COLOR_BLACK},
            1: {"name": "Red", "value": curses.COLOR_RED},
            2: {"name": "Green", "value": curses.COLOR_GREEN},
            3: {"name": "Yellow", "value": curses.COLOR_YELLOW},
            4: {"name": "Blue", "value": curses.COLOR_BLUE},
            5: {"name": "Magenta", "value": curses.COLOR_MAGENTA},
            6: {"name": "Cyan", "value": curses.COLOR_CYAN},
            7: {"name": "White", "value": curses.COLOR_WHITE},
            8: {"name": "Default", "value": -1}
        }
        
        # Main loop for color settings menu
        while in_color_menu:
            # Clear screen
            self.screen.clear()
            
            # Draw header
            self.screen.addstr(0, 0, "Color Settings", self.menu_color | curses.A_BOLD)
            self.screen.addstr(1, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw instructions
            self.screen.addstr(2, 0, "Use ↑/↓ to select an element, ←/→ to change foreground/background color", self.menu_color)
            self.screen.addstr(3, 0, "Press ENTER to apply changes, ESC to exit", self.menu_color)
            self.screen.addstr(4, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw color settings
            for i, name in enumerate(color_names):
                setting = self.color_settings[name]
                # Create a sample of the color
                color_pair = curses.color_pair(setting['color_id'])
                
                # Get color names
                fg_name = "Default" if setting['fg'] == -1 else next((opt["name"] for opt in color_options.values() if opt["value"] == setting['fg']), "Unknown")
                bg_name = "Default" if setting['bg'] == -1 else next((opt["name"] for opt in color_options.values() if opt["value"] == setting['bg']), "Unknown")
                
                # Highlight the selected item
                if i == current_selection:
                    attr = self.selected_menu_color | curses.A_BOLD
                else:
                    attr = self.menu_color
                
                # Draw the item
                self.screen.addstr(i + 6, 2, f"{name}", attr)
                self.screen.addstr(i + 6, 25, f"FG: {fg_name}", attr)
                self.screen.addstr(i + 6, 45, f"BG: {bg_name}", attr)
                
                # Draw a sample with the current color
                try:
                    sample_text = " SAMPLE "
                    self.screen.addstr(i + 6, 65, sample_text, color_pair | setting['attr'])
                except:
                    pass
            
            # Draw footer
            self.screen.addstr(self.max_y - 2, 0, "═" * (self.max_x - 1), self.menu_color)
            self.screen.addstr(self.max_y - 1, 0, "R: Reset to defaults", self.menu_color)
            
            # Refresh screen
            self.screen.refresh()
            
            # Get input
            key = self.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(color_names)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(color_names)
            elif key == curses.KEY_LEFT:
                # Change foreground color
                name = color_names[current_selection]
                setting = self.color_settings[name]
                current_fg = setting['fg']
                
                # Find the next color in the list
                next_color_idx = 0
                for idx, opt in color_options.items():
                    if opt["value"] == current_fg:
                        next_color_idx = (idx - 1) % len(color_options)
                        break
                
                # Update the color
                setting['fg'] = color_options[next_color_idx]["value"]
                curses.init_pair(setting['color_id'], setting['fg'], setting['bg'])
                
                # Update the attribute if needed
                if name == "Player":
                    self.player_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Menu":
                    self.menu_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Selected Menu":
                    self.selected_menu_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Panel":
                    self.panel_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "@ Symbol":
                    self.at_symbol_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Snake Indicator":
                    self.snake_indicator_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "FPS Counter":
                    self.fps_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Snake":
                    self.snake_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Fuel":
                    self.fuel_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Egg":
                    self.zero_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Dot":
                    self.dot_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Coordinate Notches":
                    self.coordinate_notches_color = curses.color_pair(setting['color_id']) | setting['attr']
                
            elif key == curses.KEY_RIGHT:
                # Change background color
                name = color_names[current_selection]
                setting = self.color_settings[name]
                current_bg = setting['bg']
                
                # Find the next color in the list
                next_color_idx = 0
                for idx, opt in color_options.items():
                    if opt["value"] == current_bg:
                        next_color_idx = (idx + 1) % len(color_options)
                        break
                
                # Update the color
                setting['bg'] = color_options[next_color_idx]["value"]
                curses.init_pair(setting['color_id'], setting['fg'], setting['bg'])
                
                # Update the attribute if needed
                if name == "Player":
                    self.player_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Menu":
                    self.menu_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Selected Menu":
                    self.selected_menu_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Panel":
                    self.panel_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "@ Symbol":
                    self.at_symbol_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Snake Indicator":
                    self.snake_indicator_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "FPS Counter":
                    self.fps_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Snake":
                    self.snake_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Fuel":
                    self.fuel_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Egg":
                    self.zero_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Dot":
                    self.dot_color = curses.color_pair(setting['color_id']) | setting['attr']
                elif name == "Coordinate Notches":
                    self.coordinate_notches_color = curses.color_pair(setting['color_id']) | setting['attr']
                
            elif key == ord('r') or key == ord('R'):
                # Reset to defaults
                self.color_settings = copy.deepcopy(self.original_color_settings)
                
                # Reinitialize all color pairs
                for name, setting in self.color_settings.items():
                    curses.init_pair(setting['color_id'], setting['fg'], setting['bg'])
            
                # Update all color attributes
                self.player_color = curses.color_pair(self.color_settings["Player"]["color_id"]) | self.color_settings["Player"]["attr"]
                self.menu_color = curses.color_pair(self.color_settings["Menu"]["color_id"]) | self.color_settings["Menu"]["attr"]
                self.selected_menu_color = curses.color_pair(self.color_settings["Selected Menu"]["color_id"]) | self.color_settings["Selected Menu"]["attr"]
                self.panel_color = curses.color_pair(self.color_settings["Panel"]["color_id"]) | self.color_settings["Panel"]["attr"]
                self.at_symbol_color = curses.color_pair(self.color_settings["@ Symbol"]["color_id"]) | self.color_settings["@ Symbol"]["attr"]
                self.snake_indicator_color = curses.color_pair(self.color_settings["Snake Indicator"]["color_id"]) | self.color_settings["Snake Indicator"]["attr"]
                self.fps_color = curses.color_pair(self.color_settings["FPS Counter"]["color_id"]) | self.color_settings["FPS Counter"]["attr"]
                self.snake_color = curses.color_pair(self.color_settings["Snake"]["color_id"]) | self.color_settings["Snake"]["attr"]
                self.fuel_color = curses.color_pair(self.color_settings["Fuel"]["color_id"]) | self.color_settings["Fuel"]["attr"]
                self.zero_color = curses.color_pair(self.color_settings["Egg"]["color_id"]) | self.color_settings["Egg"]["attr"]
                self.dot_color = curses.color_pair(self.color_settings["Dot"]["color_id"]) | self.color_settings["Dot"]["attr"]
                self.coordinate_notches_color = curses.color_pair(self.color_settings["Coordinate Notches"]["color_id"]) | self.color_settings["Coordinate Notches"]["attr"]
                
            elif key == 10:  # Enter key
                # Save color settings
                self.save_color_settings()
                in_color_menu = False
            elif key == 27:  # Escape key
                in_color_menu = False
        
        # Force redraw
        self.needs_redraw = True
    
    def save_color_settings(self):
        """Save the current color settings to a file."""
        # Create a dictionary to store the color settings
        color_data = {}
        for name, setting in self.color_settings.items():
            color_data[name] = {
                "fg": setting['fg'],
                "bg": setting['bg'],
                "attr": setting['attr']
            }
        
        # Save the color settings to a file
        try:
            with open("colors.json", "w") as f:
                json.dump(color_data, f)
        except:
            pass  # Ignore errors
    
    def load_color_settings(self):
        """Load color settings from a file."""
        try:
            with open("colors.json", "r") as f:
                color_data = json.load(f)
            
            # Update the color settings
            for name, data in color_data.items():
                if name in self.color_settings:
                    self.color_settings[name]['fg'] = data['fg']
                    self.color_settings[name]['bg'] = data['bg']
                    self.color_settings[name]['attr'] = data['attr']
                    
                    # Update the color pair
                    curses.init_pair(self.color_settings[name]['color_id'], data['fg'], data['bg'])
            
            # Update all color attributes
            self.player_color = curses.color_pair(self.color_settings["Player"]["color_id"]) | self.color_settings["Player"]["attr"]
            self.menu_color = curses.color_pair(self.color_settings["Menu"]["color_id"]) | self.color_settings["Menu"]["attr"]
            self.selected_menu_color = curses.color_pair(self.color_settings["Selected Menu"]["color_id"]) | self.color_settings["Selected Menu"]["attr"]
            self.panel_color = curses.color_pair(self.color_settings["Panel"]["color_id"]) | self.color_settings["Panel"]["attr"]
            self.at_symbol_color = curses.color_pair(self.color_settings["@ Symbol"]["color_id"]) | self.color_settings["@ Symbol"]["attr"]
            self.snake_indicator_color = curses.color_pair(self.color_settings["Snake Indicator"]["color_id"]) | self.color_settings["Snake Indicator"]["attr"]
            self.fps_color = curses.color_pair(self.color_settings["FPS Counter"]["color_id"]) | self.color_settings["FPS Counter"]["attr"]
            self.snake_color = curses.color_pair(self.color_settings["Snake"]["color_id"]) | self.color_settings["Snake"]["attr"]
            self.fuel_color = curses.color_pair(self.color_settings["Fuel"]["color_id"]) | self.color_settings["Fuel"]["attr"]
            self.zero_color = curses.color_pair(self.color_settings["Egg"]["color_id"]) | self.color_settings["Egg"]["attr"]
            self.dot_color = curses.color_pair(self.color_settings["Dot"]["color_id"]) | self.color_settings["Dot"]["attr"]
            self.coordinate_notches_color = curses.color_pair(self.color_settings["Coordinate Notches"]["color_id"]) | self.color_settings["Coordinate Notches"]["attr"]
        except:
            pass  # Ignore errors if the file doesn't exist or is invalid

    def load_location_settings(self):
        """Load location settings from a file."""
        try:
            with open("location_settings.json", "r") as f:
                location_data = json.load(f)
            
            # Update the location settings
            self.start_at_last_location = location_data.get("start_at_last_location", True)
        except:
            pass  # Ignore errors if the file doesn't exist or is invalid

    def save_location_settings(self):
        """Save location settings to a file."""
        try:
            with open("location_settings.json", "w") as f:
                json.dump({
                    "start_at_last_location": self.start_at_last_location
                }, f)
        except:
            pass  # Ignore errors if the file can't be written

    def save_current_location(self):
        """Save the current location to a file."""
        try:
            with open("last_location.json", "w") as f:
                json.dump({
                    "x": self.world_x,
                    "y": self.world_y
                }, f)
        except:
            pass  # Ignore errors if the file can't be written

    def show_audio_settings_menu(self):
        """Show the audio settings menu."""
        # Find the audio plugin
        audio_plugin = None
        for plugin in self.plugins:
            if isinstance(plugin, AudioPlugin):
                audio_plugin = plugin
                break
                
        if not audio_plugin:
            self.message = "Audio plugin not found!"
            self.message_timeout = 3.0
            return
            
        # Make sure the plugin is active
        if not audio_plugin.active:
            audio_plugin.activate()
            
        # Show the audio menu
        audio_plugin.show_audio_menu()

    def show_key_bindings_menu(self):
        """Show the key bindings menu."""
        # Variables for menu navigation
        current_selection = 0
        in_key_bindings_menu = True
        
        # Menu options
        menu_options = [
            "Terminal Controls",
            "3D GUI Controls",
            "Reset All to Defaults",
            "Back to Main Menu"
        ]
        
        # Main loop for key bindings menu
        while in_key_bindings_menu:
            # Clear screen
            self.screen.clear()
            
            # Draw header
            self.screen.addstr(0, 0, "Key Bindings Settings", self.menu_color | curses.A_BOLD)
            self.screen.addstr(1, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw instructions
            self.screen.addstr(2, 0, "Use ↑/↓ to select an option, ENTER to select", self.menu_color)
            self.screen.addstr(3, 0, "Press ESC to exit", self.menu_color)
            self.screen.addstr(4, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw menu options
            for i, option in enumerate(menu_options):
                # Highlight the selected item
                if i == current_selection:
                    attr = self.menu_color | curses.A_BOLD
                else:
                    attr = self.menu_color
                
                # Draw the item
                self.screen.addstr(i + 6, 2, option, attr)
            
            # Draw footer
            self.screen.addstr(self.max_y - 2, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Refresh screen
            self.screen.refresh()
            
            # Get input
            key = self.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(menu_options)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(menu_options)
            elif key == 10:  # Enter key
                if current_selection == 0:  # Terminal Controls
                    self.show_terminal_key_bindings()
                elif current_selection == 1:  # 3D GUI Controls
                    self.show_gui_key_bindings()
                elif current_selection == 2:  # Reset All to Defaults
                    self.key_bindings.reset_to_defaults()
                    self.key_bindings.save_bindings()
                    self.message = "All key bindings reset to defaults"
                    self.message_timeout = 2.0
                elif current_selection == 3:  # Back to Main Menu
                    in_key_bindings_menu = False
            elif key == 27:  # Escape key
                in_key_bindings_menu = False
        
        # Force redraw
        self.needs_redraw = True

    def show_terminal_key_bindings(self):
        """Show the terminal key bindings menu."""
        # Variables for menu navigation
        current_selection = 0
        key_bindings = list(self.key_bindings.terminal_keys.keys())
        in_key_bindings_menu = True
        
        # Main loop for key bindings menu
        while in_key_bindings_menu:
            # Clear screen
            self.screen.clear()
            
            # Draw header
            self.screen.addstr(0, 0, "Terminal Key Bindings", self.menu_color | curses.A_BOLD)
            self.screen.addstr(1, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw instructions
            self.screen.addstr(2, 0, "Use ↑/↓ to select a key binding, ENTER to edit", self.menu_color)
            self.screen.addstr(3, 0, "Press ESC to exit", self.menu_color)
            self.screen.addstr(4, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw key bindings
            for i, key in enumerate(key_bindings):
                # Highlight the selected item
                if i == current_selection:
                    attr = self.menu_color | curses.A_BOLD
                else:
                    attr = self.menu_color
                
                # Get the key name for display
                key_code = self.key_bindings.terminal_keys[key]
                key_name = self.key_bindings.get_key_name(key_code)
                action_desc = self.key_bindings.get_action_description(key)
                
                # Draw the item
                self.screen.addstr(i + 6, 2, f"{action_desc}: {key_name}", attr)
            
            # Draw footer
            self.screen.addstr(self.max_y - 2, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Refresh screen
            self.screen.refresh()
            
            # Get input
            key = self.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(key_bindings)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(key_bindings)
            elif key == 10:  # Enter key
                # Edit the selected key binding
                self.edit_key_binding(key_bindings[current_selection])
                # Save the changes
                self.key_bindings.save_bindings()
            elif key == 27:  # Escape key
                in_key_bindings_menu = False
        
        # Force redraw
        self.needs_redraw = True

    def show_gui_key_bindings(self):
        """Show the 3D GUI key bindings menu."""
        # Find the GUI3D plugin
        gui3d_plugin = None
        for plugin in self.plugins:
            if isinstance(plugin, GUI3DPlugin):
                gui3d_plugin = plugin
                break
                
        if gui3d_plugin:
            # Show the GUI key bindings menu
            gui3d_plugin.show_key_bindings_menu()
        else:
            # Show message that plugin is not found
            self.message = "3D GUI plugin not found"
            self.message_timeout = 2.0

    def edit_key_binding(self, key):
        """Edit a key binding."""
        # Variables for editing
        new_key = None
        editing = True
        
        # Main loop for editing
        while editing:
            # Clear screen
            self.screen.clear()
            
            # Draw header
            self.screen.addstr(0, 0, "Edit Key Binding", self.menu_color | curses.A_BOLD)
            self.screen.addstr(1, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw instructions
            self.screen.addstr(2, 0, "Press a key to bind it to this action", self.menu_color)
            self.screen.addstr(3, 0, "Press ESC to cancel", self.menu_color)
            self.screen.addstr(4, 0, "═" * (self.max_x - 1), self.menu_color)
            
            # Draw current key binding
            self.screen.addstr(6, 2, f"Current key binding: {self.key_bindings.terminal_keys[key]}", self.menu_color)
            
            # Refresh screen
            self.screen.refresh()
            
            # Get input
            new_key = self.screen.getch()
            
            # Handle input
            if new_key == 27:  # Escape key
                editing = False
            else:
                # Update the key binding
                self.key_bindings.terminal_keys[key] = new_key
                editing = False
        
        # Force redraw
        self.needs_redraw = True

    def show_3d_settings_menu(self):
        """Show the 3D settings menu."""
        # Find the GUI3D plugin
        gui3d_plugin = None
        for plugin in self.plugins:
            if isinstance(plugin, GUI3DPlugin):
                gui3d_plugin = plugin
                break
                
        if gui3d_plugin:
            # Show the 3D settings menu
            gui3d_plugin.show_3d_settings_menu()
        else:
            # Show message that plugin is not found
            self.message = "3D GUI plugin not found"
            self.message_timeout = 2.0

    def show_network_menu(self):
        """Show the network menu."""
        # Find the Network plugin
        network_plugin = None
        for plugin in self.plugins:
            if isinstance(plugin, NetworkPlugin):
                network_plugin = plugin
                break
                
        if network_plugin:
            # Show the network menu
            network_plugin.show_network_menu()
        else:
            # Show message that plugin is not found
            self.message = "Network plugin not found"
            self.message_timeout = 2.0

def main():
    """Main function to run the game."""
    try:
        # Initialize curses
        screen = curses.initscr()
        game = TextAdventure(screen)
        game.run()
    finally:
        # Clean up curses
        curses.endwin()

if __name__ == "__main__":
    main()