import threading
import time
import math
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
from plugins.base import Plugin

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
        super().__init__(game)
        self.window = None
        self.running = False
        self.gui_thread = None
        self.characters = {}  # 3D character objects
        self.rotation_x = 30  # Initial rotation angles
        self.rotation_y = 0
        self.rotation_z = 0
        self.zoom = -15
        self.last_mouse_pos = None
        self.dragging = False
        self.font_texture = None
        self.char_textures = {}
        self.lock = threading.Lock()  # Lock for thread safety
        self.snakes = []  # List to store snake data for connected rendering
        
        # Display options
        self.show_letters = True
        self.show_sticks = True
        self.show_mesh = True
        self.show_terrain_mesh = False  # New option for terrain mesh
        self.terrain_mesh_style = "filled"  # Options: "filled", "wireframe"
        self.terrain_mesh_opacity = 0.7  # 0.0 to 1.0
        self.terrain_color_scheme = "height"  # Options: "height", "viridis", "viridis_inverted", "plasma", "inferno", "magma", "cividis"
        self.stick_dot_size = 8.0  # Size of dots at the end of sticks
        self.show_snake_connections = True  # New option to show snakes as connected balls
        
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
        
    def render(self, screen):
        """Render the plugin on the curses screen.
        
        This method is required by the Plugin base class, but we don't need to
        render anything on the curses screen since we're using a separate window.
        """
        # We don't need to render anything on the curses screen
        # Our rendering happens in the separate PyGame window
        pass
        
    def update_character_map(self):
        """Update the 3D character map from the game world."""
        if not self.active or not self.running:
            return
            
        # Clear existing characters
        with self.lock:
            self.characters = {}
            self.snakes = []  # Clear snake data
        
        # Get visible area dimensions
        max_y, max_x = self.game.max_y, self.game.max_x
        
        # Get the visible area of the game world
        for y in range(max_y):
            for x in range(max_x):
                # Calculate world coordinates
                world_x = x - max_x // 2 + self.game.world_x
                world_y = y - max_y // 2 + self.game.world_y
                
                # Get the character at this position
                char = self.game.get_char_at(world_x, world_y)
                
                # Skip spaces
                if char == ' ':
                    continue
                    
                # Calculate relative coordinates
                rel_x = world_x - self.game.world_x
                rel_y = world_y - self.game.world_y
                
                # Determine color based on character
                color = self.get_color_for_char(char, world_x, world_y)
                
                # Create a 3D character object
                with self.lock:
                    self.characters[(rel_x, rel_y)] = Character3D(char, rel_x, rel_y, color)
        
        # Add snakes if snake plugin is active
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                for snake_idx, snake in enumerate(plugin.snakes):
                    # Create a list to store this snake's segments
                    snake_segments = []
                    
                    for i, (sx, sy) in enumerate(snake.body):
                        # Calculate relative coordinates
                        rel_x = sx - self.game.world_x
                        rel_y = sy - self.game.world_y
                        
                        # Determine color based on segment type
                        if i == 0:
                            color = (0.0, 0.6, 0.0, 1.0)  # Green for head
                        else:
                            color = (0.0, 0.0, 0.6, 1.0)  # Lighter blue for body
                            
                        # Rattles are red
                        if i >= len(snake.body) - snake.rattles:
                            color = (0.8, 0.0, 0.0, 1.0)  # Red for rattles
                        
                        # Create a character object for the snake segment
                        char_obj = Character3D('S', rel_x, rel_y, color)
                        
                        # Add to the characters dictionary
                        with self.lock:
                            char_key = f"{rel_x},{rel_y}"
                            self.characters[char_key] = char_obj
                            
                            # Add to the snake segments list
                            snake_segments.append({
                                'position': (rel_x, rel_y, char_obj.height),
                                'color': color,
                                'type': 'head' if i == 0 else ('rattle' if i >= len(snake.body) - snake.rattles else 'body')
                            })
                    
                    # Add this snake's segments to the snakes list
                    if snake_segments:
                        self.snakes.append(snake_segments)
        
        # Add player character at center (0,0)
        with self.lock:
            self.characters[(0, 0)] = Character3D('X', 0, 0, (1.0, 0.0, 0.0, 1.0))
        
        # Add remote players if networking is active
        for plugin in self.game.plugins:
            if hasattr(plugin, 'players') and plugin.active:
                for player in plugin.players.values():
                    # Convert to relative coordinates
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
    
    def run_gui(self):
        """Run the GUI in a separate thread."""
        try:
            # Initialize Pygame
            pygame.init()
            
            # Create a window
            display = (800, 600)
            pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
            pygame.display.set_caption("TextWarp 3D Visualization")
            
            # Set up the OpenGL environment
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Set up the perspective
            glMatrixMode(GL_PROJECTION)
            gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
            
            # Initialize font texture
            self.init_font_texture()
            
            # Main loop
            clock = pygame.time.Clock()
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left mouse button
                            self.dragging = True
                            self.last_mouse_pos = pygame.mouse.get_pos()
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:  # Left mouse button
                            self.dragging = False
                    elif event.type == pygame.MOUSEMOTION:
                        if self.dragging and self.last_mouse_pos:
                            x, y = pygame.mouse.get_pos()
                            dx = x - self.last_mouse_pos[0]
                            dy = y - self.last_mouse_pos[1]
                            self.rotation_y += dx * 0.5
                            self.rotation_x += dy * 0.5
                            self.last_mouse_pos = (x, y)
                    elif event.type == pygame.MOUSEWHEEL:
                        self.zoom += event.y
                        
                # Clear the screen
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                
                # Reset the modelview matrix
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                
                # Apply zoom
                glTranslatef(0, 0, self.zoom)
                
                # Apply rotation
                glRotatef(self.rotation_x, 1, 0, 0)
                glRotatef(self.rotation_y, 0, 1, 0)
                glRotatef(self.rotation_z, 0, 0, 1)
                
                # Draw coordinate axes
                self.draw_axes()
                
                # Draw ground plane
                if self.show_mesh:
                    self.draw_ground_plane()
                
                # Draw terrain mesh if enabled
                if self.show_terrain_mesh:
                    self.draw_terrain_mesh()
                
                # Draw vertical lines (sticks) from ground to character height
                if self.show_sticks:
                    self.draw_vertical_lines()
                
                # Draw characters
                if self.show_letters:
                    self.draw_characters()
                
                # Draw snakes as connected balls if enabled
                if self.show_snake_connections:
                    self.draw_connected_snakes()
                
                # Update the display
                pygame.display.flip()
                
                # Cap the frame rate
                clock.tick(60)
                
        except Exception as e:
            self.game.message = f"3D GUI error: {e}"
            self.game.message_timeout = 5.0
        finally:
            pygame.quit()
            
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
        # Disable texturing
        glDisable(GL_TEXTURE_2D)
        
        # Make a copy of the characters dictionary to avoid modification during iteration
        with self.lock:
            characters_copy = dict(self.characters)
        
        # Draw vertical lines from ground to character height
        glBegin(GL_LINES)
        for char_key, char_obj in characters_copy.items():
            # Get color based on height and selected color scheme
            rgb = self.get_color_from_scheme(char_obj.height, self.terrain_color_scheme)
            
            # Set color for the line
            glColor3f(*rgb)
            
            # Draw line from ground to character height
            glVertex3f(char_obj.x, 0, char_obj.y)  # Ground point
            glVertex3f(char_obj.x, char_obj.height, char_obj.y)  # Character height point
        
        glEnd()
        
        # Draw 3D dots at the end of each stick
        for char_key, char_obj in characters_copy.items():
            # Get color based on height and selected color scheme
            rgb = self.get_color_from_scheme(char_obj.height, self.terrain_color_scheme)
            
            # Calculate dot size (half the width/height of the square)
            dot_size = self.stick_dot_size / 20.0  # Scale down to appropriate size
            
            # Save current matrix
            glPushMatrix()
            
            # Position at the top of the stick
            glTranslatef(char_obj.x, char_obj.height, char_obj.y)
            
            # Always face the camera (billboarding)
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            
            # Extract the rotation from the modelview matrix
            camera_right = [modelview[0][0], modelview[1][0], modelview[2][0]]
            camera_up = [modelview[0][1], modelview[1][1], modelview[2][1]]
            
            # Set color for the dot
            glColor3f(*rgb)
            
            # Draw a small quad at the top of the stick
            glBegin(GL_QUADS)
            glVertex3f(-dot_size, -dot_size, 0)
            glVertex3f(dot_size, -dot_size, 0)
            glVertex3f(dot_size, dot_size, 0)
            glVertex3f(-dot_size, dot_size, 0)
            glEnd()
            
            # Restore matrix
            glPopMatrix()
        
        # Re-enable texturing
        glEnable(GL_TEXTURE_2D)
    
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
        
    def draw_connected_snakes(self):
        """Draw snakes as balls connected by lines."""
        if not self.show_snake_connections or not self.snakes:
            return
            
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Draw each snake
        for snake in self.snakes:
            if len(snake) < 2:
                continue  # Need at least 2 segments to draw connections
                
            # Draw the connecting lines first (behind the balls)
            glLineWidth(3.0)  # Thicker lines
            glBegin(GL_LINE_STRIP)
            
            for segment in snake:
                pos = segment['position']
                color = segment['color']
                # Make the line slightly transparent
                glColor4f(color[0], color[1], color[2], 0.7)
                glVertex3f(pos[0], pos[2], pos[1])  # Note: Y is up in OpenGL
                
            glEnd()
            
            # Now draw the balls (spheres) for each segment
            for segment in snake:
                pos = segment['position']
                color = segment['color']
                segment_type = segment['type']
                
                # Push matrix for this segment
                glPushMatrix()
                
                # Position the sphere
                glTranslatef(pos[0], pos[2], pos[1])  # Note: Y is up in OpenGL
                
                # Set color
                glColor4f(color[0], color[1], color[2], 1.0)
                
                # Draw a sphere with appropriate size based on segment type
                if segment_type == 'head':
                    radius = 0.3  # Larger head
                elif segment_type == 'rattle':
                    radius = 0.25  # Medium rattles
                else:
                    radius = 0.2  # Smaller body segments
                    
                # Create a sphere quadric object
                quadric = gluNewQuadric()
                gluQuadricDrawStyle(quadric, GLU_FILL)
                gluQuadricNormals(quadric, GLU_SMOOTH)
                gluSphere(quadric, radius, 16, 16)  # Draw the sphere
                gluDeleteQuadric(quadric)
                
                glPopMatrix()
                
        # Disable blending
        glDisable(GL_BLEND)
    
    def draw_terrain_mesh(self):
        """Draw a mesh connecting the tips of the sticks to visualize the terrain surface."""
        # Disable texturing
        glDisable(GL_TEXTURE_2D)
        
        # Make a copy of the characters dictionary to avoid modification during iteration
        with self.lock:
            characters_copy = dict(self.characters)
        
        # Create a grid of points for the terrain mesh
        grid_size = 50  # Same as ground plane grid size
        grid_points = {}
        
        # First, collect all character positions and heights
        for char_key, char_obj in characters_copy.items():
            # Convert to grid coordinates (rounded to nearest integer)
            grid_x = round(char_obj.x)
            grid_z = round(char_obj.y)  # y in world is z in OpenGL
            
            # Store the height at this grid point
            grid_key = f"{grid_x},{grid_z}"
            grid_points[grid_key] = char_obj.height
        
        # Set rendering mode based on style
        if self.terrain_mesh_style == "wireframe":
            # Draw wireframe (lines only)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            # Make lines thicker for better visibility
            glLineWidth(2.0)
        else:
            # Draw filled triangles (default)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            
            # Enable blending for transparency
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Draw triangles to connect adjacent grid points
        glBegin(GL_TRIANGLES)
        
        # Iterate through the grid
        for x in range(-grid_size, grid_size):
            for z in range(-grid_size, grid_size):
                # Check if we have all four corners of a grid cell
                corners = [
                    (x, z),       # Bottom-left
                    (x+1, z),     # Bottom-right
                    (x, z+1),     # Top-left
                    (x+1, z+1)    # Top-right
                ]
                
                # Get heights for each corner
                heights = []
                corner_positions = []
                for cx, cz in corners:
                    grid_key = f"{cx},{cz}"
                    if grid_key in grid_points:
                        # Use the actual height from the character
                        heights.append(grid_points[grid_key])
                    else:
                        # Use interpolated height or zero if no data
                        # Try to interpolate from neighboring points
                        neighbor_heights = []
                        for dx in [-1, 0, 1]:
                            for dz in [-1, 0, 1]:
                                if dx == 0 and dz == 0:
                                    continue
                                neighbor_key = f"{cx+dx},{cz+dz}"
                                if neighbor_key in grid_points:
                                    neighbor_heights.append(grid_points[neighbor_key])
                        
                        if neighbor_heights:
                            # Use average of neighboring heights
                            heights.append(sum(neighbor_heights) / len(neighbor_heights))
                        else:
                            # No neighbors, use zero
                            heights.append(0)
                    
                    corner_positions.append((cx, cz))
                
                # Only draw triangles if we have valid heights for all corners
                if len(heights) == 4:
                    # Calculate the midpoint position and height (average of the four corners)
                    mid_x = (corners[0][0] + corners[1][0] + corners[2][0] + corners[3][0]) / 4
                    mid_z = (corners[0][1] + corners[1][1] + corners[2][1] + corners[3][1]) / 4
                    mid_height = sum(heights) / 4
                    
                    # Calculate colors for all points including the midpoint
                    colors = []
                    for h in heights + [mid_height]:  # Add midpoint height
                        # Get RGB color based on height and color scheme
                        rgb = self.get_color_from_scheme(h, self.terrain_color_scheme)
                        
                        # Adjust alpha for wireframe mode
                        if self.terrain_mesh_style == "wireframe":
                            colors.append((*rgb, 1.0))  # Solid lines
                        else:
                            colors.append((*rgb, self.terrain_mesh_opacity))  # User-controlled transparency
                    
                    # Draw four triangles connecting each corner to the midpoint
                    if self.terrain_mesh_style == "filled":
                        # Use RGBA for filled mode with transparency
                        # Triangle 1: Bottom-left to midpoint to Bottom-right
                        glColor4f(*colors[0])
                        glVertex3f(corners[0][0], heights[0], corners[0][1])
                        
                        glColor4f(*colors[4])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor4f(*colors[1])
                        glVertex3f(corners[1][0], heights[1], corners[1][1])
                        
                        # Triangle 2: Bottom-right to midpoint to Top-right
                        glColor4f(*colors[1])
                        glVertex3f(corners[1][0], heights[1], corners[1][1])
                        
                        glColor4f(*colors[4])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor4f(*colors[3])
                        glVertex3f(corners[3][0], heights[3], corners[3][1])
                        
                        # Triangle 3: Top-right to midpoint to Top-left
                        glColor4f(*colors[3])
                        glVertex3f(corners[3][0], heights[3], corners[3][1])
                        
                        glColor4f(*colors[4])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor4f(*colors[2])
                        glVertex3f(corners[2][0], heights[2], corners[2][1])
                        
                        # Triangle 4: Top-left to midpoint to Bottom-left
                        glColor4f(*colors[2])
                        glVertex3f(corners[2][0], heights[2], corners[2][1])
                        
                        glColor4f(*colors[4])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor4f(*colors[0])
                        glVertex3f(corners[0][0], heights[0], corners[0][1])
                    else:
                        # Use RGB for wireframe mode (no transparency)
                        # Triangle 1: Bottom-left to midpoint to Bottom-right
                        glColor3f(*colors[0][:3])
                        glVertex3f(corners[0][0], heights[0], corners[0][1])
                        
                        glColor3f(*colors[4][:3])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor3f(*colors[1][:3])
                        glVertex3f(corners[1][0], heights[1], corners[1][1])
                        
                        # Triangle 2: Bottom-right to midpoint to Top-right
                        glColor3f(*colors[1][:3])
                        glVertex3f(corners[1][0], heights[1], corners[1][1])
                        
                        glColor3f(*colors[4][:3])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor3f(*colors[3][:3])
                        glVertex3f(corners[3][0], heights[3], corners[3][1])
                        
                        # Triangle 3: Top-right to midpoint to Top-left
                        glColor3f(*colors[3][:3])
                        glVertex3f(corners[3][0], heights[3], corners[3][1])
                        
                        glColor3f(*colors[4][:3])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor3f(*colors[2][:3])
                        glVertex3f(corners[2][0], heights[2], corners[2][1])
                        
                        # Triangle 4: Top-left to midpoint to Bottom-left
                        glColor3f(*colors[2][:3])
                        glVertex3f(corners[2][0], heights[2], corners[2][1])
                        
                        glColor3f(*colors[4][:3])  # Midpoint color
                        glVertex3f(mid_x, mid_height, mid_z)
                        
                        glColor3f(*colors[0][:3])
                        glVertex3f(corners[0][0], heights[0], corners[0][1])
        
        glEnd()
        
        # Reset polygon mode to filled for other rendering
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        # Reset line width
        glLineWidth(1.0)
        # Disable blending
        glDisable(GL_BLEND)
    
    def draw_ground_plane(self):
        """Draw the ground plane."""
        # Draw a grid on the ground plane
        glDisable(GL_TEXTURE_2D)
        glBegin(GL_LINES)
        
        # Set grid color (dark gray)
        glColor3f(0.2, 0.2, 0.2)
        
        # Draw grid lines
        grid_size = 50
        for i in range(-grid_size, grid_size + 1, 1):
            # X axis lines
            glVertex3f(i, 0, -grid_size)
            glVertex3f(i, 0, grid_size)
            
            # Z axis lines
            glVertex3f(-grid_size, 0, i)
            glVertex3f(grid_size, 0, i)
        
        glEnd()
        
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
        
    def draw_axes(self):
        """Draw coordinate axes for better orientation."""
        glDisable(GL_TEXTURE_2D)
        glBegin(GL_LINES)
        
        # X-axis (red)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(10, 0, 0)
        
        # Y-axis (green)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 10, 0)
        
        # Z-axis (blue)
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 10)
        
        glEnd()
        glEnable(GL_TEXTURE_2D)
    
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
                self.show_mesh = settings.get("show_mesh", True)
                self.show_terrain_mesh = settings.get("show_terrain_mesh", False)
                self.terrain_mesh_style = settings.get("terrain_mesh_style", "filled")
                self.terrain_mesh_opacity = settings.get("terrain_mesh_opacity", 0.7)
                self.terrain_color_scheme = settings.get("terrain_color_scheme", "height")
                self.stick_dot_size = settings.get("stick_dot_size", 8.0)
                self.show_snake_connections = settings.get("show_snake_connections", True)
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
                    "show_mesh": self.show_mesh,
                    "show_terrain_mesh": self.show_terrain_mesh,
                    "terrain_mesh_style": self.terrain_mesh_style,
                    "terrain_mesh_opacity": self.terrain_mesh_opacity,
                    "terrain_color_scheme": self.terrain_color_scheme,
                    "stick_dot_size": self.stick_dot_size,
                    "show_snake_connections": self.show_snake_connections
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
        original_show_mesh = self.show_mesh
        original_show_terrain_mesh = self.show_terrain_mesh
        original_terrain_mesh_style = self.terrain_mesh_style
        original_terrain_mesh_opacity = self.terrain_mesh_opacity
        original_terrain_color_scheme = self.terrain_color_scheme
        original_stick_dot_size = self.stick_dot_size
        original_show_snake_connections = self.show_snake_connections
        
        # Variables for menu navigation
        current_selection = 0
        in_settings_menu = True
        
        # Create settings list
        settings = [
            {"name": "Show Letters", "value": self.show_letters, "type": "bool"},
            {"name": "Show Sticks", "value": self.show_sticks, "type": "bool"},
            {"name": "Show Mesh", "value": self.show_mesh, "type": "bool"},
            {"name": "Show Terrain Mesh", "value": self.show_terrain_mesh, "type": "bool"},
            {"name": "Terrain Mesh Style", "value": self.terrain_mesh_style, "type": "str"},
            {"name": "Terrain Mesh Opacity", "value": self.terrain_mesh_opacity, "type": "float"},
            {"name": "Terrain Color Scheme", "value": self.terrain_color_scheme, "type": "str"},
            {"name": "Stick Dot Size", "value": self.stick_dot_size, "type": "float"},
            {"name": "Show Snake Connections", "value": self.show_snake_connections, "type": "bool"}
        ]
        
        # Get curses module from the game
        curses = self.game.curses
        self.game.in_menu = True
        self.game.needs_redraw = True
        
        # Main loop for settings menu
        while in_settings_menu and self.game.running:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            self.game.screen.addstr(1, 2, "3D Visualization Settings", curses.A_BOLD)
            self.game.screen.addstr(3, 2, "Use UP/DOWN to navigate, SPACE to toggle/change, ENTER to save, ESC to cancel")
            self.game.screen.addstr(4, 2, "Press 'R' to reset all settings to defaults")
            
            # Draw settings
            for i, setting in enumerate(settings):
                # Highlight the selected item
                if i == current_selection:
                    attr = curses.A_REVERSE | curses.A_BOLD
                else:
                    attr = 0
                    
                # Format the value display
                if setting["type"] == "bool":
                    value_display = "ON" if setting["value"] else "OFF"
                elif setting["type"] == "float":
                    value_display = f"{setting['value']:.1f}"
                else:
                    value_display = setting["value"]
                    
                # Draw the setting
                self.game.screen.addstr(6 + i, 4, setting["name"], attr)
                self.game.screen.addstr(6 + i, 30, value_display, attr)
                
            # Refresh the screen
            self.game.screen.refresh()
            
            # Get user input
            key = self.game.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(settings)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(settings)
            elif key == ord(' '):  # Space key
                # Toggle boolean value or cycle through string options
                if settings[current_selection]["type"] == "bool":
                    settings[current_selection]["value"] = not settings[current_selection]["value"]
                elif settings[current_selection]["type"] == "str" and settings[current_selection]["name"] == "Terrain Mesh Style":
                    # Cycle through mesh style options
                    if settings[current_selection]["value"] == "filled":
                        settings[current_selection]["value"] = "wireframe"
                    else:
                        settings[current_selection]["value"] = "filled"
                elif settings[current_selection]["type"] == "str" and settings[current_selection]["name"] == "Terrain Color Scheme":
                    # Cycle through color scheme options
                    if settings[current_selection]["value"] == "height":
                        settings[current_selection]["value"] = "viridis"
                    elif settings[current_selection]["value"] == "viridis":
                        settings[current_selection]["value"] = "viridis_inverted"
                    elif settings[current_selection]["value"] == "viridis_inverted":
                        settings[current_selection]["value"] = "plasma"
                    elif settings[current_selection]["value"] == "plasma":
                        settings[current_selection]["value"] = "inferno"
                    elif settings[current_selection]["value"] == "inferno":
                        settings[current_selection]["value"] = "magma"
                    elif settings[current_selection]["value"] == "magma":
                        settings[current_selection]["value"] = "cividis"
                    else:
                        settings[current_selection]["value"] = "height"
                elif settings[current_selection]["type"] == "float":
                    # Adjust opacity value
                    if settings[current_selection]["value"] < 10.0:
                        settings[current_selection]["value"] += 0.1
                    else:
                        settings[current_selection]["value"] = 0.0
            elif key == ord('r') or key == ord('R'):
                # Reset to defaults
                for setting in settings:
                    if setting["type"] == "bool":
                        setting["value"] = True
                    elif setting["type"] == "str" and setting["name"] == "Terrain Mesh Style":
                        setting["value"] = "filled"
                    elif setting["type"] == "str" and setting["name"] == "Terrain Color Scheme":
                        setting["value"] = "height"
                    elif setting["type"] == "float":
                        setting["value"] = 8.0 if setting["name"] == "Stick Dot Size" else 0.7
            elif key == 10:  # Enter key
                # Apply changes
                self.show_letters = settings[0]["value"]
                self.show_sticks = settings[1]["value"]
                self.show_mesh = settings[2]["value"]
                self.show_terrain_mesh = settings[3]["value"]
                self.terrain_mesh_style = settings[4]["value"]
                self.terrain_mesh_opacity = settings[5]["value"]
                self.terrain_color_scheme = settings[6]["value"]
                self.stick_dot_size = settings[7]["value"]
                self.show_snake_connections = settings[8]["value"]
                
                # Save settings
                self.save_settings()
                
                # Exit menu
                in_settings_menu = False
            elif key == 27:  # Escape key
                # Restore original settings
                self.show_letters = original_show_letters
                self.show_sticks = original_show_sticks
                self.show_mesh = original_show_mesh
                self.show_terrain_mesh = original_show_terrain_mesh
                self.terrain_mesh_style = original_terrain_mesh_style
                self.terrain_mesh_opacity = original_terrain_mesh_opacity
                self.terrain_color_scheme = original_terrain_color_scheme
                self.stick_dot_size = original_stick_dot_size
                self.show_snake_connections = original_show_snake_connections
                
                # Exit without saving
                in_settings_menu = False
        
        # Restore game state
        self.game.in_menu = True
        self.game.needs_redraw = True
