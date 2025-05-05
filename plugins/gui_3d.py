import os
import sys
import time
import math
import random
import threading
import traceback
import curses  # Added for snake rendering on text map
import json
import hashlib
from datetime import datetime

try:
    import pygame
    from pygame.locals import *
    from OpenGL.GL import *
    from OpenGL.GLU import *
    from OpenGL.GLUT import *
except ImportError as e:
    print(f"Error importing 3D libraries: {e}")
    print("Please install the required packages: pip install pygame PyOpenGL PyOpenGL_accelerate")

import threading
import time
import math
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import numpy as np
import curses
from plugins.base import Plugin
from keybindings import KeyBindings

class Character3D:
    """Represents a character in 3D space."""
    
    def __init__(self, char, x, y, color=(1.0, 1.0, 1.0, 1.0), height=None):
        self.char = char
        self.x = x
        self.y = y
        self.z = 0
        self.color = color
        # Allow external height to be provided, otherwise calculate it
        self.height = height if height is not None else self.calculate_height()
        
    def calculate_height(self):
        """Calculate height based on character."""
        # Special characters have different heights
        if self.char == 'X':
            return 0.5  # Player is taller
        elif self.char == '@':
            return 0.3  # Plants are medium height
        elif self.char == '0':
            return 0.2  # Eggs are small
        elif self.char == '&':
            return 0.4  # Fuel is medium-tall
        elif self.char == 'O':  # Remote players
            return 0.5
        else:
            # Calculate height based on ASCII value (normalized)
            return 0.1 + (ord(self.char) % 20) / 100.0
            
    def get_color(self):
        """Get the color for this character."""
        return self.color


