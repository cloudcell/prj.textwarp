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
        # Don't set self.name here since it's a property
        self.description = "Provides a 3D visualization of the game world."
        self.active = False
        self.running = False
        self.gui_thread = None
        
        # Initialize key bindings
        self.key_bindings = KeyBindings()
        
        # Camera settings
        self.rotation_x = 30.0
        self.rotation_y = 0.0
        self.rotation_z = 0.0
        self.zoom = -50.0
        
        # Camera movement properties
        self.camera_direction = [0, 0, 1]  # Forward vector (z-axis)
        self.camera_right = [1, 0, 0]      # Right vector (x-axis)
        self.camera_up = [0, 1, 0]         # Up vector (y-axis)
        self.movement_speed = 1.0          # Movement speed
        self.camera_move_speed = 1.0       # For backward compatibility
        self.rotation_speed = 2.0          # Rotation speed in degrees
        self.handle_3d_input = True        # Whether to handle keyboard input in 3D view
        
        # New camera variables
        self.camera_x = 0.0
        self.camera_y = 10.0
        self.camera_z = 30.0
        self.camera_pitch = -20.0
        self.camera_yaw = 0.0
        self.camera_move_speed = 1.0  # Speed for camera movement
        
        self.window = None
        self.characters = {}  # 3D character objects
        self.last_mouse_pos = None
        self.dragging = False
        self.font_texture = None
        self.char_textures = {}
        self.lock = threading.Lock()  # Lock for thread safety
        self.snakes = []  # List to store snake data for connected rendering
        self.debug_messages = []  # List to store debug messages
        self.max_debug_messages = 5  # Maximum number of debug messages to display
        
        # Display options
        self.show_letters = True
        self.show_sticks = True
        self.show_dots_without_sticks = False
        self.show_mesh = True
        self.show_terrain_mesh = True
        self.show_zero_level_grid = True  # Show a grid at zero height level
        self.ascii_intensity = True  # Adjust dot intensity based on ASCII value
        self.ascii_height = False  # Use ASCII value to determine height
        self.terrain_mesh_style = "filled"  # Options: "filled", "wireframe"
        self.terrain_mesh_opacity = 0.7  # 0.0 to 1.0
        self.terrain_color_scheme = "height"  # Options: "height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"
        self.stick_dot_size = 8.0  # Size of dots at the end of sticks
        self.show_snake_connections = True  # New option to show snakes as connected balls
        self.render_distance = 100  # New option to control how far to render
        self.show_axes = True  # New option to show or hide the 3D axes
        
        # Fullscreen toggle variables
        self.fullscreen = False
        self.pre_fullscreen_size = (800, 600)
        self.double_click_time = 0.5  # Time window for double click in seconds
        self.last_click_time = 0  # Time of the last click
        
        # Load settings if they exist
        self.load_settings()
        
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
            # Add a small delay to ensure the terminal has fully rendered everything
            time.sleep(0.05)
            
            # Get the screen dimensions
            max_y, max_x = self.game.screen.getmaxyx()
            
            # Define rendering boundaries
            # Leave space for coordinate notches (3 columns on left, 6 rows at top)
            notch_left_margin = 3
            notch_top_margin = 6
            
            # Reserve 12 lines at the bottom for admin info
            bottom_margin = 12
            
            # Calculate the actual rendering area
            render_top = notch_top_margin
            render_bottom = max_y - bottom_margin
            render_left = notch_left_margin
            render_right = max_x - 2
            
            # Create a new character map
            new_character_map = {}
            
            # Get the player position
            player_x = self.game.world_x
            player_y = self.game.world_y
            
            # Get the half width and height
            half_width = max_x // 2
            half_height = max_y // 2
            
            # Clear the snake list for this update
            with self.lock:
                self.snakes = []
            
            # Process snakes in the text map only, not in 3D visualization
            # This ensures snakes are visible in the text map but won't cause OpenGL errors
            
            # Iterate through the screen within the defined rendering boundaries
            for y in range(render_top, render_bottom):
                for x in range(render_left, render_right):
                    # Try to get the character at this position
                    try:
                        # Get the character and its attributes
                        char = self.game.screen.inch(y, x)
                        
                        # Extract the character and attributes
                        char_value = chr(char & 0xFF)
                        attr = char & curses.A_ATTRIBUTES
                        
                        # Skip empty spaces
                        if char_value == ' ':
                            continue
                            
                        # Calculate render coordinates (relative to viewport)
                        # The render coordinates are centered around (0,0)
                        render_x = x - half_width
                        render_y = y - half_height
                        
                        # Create a character object
                        char_obj = Character3D(char_value, render_x, render_y)
                        
                        # Add height based on ASCII value if enabled
                        if self.ascii_height:
                            char_obj.height = ord(char_value) / 32.0  # Scale height
                        else:
                            char_obj.height = 1.0  # Default height
                            
                        # Add to the character map using render coordinates
                        new_character_map[(render_x, render_y)] = char_obj
                        
                    except:
                        # Ignore errors from reading from the screen
                        pass
            
            # Update the character map
            with self.lock:
                self.characters = new_character_map
                
        except Exception as e:
            # Log the error but don't crash
            self.add_debug_message(f"Error updating character map: {e}")
    
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
            # Initialize pygame
            pygame.init()
            
            # Create a window
            display = (800, 600)
            pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
            pygame.display.set_caption("TextWarp 3D Visualization")
            
            # Set up the OpenGL environment
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            
            # Set up the light
            glLightfv(GL_LIGHT0, GL_POSITION, (0, 10, 0, 1))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.8, 0.8, 0.8, 1))
            
            # Set up the projection matrix with a wider field of view and greater depth range
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(60, (800/600), 0.1, 200.0)  # Increased FOV and far clipping plane
            
            # Main loop
            clock = pygame.time.Clock()
            while self.running:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left mouse button
                            self.dragging = True
                            self.last_mouse_pos = pygame.mouse.get_pos()
                        elif event.button == 4:  # Scroll up
                            self.zoom += 1.0  # Increased zoom step for larger distances
                        elif event.button == 5:  # Scroll down
                            self.zoom -= 1.0  # Increased zoom step for larger distances
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:  # Left mouse button
                            self.dragging = False
                    elif event.type == pygame.MOUSEMOTION:
                        if self.dragging:
                            x, y = pygame.mouse.get_pos()
                            if self.last_mouse_pos:
                                dx = x - self.last_mouse_pos[0]
                                dy = y - self.last_mouse_pos[1]
                                self.rotation_y += dx * 0.5
                                self.rotation_x += dy * 0.5
                            self.last_mouse_pos = (x, y)
                
                # Handle keyboard input for camera-relative movement
                if self.handle_3d_input:
                    self.handle_camera_movement()
                
                # Render the scene using our dedicated method
                self.render_scene()
                
                # Limit the frame rate
                clock.tick(60)
                
        except Exception as e:
            self.add_debug_message(f"Error in GUI thread: {e}")
            traceback.print_exc()
            self.running = False
    
    def handle_camera_movement(self):
        """Handle keyboard input for camera-relative movement."""
        try:
            # Get pressed keys
            keys = pygame.key.get_pressed()
            
            # Calculate movement speed based on frame time
            speed = self.camera_move_speed * 0.1  # Adjust as needed
            
            # Calculate forward vector based on camera rotation
            forward_x = math.sin(math.radians(self.rotation_y)) * math.cos(math.radians(self.rotation_x))
            forward_y = math.sin(math.radians(self.rotation_x))
            forward_z = math.cos(math.radians(self.rotation_y)) * math.cos(math.radians(self.rotation_x))
            
            # Calculate right vector (perpendicular to forward and up)
            right_x = math.sin(math.radians(self.rotation_y + 90))
            right_y = 0
            right_z = math.cos(math.radians(self.rotation_y + 90))
            
            # Normalize vectors
            forward_length = math.sqrt(forward_x**2 + forward_y**2 + forward_z**2)
            if forward_length > 0:
                forward_x /= forward_length
                forward_y /= forward_length
                forward_z /= forward_length
                
            right_length = math.sqrt(right_x**2 + right_y**2 + right_z**2)
            if right_length > 0:
                right_x /= right_length
                right_y /= right_length
                right_z /= right_length
            
            # Handle movement keys
            if keys[pygame.K_w]:  # Forward
                self.camera_x += forward_x * speed
                self.camera_y += forward_y * speed
                self.camera_z += forward_z * speed
            if keys[pygame.K_s]:  # Backward
                self.camera_x -= forward_x * speed
                self.camera_y -= forward_y * speed
                self.camera_z -= forward_z * speed
            if keys[pygame.K_a]:  # Left
                self.camera_x -= right_x * speed
                self.camera_y -= right_y * speed
                self.camera_z -= right_z * speed
            if keys[pygame.K_d]:  # Right
                self.camera_x += right_x * speed
                self.camera_y += right_y * speed
                self.camera_z += right_z * speed
            if keys[pygame.K_SPACE]:  # Up
                self.camera_y += speed
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:  # Down
                self.camera_y -= speed
                
            # Handle rotation keys
            if keys[pygame.K_LEFT]:
                self.rotation_y -= speed * 10
            if keys[pygame.K_RIGHT]:
                self.rotation_y += speed * 10
            if keys[pygame.K_UP]:
                self.rotation_x -= speed * 10
                # Clamp pitch to prevent flipping
                self.rotation_x = max(-89.0, min(89.0, self.rotation_x))
            if keys[pygame.K_DOWN]:
                self.rotation_x += speed * 10
                # Clamp pitch to prevent flipping
                self.rotation_x = max(-89.0, min(89.0, self.rotation_x))
                
        except Exception as e:
            self.add_debug_message(f"Camera movement error: {e}")
    
    def render_scene(self):
        """Render a placeholder scene to avoid OpenGL errors."""
        try:
            # Clear the screen 
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glClearColor(0.0, 0.0, 0.0, 1.0)
            
            # Set up a simple 2D rendering mode
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(0, self.width, self.height, 0, -1, 1)
            
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            
            # Draw a simple message
            self.render_text(10, 10, "3D Visualization Disabled - Snakes visible in text map")
            self.render_text(10, 30, f"Snakes Detected: {self.get_snake_count()}")
            
            # Draw debug info
            y_pos = 50
            for msg in self.debug_messages[-10:]:  # Show last 10 messages
                self.render_text(10, y_pos, msg)
                y_pos += 20
            
            # Swap the buffers
            pygame.display.flip()
            
        except Exception as e:
            # Just silently fail - we don't want to spam the console
            pass
    
    def render_text(self, x, y, text):
        """Render text using pygame instead of OpenGL to avoid errors."""
        try:
            # Create a font object if not already created
            if not hasattr(self, 'font'):
                self.font = pygame.font.Font(None, 24)
            
            # Render the text
            text_surface = self.font.render(text, True, (255, 255, 255))
            
            # Convert the surface to a string of bytes
            text_data = pygame.image.tostring(text_surface, "RGBA", True)
            
            # Create a texture
            texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture)
            
            # Set texture parameters
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            
            # Upload the texture data
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_surface.get_width(), text_surface.get_height(), 
                         0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
            
            # Enable texturing
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Draw a textured quad
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(x, y)
            glTexCoord2f(1, 0); glVertex2f(x + text_surface.get_width(), y)
            glTexCoord2f(1, 1); glVertex2f(x + text_surface.get_width(), y + text_surface.get_height())
            glTexCoord2f(0, 1); glVertex2f(x, y + text_surface.get_height())
            glEnd()
            
            # Disable texturing
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_BLEND)
            
            # Delete the texture
            glDeleteTextures(1, [texture])
            
        except Exception as e:
            # Just silently fail - we don't want to spam the console
            pass
    
    def get_snake_count(self):
        """Get the count of snakes in the game."""
        try:
            for plugin in self.game.plugins:
                if hasattr(plugin, 'snakes') and plugin.active:
                    return len(plugin.snakes)
            return 0
        except:
            return 0
            
    def check_for_snakes(self):
        """Simplified method to ensure snakes are visible in the text map."""
        # Find the snake plugin
        snake_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                snake_plugin = plugin
                break
        
        # If we found a snake plugin, create a test snake if there are none
        if snake_plugin and hasattr(snake_plugin, 'snakes') and not snake_plugin.snakes:
            # Create a test snake near the player
            try:
                test_snake = TestSnake(self.game, self.game.world_x + 5, self.game.world_y + 5)
                snake_plugin.snakes.append(test_snake)
                self.add_debug_message(f"Created test snake at ({test_snake.x}, {test_snake.y})")
            except Exception as e:
                self.add_debug_message(f"Error creating test snake: {e}")
    
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
                    debug_info += f" Snake {i} has {len(self.snakes[i].body)} segments"
                
        return debug_info
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        try:
            self.fullscreen = not self.fullscreen
            
            if self.fullscreen:
                # Save current window size before going fullscreen
                self.pre_fullscreen_size = pygame.display.get_surface().get_size()
                
                # Set to fullscreen mode
                self.window = pygame.display.set_mode(
                    (0, 0),  # Use current desktop resolution
                    DOUBLEBUF | OPENGL | pygame.FULLSCREEN
                )
                self.add_debug_message("Switched to fullscreen mode")
            else:
                # Restore previous window size
                self.window = pygame.display.set_mode(
                    self.pre_fullscreen_size,
                    DOUBLEBUF | OPENGL
                )
                self.add_debug_message("Switched to windowed mode")
                
            # Reset the projection matrix for the new aspect ratio
            width, height = pygame.display.get_surface().get_size()
            aspect_ratio = width / height if height > 0 else 1.0
            
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(60, aspect_ratio, 0.1, self.draw_distance)
            
            # Return to modelview matrix
            glMatrixMode(GL_MODELVIEW)
            
        except Exception as e:
            self.add_debug_message(f"Error toggling fullscreen: {e}")
    
    def init_gl(self):
        """Initialize OpenGL settings."""
        try:
            # Set up the OpenGL environment
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            
            # Set up the light
            glLightfv(GL_LIGHT0, GL_POSITION, (0, 10, 0, 1))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.8, 0.8, 0.8, 1))
            
            # Set up the projection matrix with a wider field of view and greater depth range
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(self.fov, (self.window_width/self.window_height), 0.1, self.draw_distance)
            
            # Initialize font texture if needed
            if not hasattr(self, 'font_texture'):
                self.init_font_texture()
                
            self.add_debug_message("OpenGL initialized successfully")
        except Exception as e:
            self.add_debug_message(f"Error initializing OpenGL: {e}")

    def draw_vertical_lines(self):
        """Draw vertical lines (sticks) from ground to characters."""
        try:
            # Skip if no characters
            if not self.characters:
                return
                
            # Use a simpler approach without pushing/popping matrix states
            # Disable lighting for simpler rendering
            glDisable(GL_LIGHTING)
            
            # Set up for vertical lines
            glLineWidth(1.0)
            
            # Get the maximum render distance
            max_range = int(self.render_distance)
            
            # Draw vertical lines
            glBegin(GL_LINES)
            for pos, char_obj in self.characters.items():
                # Skip if no character
                if not char_obj or not hasattr(char_obj, 'char') or not char_obj.char:
                    continue
                    
                # Get position
                x, y = pos
                
                # Skip if outside render distance
                if abs(x) > max_range or abs(y) > max_range:
                    continue
                
                # Get color
                color = char_obj.color
                
                # Get height
                height = getattr(char_obj, 'height', 1.0)
                
                # Set color
                glColor3f(color[0], color[1], color[2])
                
                # Draw vertical line
                glVertex3f(x, 0, y)
                glVertex3f(x, height, y)
            glEnd()
            
            # Draw dots at the top if enabled
            if self.show_dots_without_sticks:
                glPointSize(self.stick_dot_size)
                glBegin(GL_POINTS)
                for pos, char_obj in self.characters.items():
                    # Skip if no character
                    if not char_obj or not hasattr(char_obj, 'char') or not char_obj.char:
                        continue
                        
                    # Get position
                    x, y = pos
                    
                    # Skip if outside render distance
                    if abs(x) > max_range or abs(y) > max_range:
                        continue
                    
                    # Get color
                    color = char_obj.color
                    
                    # Get height
                    height = getattr(char_obj, 'height', 1.0)
                    
                    # Set color
                    glColor3f(color[0], color[1], color[2])
                    
                    # Draw dot at the top
                    glVertex3f(x, height, y)
                glEnd()
            
            # Restore lighting
            glEnable(GL_LIGHTING)
            
        except Exception as e:
            self.add_debug_message(f"Error drawing vertical lines: {e}")
    
    def get_height_at(self, x, z):
        """Get the height at the given position."""
        # Convert to integer coordinates
        ix, iz = int(round(x)), int(round(z))
        
        # Check if we have a character at this position
        pos = (ix, iz)
        if pos in self.characters:
            char_obj = self.characters[pos]
            if hasattr(char_obj, 'height'):
                return char_obj.height
        
        # Default height
        return 0.0
    
    def get_color_for_height(self, height):
        """Get a color for the given height."""
        # Choose color scheme
        if self.terrain_color_scheme == "height":
            # Simple height-based coloring
            if height <= 0:
                # Blue to cyan for negative heights (below ground)
                r = 0
                g = 0.5 + (height / -10) * 0.5  # 0.5 to 1.0 as height goes from 0 to -10
                b = 1.0
            else:
                # Green to yellow to red for positive heights (above ground)
                if height < 0.5:
                    # Green to yellow (0 to 0.5)
                    r = height / 0.5
                    g = 0.8
                    b = 0
                else:
                    # Yellow to red (0.5 to 1.0)
                    r = 1.0
                    g = 0.8 - ((height - 0.5) / 0.5) * 0.8
                    b = 0
        elif self.terrain_color_scheme == "viridis":
            # Viridis colormap approximation (perceptually uniform, colorblind-friendly)
            if height < -5:
                # Dark purple to blue
                r = 0.267 + (height / -10) * 4 * (0.128 - 0.267)
                g = 0.004 + (height / -10) * 4 * (0.267 - 0.004)
                b = 0.329 + (height / -10) * 4 * (0.533 - 0.329)
            elif height < 0:
                # Blue to green
                t = (height / -5) * 4
                r = 0.128 + t * (0.094 - 0.128)
                g = 0.267 + t * (0.464 - 0.267)
                b = 0.533 + t * (0.558 - 0.533)
            elif height < 0.5:
                # Green to yellow
                t = (height / 0.5) * 4
                r = 0.094 + t * (0.497 - 0.094)
                g = 0.464 + t * (0.731 - 0.464)
                b = 0.558 + t * (0.142 - 0.558)
            else:
                # Yellow to light yellow
                t = ((height - 0.5) / 0.5) * 4
                r = 0.497 + t * (0.993 - 0.497)
                g = 0.731 + t * (0.906 - 0.731)
                b = 0.142 + t * (0.143 - 0.142)
        elif self.terrain_color_scheme == "viridis_inverted":
            # Inverted Viridis colormap
            if height < -5:
                # Light yellow to yellow
                r = 0.993 + (height / -10) * 4 * (0.497 - 0.993)
                g = 0.906 + (height / -10) * 4 * (0.731 - 0.906)
                b = 0.143 + (height / -10) * 4 * (0.142 - 0.143)
            elif height < 0:
                # Yellow to green
                t = (height / -5) * 4
                r = 0.497 + t * (0.094 - 0.497)
                g = 0.731 + t * (0.464 - 0.731)
                b = 0.142 + t * (0.558 - 0.142)
            elif height < 0.5:
                # Green to blue
                t = (height / 0.5) * 4
                r = 0.094 + t * (0.128 - 0.094)
                g = 0.464 + t * (0.267 - 0.464)
                b = 0.558 + t * (0.533 - 0.558)
            else:
                # Blue to dark purple
                t = ((height - 0.5) / 0.5) * 4
                r = 0.128 + t * (0.267 - 0.128)
                g = 0.267 + t * (0.004 - 0.267)
                b = 0.533 + t * (0.329 - 0.533)
        elif self.terrain_color_scheme == "plasma":
            # Plasma colormap approximation
            if height < -5:
                # Dark purple to purple
                r = 0.050 + (height / -10) * 4 * (0.403 - 0.050)
                g = 0.029 + (height / -10) * 4 * (0.029 - 0.029)
                b = 0.527 + (height / -10) * 4 * (0.692 - 0.527)
            elif height < 0:
                # Purple to pink
                t = (height / -5) * 4
                r = 0.403 + t * (0.761 - 0.403)
                g = 0.029 + t * (0.214 - 0.029)
                b = 0.692 + t * (0.558 - 0.692)
            elif height < 0.5:
                # Pink to orange
                t = (height / 0.5) * 4
                r = 0.761 + t * (0.935 - 0.761)
                g = 0.214 + t * (0.528 - 0.214)
                b = 0.558 + t * (0.126 - 0.558)
            else:
                # Orange to yellow
                t = ((height - 0.5) / 0.5) * 4
                r = 0.935 + t * (0.993 - 0.935)
                g = 0.528 + t * (0.906 - 0.528)
                b = 0.126 + t * (0.143 - 0.126)
        elif self.terrain_color_scheme == "inferno":
            # Inferno colormap approximation
            if height < -5:
                # Black to purple
                r = 0.001 + (height / -10) * 4 * (0.253 - 0.001)
                g = 0.000 + (height / -10) * 4 * (0.066 - 0.000)
                b = 0.014 + (height / -10) * 4 * (0.431 - 0.014)
            elif height < 0:
                # Purple to red
                t = (height / -5) * 4
                r = 0.253 + t * (0.632 - 0.253)
                g = 0.066 + t * (0.194 - 0.066)
                b = 0.431 + t * (0.364 - 0.431)
            elif height < 0.5:
                # Red to orange
                t = (height / 0.5) * 4
                r = 0.632 + t * (0.904 - 0.632)
                g = 0.194 + t * (0.516 - 0.194)
                b = 0.364 + t * (0.158 - 0.364)
            else:
                # Orange to yellow
                t = ((height - 0.5) / 0.5) * 4
                r = 0.904 + t * (0.988 - 0.904)
                g = 0.516 + t * (0.998 - 0.516)
                b = 0.158 + t * (0.645 - 0.158)
        elif self.terrain_color_scheme == "magma":
            # Magma colormap approximation
            if height < -5:
                # Black to purple
                r = 0.001 + (height / -10) * 4 * (0.295 - 0.001)
                g = 0.000 + (height / -10) * 4 * (0.057 - 0.000)
                b = 0.014 + (height / -10) * 4 * (0.329 - 0.014)
            elif height < 0:
                # Purple to pink
                t = (height / -5) * 4
                r = 0.295 + t * (0.651 - 0.295)
                g = 0.057 + t * (0.125 - 0.057)
                b = 0.329 + t * (0.394 - 0.329)
            elif height < 0.5:
                # Pink to orange
                t = (height / 0.5) * 4
                r = 0.651 + t * (0.918 - 0.651)
                g = 0.125 + t * (0.486 - 0.125)
                b = 0.394 + t * (0.282 - 0.394)
            else:
                # Orange to light yellow
                t = ((height - 0.5) / 0.5) * 4
                r = 0.918 + t * (0.988 - 0.918)
                g = 0.486 + t * (0.998 - 0.486)
                b = 0.282 + t * (0.645 - 0.282)
        elif self.terrain_color_scheme == "cividis":
            # Cividis colormap approximation (colorblind-friendly)
            if height < -5:
                # Dark blue to blue
                r = 0.000 + (height / -10) * 4 * (0.127 - 0.000)
                g = 0.135 + (height / -10) * 4 * (0.302 - 0.135)
                b = 0.304 + (height / -10) * 4 * (0.385 - 0.304)
            elif height < 0:
                # Blue to teal
                t = (height / -5) * 4
                r = 0.127 + t * (0.255 - 0.127)
                g = 0.302 + t * (0.455 - 0.302)
                b = 0.385 + t * (0.365 - 0.385)
            elif height < 0.5:
                # Teal to yellow-green
                t = (height / 0.5) * 4
                r = 0.255 + t * (0.540 - 0.255)
                g = 0.455 + t * (0.600 - 0.455)
                b = 0.365 + t * (0.260 - 0.365)
            else:
                # Yellow-green to yellow
                t = ((height - 0.5) / 0.5) * 4
                r = 0.540 + t * (0.993 - 0.540)
                g = 0.600 + t * (0.906 - 0.600)
                b = 0.260 + t * (0.144 - 0.260)
        else:
            # Default to grayscale
            r = g = b = height
            
        return (r, g, b)

    def draw_terrain_mesh(self):
        """Draw a mesh connecting the tips of the sticks to visualize the terrain surface."""
        try:
            # Skip if no characters
            if not self.characters:
                return
                
            # Use a simpler approach without pushing/popping matrix states
            # Set up for terrain mesh
            glDisable(GL_LIGHTING)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Set mesh style
            if self.terrain_mesh_style == "wireframe":
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            else:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            
            # Set mesh opacity
            mesh_alpha = self.terrain_mesh_opacity
            
            # Create a grid of points
            grid_size = 1.0  # Distance between grid points
            max_range = int(self.render_distance / 2)  # Reduce range for better performance
            
            # Draw the mesh as a series of triangle strips
            for z in range(-max_range, max_range, int(grid_size)):
                glBegin(GL_TRIANGLE_STRIP)
                for x in range(-max_range, max_range, int(grid_size)):
                    # Get heights at these positions
                    h1 = self.get_height_at(x, z)
                    h2 = self.get_height_at(x, z + grid_size)
                    
                    # Set colors based on height
                    color1 = self.get_color_for_height(h1)
                    color2 = self.get_color_for_height(h2)
                    
                    # Add alpha
                    color1 = (color1[0], color1[1], color1[2], mesh_alpha)
                    color2 = (color2[0], color2[1], color2[2], mesh_alpha)
                    
                    # Add vertices
                    glColor4f(*color1)
                    glVertex3f(x, h1, z)
                    
                    glColor4f(*color2)
                    glVertex3f(x, h2, z + grid_size)
                glEnd()
            
            # Restore state
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glDisable(GL_BLEND)
            glEnable(GL_LIGHTING)
            
        except Exception as e:
            self.add_debug_message(f"Error drawing terrain mesh: {e}")
    
    def draw_connected_snakes(self):
        """Draw snakes as connected balls."""
        try:
            # Skip if no snakes
            if not self.snakes:
                return
                
            # Use a simpler approach without pushing/popping matrix states
            # Draw each snake as simple colored cubes
            
            # Set up once for all snakes
            glDisable(GL_LIGHTING)  # Disable lighting for simpler rendering
            
            for snake_idx, snake_body in enumerate(self.snakes):
                if not snake_body:
                    continue
                
                # Draw each segment as a simple cube without matrix operations
                for i, (x, y) in enumerate(snake_body):
                    # Determine color based on segment type
                    if i == 0:
                        # Head - red
                        glColor3f(0.8, 0.2, 0.2)
                    elif i >= len(snake_body) - 2:  # Assume last 2 segments are rattles
                        # Rattle - yellow
                        glColor3f(0.8, 0.8, 0.2)
                    else:
                        # Body - dark blue (matching the text map color)
                        glColor3f(0.0, 0.0, 0.7)
                    
                    # Draw a simple cube
                    self.draw_simple_cube(x, 0.5, y, 0.4)
            
            # Restore lighting
            glEnable(GL_LIGHTING)
            
        except Exception as e:
            self.add_debug_message(f"Error drawing connected snakes: {e}")
    
    def draw_simple_cube(self, x, y, z, size):
        """Draw a simple marker at the given position instead of a cube to avoid OpenGL errors."""
        try:
            # Draw a simple point instead of a cube
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_LIGHTING)
            
            # Set point size
            glPointSize(5.0)
            
            # Draw a point at the specified position
            glBegin(GL_POINTS)
            glVertex3f(x, y, z)
            glEnd()
            
            # Reset point size
            glPointSize(1.0)
            
        except Exception as e:
            self.add_debug_message(f"Error drawing point marker: {e}")

    def draw_ground_plane(self):
        """Draw a simple ground plane."""
        try:
            # Disable lighting and texturing for simpler rendering
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            
            # Set color for ground plane
            glColor3f(0.2, 0.2, 0.2)
            
            # Draw a simple grid
            grid_size = 50
            grid_step = 5
            
            # Use GL_LINES for better performance
            glBegin(GL_LINES)
            
            # Draw lines along X axis
            for i in range(-grid_size, grid_size + 1, grid_step):
                glVertex3f(i, 0, -grid_size)
                glVertex3f(i, 0, grid_size)
            
            # Draw lines along Z axis
            for i in range(-grid_size, grid_size + 1, grid_step):
                glVertex3f(-grid_size, 0, i)
                glVertex3f(grid_size, 0, i)
                
            glEnd()
            
        except Exception as e:
            self.add_debug_message(f"Error drawing ground plane: {e}")
