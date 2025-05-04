#!/usr/bin/env python3
import curses
import time
import math
import os
import json
import hashlib
import random
from plugins.base import Plugin
from plugins.snake import SnakePlugin
from plugins.graph_classifier import GraphClassifierPlugin

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
        
        # Menu system
        self.in_menu = False
        self.current_menu = "main"
        self.menu_selection = 0
        self.menus = {
            "main": ["Resume Game", "Plugin Management", "Exit"],
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
        
        self.player_color = curses.color_pair(1)
        self.background_color = curses.color_pair(2)
        self.at_symbol_color = curses.color_pair(3)
        self.zero_color = curses.color_pair(4)
        self.panel_color = curses.color_pair(2)
        self.menu_color = curses.color_pair(5)
        self.snake_color = curses.color_pair(6)
        
        # Get screen dimensions
        self.max_y, self.max_x = self.screen.getmaxyx()
        
        # Setup colors
        self.screen.timeout(50)  # Non-blocking input with 50ms timeout
        
    def handle_input(self):
        # Get input
        key = self.screen.getch()
        self.last_key = key  # Store for debugging
        
        # Handle menu input if in menu
        if self.in_menu:
            self.handle_menu_input(key)
            # Clear any key states to prevent movement when exiting menu
            for k in self.key_states:
                self.key_states[k] = False
            # Reset movement direction
            self.dx = 0
            self.dy = 0
            return
        
        # Toggle menu with ESC key
        if key == 27:  # ESC key
            self.in_menu = True
            self.current_menu = "main"
            self.menu_selection = 0
            self.needs_redraw = True
            # Clear any key states to prevent movement when entering menu
            for k in self.key_states:
                self.key_states[k] = False
            # Reset movement direction
            self.dx = 0
            self.dy = 0
            return
            
        # Update key states based on key press/release
        if key != -1:  # A key was pressed
            if key in self.key_states:
                self.key_states[key] = True
        
        # Reset movement direction
        self.dx = 0
        self.dy = 0
        
        # Handle space key to create a space at current position
        if key == ord(' '):
            # Create a space at the current world position
            space_key = self.get_space_key(self.world_x, self.world_y)
            self.spaces[space_key] = True
            self.save_spaces()
            self.needs_redraw = True
            self.message = f"Space created at ({self.world_x}, {self.world_y})"
            self.message_timeout = time.time() + 2  # Show message for 2 seconds
            return
        
        # Check for numpad input first (takes precedence)
        if key in self.numpad_directions:
            self.dx, self.dy = self.numpad_directions[key]
        else:
            # Check vertical movement
            if (self.key_states[curses.KEY_UP] or self.key_states[ord('w')] or 
                self.key_states[ord('8')]):
                self.dy = -1
            elif (self.key_states[curses.KEY_DOWN] or self.key_states[ord('s')] or 
                  self.key_states[ord('2')]):
                self.dy = 1
                
            # Check horizontal movement
            if (self.key_states[curses.KEY_LEFT] or self.key_states[ord('a')] or 
                self.key_states[ord('4')]):
                self.dx = -1
            elif (self.key_states[curses.KEY_RIGHT] or self.key_states[ord('d')] or 
                  self.key_states[ord('6')]):
                self.dx = 1
            
            # Check diagonal movement
            if self.key_states[ord('7')]:  # NW
                self.dx = -1
                self.dy = -1
            elif self.key_states[ord('9')]:  # NE
                self.dx = 1
                self.dy = -1
            elif self.key_states[ord('1')]:  # SW
                self.dx = -1
                self.dy = 1
            elif self.key_states[ord('3')]:  # SE
                self.dx = 1
                self.dy = 1
        
        # Handle quit
        if key == ord('q') or key == ord('Q'):
            self.running = False
            
        # If any movement is happening, force a redraw
        if self.dx != 0 or self.dy != 0:
            self.needs_redraw = True
            # Move the world immediately by 1 cell in the pressed direction
            self.world_x += self.dx
            self.world_y += self.dy
            
            # Display direction in panel
            direction = ""
            if self.dy < 0:
                direction += "N"
            elif self.dy > 0:
                direction += "S"
            if self.dx > 0:
                direction += "E"
            elif self.dx < 0:
                direction += "W"
            self.direction = direction

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
        if self.current_menu == "main":
            if self.menu_selection == 0:  # Resume Game
                self.in_menu = False
            elif self.menu_selection == 1:  # Plugin Management
                self.current_menu = "plugins"
                self.menu_selection = 0
            elif self.menu_selection == 2:  # Exit
                self.running = False
        elif self.current_menu == "plugins":
            if self.menu_selection < len(self.plugins):
                # Toggle plugin active state
                plugin = self.plugins[self.menu_selection]
                if plugin.active:
                    plugin.deactivate()
                else:
                    plugin.activate()
                self.save_plugin_config()
                # Update menu text
                self.menus["plugins"][self.menu_selection] = plugin.name + (" [Active]" if plugin.active else " [Inactive]")
            else:  # Back option
                self.current_menu = "main"
                self.menu_selection = 0
        
        self.needs_redraw = True

    def update(self):
        # Calculate time since last update
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Skip game world updates if in menu, but still update plugins
        # This allows snakes to continue moving while in menu
        if not self.in_menu:
            # Check if message timeout has expired
            if self.message_timeout > 0 and current_time > self.message_timeout:
                self.message = ""
                self.message_timeout = 0
                self.needs_redraw = True
            
            # Simulate key release after a short time
            # This allows for diagonal movement by pressing keys in sequence
            for key in self.key_states:
                if self.key_states[key]:
                    self.key_states[key] = False  # Auto-release keys
            
            # Accumulate movement (for smooth continuous movement if needed)
            self.acc_x += self.dx * self.move_speed * dt
            self.acc_y += self.dy * self.move_speed * dt
            
            # Apply accumulated movement when it reaches at least 1 cell
            if abs(self.acc_x) >= 1:
                move_x = int(self.acc_x)
                self.world_x += move_x
                self.acc_x -= move_x  # Keep remainder for next update
                self.needs_redraw = True
                
            if abs(self.acc_y) >= 1:
                move_y = int(self.acc_y)
                self.world_y += move_y
                self.acc_y -= move_y  # Keep remainder for next update
                self.needs_redraw = True
        
        # Update plugins even when in menu
        for plugin in self.plugins:
            plugin.update(dt)

    def render(self):
        # Only redraw if needed
        if not self.needs_redraw:
            return
            
        self.screen.clear()
        
        # Draw the game world first (even when menu is active)
        self.render_game_world()
        
        # Draw menu on top if active
        if self.in_menu:
            self.render_menu()
            
        # Update screen
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
            panel_text = f"Top-Left: ({self.world_x - self.max_x // 2}, {self.world_y - self.max_y // 2}) | X: ({self.world_x}, {self.world_y}) | Dir: {direction} | Space: Create space | ESC: Menu"
        
        # Fill panel background
        for x in range(self.max_x - 1):
            self.screen.addch(panel_y, x, ' ', self.panel_color)
        
        # Draw panel text
        self.screen.addstr(panel_y, 1, panel_text[:self.max_x - 3], self.panel_color)
        
        # Draw menu bar at top
        self.screen.addstr(0, 0, " " * (self.max_x - 1), self.menu_color)
        menu_text = "TextWarp Adventure | Press ESC for Menu"
        self.screen.addstr(0, (self.max_x - len(menu_text)) // 2, menu_text, self.menu_color)

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

    def run(self):
        try:
            self.setup()
            
            while self.running:
                self.handle_input()
                self.update()
                self.render()
                
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
                
        except Exception as e:
            self.cleanup()
            print(f"An error occurred: {e}")
        finally:
            self.cleanup()

def main():
    game = TextAdventure()
    game.run()

if __name__ == "__main__":
    main()