class GUI3DPlugin(Plugin):
    """Plugin that provides a 3D visualization of the game world."""
    
    def __init__(self, game):
        """Initialize the plugin."""
        super().__init__(game)
        self.active = True
        # Don't set self.name here since it's a property
        self.description = "3D visualization of the game world"
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
        self.original_fullscreen = False
        
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
        self.handle_3d_input = True
        
        # Terrain visualization settings
        self.show_dots_without_sticks = True
        self.stick_dot_size = 5.0
        self.terrain_mesh_style = "solid"  # "wireframe" or "solid"
        self.terrain_mesh_opacity = 0.7
        self.terrain_color_scheme = "height"  # "height", "viridis", "plasma", etc.
        self.show_terrain_mesh = True
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
        return "3D Visualization"
        
    def activate(self):
        """Activate the plugin."""
        super().activate()
        
        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
        
        # Start the GUI thread
        self.running = True
        self.gui_thread = threading.Thread(target=self.run_gui, daemon=True)
        self.gui_thread.start()
        
        # Force snake connections to be enabled
        self.show_snake_connections = True
        
        # Create a test snake to ensure visibility
        self.create_test_snake()
        
        # Add a message to the game
        self.game.message = "3D visualization activated. Press ESC to return to the game."
        self.game.message_timeout = 3.0
        
    def deactivate(self):
        """Deactivate the plugin."""
        self.running = False
        if self.gui_thread:
            self.gui_thread.join(timeout=1.0)
        super().deactivate()
        
    def update(self, dt):
        """Update the plugin state."""
        if not self.active or not self.running:
            return
            
        # Update the character map
        self.update_character_map()
        
        # Force a refresh to ensure all drawing is complete before updating the 3D GUI
        try:
            self.game.screen.refresh()
            # Small sleep to ensure the terminal has fully rendered everything
            time.sleep(0.01)
        except:
            pass
            
        # Check for snakes directly
        self.check_for_snakes()
        
        # No need to update debug info here as it's handled elsewhere
        
    def check_for_snakes(self):
        """Directly check for snakes in the game and add them to the visualization."""
        # Skip if not active or running
        if not self.active or not self.running:
            return
            
        # Find the snake plugin
        snake_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active and plugin.__class__.__name__ == "SnakePlugin":
                snake_plugin = plugin
                break
                
        # Skip if no snake plugin found
        if not snake_plugin:
            # Clear the snakes list
            with self.lock:
                self.snakes = []
            return
            
        # Skip if the plugin has no snakes
        if not hasattr(snake_plugin, 'snakes') or not snake_plugin.snakes:
            # Clear the snakes list
            with self.lock:
                self.snakes = []
            return
            
        # Process each snake
        for snake_idx, snake in enumerate(snake_plugin.snakes):
            # Skip if the snake has no body
            if not hasattr(snake, 'body') or not snake.body:
                continue
                
            # Get the snake's body segments
            snake_segments = []
            
            # Add each segment to the list
            # Note: We're just storing the positions, not rendering anything here
            for segment_idx, (x, y) in enumerate(snake.body):
                snake_segments.append((x, y))
            
            # Add this snake's segments to the snakes list
            if snake_segments:
                with self.lock:
                    # Replace any existing snake with the same index
                    while len(self.snakes) <= snake_idx:
                        self.snakes.append([])
                    self.snakes[snake_idx] = snake_segments
        
    def update_character_map(self):
        """Update the 3D character map from the game world."""
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
            player_x = self.game.player_x
            player_y = self.game.player_y
            
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
            
            # Process snakes separately to avoid OpenGL errors
            with self.lock:
                self.snakes = []
            
            # Process snakes in the text map only, not in 3D visualization
            # This ensures snakes are visible in the text map but won't cause pygame errors
            
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
    
    def get_color_for_char(self, char, x, y):
        """Get the color for a character."""
        if char == 'X':  # Player
            return (1.0, 0.0, 0.0, 1.0)  # Red
        elif char == '@':  # Plants
            return (0.0, 0.8, 0.0, 1.0)  # Green
        elif char == '0':  # Eggs
            return (1.0, 0.5, 0.0, 1.0)  # Orange
        elif char == '&':  # Fuel
            return (0.0, 1.0, 1.0, 1.0)  # Cyan
        elif char == '.':  # Dots
            return (0.5, 0.25, 0.0, 1.0)  # Brown
        else:
            # Generate color based on character code
            h = (ord(char) % 360) / 360.0
            s = 0.7
            v = 0.7
            
            # Convert HSV to RGB
            if s == 0.0:
                return (v, v, v, 1.0)
                
            i = int(h * 6.0)
            f = (h * 6.0) - i
            p = v * (1.0 - s)
            q = v * (1.0 - s * f)
            t = v * (1.0 - s * (1.0 - f))
            
            if i % 6 == 0:
                return (v, t, p, 1.0)
            elif i % 6 == 1:
                return (q, v, p, 1.0)
            elif i % 6 == 2:
                return (p, v, t, 1.0)
            elif i % 6 == 3:
                return (p, q, v, 1.0)
            elif i % 6 == 4:
                return (t, p, v, 1.0)
            else:
                return (v, p, q, 1.0)
    
    def get_color_from_scheme(self, height, scheme):
        """Get color based on height and selected color scheme."""
        # Normalize height to 0-1 range
        norm_height = (height + 10) / 20.0  # Convert from [-10, 10] to [0, 1]
        norm_height = max(0.0, min(1.0, norm_height))  # Clamp to [0, 1]
        
        if scheme == "height":
            # Original height-based coloring
            if height < 0:
                # Blue to cyan for negative heights (below ground)
                r = 0
                g = 0.5 + (height / -10) * 0.5  # 0.5 to 1.0 as height goes from 0 to -10
                b = 1.0
            else:
                # Green to yellow to red for positive heights (above ground)
                if height < 5:
                    # Green to yellow (0 to 5)
                    r = height / 5
                    g = 0.8
                    b = 0
                else:
                    # Yellow to red (5 to 10)
                    r = 1.0
                    g = 0.8 - ((height - 5) / 5) * 0.8
                    b = 0
        elif scheme == "viridis":
            # Viridis colormap approximation (perceptually uniform, colorblind-friendly)
            if norm_height < 0.25:
                # Dark purple to blue
                r = 0.267 + norm_height * 4 * (0.128 - 0.267)
                g = 0.004 + norm_height * 4 * (0.267 - 0.004)
                b = 0.329 + norm_height * 4 * (0.533 - 0.329)
            elif norm_height < 0.5:
                # Blue to green
                t = (norm_height - 0.25) * 4
                r = 0.128 + t * (0.094 - 0.128)
                g = 0.267 + t * (0.464 - 0.267)
                b = 0.533 + t * (0.558 - 0.533)
            elif norm_height < 0.75:
                # Green to yellow
                t = (norm_height - 0.5) * 4
                r = 0.094 + t * (0.497 - 0.094)
                g = 0.464 + t * (0.731 - 0.464)
                b = 0.558 + t * (0.142 - 0.558)
            else:
                # Yellow to light yellow
                t = (norm_height - 0.75) * 4
                r = 0.497 + t * (0.993 - 0.497)
                g = 0.731 + t * (0.906 - 0.731)
                b = 0.142 + t * (0.143 - 0.142)
        elif scheme == "viridis_inverted":
            # Inverted Viridis colormap
            if norm_height < 0.25:
                # Light yellow to yellow
                r = 0.993 + norm_height * 4 * (0.497 - 0.993)
                g = 0.906 + norm_height * 4 * (0.731 - 0.906)
                b = 0.143 + norm_height * 4 * (0.142 - 0.143)
            elif norm_height < 0.5:
                # Yellow to green
                t = (norm_height - 0.25) * 4
                r = 0.497 + t * (0.094 - 0.497)
                g = 0.731 + t * (0.464 - 0.731)
                b = 0.142 + t * (0.558 - 0.142)
            elif norm_height < 0.75:
                # Green to blue
                t = (norm_height - 0.5) * 4
                r = 0.094 + t * (0.128 - 0.094)
                g = 0.464 + t * (0.267 - 0.464)
                b = 0.558 + t * (0.533 - 0.558)
            else:
                # Blue to dark purple
                t = (norm_height - 0.75) * 4
                r = 0.128 + t * (0.267 - 0.128)
                g = 0.267 + t * (0.004 - 0.267)
                b = 0.533 + t * (0.329 - 0.533)
        elif scheme == "plasma":
            # Plasma colormap approximation
            if norm_height < 0.25:
                # Dark purple to purple
                r = 0.050 + norm_height * 4 * (0.403 - 0.050)
                g = 0.029 + norm_height * 4 * (0.029 - 0.029)
                b = 0.527 + norm_height * 4 * (0.692 - 0.527)
            elif norm_height < 0.5:
                # Purple to pink
                t = (norm_height - 0.25) * 4
                r = 0.403 + t * (0.761 - 0.403)
                g = 0.029 + t * (0.214 - 0.029)
                b = 0.692 + t * (0.558 - 0.692)
            elif norm_height < 0.75:
                # Pink to orange
                t = (norm_height - 0.5) * 4
                r = 0.761 + t * (0.935 - 0.761)
                g = 0.214 + t * (0.528 - 0.214)
                b = 0.558 + t * (0.126 - 0.558)
            else:
                # Orange to yellow
                t = (norm_height - 0.75) * 4
                r = 0.935 + t * (0.993 - 0.935)
                g = 0.528 + t * (0.906 - 0.528)
                b = 0.126 + t * (0.143 - 0.126)
        elif scheme == "inferno":
            # Inferno colormap approximation
            if norm_height < 0.25:
                # Black to purple
                r = 0.001 + norm_height * 4 * (0.253 - 0.001)
                g = 0.000 + norm_height * 4 * (0.066 - 0.000)
                b = 0.014 + norm_height * 4 * (0.431 - 0.014)
            elif norm_height < 0.5:
                # Purple to red
                t = (norm_height - 0.25) * 4
                r = 0.253 + t * (0.632 - 0.253)
                g = 0.066 + t * (0.194 - 0.066)
                b = 0.431 + t * (0.364 - 0.431)
            elif norm_height < 0.75:
                # Red to orange
                t = (norm_height - 0.5) * 4
                r = 0.632 + t * (0.904 - 0.632)
                g = 0.194 + t * (0.516 - 0.194)
                b = 0.364 + t * (0.158 - 0.364)
            else:
                # Orange to yellow
                t = (norm_height - 0.75) * 4
                r = 0.904 + t * (0.988 - 0.904)
                g = 0.516 + t * (0.998 - 0.516)
                b = 0.158 + t * (0.645 - 0.158)
        elif scheme == "magma":
            # Magma colormap approximation
            if norm_height < 0.25:
                # Black to purple
                r = 0.001 + norm_height * 4 * (0.295 - 0.001)
                g = 0.000 + norm_height * 4 * (0.057 - 0.000)
                b = 0.014 + norm_height * 4 * (0.329 - 0.014)
            elif norm_height < 0.5:
                # Purple to pink
                t = (norm_height - 0.25) * 4
                r = 0.295 + t * (0.651 - 0.295)
                g = 0.057 + t * (0.125 - 0.057)
                b = 0.329 + t * (0.394 - 0.329)
            elif norm_height < 0.75:
                # Pink to orange
                t = (norm_height - 0.5) * 4
                r = 0.651 + t * (0.918 - 0.651)
                g = 0.125 + t * (0.486 - 0.125)
                b = 0.394 + t * (0.282 - 0.394)
            else:
                # Orange to light yellow
                t = (norm_height - 0.75) * 4
                r = 0.918 + t * (0.988 - 0.918)
                g = 0.486 + t * (0.998 - 0.486)
                b = 0.282 + t * (0.645 - 0.282)
        elif scheme == "cividis":
            # Cividis colormap approximation (colorblind-friendly)
            if norm_height < 0.25:
                # Dark blue to blue
                r = 0.000 + norm_height * 4 * (0.127 - 0.000)
                g = 0.135 + norm_height * 4 * (0.302 - 0.135)
                b = 0.304 + norm_height * 4 * (0.385 - 0.304)
            elif norm_height < 0.5:
                # Blue to teal
                t = (norm_height - 0.25) * 4
                r = 0.127 + t * (0.255 - 0.127)
                g = 0.302 + t * (0.455 - 0.302)
                b = 0.385 + t * (0.365 - 0.385)
            elif norm_height < 0.75:
                # Teal to yellow-green
                t = (norm_height - 0.5) * 4
                r = 0.255 + t * (0.540 - 0.255)
                g = 0.455 + t * (0.600 - 0.455)
                b = 0.365 + t * (0.260 - 0.365)
            else:
                # Yellow-green to yellow
                t = (norm_height - 0.75) * 4
                r = 0.540 + t * (0.993 - 0.540)
                g = 0.600 + t * (0.906 - 0.600)
                b = 0.260 + t * (0.144 - 0.260)
        else:
            # Default to grayscale
            r = g = b = norm_height
            
        return (r, g, b)
    
    def render(self, screen):
        """Render the plugin on the curses screen.
        
        This method is required by the Plugin base class, but we don't need to
        render anything on the curses screen since we're using a separate window.
        """
        # We don't need to render anything on the curses screen
        # Our rendering happens in the separate PyGame window
        
        # Render debug messages
        self.render_debug_messages(screen)
    
    def run_gui(self):
        """Run the 3D GUI in a separate thread."""
        try:
            # Initialize pygame only if it hasn't been initialized already
            if not pygame.get_init():
                pygame.init()
            
            # Initialize GLUT
            glutInit()
            
            # Create the window with OpenGL support
            self.screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.OPENGL | pygame.DOUBLEBUF
            )
            
            pygame.display.set_caption("TextWarp Snake Visualization (3D)")
            
            # Initialize font
            self.font = pygame.font.Font(None, 24)
            
            # Set up OpenGL
            glViewport(0, 0, self.width, self.height)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45, (self.width / self.height), 0.1, 50.0)
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            glEnable(GL_DEPTH_TEST)
            
            # Set up lighting
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            
            # Set light position
            light_position = [5.0, 5.0, 5.0, 1.0]
            glLightfv(GL_LIGHT0, GL_POSITION, light_position)
            
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
        """Render the 3D scene."""
        try:
            # Clear the screen
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
            
            # Set up the camera
            gluLookAt(
                self.camera_x, self.camera_y, self.camera_z,  # Camera position
                self.camera_x, 0, self.camera_z - 10,  # Look at point
                0, 1, 0  # Up vector
            )
            
            # Apply camera rotation
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)
            
            # Draw a grid for reference
            self.draw_grid()
            
            # Draw the characters
            with self.lock:
                for row in self.character_map:
                    for char_info in row:
                        if char_info is not None:
                            self.draw_character(char_info)
                
                # Draw snakes
                if self.show_snakes:
                    for snake in self.snakes:
                        self.draw_snake(snake)
            
            # Swap the buffers to display what we just drew
            pygame.display.flip()
            
        except Exception as e:
            self.add_debug_message(f"Error rendering scene: {str(e)}")
            traceback.print_exc()
            
    def draw_grid(self):
        """Draw a reference grid."""
        glBegin(GL_LINES)
        
        # Draw grid lines
        grid_size = 20
        grid_step = 1
        
        glColor3f(0.2, 0.2, 0.2)  # Dark gray
        
        for i in range(-grid_size, grid_size + 1, grid_step):
            # X axis lines
            glVertex3f(i, 0, -grid_size)
            glVertex3f(i, 0, grid_size)
            
            # Z axis lines
            glVertex3f(-grid_size, 0, i)
            glVertex3f(grid_size, 0, i)
            
        glEnd()
        
        # Draw coordinate axes
        glBegin(GL_LINES)
        
        # X axis (red)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(5, 0, 0)
        
        # Y axis (green)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 5, 0)
        
        # Z axis (blue)
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 5)
        
        glEnd()
        
        # Draw a plane for the ground
        glBegin(GL_QUADS)
        glColor3f(0.1, 0.3, 0.2)  # Dark green-blue for the ground
        glVertex3f(-grid_size, 0, -grid_size)
        glVertex3f(-grid_size, 0, grid_size)
        glVertex3f(grid_size, 0, grid_size)
        glVertex3f(grid_size, 0, -grid_size)
        glEnd()
        
    def draw_character(self, char_info):
        """Draw a character in 3D space."""
        if not char_info:
            return
            
        x = char_info["x"]
        y = char_info["y"]
        z = char_info["z"]
        char = char_info["char"]
        color_pair = char_info["color"]
        is_snake = char_info["is_snake"]
        
        # Skip drawing snakes here, they're drawn separately
        if is_snake:
            return
            
        # Set color based on color pair
        if color_pair == 1:  # Default
            glColor3f(1.0, 1.0, 1.0)  # White
        elif color_pair == 2:  # Red
            glColor3f(1.0, 0.0, 0.0)  # Red
        elif color_pair == 3:  # Green
            glColor3f(0.0, 1.0, 0.0)  # Green
        elif color_pair == 4:  # Yellow
            glColor3f(1.0, 1.0, 0.0)  # Yellow
        elif color_pair == 5:  # Blue
            glColor3f(0.0, 0.0, 1.0)  # Blue
        elif color_pair == 6:  # Magenta
            glColor3f(1.0, 0.0, 1.0)  # Magenta
        elif color_pair == 7:  # Cyan
            glColor3f(0.0, 1.0, 1.0)  # Cyan
        else:
            glColor3f(0.7, 0.7, 0.7)  # Light gray
            
        # Draw a cube for the character
        glPushMatrix()
        glTranslatef(x, y, z)
        glutSolidCube(0.5)
        glPopMatrix()
        
    def draw_snake(self, snake):
        """Draw a snake in 3D space."""
        if not snake:
            return
            
        # Draw each segment
        segments = snake.segments if hasattr(snake, 'segments') else snake
        for i, segment in enumerate(segments):
            try:
                # Handle different segment formats
                if isinstance(segment, dict):
                    x, y = segment.get('x', 0), segment.get('y', 0)
                elif isinstance(segment, (list, tuple)) and len(segment) >= 2:
                    x, y = segment[0], segment[1]
                else:
                    continue  # Skip invalid segments
                
                z = 0.3  # Slightly above the ground
                
                glPushMatrix()
                glTranslatef(x, z, y)  # Note: y and z are swapped in OpenGL
                
                # Head is red
                if i == 0:
                    glColor3f(1.0, 0.0, 0.0)  # Red
                # Tail/rattle is yellow
                elif i == len(segments) - 1:
                    glColor3f(1.0, 1.0, 0.0)  # Yellow
                # Body is dark blue (as per user memory)
                else:
                    glColor3f(0.0, 0.0, 0.5)  # Dark blue
                    
                # Draw a sphere for each segment
                glutSolidSphere(0.3, 8, 8)
                
                glPopMatrix()
                
                # Draw connections between segments
                if i > 0:
                    # Get previous segment
                    prev_segment = segments[i-1]
                    if isinstance(prev_segment, dict):
                        prev_x, prev_y = prev_segment.get('x', 0), prev_segment.get('y', 0)
                    elif isinstance(prev_segment, (list, tuple)) and len(prev_segment) >= 2:
                        prev_x, prev_y = prev_segment[0], prev_segment[1]
                    else:
                        continue
                    
                    prev_z = 0.3  # Slightly above the ground
                    
                    glColor3f(0.0, 0.0, 0.4)  # Darker blue for connections
                    
                    glBegin(GL_LINES)
                    glVertex3f(prev_x, prev_z, prev_y)  # Note: y and z are swapped in OpenGL
                    glVertex3f(x, z, y)  # Note: y and z are swapped in OpenGL
                    glEnd()
            except Exception as e:
                self.add_debug_message(f"Error drawing snake segment: {str(e)}")
    
    def handle_key_event(self, event):
        """Handle keyboard events."""
        try:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_f:
                self.toggle_fullscreen()
            # Forward WASD keys to the game for player movement
            elif event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                self.forward_key_to_game(event.key)
            
        except Exception as e:
            self.add_debug_message(f"Error handling key event: {e}")
    
    def forward_key_to_game(self, key):
        """Forward key presses to the main game for player movement."""
        try:
            # Map pygame keys to curses keys
            key_map = {
                pygame.K_w: curses.KEY_UP,
                pygame.K_a: curses.KEY_LEFT,
                pygame.K_s: curses.KEY_DOWN,
                pygame.K_d: curses.KEY_RIGHT
            }
            
            if key in key_map:
                # Get the corresponding curses key
                curses_key = key_map[key]
                
                # Call the game's handle_input method with this key
                if hasattr(self.game, 'handle_input'):
                    # Use threading to avoid blocking the pygame event loop
                    threading.Thread(
                        target=self.game.handle_input,
                        args=(curses_key,),
                        daemon=True
                    ).start()
                    
                    # Add a debug message
                    direction = {
                        curses.KEY_UP: "up",
                        curses.KEY_LEFT: "left",
                        curses.KEY_DOWN: "down",
                        curses.KEY_RIGHT: "right"
                    }.get(curses_key, "unknown")
                    
                    self.add_debug_message(f"Sent {direction} command to game")
                
        except Exception as e:
            self.add_debug_message(f"Error forwarding key to game: {e}")
    
    def handle_mouse_button_down(self, event):
        """Handle mouse button down events."""
        try:
            if event.button == 1:  # Left mouse button
                self.dragging = True
                self.last_mouse_pos = pygame.mouse.get_pos()
            elif event.button == 3:  # Right mouse button
                # Toggle fullscreen on right-click
                self.toggle_fullscreen()
            elif event.button == 4:  # Scroll up
                # Zoom in functionality could be implemented here
                pass
            elif event.button == 5:  # Scroll down
                # Zoom out functionality could be implemented here
                pass
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button down: {e}")
    
    def handle_mouse_button_up(self, event):
        """Handle mouse button up events."""
        try:
            if hasattr(self, 'dragging') and self.dragging:
                self.dragging = False
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button up: {e}")
    
    def handle_mouse_motion(self, event):
        """Handle mouse motion events."""
        try:
            if hasattr(self, 'dragging') and self.dragging:
                x, y = pygame.mouse.get_pos()
                if hasattr(self, 'last_mouse_pos') and self.last_mouse_pos:
                    dx = x - self.last_mouse_pos[0]
                    dy = y - self.last_mouse_pos[1]
                    # Use dx and dy for dragging functionality
                    # For example, panning the 3D map view
                self.last_mouse_pos = (x, y)
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse motion: {e}")

    def handle_key_down(self, event):
        """Handle key down events."""
        try:
            # Check if we should handle this key
            if not self.handle_3d_input:
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
            
            # Camera controls
            elif event.key == pygame.K_UP or event.key == pygame.K_w:
                # Forward key - move forward in the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('w')
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                # Backward key - move backward from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('s')
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                # Left key - move left from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('a')
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                # Right key - move right from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('d')
            elif event.key == pygame.K_PAGEUP:
                # Move up
                self.camera_y += self.camera_move_speed
            elif event.key == pygame.K_PAGEDOWN:
                # Move down
                self.camera_y -= self.camera_move_speed
            elif event.key == pygame.K_HOME:
                # Reset camera position
                self.camera_x = 0
                self.camera_y = 10
                self.camera_z = 0
                self.rotation_x = 30
                self.rotation_y = 0
                
        except Exception as e:
            self.add_debug_message(f"Error handling key down: {str(e)}")
            
    def handle_key_up(self, event):
        """Handle key up events."""
        try:
            # Check if we should handle this key
            if not self.handle_3d_input:
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
                
            # Set new display mode - always use regular pygame (no OpenGL)
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

    def load_settings(self):
        """Load display settings from a file."""
        try:
            import json
            with open("gui_3d_settings.json", "r") as f:
                settings = json.load(f)
                self.show_letters = settings.get("show_letters", True)
                self.show_sticks = settings.get("show_sticks", True)
                self.show_dots_without_sticks = settings.get("show_dots_without_sticks", False)
                self.show_mesh = settings.get("show_mesh", True)
                self.show_terrain_mesh = settings.get("show_terrain_mesh", True)
                self.terrain_mesh_style = settings.get("terrain_mesh_style", "filled")
                self.terrain_mesh_opacity = settings.get("terrain_mesh_opacity", 0.7)
                self.terrain_color_scheme = settings.get("terrain_color_scheme", "height")
                self.stick_dot_size = settings.get("stick_dot_size", 8.0)
                self.show_snake_connections = settings.get("show_snake_connections", True)
                self.render_distance = settings.get("render_distance", 100)
                self.show_axes = settings.get("show_axes", True)
                self.show_zero_level_grid = settings.get("show_zero_level_grid", True)
                self.ascii_intensity = settings.get("ascii_intensity", True)
                self.ascii_height = settings.get("ascii_height", False)
        except:
            # Use default settings if file doesn't exist or is invalid
            pass
    
    def save_settings(self):
        """Save display settings to a file."""
        try:
            import json
            with open("gui_3d_settings.json", "w") as f:
                settings = {
                    "show_letters": self.show_letters,
                    "show_sticks": self.show_sticks,
                    "show_dots_without_sticks": self.show_dots_without_sticks,
                    "show_mesh": self.show_mesh,
                    "show_terrain_mesh": self.show_terrain_mesh,
                    "terrain_mesh_style": self.terrain_mesh_style,
                    "terrain_mesh_opacity": self.terrain_mesh_opacity,
                    "terrain_color_scheme": self.terrain_color_scheme,
                    "stick_dot_size": self.stick_dot_size,
                    "show_snake_connections": self.show_snake_connections,
                    "render_distance": self.render_distance,
                    "show_axes": self.show_axes,
                    "show_zero_level_grid": self.show_zero_level_grid,
                    "ascii_intensity": self.ascii_intensity,
                    "ascii_height": self.ascii_height
                }
                json.dump(settings, f)
        except:
            # Ignore errors
            pass

    def show_settings_menu(self):
        """Show the settings menu for the 3D visualization plugin."""
        # Store original settings in case user cancels
        original_show_letters = self.show_letters
        original_show_sticks = self.show_sticks
        original_show_dots_without_sticks = self.show_dots_without_sticks
        original_show_mesh = self.show_mesh
        original_show_terrain_mesh = self.show_terrain_mesh
        original_terrain_mesh_style = self.terrain_mesh_style
        original_terrain_mesh_opacity = self.terrain_mesh_opacity
        original_terrain_color_scheme = self.terrain_color_scheme
        original_stick_dot_size = self.stick_dot_size
        original_show_snake_connections = self.show_snake_connections
        original_render_distance = self.render_distance
        original_show_axes = self.show_axes
        original_show_zero_level_grid = self.show_zero_level_grid
        original_ascii_intensity = self.ascii_intensity
        original_ascii_height = self.ascii_height
        
        # Variables for menu navigation
        current_selection = 0
        in_settings_menu = True
        
        # Create settings list
        settings = [
            {"name": "Show Letters", "value": self.show_letters, "type": "bool"},
            {"name": "Show Sticks", "value": self.show_sticks, "type": "bool"},
            {"name": "Show Dots Without Sticks", "value": self.show_dots_without_sticks, "type": "bool"},
            {"name": "Show Mesh", "value": self.show_mesh, "type": "bool"},
            {"name": "Show Terrain Mesh", "value": self.show_terrain_mesh, "type": "bool"},
            {"name": "Terrain Mesh Style", "value": self.terrain_mesh_style, "type": "str"},
            {"name": "Terrain Mesh Opacity", "value": self.terrain_mesh_opacity, "type": "float", "min": 0.1, "max": 1.0, "step": 0.1},
            {"name": "Terrain Color Scheme", "value": self.terrain_color_scheme, "type": "str"},
            {"name": "Stick Dot Size", "value": self.stick_dot_size, "type": "float", "min": 1.0, "max": 20.0, "step": 1.0},
            {"name": "Show Snake Connections", "value": self.show_snake_connections, "type": "bool"},
            {"name": "Render Distance", "value": self.render_distance, "type": "int", "min": 10, "max": 1000, "step": 10},
            {"name": "Show Axes", "value": self.show_axes, "type": "bool"},
            {"name": "Show Zero Level Grid", "value": self.show_zero_level_grid, "type": "bool"},
            {"name": "ASCII Intensity", "value": self.ascii_intensity, "type": "bool"},
            {"name": "ASCII Height", "value": self.ascii_height, "type": "bool"},
            {"name": "Save Settings", "value": None, "type": "button"},
            {"name": "Cancel", "value": None, "type": "button"}
        ]
        
        # Variables for menu navigation
        current_selection = 0
        in_menu = True
        
        # Main loop for settings menu
        while in_menu:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            self.game.screen.addstr(0, 0, "3D Visualization Settings", self.game.menu_color | curses.A_BOLD)
            self.game.screen.addstr(1, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw instructions
            self.game.screen.addstr(2, 0, "Use ↑/↓ to navigate, ENTER to toggle/edit, ←/→ to adjust values", self.game.menu_color)
            self.game.screen.addstr(3, 0, "Press ESC to exit without saving", self.game.menu_color)
            self.game.screen.addstr(4, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw settings
            for i, setting in enumerate(settings):
                # Highlight the selected item
                if i == current_selection:
                    attr = self.game.menu_color | curses.A_BOLD
                else:
                    attr = self.game.menu_color
                
                # Draw the item
                if setting["type"] == "bool":
                    value_str = "Yes" if setting["value"] else "No"
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {value_str}", attr)
                elif setting["type"] == "float" or setting["type"] == "int":
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {setting['value']}", attr)
                elif setting["type"] == "str":
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {setting['value']}", attr)
                else:
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}", attr)
            
            # Draw footer
            self.game.screen.addstr(self.game.max_y - 2, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Refresh screen
            self.game.screen.refresh()
            
            # Get input
            key = self.game.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(settings)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(settings)
            elif key == 10:  # Enter key
                # Handle selection
                setting = settings[current_selection]
                if setting["type"] == "bool":
                    # Toggle boolean value
                    setting["value"] = not setting["value"]
                elif setting["type"] == "button":
                    if setting["name"] == "Save Settings":
                        # Save settings
                        self.show_letters = settings[0]["value"]
                        self.show_sticks = settings[1]["value"]
                        self.show_dots_without_sticks = settings[2]["value"]
                        self.show_mesh = settings[3]["value"]
                        self.show_terrain_mesh = settings[4]["value"]
                        self.terrain_mesh_style = settings[5]["value"]
                        self.terrain_mesh_opacity = settings[6]["value"]
                        self.terrain_color_scheme = settings[7]["value"]
                        self.stick_dot_size = settings[8]["value"]
                        self.show_snake_connections = settings[9]["value"]
                        self.render_distance = settings[10]["value"]
                        self.show_axes = settings[11]["value"]
                        self.show_zero_level_grid = settings[12]["value"]
                        self.ascii_intensity = settings[13]["value"]
                        self.ascii_height = settings[14]["value"]
                        self.save_settings()
                        in_menu = False
                    elif setting["name"] == "Cancel":
                        # Restore original settings
                        self.show_letters = original_show_letters
                        self.show_sticks = original_show_sticks
                        self.show_dots_without_sticks = original_show_dots_without_sticks
                        self.show_mesh = original_show_mesh
                        self.show_terrain_mesh = original_show_terrain_mesh
                        self.terrain_mesh_style = original_terrain_mesh_style
                        self.terrain_mesh_opacity = original_terrain_mesh_opacity
                        self.terrain_color_scheme = original_terrain_color_scheme
                        self.stick_dot_size = original_stick_dot_size
                        self.show_snake_connections = original_show_snake_connections
                        self.render_distance = original_render_distance
                        self.show_axes = original_show_axes
                        self.show_zero_level_grid = original_show_zero_level_grid
                        self.ascii_intensity = original_ascii_intensity
                        self.ascii_height = original_ascii_height
                        in_menu = False
            elif key == curses.KEY_LEFT:
                # Decrease value
                setting = settings[current_selection]
                if setting["type"] == "float":
                    # Check if min and step exist, use defaults if not
                    min_val = setting.get("min", 0.0)
                    step = setting.get("step", 0.1)
                    setting["value"] = max(min_val, setting["value"] - step)
                elif setting["type"] == "int":
                    # Check if min and step exist, use defaults if not
                    min_val = setting.get("min", 0)
                    step = setting.get("step", 1)
                    setting["value"] = max(min_val, setting["value"] - step)
                elif setting["type"] == "str" and setting["name"] == "Terrain Mesh Style":
                    # Cycle through mesh style options
                    if setting["value"] == "filled":
                        setting["value"] = "wireframe"
                    else:
                        setting["value"] = "filled"
                elif setting["type"] == "str" and setting["name"] == "Terrain Color Scheme":
                    # Cycle through color scheme options
                    schemes = ["height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"]
                    idx = schemes.index(setting["value"])
                    setting["value"] = schemes[(idx - 1) % len(schemes)]
            elif key == curses.KEY_RIGHT:
                # Increase value
                setting = settings[current_selection]
                if setting["type"] == "float":
                    # Check if max and step exist, use defaults if not
                    max_val = setting.get("max", 10.0)
                    step = setting.get("step", 0.1)
                    setting["value"] = min(max_val, setting["value"] + step)
                elif setting["type"] == "int":
                    # Check if max and step exist, use defaults if not
                    max_val = setting.get("max", 100)
                    step = setting.get("step", 1)
                    setting["value"] = min(max_val, setting["value"] + step)
                elif setting["type"] == "str" and setting["name"] == "Terrain Mesh Style":
                    # Cycle through mesh style options
                    if setting["value"] == "wireframe":
                        setting["value"] = "filled"
                    else:
                        setting["value"] = "wireframe"
                elif setting["type"] == "str" and setting["name"] == "Terrain Color Scheme":
                    # Cycle through color scheme options
                    schemes = ["height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"]
                    idx = schemes.index(setting["value"])
                    setting["value"] = schemes[(idx + 1) % len(schemes)]
            elif key == 27:  # Escape key
                # Restore original settings
                self.show_letters = original_show_letters
                self.show_sticks = original_show_sticks
                self.show_dots_without_sticks = original_show_dots_without_sticks
                self.show_mesh = original_show_mesh
                self.show_terrain_mesh = original_show_terrain_mesh
                self.terrain_mesh_style = original_terrain_mesh_style
                self.terrain_mesh_opacity = original_terrain_mesh_opacity
                self.terrain_color_scheme = original_terrain_color_scheme
                self.stick_dot_size = original_stick_dot_size
                self.show_snake_connections = original_show_snake_connections
                self.render_distance = original_render_distance
                self.show_axes = original_show_axes
                self.show_zero_level_grid = original_show_zero_level_grid
                self.ascii_intensity = original_ascii_intensity
                self.ascii_height = original_ascii_height
                in_menu = False
        
        # Force redraw
        self.game.needs_redraw = True

    def show_3d_settings_menu(self):
        """Show the 3D settings menu."""
        # Store original settings in case user cancels
        original_show_letters = self.show_letters
        original_show_sticks = self.show_sticks
        original_show_dots_without_sticks = self.show_dots_without_sticks
        original_show_mesh = self.show_mesh
        original_show_terrain_mesh = self.show_terrain_mesh
        original_terrain_mesh_style = self.terrain_mesh_style
        original_terrain_mesh_opacity = self.terrain_mesh_opacity
        original_terrain_color_scheme = self.terrain_color_scheme
        original_stick_dot_size = self.stick_dot_size
        original_show_snake_connections = self.show_snake_connections
        original_render_distance = self.render_distance
        original_show_axes = self.show_axes
        original_show_zero_level_grid = self.show_zero_level_grid
        original_ascii_intensity = self.ascii_intensity
        original_ascii_height = self.ascii_height
        original_fullscreen = self.fullscreen
        
        # Variables for menu navigation
        current_selection = 0
        in_settings_menu = True
        
        # Create settings list
        settings = [
            {"name": "Show Letters", "value": self.show_letters, "type": "bool"},
            {"name": "Show Sticks", "value": self.show_sticks, "type": "bool"},
            {"name": "Show Dots Without Sticks", "value": self.show_dots_without_sticks, "type": "bool"},
            {"name": "Show Mesh", "value": self.show_mesh, "type": "bool"},
            {"name": "Show Terrain Mesh", "value": self.show_terrain_mesh, "type": "bool"},
            {"name": "Terrain Mesh Style", "value": self.terrain_mesh_style, "type": "str"},
            {"name": "Terrain Mesh Opacity", "value": self.terrain_mesh_opacity, "type": "float", "min": 0.1, "max": 1.0, "step": 0.1},
            {"name": "Terrain Color Scheme", "value": self.terrain_color_scheme, "type": "str"},
            {"name": "Stick Dot Size", "value": self.stick_dot_size, "type": "float", "min": 1.0, "max": 20.0, "step": 1.0},
            {"name": "Show Snake Connections", "value": self.show_snake_connections, "type": "bool"},
            {"name": "Render Distance", "value": self.render_distance, "type": "int", "min": 10, "max": 1000, "step": 10},
            {"name": "Show Axes", "value": self.show_axes, "type": "bool"},
            {"name": "Show Zero Level Grid", "value": self.show_zero_level_grid, "type": "bool"},
            {"name": "ASCII Intensity", "value": self.ascii_intensity, "type": "bool"},
            {"name": "ASCII Height", "value": self.ascii_height, "type": "bool"},
            {"name": "Fullscreen", "value": self.fullscreen, "type": "bool"},
            {"name": "Save Settings", "value": None, "type": "button"},
            {"name": "Cancel", "value": None, "type": "button"}
        ]
        
        # Variables for menu navigation
        current_selection = 0
        in_menu = True
        
        # Main loop for settings menu
        while in_menu:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            self.game.screen.addstr(0, 0, "3D Visualization Settings", self.game.menu_color | curses.A_BOLD)
            self.game.screen.addstr(1, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw instructions
            self.game.screen.addstr(2, 0, "Use ↑/↓ to navigate, ENTER to toggle/edit, ←/→ to adjust values", self.game.menu_color)
            self.game.screen.addstr(3, 0, "Press ESC to exit without saving", self.game.menu_color)
            self.game.screen.addstr(4, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw settings
            for i, setting in enumerate(settings):
                # Highlight the selected item
                if i == current_selection:
                    attr = self.game.menu_color | curses.A_BOLD
                else:
                    attr = self.game.menu_color
                
                # Draw the item
                if setting["type"] == "bool":
                    value_str = "Yes" if setting["value"] else "No"
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {value_str}", attr)
                elif setting["type"] == "float" or setting["type"] == "int":
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {setting['value']}", attr)
                elif setting["type"] == "str":
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {setting['value']}", attr)
                else:
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}", attr)
            
            # Draw footer
            self.game.screen.addstr(self.game.max_y - 2, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Refresh screen
            self.game.screen.refresh()
            
            # Get input
            key = self.game.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(settings)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(settings)
            elif key == 10:  # Enter key
                # Handle selection
                setting = settings[current_selection]
                if setting["type"] == "bool":
                    # Toggle boolean value
                    setting["value"] = not setting["value"]
                elif setting["type"] == "button":
                    if setting["name"] == "Save Settings":
                        # Save settings
                        self.show_letters = settings[0]["value"]
                        self.show_sticks = settings[1]["value"]
                        self.show_dots_without_sticks = settings[2]["value"]
                        self.show_mesh = settings[3]["value"]
                        self.show_terrain_mesh = settings[4]["value"]
                        self.terrain_mesh_style = settings[5]["value"]
                        self.terrain_mesh_opacity = settings[6]["value"]
                        self.terrain_color_scheme = settings[7]["value"]
                        self.stick_dot_size = settings[8]["value"]
                        self.show_snake_connections = settings[9]["value"]
                        self.render_distance = settings[10]["value"]
                        self.show_axes = settings[11]["value"]
                        self.show_zero_level_grid = settings[12]["value"]
                        self.ascii_intensity = settings[13]["value"]
                        self.ascii_height = settings[14]["value"]
                        self.fullscreen = settings[15]["value"]
                        self.save_settings()
                        in_menu = False
                    elif setting["name"] == "Cancel":
                        # Restore original settings
                        self.show_letters = original_show_letters
                        self.show_sticks = original_show_sticks
                        self.show_dots_without_sticks = original_show_dots_without_sticks
                        self.show_mesh = original_show_mesh
                        self.show_terrain_mesh = original_show_terrain_mesh
                        self.terrain_mesh_style = original_terrain_mesh_style
                        self.terrain_mesh_opacity = original_terrain_mesh_opacity
                        self.terrain_color_scheme = original_terrain_color_scheme
                        self.stick_dot_size = original_stick_dot_size
                        self.show_snake_connections = original_show_snake_connections
                        self.render_distance = original_render_distance
                        self.show_axes = original_show_axes
                        self.show_zero_level_grid = original_show_zero_level_grid
                        self.ascii_intensity = original_ascii_intensity
                        self.ascii_height = original_ascii_height
                        self.fullscreen = original_fullscreen
                        in_menu = False
            elif key == curses.KEY_LEFT:
                # Decrease value
                setting = settings[current_selection]
                if setting["type"] == "float":
                    # Check if min and step exist, use defaults if not
                    min_val = setting.get("min", 0.0)
                    step = setting.get("step", 0.1)
                    setting["value"] = max(min_val, setting["value"] - step)
                elif setting["type"] == "int":
                    # Check if min and step exist, use defaults if not
                    min_val = setting.get("min", 0)
                    step = setting.get("step", 1)
                    setting["value"] = max(min_val, setting["value"] - step)
                elif setting["type"] == "str" and setting["name"] == "Terrain Mesh Style":
                    # Cycle through mesh style options
                    if setting["value"] == "filled":
                        setting["value"] = "wireframe"
                    else:
                        setting["value"] = "filled"
                elif setting["type"] == "str" and setting["name"] == "Terrain Color Scheme":
                    # Cycle through color scheme options
                    schemes = ["height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"]
                    idx = schemes.index(setting["value"])
                    setting["value"] = schemes[(idx - 1) % len(schemes)]
            elif key == curses.KEY_RIGHT:
                # Increase value
                setting = settings[current_selection]
                if setting["type"] == "float":
                    # Check if max and step exist, use defaults if not
                    max_val = setting.get("max", 10.0)
                    step = setting.get("step", 0.1)
                    setting["value"] = min(max_val, setting["value"] + step)
                elif setting["type"] == "int":
                    # Check if max and step exist, use defaults if not
                    max_val = setting.get("max", 100)
                    step = setting.get("step", 1)
                    setting["value"] = min(max_val, setting["value"] + step)
                elif setting["type"] == "str" and setting["name"] == "Terrain Mesh Style":
                    # Cycle through mesh style options
                    if setting["value"] == "wireframe":
                        setting["value"] = "filled"
                    else:
                        setting["value"] = "wireframe"
                elif setting["type"] == "str" and setting["name"] == "Terrain Color Scheme":
                    # Cycle through color scheme options
                    schemes = ["height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"]
                    idx = schemes.index(setting["value"])
                    setting["value"] = schemes[(idx + 1) % len(schemes)]
            elif key == 27:  # Escape key
                # Restore original settings
                self.show_letters = original_show_letters
                self.show_sticks = original_show_sticks
                self.show_dots_without_sticks = original_show_dots_without_sticks
                self.show_mesh = original_show_mesh
                self.show_terrain_mesh = original_show_terrain_mesh
                self.terrain_mesh_style = original_terrain_mesh_style
                self.terrain_mesh_opacity = original_terrain_mesh_opacity
                self.terrain_color_scheme = original_terrain_color_scheme
                self.stick_dot_size = original_stick_dot_size
                self.show_snake_connections = original_show_snake_connections
                self.render_distance = original_render_distance
                self.show_axes = original_show_axes
                self.show_zero_level_grid = original_show_zero_level_grid
                self.ascii_intensity = original_ascii_intensity
                self.ascii_height = original_ascii_height
                self.fullscreen = original_fullscreen
                in_menu = False
        
        # Force redraw
        self.game.needs_redraw = True

    def show_connected_snakes(self, value):
        """Set whether to show snakes as connected balls."""
        self.show_snake_connections = value
        
        # Force a check for snakes to update the visualization
        self.check_for_snakes()
        
        return True
    
    def create_test_snake(self):
        """Create a test snake for debugging purposes."""
        try:
            # Find the snake plugin
            snake_plugin = None
            for plugin in self.game.plugins:
                if hasattr(plugin, 'snakes'):
                    snake_plugin = plugin
                    break
            
            if not snake_plugin:
                self.add_debug_message("No snake plugin found")
                return
            
            # Clear existing snakes for testing
            if hasattr(snake_plugin, 'snakes'):
                snake_plugin.snakes = []
            
            # Create a test snake with a specific pattern
            # Position it relative to the player for better visibility
            player_x = self.game.world_x
            player_y = self.game.world_y
            
            # Create snake body segments in a pattern
            # Start with a straight line away from the player
            snake_body = [
                (player_x, player_y),  # Head at player position
                (player_x + 1, player_y),
                (player_x + 2, player_y),
                (player_x + 3, player_y),
                (player_x + 4, player_y),
                # Then make a right turn
                (player_x + 5, player_y),
                (player_x + 5, player_y + 1),
                (player_x + 5, player_y + 2),
                # Then another right turn
                (player_x + 4, player_y + 2),
                (player_x + 3, player_y + 2)
            ]
            
            # Create a snake class instance with proper game reference
            game_ref = self.game  # Store reference to the game
            
            class TestSnake:
                def __init__(self, body, game):
                    self.body = body
                    self.rattles = 2  # Last two segments will be rattles
                    self.direction = (1, 0)  # Moving right initially
                    self.time_to_move = 0
                    self.move_interval = 0.5  # seconds between moves
                    self.game = game  # Reference to the game
                    
                def update(self, dt):
                    """Update the snake's position (stub method to prevent errors)."""
                    # This is a static test snake, so we don't actually move it
                    # But we need this method to prevent AttributeError
                    pass
                    
                def render(self, screen):
                    """Render the snake on the screen."""
                    for i, (x, y) in enumerate(self.body):
                        # Only render if the body segment is on screen
                        screen_x = x - self.game.world_x + self.game.max_x // 2
                        screen_y = y - self.game.world_y + self.game.max_y // 2
                        
                        if 0 <= screen_x < self.game.max_x and 0 <= screen_y < self.game.max_y:
                            # Determine character and color based on position
                            if i == 0:
                                # Head
                                char = 'S'
                                color = self.game.snake_color
                            elif hasattr(self, 'rattles') and i >= len(self.body) - self.rattles:
                                # Rattle (red dot)
                                char = '.'
                                color = curses.color_pair(1)  # Red color
                            else:
                                # Body
                                char = 's'
                                color = self.game.snake_color
                            
                            # Add a visual indicator when snake is at max length
                            attr = curses.A_BOLD
                            
                            try:
                                # Use the appropriate color
                                screen.addstr(screen_y, screen_x, char, color | attr)
                            except:
                                # Ignore errors from writing to the bottom-right corner
                                pass
                def bite(self, other_snake):
                    """Bite another snake (stub method)."""
                    return False
            
            # Add the test snake to the snake plugin
            test_snake = TestSnake(snake_body, game_ref)
            snake_plugin.snakes.append(test_snake)
            
            self.add_debug_message(f"Created test snake at ({player_x}, {player_y}) with {len(snake_body)} segments")
            
        except Exception as e:
            self.add_debug_message(f"Error creating test snake: {e}")
    
    def add_debug_message(self, message):
        """Add a debug message to the list of messages to display."""
        # Filter out any XYZ prefixes that might be in the message
        message = message.replace("XYZ", "")
        
        self.debug_messages.append(message)
        # Keep only the most recent messages
        if len(self.debug_messages) > self.max_debug_messages:
            self.debug_messages = self.debug_messages[-self.max_debug_messages:]
    
    def render_debug_messages(self, screen):
        """Render debug messages at the bottom of the terminal."""
        if not self.debug_messages:
            return
            
        try:
            # Get curses module from the game
            curses = self.game.curses
            
            # Get screen dimensions
            max_y, max_x = screen.getmaxyx()
            
            # Clear the bottom lines
            for i in range(self.max_debug_messages):
                screen.move(max_y - 2 - i, 0)
                screen.clrtoeol()
            
            # Display debug messages
            for i, message in enumerate(reversed(self.debug_messages)):
                if i >= self.max_debug_messages:
                    break
                # Clean the message to ensure no XYZ strings
                clean_message = message.replace("XYZ", "").strip()
                if clean_message:  # Only display non-empty messages
                    screen.addstr(max_y - 2 - i, 0, clean_message[:max_x-1])
        except:
            # Silently handle any errors to prevent crashes
            pass

    def render_debug_info(self):
        """Generate debug information string."""
        # Format the debug information string with specific content
        if not self.snakes:
            return "Drawing 0 snakes"
            
        # Format the debug message to match the requested format
        debug_info = f"Drawing {len(self.snakes)} snakes"
        
        # Add snake segment information if available
        if len(self.snakes) > 0:
            for i in range(min(3, len(self.snakes))):
                if hasattr(self.snakes[i], 'body'):
                    debug_info += f" Snake {i+1} has {len(self.snakes[i].body)} segments"
                
        return debug_info
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        try:
            # Toggle fullscreen flag
            self.is_fullscreen = not self.is_fullscreen
            
            # Remember current size if going to fullscreen
            if self.is_fullscreen:
                # Save current window size before going fullscreen
                self.pre_fullscreen_size = pygame.display.get_surface().get_size()
                
                # Set to fullscreen mode
                self.window = pygame.display.set_mode(
                    (0, 0),  # Use current desktop resolution
                    DOUBLEBUF | pygame.FULLSCREEN
                )
                self.add_debug_message("Switched to fullscreen mode")
            else:
                # Restore previous window size
                self.window = pygame.display.set_mode(
                    self.pre_fullscreen_size,
                    DOUBLEBUF
                )
                self.add_debug_message("Switched to windowed mode")
                
            # Reset the projection matrix for the new aspect ratio
            width, height = pygame.display.get_surface().get_size()
            aspect_ratio = width / height if height > 0 else 1.0
            
            # Return to modelview matrix
            # glMatrixMode(GL_MODELVIEW)
            
        except Exception as e:
            self.add_debug_message(f"Error toggling fullscreen: {e}")
    
    def handle_key_event(self, event):
        """Handle keyboard events."""
        try:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_f:
                self.toggle_fullscreen()
            # Forward WASD keys to the game for player movement
            elif event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                self.forward_key_to_game(event.key)
            
        except Exception as e:
            self.add_debug_message(f"Error handling key event: {e}")
    
    def forward_key_to_game(self, key):
        """Forward key presses to the main game for player movement."""
        try:
            # Map pygame keys to curses keys
            key_map = {
                pygame.K_w: curses.KEY_UP,
                pygame.K_a: curses.KEY_LEFT,
                pygame.K_s: curses.KEY_DOWN,
                pygame.K_d: curses.KEY_RIGHT
            }
            
            if key in key_map:
                # Get the corresponding curses key
                curses_key = key_map[key]
                
                # Call the game's handle_input method with this key
                if hasattr(self.game, 'handle_input'):
                    # Use threading to avoid blocking the pygame event loop
                    threading.Thread(
                        target=self.game.handle_input,
                        args=(curses_key,),
                        daemon=True
                    ).start()
                    
                    # Add a debug message
                    direction = {
                        curses.KEY_UP: "up",
                        curses.KEY_LEFT: "left",
                        curses.KEY_DOWN: "down",
                        curses.KEY_RIGHT: "right"
                    }.get(curses_key, "unknown")
                    
                    self.add_debug_message(f"Sent {direction} command to game")
                
        except Exception as e:
            self.add_debug_message(f"Error forwarding key to game: {e}")
    
    def handle_mouse_button_down(self, event):
        """Handle mouse button down events."""
        try:
            if event.button == 1:  # Left mouse button
                self.dragging = True
                self.last_mouse_pos = pygame.mouse.get_pos()
            elif event.button == 3:  # Right mouse button
                # Toggle fullscreen on right-click
                self.toggle_fullscreen()
            elif event.button == 4:  # Scroll up
                # Zoom in functionality could be implemented here
                pass
            elif event.button == 5:  # Scroll down
                # Zoom out functionality could be implemented here
                pass
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button down: {e}")
    
    def handle_mouse_button_up(self, event):
        """Handle mouse button up events."""
        try:
            if hasattr(self, 'dragging') and self.dragging:
                self.dragging = False
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse button up: {e}")
    
    def handle_mouse_motion(self, event):
        """Handle mouse motion events."""
        try:
            if hasattr(self, 'dragging') and self.dragging:
                x, y = pygame.mouse.get_pos()
                if hasattr(self, 'last_mouse_pos') and self.last_mouse_pos:
                    dx = x - self.last_mouse_pos[0]
                    dy = y - self.last_mouse_pos[1]
                    # Use dx and dy for dragging functionality
                    # For example, panning the 3D map view
                self.last_mouse_pos = (x, y)
                
        except Exception as e:
            self.add_debug_message(f"Error handling mouse motion: {e}")

    def handle_key_down(self, event):
        """Handle key down events."""
        try:
            # Check if we should handle this key
            if not self.handle_3d_input:
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
            
            # Camera controls
            elif event.key == pygame.K_UP or event.key == pygame.K_w:
                # Forward key - move forward in the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('w')
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                # Backward key - move backward from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('s')
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                # Left key - move left from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('a')
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                # Right key - move right from the direction we're facing
                # Forward the key to the game for player movement
                if self.game:
                    self.game.handle_key('d')
            elif event.key == pygame.K_PAGEUP:
                # Move up
                self.camera_y += self.camera_move_speed
            elif event.key == pygame.K_PAGEDOWN:
                # Move down
                self.camera_y -= self.camera_move_speed
            elif event.key == pygame.K_HOME:
                # Reset camera position
                self.camera_x = 0
                self.camera_y = 10
                self.camera_z = 0
                self.rotation_x = 30
                self.rotation_y = 0
                
        except Exception as e:
            self.add_debug_message(f"Error handling key down: {str(e)}")
            
    def handle_key_up(self, event):
        """Handle key up events."""
        try:
            # Check if we should handle this key
            if not self.handle_3d_input:
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
                
            # Set new display mode - always use regular pygame (no OpenGL)
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

    def restart_gui(self):
        """Restart the GUI thread with new settings."""
        try:
            # Set new display mode - always use regular pygame (no OpenGL)
            flags = pygame.FULLSCREEN if self.is_fullscreen else 0
            flags |= pygame.DOUBLEBUF
                
            # Create new screen
            self.screen = pygame.display.set_mode(
                (self.width, self.height),
                flags
            )
            
            # Update caption
            pygame.display.set_caption("TextWarp Debug View")
                
        except Exception as e:
            self.add_debug_message(f"Error restarting GUI: {e}")
