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
        self.show_terrain_mesh = False
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
        
        # Load settings if they exist
        self.load_settings()
        
    @property
    def name(self):
        """Return the name of the plugin."""
        return "3D Visualization"
        
    def activate(self):
        """Activate the plugin."""
        super().activate()
        self.running = True
        self.gui_thread = threading.Thread(target=self.run_gui, daemon=True)
        self.gui_thread.start()
        
    def deactivate(self):
        """Deactivate the plugin."""
        self.running = False
        if self.gui_thread:
            self.gui_thread.join(timeout=1.0)
        super().deactivate()
        
    def update(self, dt):
        """Update the plugin state."""
        if not self.active:
            return
            
        # Update the character map based on the current game state
        self.update_character_map()
        
        # Directly check for snakes to ensure they're visualized
        self.check_for_snakes()
    
    def check_for_snakes(self):
        """Directly check for snakes in the game and add them to the visualization."""
        # Skip if not active or running
        if not self.active or not self.running:
            return
            
        # Find the snake plugin
        snake_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                snake_plugin = plugin
                break
                
        # If no snake plugin or no snakes, return
        if not snake_plugin or not hasattr(snake_plugin, 'snakes') or not snake_plugin.snakes:
            return
            
        # Debug output
        self.add_debug_message(f"Direct snake check found {len(snake_plugin.snakes)} snakes")
        
        # Find height plugin if available
        height_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'get_height'):
                height_plugin = plugin
                break
        
        # Process each snake
        for snake_idx, snake in enumerate(snake_plugin.snakes):
            if not hasattr(snake, 'body') or len(snake.body) < 2:
                continue
                
            # Create a list to store this snake's segments
            snake_segments = []
            
            # Get the number of rattles for this snake
            num_rattles = getattr(snake, 'rattles', 0)
            
            # Process each segment of the snake
            for i, (sx, sy) in enumerate(snake.body):
                # Calculate relative coordinates - center around player position
                rel_x = sx - self.game.world_x
                rel_y = sy - self.game.world_y
                
                # Skip segments that are too far away
                if abs(rel_x) > self.render_distance or abs(rel_y) > self.render_distance:
                    continue
                
                # Get height for this position (if available)
                height = 1.0  # Default height if no height plugin
                if height_plugin:
                    try:
                        height = height_plugin.get_height(sx, sy) / 10.0  # Scale height appropriately
                    except:
                        pass  # Use default height if there's an error
                
                # Ensure height is positive for visibility
                height = max(1.0, abs(height))
                
                # Determine segment type and color
                if i == 0:
                    # Head is green
                    segment_type = 'head'
                    color = (0.0, 1.0, 0.0, 1.0)  # Bright green for head
                elif num_rattles > 0 and i >= len(snake.body) - num_rattles:
                    # Rattles are red
                    segment_type = 'rattle'
                    color = (1.0, 0.0, 0.0, 1.0)  # Bright red for rattles
                else:
                    # Body is blue
                    segment_type = 'body'
                    color = (0.0, 0.0, 1.0, 1.0)  # Bright blue for body
                
                # Add to the snake segments list with explicit position
                snake_segments.append({
                    'position': (rel_x, height, rel_y),
                    'color': color,
                    'type': segment_type
                })
            
            # Add this snake's segments to the snakes list
            if snake_segments:
                with self.lock:
                    # Replace any existing snake with the same index
                    while len(self.snakes) <= snake_idx:
                        self.snakes.append([])
                    self.snakes[snake_idx] = snake_segments
                    self.add_debug_message(f"Updated snake {snake_idx} with {len(snake_segments)} segments")
    
    def update_character_map(self):
        """Update the 3D character map from the game world."""
        if not self.active or not self.running:
            return
            
        # Clear the snake list for this update
        with self.lock:
            self.snakes = []
            self.characters = {}  # Clear existing characters
            
        # Get the current game world state
        world_x = self.game.world_x
        world_y = self.game.world_y
        width = self.game.width
        height = self.game.height
        
        # Find the snake plugin
        snake_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                snake_plugin = plugin
                break
                
        # Find a height plugin if available
        height_plugin = None
        for plugin in self.game.plugins:
            if hasattr(plugin, 'get_height'):
                height_plugin = plugin
                break
                
        # Process snakes if available
        if snake_plugin and hasattr(snake_plugin, 'snakes'):
            try:
                # Debug output
                self.add_debug_message(f"Found {len(snake_plugin.snakes)} snakes in update_character_map")
                
                # Process each snake
                for snake_idx, snake in enumerate(snake_plugin.snakes):
                    if not hasattr(snake, 'body') or not snake.body:
                        continue
                        
                    # Create a list to store this snake's segments
                    snake_segments = []
                    
                    # Get the number of rattles for this snake
                    num_rattles = getattr(snake, 'rattles', 0)
                    
                    # Process each segment of the snake
                    for i, (sx, sy) in enumerate(snake.body):
                        # Calculate relative coordinates - center around player position
                        rel_x = sx - world_x
                        rel_y = sy - world_y
                        
                        # Skip segments outside the visible area
                        if (abs(rel_x) > self.render_distance or 
                            abs(rel_y) > self.render_distance):
                            continue
                            
                        # Get height for this position (if available)
                        segment_height = 1.0  # Default height if no height plugin
                        if height_plugin:
                            try:
                                segment_height = height_plugin.get_height(sx, sy) / 10.0
                            except Exception as e:
                                self.add_debug_message(f"Height error: {e}")
                                
                        # Ensure height is positive for visibility
                        segment_height = max(1.0, abs(segment_height))
                        
                        # Determine segment type and color
                        if i == 0:
                            # Head is green
                            segment_type = 'head'
                            color = (0.0, 1.0, 0.0, 1.0)  # Bright green for head
                        elif num_rattles > 0 and i >= len(snake.body) - num_rattles:
                            # Rattles are red
                            segment_type = 'rattle'
                            color = (1.0, 0.0, 0.0, 1.0)  # Bright red for rattles
                        else:
                            # Body is blue
                            segment_type = 'body'
                            color = (0.0, 0.0, 1.0, 1.0)  # Bright blue for body
                        
                        # Add to the snake segments list
                        snake_segments.append({
                            'position': (rel_x, segment_height, rel_y),
                            'color': color,
                            'type': segment_type
                        })
                        
                        # Also add as a character for compatibility
                        char_obj = Character3D('S', rel_x, rel_y, color)
                        char_obj.height = segment_height  # Override the height
                        with self.lock:
                            self.characters[(rel_x, rel_y)] = char_obj
                    
                    # Add this snake's segments to the snakes list
                    if snake_segments:
                        with self.lock:
                            # Replace any existing snake with the same index
                            while len(self.snakes) <= snake_idx:
                                self.snakes.append([])
                            self.snakes[snake_idx] = snake_segments
                            self.add_debug_message(f"Added snake {snake_idx} with {len(snake_segments)} segments")
            except Exception as e:
                self.add_debug_message(f"Snake processing error: {e}")
        
        # Get visible area dimensions
        max_y, max_x = self.game.max_y, self.game.max_x
        
        # Add characters from the game world
        for y in range(max_y):
            for x in range(max_x):
                # Get the character at this position
                char = self.game.get_char_at(x, y)
                if not char or char == ' ':
                    continue
                    
                # Calculate world coordinates
                world_x_pos = x - max_x // 2 + world_x
                world_y_pos = y - max_y // 2 + world_y
                
                # Get relative coordinates
                rel_x = x - max_x // 2
                rel_y = y - max_y // 2
                
                # Get color for this character
                color = self.get_color_for_char(char, rel_x, rel_y)
                
                # Create a 3D character object
                char_obj = Character3D(char, rel_x, rel_y, color)
                
                # Override height if using ASCII height or if a height plugin is available
                if self.ascii_height:
                    # Use ASCII value to determine height (scale between 0.5 and 5.0)
                    ascii_val = ord(char)
                    char_obj.height = 0.5 + (ascii_val / 255.0) * 4.5
                elif height_plugin:
                    try:
                        char_obj.height = height_plugin.get_height(world_x_pos, world_y_pos) / 10.0
                    except:
                        pass  # Use default height if there's an error
                
                # Add the character to our map
                with self.lock:
                    self.characters[(rel_x, rel_y)] = char_obj
        
        # Add remote players if network plugin is active
        for plugin in self.game.plugins:
            if hasattr(plugin, 'players') and plugin.active:
                for player in plugin.players.values():
                    if not player.is_active():
                        continue
                    rel_x = player.x - self.game.world_x
                    rel_y = player.y - self.game.world_y
                    with self.lock:
                        self.characters[(rel_x, rel_y)] = Character3D('O', rel_x, rel_y, (0.0, 1.0, 0.0, 1.0))
    
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
        """Run the GUI in a separate thread."""
        try:
            # Initialize pygame
            pygame.init()
            
            # Initialize GLUT for text rendering
            try:
                glutInit()
            except:
                # GLUT might not be available, so we'll provide a fallback
                self.draw_text = self.draw_text_fallback
            
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
            
            # Initialize font texture
            self.init_font_texture()
            
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
                
                # Cap the frame rate
                clock.tick(60)
                
        except Exception as e:
            self.game.message = f"3D GUI error: {e}"
            self.game.message_timeout = 5.0
        finally:
            pygame.quit()
            
    def handle_camera_movement(self):
        """Handle keyboard input for camera-relative movement."""
        # Get pressed keys
        keys = pygame.key.get_pressed()
        
        # Calculate movement direction based on camera rotation
        # Convert rotation angles to radians
        rotation_y_rad = math.radians(self.rotation_y)
        
        # Calculate forward and right vectors based on camera rotation
        # In our coordinate system:
        # - Forward is along the negative Z axis when rotation_y = 0
        # - Right is along the positive X axis when rotation_y = 0
        forward_x = -math.sin(rotation_y_rad)
        forward_z = -math.cos(rotation_y_rad)
        
        right_x = math.cos(rotation_y_rad)
        right_z = -math.sin(rotation_y_rad)
        
        # Initialize movement vector
        move_x = 0
        move_z = 0
        
        # Apply movement based on key bindings
        if keys[self.key_bindings.gui_keys["move_forward"]]:
            # Move forward
            move_x += forward_x * self.movement_speed
            move_z += forward_z * self.movement_speed
        if keys[self.key_bindings.gui_keys["move_backward"]]:
            # Move backward
            move_x -= forward_x * self.movement_speed
            move_z -= forward_z * self.movement_speed
        if keys[self.key_bindings.gui_keys["strafe_right"]]:
            # Move right
            move_x += right_x * self.movement_speed
            move_z += right_z * self.movement_speed
        if keys[self.key_bindings.gui_keys["strafe_left"]]:
            # Move left
            move_x -= right_x * self.movement_speed
            move_z -= right_z * self.movement_speed
        
        # Handle rotation
        if keys[self.key_bindings.gui_keys["rotate_ccw"]]:
            # Rotate counter-clockwise
            self.rotation_y += self.rotation_speed
        if keys[self.key_bindings.gui_keys["rotate_cw"]]:
            # Rotate clockwise
            self.rotation_y -= self.rotation_speed
            
        # Apply movement to game world coordinates if any movement occurred
        if move_x != 0 or move_z != 0:
            self.game.world_x += move_x
            self.game.world_y += move_z  # Note: game's Y is our Z in 3D space
            self.game.needs_redraw = True
    
    def render_scene(self):
        """Render the 3D scene."""
        try:
            # Clear the screen and depth buffer
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glClearColor(0.0, 0.0, 0.0, 1.0)
            
            # Set up the modelview matrix
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            
            # Apply camera transformations
            glTranslatef(0, 0, self.zoom)
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)
            glRotatef(self.rotation_z, 0, 0, 1)
            
            # Add debug message with snake information (without any prefix)
            debug_info = self.render_debug_info()
            if debug_info:
                self.add_debug_message(debug_info)
            
            # Draw coordinate axes if enabled
            if self.show_axes:
                self.draw_axes()
            
            # Draw the ground plane
            self.draw_ground_plane()
            
            # Draw vertical lines (sticks) if enabled
            if self.show_sticks or self.show_dots_without_sticks:
                self.draw_vertical_lines()
            
            # Draw terrain mesh if enabled
            if self.show_terrain_mesh:
                self.draw_terrain_mesh()
            
            # Draw characters if enabled
            if self.show_letters:
                self.draw_characters()
            
            # Draw snakes as connected balls
            self.draw_connected_snakes()
            
            # Update the display
            pygame.display.flip()
        except Exception as e:
            # Log the error but don't crash
            self.add_debug_message(f"Error rendering scene: {e}")
    
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
                debug_info += f" Snake {i} has {len(self.snakes[i])} segments"
                
        return debug_info
    
    def draw_characters(self):
        """Draw all characters in the 3D world."""
        # Make a copy of the characters dictionary to avoid modification during iteration
        with self.lock:
            characters_copy = dict(self.characters)
            
        # Sort characters by height for proper rendering (draw from back to front)
        sorted_chars = sorted(characters_copy.values(), key=lambda c: c.y)  # Sort by y position (depth)
        
        for char_obj in sorted_chars:
            # Set character position
            glPushMatrix()
            
            # Position the character
            # For negative heights, we need to adjust the vertical position
            if char_obj.height >= 0:
                # Positive height: Position with base at ground level
                glTranslatef(char_obj.x, char_obj.height / 2, char_obj.y)
                # Scale the character based on height for better visibility
                scale_factor = 0.8 + abs(char_obj.height) * 0.3
                glScalef(scale_factor, 1.0, scale_factor)
            else:
                # Negative height: Position with top at ground level
                glTranslatef(char_obj.x, char_obj.height / 2, char_obj.y)
                # Scale the character based on height for better visibility
                scale_factor = 0.8 + abs(char_obj.height) * 0.3
                glScalef(scale_factor, 1.0, scale_factor)
            
            # Always face the camera (billboarding)
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            
            # Extract the rotation from the modelview matrix
            camera_right = [modelview[0][0], modelview[1][0], modelview[2][0]]
            camera_up = [modelview[0][1], modelview[1][1], modelview[2][1]]
            
            # Draw the character as a textured quad
            if char_obj.char in self.char_textures:
                # Bind the character texture
                texture_info = self.char_textures[char_obj.char]
                glBindTexture(GL_TEXTURE_2D, texture_info['id'])
                
                # Set character color
                glColor4f(*char_obj.color)
                
                # Calculate quad size based on texture aspect ratio
                aspect = texture_info['width'] / texture_info['height']
                quad_height = abs(char_obj.height)  # Use absolute height for quad size
                quad_width = quad_height * aspect
                
                # Draw textured quad
                glBegin(GL_QUADS)
                glTexCoord2f(0, 0); glVertex3f(-quad_width/2, -quad_height/2, 0)
                glTexCoord2f(1, 0); glVertex3f(quad_width/2, -quad_height/2, 0)
                glTexCoord2f(1, 1); glVertex3f(quad_width/2, quad_height/2, 0)
                glTexCoord2f(0, 1); glVertex3f(-quad_width/2, quad_height/2, 0)
                glEnd()
            else:
                # Fallback: draw a colored cube for characters without textures
                glColor4f(*char_obj.color)
                self.draw_cube(abs(char_obj.height) / 2)  # Use absolute height for cube size
            
            glPopMatrix()
            
        # Disable texturing
        glDisable(GL_TEXTURE_2D)
        
        # Draw coordinate axes for better orientation
        glBegin(GL_LINES)
        
        # X-axis (red)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(5, 0, 0)
        
        # Y-axis (green)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 5, 0)
        
        # Z-axis (blue)
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 5)
        glEnd()
        
        # Draw a special marker at the center (0,0) to indicate player position
        glBegin(GL_LINES)
        glColor3f(1.0, 1.0, 0.0)  # Yellow
        
        # X marker
        marker_size = 0.5
        glVertex3f(-marker_size, 0, -marker_size)
        glVertex3f(marker_size, 0, marker_size)
        glVertex3f(-marker_size, 0, marker_size)
        glVertex3f(marker_size, 0, -marker_size)
        
        glEnd()
        
    def draw_connected_snakes(self):
        """Draw snakes as balls connected by lines."""
        try:
            if not self.snakes:
                return
                
            self.add_debug_message(f"Drawing {len(self.snakes)} snakes")  # Debug output
            
            # Save current OpenGL state
            glPushAttrib(GL_ALL_ATTRIB_BITS)
            
            # Disable depth test temporarily to ensure snakes are visible
            glDisable(GL_DEPTH_TEST)
            
            # Enable lighting for better 3D appearance
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            
            # Set up a stronger light for better visibility
            glLightfv(GL_LIGHT0, GL_POSITION, (0, 10, 0, 1))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.4, 0.4, 0.4, 1))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (1.0, 1.0, 1.0, 1))
            glLightfv(GL_LIGHT0, GL_SPECULAR, (1.0, 1.0, 1.0, 1))
            
            # Enable blending for transparency
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Get audio plugin for beat synchronization
            audio_plugin = None
            for plugin in self.game.plugins:
                if plugin.__class__.__name__ == "AudioPlugin" and plugin.active:
                    audio_plugin = plugin
                    break
            
            # Draw each snake
            for snake_idx, snake in enumerate(self.snakes):
                # Skip empty snakes
                if not snake:
                    continue
                    
                self.add_debug_message(f"Snake {snake_idx} has {len(snake)} segments")  # Debug output
                
                if len(snake) < 2:
                    continue  # Need at least 2 segments to draw connections
                    
                # Draw the connecting lines first (behind the balls)
                glDisable(GL_LIGHTING)  # Disable lighting for lines
                glLineWidth(5.0)  # Thicker lines for better visibility
                
                # Draw lines with bright colors
                glBegin(GL_LINE_STRIP)
                for segment in snake:
                    pos = segment['position']
                    color = segment['color']
                    # Make the line fully opaque
                    glColor4f(color[0], color[1], color[2], 1.0)
                    glVertex3f(pos[0], pos[1], pos[2])  # Use the correct position coordinates
                glEnd()
                
                # Re-enable lighting for spheres
                glEnable(GL_LIGHTING)
                
                # Now draw the balls (spheres) for each segment
                for segment_idx, segment in enumerate(snake):
                    pos = segment['position']
                    color = segment['color']
                    segment_type = segment['type']
                    
                    # Push matrix for this segment
                    glPushMatrix()
                    
                    # Position the sphere
                    glTranslatef(pos[0], pos[1], pos[2])  # Use the correct position coordinates
                    
                    # Get audio intensity for this snake (if audio plugin is active)
                    intensity = 1.0
                    if audio_plugin and segment_type == 'head':
                        try:
                            intensity = audio_plugin.get_snake_head_intensity(snake_idx)
                            # Make the head pulse with the music
                            color = (
                                min(1.0, color[0] * (0.5 + 1.0 * intensity)),
                                min(1.0, color[1] * (0.5 + 1.0 * intensity)),
                                min(1.0, color[2] * (0.5 + 1.0 * intensity))
                            )
                        except Exception:
                            # If there's an error getting intensity, just use default
                            pass
                    
                    # Set material properties for better lighting
                    glMaterialfv(GL_FRONT, GL_AMBIENT_AND_DIFFUSE, (color[0], color[1], color[2], 1.0))
                    glMaterialfv(GL_FRONT, GL_SPECULAR, (1.0, 1.0, 1.0, 1.0))
                    glMaterialf(GL_FRONT, GL_SHININESS, 100.0)
                    
                    # Set color
                    glColor4f(color[0], color[1], color[2], 1.0)
                    
                    # Draw a sphere with appropriate size based on segment type
                    if segment_type == 'head':
                        # Make heads pulse with the music
                        radius = 0.6  # Base size for head
                        if audio_plugin:
                            # Scale the radius based on audio intensity
                            radius *= 0.8 + 0.4 * intensity
                        
                        # Add glow effect that changes with the music
                        if audio_plugin:
                            glow_intensity = intensity * 0.5
                            glMaterialfv(GL_FRONT, GL_EMISSION, (glow_intensity, glow_intensity * 0.5, 0.0, 1.0))
                    elif segment_type == 'rattle':
                        radius = 0.5  # Medium rattles
                        # Add a pulsing effect to rattles to make them more noticeable
                        import math
                        pulse = 0.2 * math.sin(time.time() * 5.0) + 0.8  # Pulsing between 0.6 and 1.0
                        glColor4f(color[0] * pulse, color[1] * pulse, color[2] * pulse, 1.0)
                        glMaterialfv(GL_FRONT, GL_EMISSION, (0.3, 0.0, 0.0, 1.0))  # Add glow to rattles
                    else:
                        radius = 0.3  # Smaller body segments
                        
                    # Create a sphere quadric object with higher quality
                    quadric = gluNewQuadric()
                    gluQuadricDrawStyle(quadric, GLU_FILL)
                    gluQuadricNormals(quadric, GLU_SMOOTH)
                    gluQuadricTexture(quadric, GL_TRUE)
                    gluSphere(quadric, radius, 16, 16)  # Higher resolution spheres
                    gluDeleteQuadric(quadric)
                    
                    glPopMatrix()
                    
            # Restore OpenGL state
            glPopAttrib()
        except Exception as e:
            # Log the error but don't crash
            self.add_debug_message(f"Error drawing snakes: {e}")
    
    def draw_terrain_mesh(self):
        """Draw a mesh connecting the tips of the sticks to visualize the terrain surface."""
        # Disable texturing
        glDisable(GL_TEXTURE_2D)
        
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Get all character positions and heights
        positions = {}
        with self.lock:
            for key, char_obj in self.characters.items():
                if isinstance(key, tuple):
                    x, y = key
                else:
                    # Parse the key if it's a string (format: "x,y")
                    try:
                        x, y = map(int, key.split(','))
                    except:
                        continue
                
                positions[(x, y)] = char_obj.height
        
        # If we have no positions, return
        if not positions:
            return
            
        # Determine the bounds of the terrain
        min_x = min(x for x, _ in positions.keys())
        max_x = max(x for x, _ in positions.keys())
        min_y = min(y for _, y in positions.keys())
        max_y = max(y for _, y in positions.keys())
        
        # Expand the bounds to ensure we render a larger area
        min_x = min(min_x, -self.render_distance // 2)
        max_x = max(max_x, self.render_distance // 2)
        min_y = min(min_y, -self.render_distance // 2)
        max_y = max(max_y, self.render_distance // 2)
        
        # Set the mesh color based on style
        if self.terrain_mesh_style == "filled":
            # For filled style, use a semi-transparent color
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        else:
            # For wireframe style, use lines
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        
        # Draw triangles connecting the points
        for x in range(min_x, max_x):
            for y in range(min_y, max_y):
                # Check if we have all four corners of a grid cell
                corners = [
                    (x, y),
                    (x+1, y),
                    (x, y+1),
                    (x+1, y+1)
                ]
                
                # Count how many corners we have
                valid_corners = [c for c in corners if c in positions]
                
                # Skip if we don't have enough corners to form triangles
                if len(valid_corners) < 3:
                    continue
                
                # Calculate the midpoint if we have all four corners
                if len(valid_corners) == 4:
                    # Calculate the midpoint height as the average of the four corners
                    mid_height = sum(positions[c] for c in valid_corners) / 4
                    
                    # Draw four triangles from the corners to the midpoint
                    glBegin(GL_TRIANGLES)
                    
                    # For each corner, draw a triangle to the midpoint
                    for i, corner in enumerate(corners):
                        next_corner = corners[(i + 1) % 4]
                        
                        # Get corner positions and heights
                        cx, cy = corner
                        corner_height = positions.get(corner, 0)
                        
                        # Get next corner
                        nx, ny = next_corner
                        next_height = positions.get(next_corner, 0)
                        
                        # Calculate midpoint position
                        mid_x = (min_x + max_x) / 2
                        mid_y = (min_y + max_y) / 2
                        
                        # Set colors based on heights and color scheme
                        corner_color = self.get_color_from_scheme(corner_height, self.terrain_color_scheme)
                        next_color = self.get_color_from_scheme(next_height, self.terrain_color_scheme)
                        mid_color = self.get_color_from_scheme(mid_height, self.terrain_color_scheme)
                        
                        # Add alpha for transparency
                        corner_color = (*corner_color, self.terrain_mesh_opacity)
                        next_color = (*next_color, self.terrain_mesh_opacity)
                        mid_color = (*mid_color, self.terrain_mesh_opacity)
                        
                        # Draw the triangle
                        glColor4f(*corner_color)
                        glVertex3f(cx, corner_height, cy)
                        
                        glColor4f(*next_color)
                        glVertex3f(nx, next_height, ny)
                        
                        glColor4f(*mid_color)
                        glVertex3f((cx + nx) / 2, mid_height, (cy + ny) / 2)
                    
                    glEnd()
                else:
                    # Draw a single triangle with the corners we have
                    glBegin(GL_TRIANGLES)
                    
                    for corner in valid_corners:
                        cx, cy = corner
                        corner_height = positions.get(corner, 0)
                        corner_color = self.get_color_from_scheme(corner_height, self.terrain_color_scheme)
                        corner_color = (*corner_color, self.terrain_mesh_opacity)
                        
                        glColor4f(*corner_color)
                        glVertex3f(cx, corner_height, cy)
                    
                    glEnd()
        
        # Reset polygon mode
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        
        # Disable blending
        glDisable(GL_BLEND)
    
    def draw_ground_plane(self):
        """Draw the ground plane."""
        # Draw a larger grid for the ground plane
        glDisable(GL_LIGHTING)
        
        # Only draw the zero level grid if enabled
        if self.show_zero_level_grid:
            # Draw a grid at zero height
            glColor3f(0.2, 0.2, 0.2)
            
            # Draw a grid extending further
            grid_size = 50  # Increased from 10
            grid_step = 5   # Draw lines every 5 units for less clutter
            
            glBegin(GL_LINES)
            for i in range(-grid_size, grid_size + 1, grid_step):
                # Draw lines along X axis
                glVertex3f(i, 0, -grid_size)
                glVertex3f(i, 0, grid_size)
                
                # Draw lines along Z axis
                glVertex3f(-grid_size, 0, i)
                glVertex3f(grid_size, 0, i)
            glEnd()
        
        # Re-enable lighting
        glEnable(GL_LIGHTING)
        
        # Draw coordinate axes for better orientation
        if self.show_axes:
            glBegin(GL_LINES)
            
            # X-axis (red)
            glColor3f(1.0, 0.0, 0.0)
            glVertex3f(0, 0, 0)
            glVertex3f(5, 0, 0)
            
            # Y-axis (green)
            glColor3f(0.0, 1.0, 0.0)
            glVertex3f(0, 0, 0)
            glVertex3f(0, 5, 0)
            
            # Z-axis (blue)
            glColor3f(0.0, 0.0, 1.0)
            glVertex3f(0, 0, 0)
            glVertex3f(0, 0, 5)
            glEnd()
            
            # Draw a special marker at the center (0,0) to indicate player position
            glBegin(GL_LINES)
            glColor3f(1.0, 1.0, 0.0)  # Yellow
            
            # X marker
            marker_size = 0.5
            glVertex3f(-marker_size, 0, -marker_size)
            glVertex3f(marker_size, 0, marker_size)
            glVertex3f(-marker_size, 0, marker_size)
            glVertex3f(marker_size, 0, -marker_size)
            
            glEnd()
            
    def draw_axes(self):
        """Draw coordinate axes for better orientation."""
        # Disable lighting for clearer axes
        glDisable(GL_LIGHTING)
        
        # Set line width for better visibility
        glLineWidth(3.0)
        
        # Draw the axes with distinct colors
        glBegin(GL_LINES)
        
        # X axis - Red
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(10, 0, 0)
        
        # Y axis - Green
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 10, 0)
        
        # Z axis - Blue
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 10)
        glEnd()
        
        # Draw axis labels
        # X axis label
        glPushMatrix()
        glTranslatef(11, 0, 0)
        glColor3f(1.0, 0.0, 0.0)
        glRasterPos3f(0, 0, 0)
        self.draw_text("X")
        glPopMatrix()
        
        # Y axis label
        glPushMatrix()
        glTranslatef(0, 11, 0)
        glColor3f(0.0, 1.0, 0.0)
        glRasterPos3f(0, 0, 0)
        self.draw_text("Y")
        glPopMatrix()
        
        # Z axis label
        glPushMatrix()
        glTranslatef(0, 0, 11)
        glColor3f(0.0, 0.0, 1.0)
        glRasterPos3f(0, 0, 0)
        self.draw_text("Z")
        glPopMatrix()
        
        # Reset line width
        glLineWidth(1.0)
        
        # Re-enable lighting
        glEnable(GL_LIGHTING)
    
    def draw_text(self, text):
        """Draw text at the current raster position."""
        for c in text:
            glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(c))
    
    def draw_text_fallback(self, text):
        """Fallback for drawing text if GLUT is not available."""
        # This is a very basic fallback that doesn't print to terminal
        # It's recommended to use GLUT for proper text rendering
        
        # Instead of printing to terminal, we'll draw simple rectangles
        # to represent text in the 3D scene
        glDisable(GL_LIGHTING)
        glColor3f(1.0, 1.0, 1.0)  # White color for text
        
        # Draw a small rectangle for each character
        for i, c in enumerate(text):
            glPushMatrix()
            glTranslatef(i * 0.1, 0, 0)  # Offset each character
            
            # Draw a small rectangle
            glBegin(GL_QUADS)
            glVertex3f(0, 0, 0)
            glVertex3f(0.08, 0, 0)
            glVertex3f(0.08, 0.1, 0)
            glVertex3f(0, 0.1, 0)
            glEnd()
            
            glPopMatrix()
        
        glEnable(GL_LIGHTING)
    
    def draw_cube(self, size):
        """Draw a simple cube."""
        half = size / 2
        
        # Define the vertices of the cube
        vertices = [
            [half, half, -half],
            [-half, half, -half],
            [-half, -half, -half],
            [half, -half, -half],
            [half, half, half],
            [-half, half, half],
            [-half, -half, half],
            [half, -half, half]
        ]
        
        # Define the faces using indices into the vertices list
        faces = [
            [0, 1, 2, 3],  # Back face
            [4, 5, 6, 7],  # Front face
            [0, 4, 7, 3],  # Right face
            [1, 5, 6, 2],  # Left face
            [0, 1, 5, 4],  # Top face
            [3, 2, 6, 7]   # Bottom face
        ]
        
        # Draw each face as a quad
        glBegin(GL_QUADS)
        for face in faces:
            for vertex in face:
                glVertex3f(*vertices[vertex])
        glEnd()

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
                self.show_terrain_mesh = settings.get("show_terrain_mesh", False)
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
            {"name": "Render Distance", "value": self.render_distance, "type": "int", "min": 10, "max": 200, "step": 10},
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

    def show_key_bindings_menu(self):
        """Show the key bindings menu for the 3D GUI."""
        # Store original key bindings in case user cancels
        original_key_bindings = self.key_bindings.gui_keys.copy()
        
        # Create a list of settings
        settings = []
        for action, key_code in self.key_bindings.gui_keys.items():
            settings.append({
                "name": self.key_bindings.get_action_description(action),
                "key": action,
                "value": key_code,
                "type": "key"
            })
        
        # Add a reset option
        settings.append({
            "name": "Reset to Defaults",
            "key": "reset",
            "value": None,
            "type": "button"
        })
        
        # Add a save option
        settings.append({
            "name": "Save Changes",
            "key": "save",
            "value": None,
            "type": "button"
        })
        
        # Add a cancel option
        settings.append({
            "name": "Cancel",
            "key": "cancel",
            "value": None,
            "type": "button"
        })
        
        # Variables for menu navigation
        current_selection = 0
        in_menu = True
        
        # Main loop for settings menu
        while in_menu:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            self.game.screen.addstr(0, 0, "3D GUI Key Bindings", self.game.menu_color | curses.A_BOLD)
            self.game.screen.addstr(1, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw instructions
            self.game.screen.addstr(2, 0, "Use ↑/↓ to select, ENTER to edit/activate", self.game.menu_color)
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
                if setting["type"] == "key":
                    key_name = self.key_bindings.get_key_name(setting["value"])
                    self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {key_name}", attr)
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
                if setting["type"] == "key":
                    # Edit key binding
                    new_key = self.edit_key_binding(setting["name"])
                    if new_key is not None:
                        self.key_bindings.gui_keys[setting["key"]] = new_key
                        setting["value"] = new_key
                elif setting["key"] == "reset":
                    # Reset to defaults
                    self.key_bindings.reset_to_defaults()
                    # Update settings list
                    for i, s in enumerate(settings):
                        if s["type"] == "key":
                            s["value"] = self.key_bindings.gui_keys[s["key"]]
                elif setting["key"] == "save":
                    # Save changes
                    self.key_bindings.save_bindings()
                    in_menu = False
                elif setting["key"] == "cancel":
                    # Cancel changes
                    self.key_bindings.gui_keys = original_key_bindings
                    in_menu = False
            elif key == 27:  # Escape key
                # Cancel changes
                self.key_bindings.gui_keys = original_key_bindings
                in_menu = False
        
        # Force redraw
        self.game.needs_redraw = True
        
    def edit_key_binding(self, action_name):
        """Edit a key binding for the 3D GUI."""
        # Variables for editing
        new_key = None
        editing = True
        
        # Main loop for editing
        while editing:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            self.game.screen.addstr(0, 0, f"Edit Key Binding: {action_name}", self.game.menu_color | curses.A_BOLD)
            self.game.screen.addstr(1, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Draw instructions
            self.game.screen.addstr(2, 0, "Press a key to bind it to this action", self.game.menu_color)
            self.game.screen.addstr(3, 0, "Press ESC to cancel", self.game.menu_color)
            self.game.screen.addstr(4, 0, "═" * (self.game.max_x - 1), self.game.menu_color)
            
            # Refresh screen
            self.game.screen.refresh()
            
            # Get input
            key = self.game.screen.getch()
            
            # Handle input
            if key == 27:  # Escape key
                editing = False
            else:
                # Return the new key
                return key
        
        # Return None if cancelled
        return None

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

    def init_font_texture(self):
        """Initialize the font texture."""
        # We'll create a simple texture with ASCII characters
        try:
            # Create a surface with all ASCII characters
            font_size = 32
            font = pygame.font.SysFont('monospace', font_size, bold=True)
            
            # Create textures for each character
            for i in range(32, 127):
                char = chr(i)
                text_surface = font.render(char, True, (255, 255, 255))
                text_data = pygame.image.tostring(text_surface, "RGBA", True)
                
                # Create texture
                texture_id = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, texture_id)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                width, height = text_surface.get_size()
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
                
                # Store the texture ID and dimensions
                self.char_textures[char] = {
                    'id': texture_id,
                    'width': width,
                    'height': height
                }
        except Exception as e:
            self.game.message = f"Font texture error: {e}"
            self.game.message_timeout = 5.0
            
    def draw_vertical_lines(self):
        """Draw vertical lines from ground to character height."""
        try:
            # Disable texturing
            glDisable(GL_TEXTURE_2D)
            
            # Make a copy of the characters dictionary to avoid modification during iteration
            with self.lock:
                characters_copy = dict(self.characters)
                
            # Extend the rendering distance
            render_range = self.render_distance // 2
            
            # Draw all vertical lines first (if enabled)
            if self.show_sticks:
                # Draw vertical lines from ground to character height
                glLineWidth(1.0)
                glBegin(GL_LINES)
                for char_key, char_obj in characters_copy.items():
                    # Skip if the character is too far away
                    if abs(char_obj.x) > render_range or abs(char_obj.y) > render_range:
                        continue
                        
                    # Set color based on height and color scheme
                    color = self.get_color_from_scheme(char_obj.height, self.terrain_color_scheme)
                    glColor3f(*color)
                    
                    # Draw line from ground to character height
                    glVertex3f(char_obj.x, 0, char_obj.y)
                    glVertex3f(char_obj.x, char_obj.height, char_obj.y)
                glEnd()
            
            # Now draw dots at the end of each stick if enabled
            if self.stick_dot_size > 0:
                # Enable point sprites for better dots
                glEnable(GL_POINT_SMOOTH)
                
                # Set point size once before the loop - this is the key fix
                # We'll use the maximum size and adjust color intensity instead
                glPointSize(self.stick_dot_size)
                
                # Draw all dots in a single batch for better performance
                glBegin(GL_POINTS)
                for char_key, char_obj in characters_copy.items():
                    # Skip if the character is too far away
                    if abs(char_obj.x) > render_range or abs(char_obj.y) > render_range:
                        continue
                    
                    # Set color based on height and color scheme
                    color = self.get_color_from_scheme(char_obj.height, self.terrain_color_scheme)
                    
                    # Adjust color intensity based on ASCII value if enabled
                    if self.ascii_intensity and hasattr(char_obj, 'char'):
                        # Get ASCII value and normalize it between 0.3 and 1.0
                        ascii_value = ord(char_obj.char) if char_obj.char else 32
                        intensity = 0.3 + (ascii_value / 255.0) * 0.7
                        
                        # Adjust color intensity instead of point size
                        color = (color[0] * intensity, color[1] * intensity, color[2] * intensity)
                    
                    glColor3f(*color)
                    
                    # Draw dot at the top of the line
                    glVertex3f(char_obj.x, char_obj.height, char_obj.y)
                glEnd()
                
                # Disable point sprites
                glDisable(GL_POINT_SMOOTH)
        except Exception as e:
            # Log the error but don't crash
            self.add_debug_message(f"Error drawing lines: {e}")
    
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
            {"name": "Render Distance", "value": self.render_distance, "type": "int", "min": 10, "max": 200, "step": 10},
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
