import threading
import time
import math
import json
import os
import traceback
import pygame
from pygame.locals import *
import numpy as np
import curses
from plugins.base import Plugin

class GUI2DPlugin(Plugin):
    """Plugin that provides a 2D visualization of the game world."""
    
    def __init__(self, game):
        """Initialize the plugin."""
        super().__init__(game)
        self.active = True
        self.description = "2D visualization of the game world"
        self.version = "1.0"
        self.author = "TextWarp Team"
        
        # Visualization settings
        self.width = 800
        self.height = 600
        self.window_width = 800
        self.window_height = 600
        
        # Border information for limited rendering
        self.border_left = 0
        self.border_right = 0
        self.border_top = 0
        self.border_bottom = 0
        self.has_border_info = False
        
        # Camera settings
        self.camera_x = 0
        self.camera_y = 10
        self.camera_z = 0
        self.rotation_x = 30  # Look down 30 degrees
        self.rotation_y = 0
        self.zoom = 10
        self.camera_move_speed = 0.5
        
        # Mouse interaction
        self.dragging = False
        self.last_mouse_pos = None
        
        # Fullscreen state
        self.is_fullscreen = False
        self.pre_fullscreen_size = (800, 600)
        
        # Character map
        self.character_map = []
        self.characters = {}
        self.snakes = []
        
        # Debug messages
        self.debug_messages = []
        self.max_debug_messages = 20  # Maximum number of debug messages to store
        
        # Thread safety
        self.lock = threading.Lock()  # Lock for thread safety
        
        # Control settings
        self.handle_input = True
        
        # Terrain visualization settings
        self.show_snakes = True
        
        # Load settings if they exist
        self.load_settings()
        
        # Start the GUI thread
        self.running = True
        self.gui_thread = threading.Thread(target=self.run_gui)
        self.gui_thread.daemon = True
        self.gui_thread.start()
        
    @property
    def name(self):
        """Return the name of the plugin."""
        return "2D Visualization"
        
    def activate(self):
        """Activate the plugin."""
        self.active = True
        
        # Add a message to the game
        self.game.message = "2D visualization activated. Press ESC to return to the game."
        self.game.message_timeout = 3.0
        
    def deactivate(self):
        """Deactivate the plugin."""
        self.active = False
        
    def update(self, dt):
        """Update the plugin state."""
        if not self.active:
            return
            
        # Update the character map
        self.update_character_map()
        
        # Force a refresh to ensure all drawing is complete before updating the GUI
        try:
            self.game.screen.refresh()
            # Small sleep to ensure the terminal has fully rendered everything
            time.sleep(0.05)
        except:
            pass
            
    def update_character_map(self):
        """Update the character map from the game world."""
        if not self.active or not self.running:
            return
            
        try:
            # Get the screen dimensions
            max_y, max_x = self.game.screen.getmaxyx()
            
            # Clear the character map
            with self.lock:
                self.character_map = []
                self.characters = {}
                
            # Get the player's position
            player_x = self.game.world_x
            player_y = self.game.world_y
            
            # Get the border information if we haven't already
            if not self.has_border_info:
                # Find the border by looking for box drawing characters
                for y in range(max_y):
                    for x in range(max_x):
                        try:
                            char = chr(self.game.screen.inch(y, x) & 0xFF)
                            if char in "╔═╗║╚╝":
                                if self.border_top == 0 and char in "╔═╗":
                                    self.border_top = y
                                if self.border_left == 0 and char in "╔║╚":
                                    self.border_left = x
                                if y > self.border_bottom and char in "╚═╝":
                                    self.border_bottom = y
                                if x > self.border_right and char in "╗║╝":
                                    self.border_right = x
                        except:
                            pass
                
                # If we found a border, mark that we have the info
                if self.border_top > 0 and self.border_left > 0 and self.border_bottom > 0 and self.border_right > 0:
                    self.has_border_info = True
                    self.add_debug_message(f"Border detected: T:{self.border_top} L:{self.border_left} B:{self.border_bottom} R:{self.border_right}")
            
            # Process snakes separately
            with self.lock:
                self.snakes = []
            
            # Iterate through the screen within the defined rendering boundaries
            render_top = self.border_top + 1 if self.has_border_info else 0
            render_bottom = self.border_bottom - 1 if self.has_border_info else max_y - 1
            render_left = self.border_left + 1 if self.has_border_info else 0
            render_right = self.border_right - 1 if self.has_border_info else max_x - 1
            
            for y in range(render_top, render_bottom + 1):
                row = []
                for x in range(render_left, render_right + 1):
                    try:
                        # Get the character at this position
                        char_int = self.game.screen.inch(y, x)
                        char = chr(char_int & 0xFF)
                        
                        # Skip empty spaces
                        if char == " ":
                            row.append(None)
                            continue
                            
                        # Get color information
                        color_pair = (char_int & curses.A_COLOR) >> 8
                        
                        # Calculate world coordinates
                        world_x = x - player_x
                        world_z = y - player_y
                        
                        # Determine height based on ASCII value
                        world_y = ord(char) / 50.0  # Scale the height
                        
                        # Check if this is a snake character
                        is_snake = False
                        if char in "~^*":
                            is_snake = True
                            # Add to snakes list for special rendering
                            snake_segment = {
                                "x": world_x,
                                "y": world_y,
                                "z": world_z,
                                "char": char,
                                "color": color_pair
                            }
                            
                            # Find or create a snake for this segment
                            found_snake = False
                            for snake in self.snakes:
                                # Check if this segment is adjacent to any segment in the snake
                                for segment in snake:
                                    if (abs(segment["x"] - world_x) <= 1 and abs(segment["z"] - world_z) <= 1):
                                        snake.append(snake_segment)
                                        found_snake = True
                                        break
                                if found_snake:
                                    break
                                    
                            if not found_snake:
                                # Create a new snake
                                self.snakes.append([snake_segment])
                        
                        # Add to character map
                        char_info = {
                            "char": char,
                            "x": world_x,
                            "y": world_y,
                            "z": world_z,
                            "color": color_pair,
                            "is_snake": is_snake
                        }
                        row.append(char_info)
                        
                        # Add to characters dictionary for quick lookup
                        key = f"{world_x},{world_z}"
                        self.characters[key] = char_info
                    except Exception as e:
                        row.append(None)
                        
                self.character_map.append(row)
                
        except Exception as e:
            self.add_debug_message(f"Error updating character map: {str(e)}")
            traceback.print_exc()
    
    def render(self, screen):
        """Render the plugin on the curses screen."""
        # This method is required by the Plugin base class, but we don't need to
        # render anything on the curses screen since we're using a separate window.
        pass
    
    def run_gui(self):
        """Run the GUI in a separate thread."""
        try:
            # Initialize pygame only if it hasn't been initialized already
            if not pygame.get_init():
                pygame.init()
            
            # Create the window
            self.screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.DOUBLEBUF
            )
            
            pygame.display.set_caption("TextWarp Snake Visualization (2D)")
            
            # Initialize font
            self.font = pygame.font.Font(None, 24)
            
            # Main loop
            self.running = True
            clock = pygame.time.Clock()
            
            while self.running:
                # Process events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.handle_key_down(event)
                    elif event.type == pygame.KEYUP:
                        self.handle_key_up(event)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self.handle_mouse_button_down(event)
                    elif event.type == pygame.MOUSEBUTTONUP:
                        self.handle_mouse_button_up(event)
                    elif event.type == pygame.MOUSEMOTION:
                        self.handle_mouse_motion(event)
                
                # Render the scene
                self.render_scene()
                
                # Cap the frame rate
                clock.tick(30)
            
            # Clean up - don't quit pygame as other plugins might be using it
            # pygame.quit()
        except Exception as e:
            self.add_debug_message(f"Error in GUI thread: {str(e)}")
            traceback.print_exc()
    
    def render_scene(self):
        """Render the scene using pygame."""
        try:
            # Fill the screen with black
            screen = pygame.display.get_surface()
            screen.fill((0, 0, 0))
            
            # Draw title
            title = self.font.render("TextWarp Snake Visualization", True, (255, 255, 255))
            screen.blit(title, (10, 10))
            
            # Draw snake count
            snake_count = len(self.snakes)
            snakes_text = self.font.render(f"Snakes Detected: {snake_count}", True, (255, 255, 0))
            screen.blit(snakes_text, (10, 40))
            
            # Draw controls info
            controls_text = self.font.render("Controls: WASD=Move, ESC=Exit, F11=Fullscreen", True, (200, 200, 200))
            screen.blit(controls_text, (10, 70))
            
            # Draw snake information
            if self.snakes:
                y_pos = 100
                screen.blit(self.font.render("Snake Information:", True, (255, 255, 255)), (self.width - 300, y_pos))
                y_pos += 30
                
                for i, snake in enumerate(self.snakes):
                    if i >= 5:  # Limit to 5 snakes to avoid cluttering
                        break
                        
                    # Get snake position (head)
                    if snake:
                        head = snake[0]
                        x, y, z = head["x"], head["y"], head["z"]
                        length = len(snake)
                        
                        # Determine snake type based on characters
                        snake_type = "Unknown"
                        for segment in snake:
                            char = segment["char"]
                            if char == "^":
                                snake_type = "Viper"
                                break
                            elif char == "~":
                                snake_type = "Python"
                                break
                            elif char == "*":
                                snake_type = "Rattlesnake"
                                break
                        
                        # Draw snake info
                        pos_text = self.font.render(f"Snake {i+1}: ({x}, {z})", True, (255, 255, 255))
                        len_text = self.font.render(f"Length: {length}", True, (255, 255, 255))
                        type_text = self.font.render(f"Type: {snake_type}", True, (255, 255, 255))
                        
                        screen.blit(pos_text, (self.width - 300, y_pos))
                        screen.blit(len_text, (self.width - 300, y_pos + 20))
                        screen.blit(type_text, (self.width - 300, y_pos + 40))
                        y_pos += 70
            
            # Draw a map
            map_width = 300
            map_height = 300
            map_x = self.width - map_width - 10
            map_y = self.height - map_height - 10
            
            # Draw map background
            pygame.draw.rect(screen, (20, 20, 20), (map_x, map_y, map_width, map_height))
            pygame.draw.rect(screen, (50, 50, 50), (map_x, map_y, map_width, map_height), 2)
            
            # Draw grid lines
            grid_step = 20
            for i in range(0, map_width, grid_step):
                # Vertical lines
                pygame.draw.line(screen, (40, 40, 40), (map_x + i, map_y), (map_x + i, map_y + map_height))
                # Horizontal lines
                pygame.draw.line(screen, (40, 40, 40), (map_x, map_y + i), (map_x + map_width, map_y + i))
            
            # Draw center point (player position)
            center_x = map_x + map_width // 2
            center_y = map_y + map_height // 2
            pygame.draw.circle(screen, (0, 255, 0), (center_x, center_y), 5)
            
            # Draw characters
            with self.lock:
                for row in self.character_map:
                    for char_info in row:
                        if char_info is not None and not char_info["is_snake"]:
                            # Calculate position on map
                            x = center_x + char_info["x"] * 5
                            y = center_y + char_info["z"] * 5
                            
                            # Skip if outside map
                            if x < map_x or x > map_x + map_width or y < map_y or y > map_y + map_height:
                                continue
                            
                            # Draw character
                            color = (200, 200, 200)  # Default color
                            pygame.draw.circle(screen, color, (int(x), int(y)), 2)
            
            # Draw snakes
            with self.lock:
                for snake in self.snakes:
                    for i, segment in enumerate(snake):
                        # Calculate position on map
                        x = center_x + segment["x"] * 5
                        y = center_y + segment["z"] * 5
                        
                        # Skip if outside map
                        if x < map_x or x > map_x + map_width or y < map_y or y > map_y + map_height:
                            continue
                        
                        # Draw snake segment with different colors for head, body, and tail
                        if i == 0:  # Head
                            color = (0, 255, 0)  # Green
                            size = 4
                        elif i == len(snake) - 1:  # Tail
                            color = (255, 0, 0)  # Red
                            size = 3
                        else:  # Body
                            color = (0, 0, 255)  # Blue
                            size = 3
                            
                        pygame.draw.circle(screen, color, (int(x), int(y)), size)
                        
                        # Draw line connecting segments
                        if i > 0:
                            prev_segment = snake[i-1]
                            prev_x = center_x + prev_segment["x"] * 5
                            prev_y = center_y + prev_segment["z"] * 5
                            
                            pygame.draw.line(screen, (100, 100, 100), (prev_x, prev_y), (x, y), 1)
            
            # Update the display
            pygame.display.flip()
            
        except Exception as e:
            self.add_debug_message(f"Error rendering scene: {str(e)}")
            traceback.print_exc()
    
    def handle_key_down(self, event):
        """Handle key down events."""
        try:
            # Check if we should handle this key
            if not self.handle_input:
                return
                
            # Handle key presses
            if event.key == pygame.K_ESCAPE:
                # Exit fullscreen mode if in fullscreen
                if self.is_fullscreen:
                    self.toggle_fullscreen()
                # Otherwise, quit the GUI
                else:
                    self.running = False
            elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                # Toggle fullscreen
                self.toggle_fullscreen()
            
            # Forward movement keys to the game
            elif event.key == pygame.K_UP or event.key == pygame.K_w:
                # Forward the key to the game for player movement
                self.forward_key_to_game(curses.KEY_UP)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                # Forward the key to the game for player movement
                self.forward_key_to_game(curses.KEY_DOWN)
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                # Forward the key to the game for player movement
                self.forward_key_to_game(curses.KEY_LEFT)
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                # Forward the key to the game for player movement
                self.forward_key_to_game(curses.KEY_RIGHT)
                
        except Exception as e:
            self.add_debug_message(f"Error handling key down: {str(e)}")
            
    def forward_key_to_game(self, key):
        """Forward a key press to the game."""
        try:
            # Call the game's handle_input method with this key
            if hasattr(self.game, 'handle_input'):
                self.game.handle_input(key)
                
                # Add a debug message
                direction = {
                    curses.KEY_UP: "up",
                    curses.KEY_LEFT: "left",
                    curses.KEY_DOWN: "down",
                    curses.KEY_RIGHT: "right"
                }.get(key, "unknown")
                
                self.add_debug_message(f"Sent {direction} command to game")
                
        except Exception as e:
            self.add_debug_message(f"Error forwarding key to game: {str(e)}")
    
    def handle_key_up(self, event):
        """Handle key up events."""
        try:
            # Check if we should handle this key
            if not self.handle_input:
                return
                
            # Handle key releases
            pass
            
        except Exception as e:
            self.add_debug_message(f"Error handling key up: {str(e)}")
            
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        try:
            # Toggle fullscreen flag
            self.is_fullscreen = not self.is_fullscreen
            
            # Remember current size if going to fullscreen
            if self.is_fullscreen:
                self.pre_fullscreen_size = pygame.display.get_surface().get_size()
                
            # Set new display mode
            flags = pygame.FULLSCREEN if self.is_fullscreen else 0
            flags |= pygame.DOUBLEBUF
                
            # Create new screen
            self.screen = pygame.display.set_mode(
                (0, 0) if self.is_fullscreen else self.pre_fullscreen_size,
                flags
            )
                
            # Update width and height
            self.width, self.height = pygame.display.get_surface().get_size()
            
        except Exception as e:
            self.add_debug_message(f"Error toggling fullscreen: {e}")
    
    def handle_mouse_button_down(self, event):
        """Handle mouse button down events."""
        try:
            if event.button == 1:  # Left mouse button
                self.dragging = True
                self.last_mouse_pos = pygame.mouse.get_pos()
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button down: {e}")
    
    def handle_mouse_button_up(self, event):
        """Handle mouse button up events."""
        try:
            if self.dragging:
                self.dragging = False
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button up: {e}")
    
    def handle_mouse_motion(self, event):
        """Handle mouse motion events."""
        try:
            if self.dragging:
                x, y = pygame.mouse.get_pos()
                if self.last_mouse_pos:
                    dx = x - self.last_mouse_pos[0]
                    dy = y - self.last_mouse_pos[1]
                    # Use dx and dy for panning the map view
                self.last_mouse_pos = (x, y)
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse motion: {e}")
    
    def add_debug_message(self, message):
        """Add a debug message to the list of messages to display."""
        with self.lock:
            self.debug_messages.append(message)
            # Limit the number of messages
            if len(self.debug_messages) > self.max_debug_messages:
                self.debug_messages.pop(0)
    
    def load_settings(self):
        """Load display settings from a file."""
        try:
            with open("gui_2d_settings.json", "r") as f:
                settings = json.load(f)
                self.show_snakes = settings.get("show_snakes", True)
        except:
            # Use default settings if file doesn't exist or is invalid
            pass
            
    def save_settings(self):
        """Save display settings to a file."""
        try:
            with open("gui_2d_settings.json", "w") as f:
                settings = {
                    "show_snakes": self.show_snakes,
                }
                json.dump(settings, f)
        except:
            # Ignore errors when saving settings
            pass
