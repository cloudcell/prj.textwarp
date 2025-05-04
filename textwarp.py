#!/usr/bin/env python3
import curses
import time
import math
import os
import json
import hashlib
import random
import signal
from plugins.base import Plugin
from plugins.snake import SnakePlugin
from plugins.graph_classifier import GraphClassifierPlugin
from plugins.network import NetworkPlugin

class TextAdventure:
    def __init__(self):
        self.screen = None
        self.running = True
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
        self.max_y = 0
        self.max_x = 0
        self.last_update = time.time()
        self.move_speed = 5  # Integer cells per second
        self.dx = 0  # Horizontal movement direction
        self.dy = 0  # Vertical movement direction
        # World coordinates (player is always at center of screen)
        self.world_x = 0
        self.world_y = 0
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
            "main": ["Resume Game", "Plugin Management", "Network", "Exit"],
            "plugins": []  # Will be populated with plugin names
        }
        
        # Plugins
        self.plugins = []
        self.initialize_plugins()
        self.load_plugin_config()

    def initialize_plugins(self):
        # Add plugins here
        self.plugins.append(SnakePlugin(self))
        self.plugins.append(GraphClassifierPlugin(self))
        self.plugins.append(NetworkPlugin(self))
        
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
        # Initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.curs_set(0)  # Hide cursor
        curses.noecho()
        curses.cbreak()
        self.screen.keypad(True)
        
        # Initialize colors
        curses.init_pair(1, curses.COLOR_RED, -1)  # Player color
        curses.init_pair(2, 8, -1)  # Grey background
        curses.init_pair(3, curses.COLOR_GREEN, -1)  # @ symbol color
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # 0 symbol color
        curses.init_pair(5, curses.COLOR_GREEN, -1)  # Menu color
        curses.init_pair(6, curses.COLOR_BLUE, -1)  # Snake color
        curses.init_pair(7, curses.COLOR_CYAN, -1)  # Fuel color
        curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Snake indicator with black background
        curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # FPS counter with black background
        
        self.player_color = curses.color_pair(1)
        self.background_color = curses.color_pair(2)
        self.at_symbol_color = curses.color_pair(3)
        self.zero_color = curses.color_pair(4)
        self.panel_color = curses.color_pair(2)
        self.menu_color = curses.color_pair(5)
        self.snake_color = curses.color_pair(6)
        self.fuel_color = curses.color_pair(7)
        self.snake_indicator_color = curses.color_pair(8)
        self.fps_color = curses.color_pair(9)
        
        # Get screen dimensions
        self.max_y, self.max_x = self.screen.getmaxyx()
        
        # Setup colors
        self.screen.timeout(50)  # Non-blocking input with 50ms timeout
        
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
        
        # Arrow keys
        if self.key_states.get(curses.KEY_UP, False):
            self.dy = -1
        if self.key_states.get(curses.KEY_DOWN, False):
            self.dy = 1
        if self.key_states.get(curses.KEY_LEFT, False):
            self.dx = -1
        if self.key_states.get(curses.KEY_RIGHT, False):
            self.dx = 1
            
        # WASD keys
        if self.key_states.get(ord('w'), False):
            self.dy = -1
        if self.key_states.get(ord('s'), False):
            self.dy = 1
        if self.key_states.get(ord('a'), False):
            self.dx = -1
        if self.key_states.get(ord('d'), False):
            self.dx = 1
            
        # Numeric keypad
        for numkey, (dx, dy) in self.numpad_directions.items():
            if self.key_states.get(numkey, False):
                self.dx = dx
                self.dy = dy
                
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
            elif self.menu_selection == 2:  # Network
                # Find the network plugin
                network_plugin = None
                for plugin in self.plugins:
                    if isinstance(plugin, NetworkPlugin):
                        network_plugin = plugin
                        break
                
                if network_plugin:
                    # Temporarily exit menu mode
                    self.in_menu = False
                    self.needs_redraw = True
                    
                    # Show network menu
                    network_plugin.show_network_menu()
                    
                    # Return to menu mode
                    self.in_menu = True
                    self.needs_redraw = True
            elif self.menu_selection == 3:  # Exit
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

    def update(self):
        # Calculate time delta
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # Update FPS calculation
        self.update_fps(dt)
        
        # Update message timeout
        if self.message and self.message_timeout > 0:
            self.message_timeout -= dt
            if self.message_timeout <= 0:
                self.message = ""
                self.needs_redraw = True
        
        # Update player position based on movement direction
        if not self.in_menu and (self.dx != 0 or self.dy != 0):
            # Accumulate movement
            self.acc_x += self.dx * self.move_speed * dt
            self.acc_y += self.dy * self.move_speed * dt
            
            # Apply accumulated movement when it reaches at least 1 cell
            move_x = int(self.acc_x)
            move_y = int(self.acc_y)
            
            if move_x != 0 or move_y != 0:
                self.world_x += move_x
                self.world_y += move_y
                self.acc_x -= move_x
                self.acc_y -= move_y
                self.needs_redraw = True
                
                # Check if we moved over a fuel ('&') character
                self.check_for_fuel()
        
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
        # Only redraw if needed
        if not self.needs_redraw:
            return
            
        # Clear screen
        self.screen.clear()
        
        # Render game world
        self.render_game_world()
        
        # Render menu if active
        if self.in_menu:
            self.render_menu()
        
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
        
        # Refresh screen
        self.screen.refresh()
        
        # Reset redraw flag
        self.needs_redraw = False

    def get_char_at(self, x, y):
        """Get the character at world coordinates (x, y)"""
        # Check if there's a space at this location
        space_key = self.get_space_key(x, y)
        if space_key in self.spaces:
            return ' '
            
        # Calculate character based on location ID
        location_id = (x + y * 1000) % 127
        return chr(location_id)

    def render_game_world(self):
        # Draw the background
        for y in range(1, self.max_y - 2):
            for x in range(self.max_x - 1):
                # Calculate world coordinates
                world_x = x - self.max_x // 2 + self.world_x
                world_y = y - self.max_y // 2 + self.world_y
                
                # Get character at this position
                char = self.get_char_at(world_x, world_y)
                
                # Choose color based on character
                if char == '@':
                    color = self.at_symbol_color
                elif char == '0':
                    color = self.zero_color
                elif char == '&':
                    color = self.fuel_color
                else:
                    color = self.background_color
                    
                # Draw the character
                self.screen.addch(y, x, char, color)
        
        # Draw player at center of screen
        if 0 <= self.max_y // 2 < self.max_y - 2 and 0 <= self.max_x // 2 < self.max_x - 1:
            self.screen.addch(self.max_y // 2, self.max_x // 2, self.player_char, self.player_color)
        
        # Render active plugins
        for plugin in self.plugins:
            if plugin.active:
                plugin.render(self.screen)
        
        # Draw panel at the bottom
        panel_y = self.max_y - 2
        direction = getattr(self, 'direction', '')
        
        # Determine panel text based on whether there's a message
        if self.message:
            panel_text = self.message
        else:
            panel_text = f"Top-Left: ({self.world_x - self.max_x // 2}, {self.world_y - self.max_y // 2}) | X: ({self.world_x}, {self.world_y}) | Dir: {direction} | Space: Create space | ESC: Menu | Fuel: {self.fuel}"
        
        # Fill panel background
        for x in range(self.max_x - 1):
            self.screen.addch(panel_y, x, ' ', self.panel_color)
        
        # Draw panel text
        self.screen.addstr(panel_y, 1, panel_text[:self.max_x - 3], self.panel_color)

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

    def cleanup(self):
        # Clean up curses
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()

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
            
            while self.running:
                # Check for window resize
                if self.check_resize:
                    self.check_window_resize()
                    self.check_resize = False
                
                self.handle_input()
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
            
    def handle_resize_signal(self, signum, frame):
        """Signal handler for SIGWINCH (window resize)."""
        self.check_resize = True

def main():
    game = TextAdventure()
    game.run()

if __name__ == "__main__":
    main()