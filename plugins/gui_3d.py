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
    
    def __init__(self, char, x, y, color=(1.0, 1.0, 1.0, 1.0)):
        self.char = char
        self.x = x
        self.y = y
        self.z = 0
        self.color = color
        self.height = self.calculate_height()
        
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
                    
                # Determine color based on character
                color = self.get_color_for_char(char, world_x, world_y)
                
                # Create 3D character - use relative coordinates to keep player at center
                with self.lock:
                    self.characters[(world_x, world_y)] = Character3D(
                        char, 
                        world_x - self.game.world_x,  # Relative X position
                        world_y - self.game.world_y,  # Relative Y position
                        color
                    )
        
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
                    
        # Add snakes if snake plugin is active
        for plugin in self.game.plugins:
            if hasattr(plugin, 'snakes') and plugin.active:
                for snake in plugin.snakes:
                    for i, (sx, sy) in enumerate(snake.body):
                        # Convert to relative coordinates
                        rel_x = sx + self.game.world_x - self.game.world_x  # Simplifies to sx
                        rel_y = sy + self.game.world_y - self.game.world_y  # Simplifies to sy
                        
                        # Head is different color than body
                        if i == 0:
                            color = (0.0, 0.0, 0.8, 1.0)  # Dark blue for head
                        else:
                            color = (0.0, 0.0, 0.6, 1.0)  # Lighter blue for body
                            
                        # Rattles are red
                        if i >= len(snake.body) - snake.rattles:
                            color = (0.8, 0.0, 0.0, 1.0)  # Red for rattles
                            
                        with self.lock:
                            self.characters[(rel_x, rel_y)] = Character3D('S', rel_x, rel_y, color)
    
    def get_color_for_char(self, char, x, y):
        """Get the color for a character."""
        if char == 'X':  # Player
            return (1.0, 0.0, 0.0, 1.0)  # Red
        elif char == '@':  # Plants
            return (0.0, 0.8, 0.0, 1.0)  # Green
        elif char == '0':  # Eggs
            return (1.0, 1.0, 0.0, 1.0)  # Yellow
        elif char == '&':  # Fuel
            return (0.0, 1.0, 1.0, 1.0)  # Cyan
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
                
                # Draw the ground plane
                self.draw_ground_plane()
                
                # Draw all characters
                self.draw_characters()
                
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
            
    def draw_ground_plane(self):
        """Draw the ground plane."""
        # Draw a grid to represent the ground
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
        
        # Draw a special marker at the center (0,0) to indicate player position
        glBegin(GL_LINES)
        glColor3f(1.0, 0.0, 0.0)  # Red
        
        # X marker
        marker_size = 0.5
        glVertex3f(-marker_size, 0, -marker_size)
        glVertex3f(marker_size, 0, marker_size)
        glVertex3f(-marker_size, 0, marker_size)
        glVertex3f(marker_size, 0, -marker_size)
        
        glEnd()
        
    def draw_characters(self):
        """Draw all characters in the 3D world."""
        # Enable texturing
        glEnable(GL_TEXTURE_2D)
        
        # Make a copy of the characters dictionary to avoid modification during iteration
        with self.lock:
            characters_copy = dict(self.characters)
        
        for char_obj in characters_copy.values():
            # Set character position
            glPushMatrix()
            glTranslatef(char_obj.x, char_obj.height / 2, char_obj.y)  # Y is up in OpenGL
            
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
                quad_height = 1.0
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
                self.draw_cube(0.5)
                
            glPopMatrix()
            
        # Disable texturing
        glDisable(GL_TEXTURE_2D)
        
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
