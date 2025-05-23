import math
import random
import numpy as np
from plugins.base import Plugin
from plugins.graph_classifier import GraphClassifier
from plugins.gui_3d import Character3D

class Polygraph3DClassifier(GraphClassifier):
    """
    A 3D polygraph classifier that extends the GraphClassifier.
    In addition to ASCII characters, it also generates height values for 3D visualization.
    """
    
    def __init__(self, seed=42):
        """Initialize the 3D polygraph classifier."""
        super().__init__(seed)
        
        # Additional classifiers for height generation
        self.height_classifiers = [
            self.perlin_height_classifier,
            self.sine_wave_height_classifier,
            self.voronoi_height_classifier,
            self.fractal_height_classifier,
            self.terrain_height_classifier
        ]
        
        # Precompute terrain parameters with more dramatic features
        self.terrain_params = {
            'mountains': [(random.randint(-500, 500), random.randint(-500, 500), 
                          random.randint(50, 200), random.random() * 8 + 8) 
                         for _ in range(15)],  # More mountains with higher peaks
            'valleys': [(random.randint(-500, 500), random.randint(-500, 500), 
                        random.randint(50, 200), random.random() * 6 + 4) 
                       for _ in range(8)],  # Deeper valleys
            'plateaus': [(random.randint(-500, 500), random.randint(-500, 500), 
                         random.randint(100, 300), random.random() * 5 + 3,
                         random.random() * 5 + 2) 
                        for _ in range(5)],  # More pronounced plateaus
            'ridges': [(random.randint(-500, 500), random.randint(-500, 500), 
                       random.randint(100, 500), random.randint(10, 50), 
                       random.randint(0, 360), random.random() * 8 + 8) 
                      for _ in range(5)],  # Add ridges
            'canyons': [(random.randint(-500, 500), random.randint(-500, 500), 
                        random.randint(100, 500), random.randint(10, 50), 
                        random.randint(0, 360), random.random() * 6 + 4) 
                       for _ in range(5)]  # Add canyons
        }
    
    def get_height(self, x, y):
        """
        Get the height value for coordinates (x, y).
        The height range is determined by the plugin settings.
        """
        # Determine which region the point belongs to
        region_idx = self.get_region(x, y)
        
        # Use the appropriate height classifier for this region
        classifier = self.height_classifiers[region_idx % len(self.height_classifiers)]
        height_value = classifier(x, y)
        
        # The raw height value is in the range [-10, 10]
        # We'll let the plugin scale this to the desired min/max height
        return height_value
    
    def perlin_height_classifier(self, x, y):
        """Generate height based on Perlin noise."""
        # Scale down coordinates more for height to create smoother terrain
        x, y = x / 50.0, y / 50.0  # Reduced scale factor for more dramatic changes
        
        # Get grid cell coordinates
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        x1, y1 = x0 + 1, y0 + 1
        
        # Get interpolation weights
        sx = x - x0
        sy = y - y0
        
        # Interpolate between grid point gradients
        n0 = self.dot_grid_gradient(x0, y0, x, y)
        n1 = self.dot_grid_gradient(x1, y0, x, y)
        ix0 = self.interpolate(n0, n1, sx)
        
        n0 = self.dot_grid_gradient(x0, y1, x, y)
        n1 = self.dot_grid_gradient(x1, y1, x, y)
        ix1 = self.interpolate(n0, n1, sy)
        
        value = self.interpolate(ix0, ix1, sy)
        
        # Scale to -10 to 10 range with more dramatic peaks and valleys
        return value * 20  # Increased multiplier for more dramatic height changes
    
    def sine_wave_height_classifier(self, x, y):
        """Generate height based on sine waves."""
        value = (
            math.sin(x / 40.0) * 1.5 +  # Increased amplitude
            math.sin(y / 30.0) * 1.5 +  # Increased amplitude
            math.sin((x + y) / 50.0) * 2.0 +  # Increased amplitude
            math.sin(math.sqrt(x*x + y*y) / 25.0) * 2.0  # Increased amplitude
        )
        
        # Scale to -10 to 10 range
        return value * 3.0  # Increased multiplier
    
    def voronoi_height_classifier(self, x, y):
        """Generate height based on Voronoi diagrams."""
        # Find the two closest Voronoi points
        distances = []
        
        for px, py in self.voronoi_points:
            dist = math.sqrt((x - px)**2 + (y - py)**2)
            distances.append(dist)
            
        # Sort distances
        distances.sort()
        
        # Use the difference between the two closest points
        if len(distances) >= 2:
            # Create sharper ridges along Voronoi edges
            value = math.exp(-abs(distances[1] - distances[0]) / 5.0) * 30 - 15
        else:
            value = 0
            
        return value
    
    def fractal_height_classifier(self, x, y):
        """Generate height based on fractal patterns."""
        # Scale coordinates
        scaled_x = x / 250.0
        scaled_y = y / 250.0
        
        # Initialize complex number
        c = complex(scaled_x, scaled_y)
        z = complex(0, 0)
        
        # Iterate
        iteration = 0
        max_iter = 20
        
        while abs(z) < 2 and iteration < max_iter:
            z = z*z + c
            iteration += 1
            
        # Map iteration count to a height value with more dramatic differences
        if iteration < max_iter:
            # Create taller mountains at the edges of the fractal
            value = (iteration / max_iter) * 30 - 15
        else:
            # Create deeper valleys inside the fractal
            value = -8
            
        return value
    
    def terrain_height_classifier(self, x, y):
        """Generate height based on realistic terrain features."""
        height = 0
        
        # Add mountains (bell curves)
        for mx, my, size, height_factor in self.terrain_params['mountains']:
            dist = math.sqrt((x - mx)**2 + (y - my)**2)
            if dist < size * 3:
                # Bell curve formula with sharper peaks
                mountain_height = height_factor * math.exp(-(dist**2) / (1.5 * size**2))
                height += mountain_height
        
        # Add valleys (inverted bell curves)
        for vx, vy, size, depth_factor in self.terrain_params['valleys']:
            dist = math.sqrt((x - vx)**2 + (y - vy)**2)
            if dist < size * 3:
                # Inverted bell curve with deeper valleys
                valley_depth = -depth_factor * math.exp(-(dist**2) / (1.5 * size**2))
                height += valley_depth
        
        # Add plateaus (sigmoid function)
        for px, py, size, height_factor, sharpness in self.terrain_params['plateaus']:
            dist = math.sqrt((x - px)**2 + (y - py)**2)
            if dist < size * 2:
                # Sigmoid function for sharper edges
                plateau_height = height_factor / (1 + math.exp(sharpness * 1.5 * (dist - size)))
                height += plateau_height
        
        # Add ridges (elongated mountains along a direction)
        for rx, ry, length, width, angle, height_factor in self.terrain_params['ridges']:
            # Calculate distance to the ridge line
            # Rotate the point around the ridge center
            angle_rad = math.radians(angle)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            
            # Translate to ridge center
            tx = x - rx
            ty = y - ry
            
            # Rotate
            rx_rot = tx * cos_angle + ty * sin_angle
            ry_rot = -tx * sin_angle + ty * cos_angle
            
            # Check if within ridge length
            if abs(rx_rot) < length / 2:
                # Calculate distance to ridge line
                dist = abs(ry_rot)
                if dist < width:
                    # Bell curve for the ridge
                    ridge_height = height_factor * math.exp(-(dist**2) / (0.5 * width**2))
                    height += ridge_height
        
        # Add canyons (elongated valleys)
        for cx, cy, length, width, angle, depth_factor in self.terrain_params['canyons']:
            # Calculate distance to the canyon line
            # Rotate the point around the canyon center
            angle_rad = math.radians(angle)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            
            # Translate to canyon center
            tx = x - cx
            ty = y - cy
            
            # Rotate
            cx_rot = tx * cos_angle + ty * sin_angle
            cy_rot = -tx * sin_angle + ty * cos_angle
            
            # Check if within canyon length
            if abs(cx_rot) < length / 2:
                # Calculate distance to canyon line
                dist = abs(cy_rot)
                if dist < width:
                    # Inverted bell curve for the canyon
                    canyon_depth = -depth_factor * math.exp(-(dist**2) / (0.5 * width**2))
                    height += canyon_depth
        
        # Add some small-scale noise for texture
        noise = (math.sin(x/8) * math.cos(y/8)) * 1.0
        height += noise
        
        # Ensure the height is in the range [-10, 10] but allow for more extreme values
        return max(-10, min(10, height))


class Polygraph3DPlugin(Plugin):
    """
    A plugin that uses the Polygraph3DClassifier to generate the game world with height values.
    This enhances the 3D visualization while keeping the classic text UI unchanged.
    """
    
    def __init__(self, game):
        super().__init__(game)
        self.classifier = Polygraph3DClassifier()
        self.original_get_char = None
        self.height_map = {}  # Cache for height values
        
        # Height settings
        self.min_height = -10
        self.max_height = 10
        self.height_scale = 4.0  # Divisor for height scaling (smaller = more dramatic)
        
        # Load settings if they exist
        self.load_settings()
    
    @property
    def name(self):
        """Return the name of the plugin."""
        return "3D Polygraph"
        
    def update(self, dt):
        """Update the plugin state."""
        if not self.active:
            return
            
        # Update the height cache when player moves
        self.update_char_cache()
        
        # Find and update the GUI3D plugin if needed
        for plugin in self.game.plugins:
            if plugin.__class__.__name__ == "GUI3DPlugin" and plugin.active:
                # Make sure the GUI3D plugin is using our height values
                if not hasattr(plugin, 'using_polygraph_heights'):
                    self.integrate_with_gui3d(plugin)
                    plugin.using_polygraph_heights = True
    
    def render(self, screen):
        """No additional rendering needed for the text UI."""
        pass
    
    def get_height(self, x, y):
        """Get the height value for coordinates (x, y)."""
        # Convert coordinates to integers if they are floats
        if isinstance(x, float):
            x = int(round(x))
        if isinstance(y, float):
            y = int(round(y))
            
        # Check if the height is already cached
        key = f"{x},{y}"
        if key in self.height_map:
            return self.height_map[key]

        # Generate height using the classifier
        raw_height = self.classifier.get_height(x, y)
        
        # Scale the raw height (which is in range [-10, 10]) to our min/max height settings
        # First normalize to [0, 1] range
        normalized_height = (raw_height + 10) / 20.0
        
        # Then scale to our desired range
        height = self.min_height + normalized_height * (self.max_height - self.min_height)
        
        # Add a small deterministic variation based on coordinates to ensure
        # no two adjacent positions have exactly the same height
        # Use a hash of the coordinates to get a consistent but varied value
        variation = (hash(key) % 1000) / 2000.0 - 0.25  # Range: -0.25 to 0.25
        height += variation
        
        # Cache the height
        self.height_map[key] = height

        return height
    
    def clear_height_cache(self):
        """Clear the height cache when the player moves significantly."""
        self.height_map = {}
    
    def update_char_cache(self):
        """Update the character cache when the player moves significantly."""
        # Check if player has moved more than 10 units
        player_x = self.game.world_x
        player_y = self.game.world_y
        
        if (hasattr(self, 'last_player_x') and hasattr(self, 'last_player_y') and
            (abs(player_x - self.last_player_x) > 10 or abs(player_y - self.last_player_y) > 10)):
            self.height_map = {}
            self.last_player_x = player_x
            self.last_player_y = player_y
        elif not hasattr(self, 'last_player_x') or not hasattr(self, 'last_player_y'):
            self.last_player_x = player_x
            self.last_player_y = player_y
    
    def integrate_with_gui3d(self, gui_plugin):
        """Integrate with the GUI3D plugin to provide height values."""
        if not gui_plugin or not hasattr(gui_plugin, 'update_character_map'):
            return False
            
        # Store a reference to the plugin for use in the method
        self.gui_plugin_ref = gui_plugin
        
        # Store the original update_character_map method for later restoration
        if not hasattr(gui_plugin, 'original_update_character_map'):
            gui_plugin.original_update_character_map = gui_plugin.update_character_map
            
        # Define a new update_character_map method that uses our height values
        def new_update_character_map(self_gui):
            """Update the 3D character map from the game world."""
            if not self_gui.active or not self_gui.running:
                return
                
            # Clear existing characters
            with self_gui.lock:
                self_gui.characters = {}
            
            # Get visible area dimensions
            max_y, max_x = self_gui.game.max_y, self_gui.game.max_x
            
            # First, update the height map with the visible area
            for y in range(max_y):
                for x in range(max_x):
                    # Calculate world coordinates
                    world_x = x - max_x // 2 + self_gui.game.world_x
                    world_y = y - max_y // 2 + self_gui.game.world_y
                    
                    # Get the character at this position
                    char = self_gui.game.get_char_at(world_x, world_y)
                    
                    # Skip spaces
                    if char == ' ':
                        continue
                        
                    # Get the height from our plugin (this updates the cache)
                    self.get_height(world_x, world_y)
            
            # Create a copy of the height map to avoid modification during iteration
            height_map_copy = dict(self.height_map)
            
            # Now visualize all cached terrain points, not just the visible area
            for key, height in height_map_copy.items():
                try:
                    # Parse the coordinates from the key
                    # Handle floating-point coordinates by converting to float first, then to int
                    coords = key.split(',')
                    world_x = int(float(coords[0]))
                    world_y = int(float(coords[1]))
                    
                    # Get the character at this position
                    char = self_gui.game.get_char_at(world_x, world_y)
                    
                    # If there's no character (e.g., it's outside the loaded area), use a default
                    if char == ' ':
                        char = '.'  # Use a dot to represent terrain without a character
                    
                    # Determine color based on character
                    color = self_gui.get_color_for_char(char, world_x, world_y)
                    
                    # Calculate the visual height
                    visual_height = height / self.height_scale
                    
                    # Create a 3D character object with the explicit height value
                    char_obj = Character3D(
                        char, 
                        world_x - self_gui.game.world_x, 
                        world_y - self_gui.game.world_y, 
                        color,
                        height=visual_height  # Pass height directly
                    )
                    
                    # Add to the character map
                    with self_gui.lock:
                        char_key = f"{world_x},{world_y}"
                        self_gui.characters[char_key] = char_obj
                except ValueError as e:
                    # Skip invalid coordinates
                    continue
        
        # Replace the method - this is the key fix
        gui_plugin.update_character_map = lambda: new_update_character_map(gui_plugin)
    
    def load_settings(self):
        """Load settings from a file."""
        try:
            import json
            with open("polygraph_3d_settings.json", "r") as f:
                settings = json.load(f)
                self.min_height = settings.get("min_height", -10)
                self.max_height = settings.get("max_height", 10)
                self.height_scale = settings.get("height_scale", 4.0)
        except:
            # Use default settings if file doesn't exist or is invalid
            pass
    
    def save_settings(self):
        """Save settings to a file."""
        try:
            import json
            with open("polygraph_3d_settings.json", "w") as f:
                settings = {
                    "min_height": self.min_height,
                    "max_height": self.max_height,
                    "height_scale": self.height_scale
                }
                json.dump(settings, f)
        except:
            # Ignore errors
            pass
    
    def show_settings_menu(self):
        """Show the settings menu for the 3D Polygraph plugin."""
        # Store original settings in case user cancels
        original_min_height = self.min_height
        original_max_height = self.max_height
        original_height_scale = self.height_scale
        
        # Variables for menu navigation
        current_selection = 0
        in_settings_menu = True
        settings = [
            {"name": "Minimum Height", "value": self.min_height, "min": -50, "max": 0, "step": 1},
            {"name": "Maximum Height", "value": self.max_height, "min": 1, "max": 50, "step": 1},
            {"name": "Height Scale", "value": self.height_scale, "min": 1.0, "max": 20.0, "step": 0.5}
        ]
        
        # Get curses module from the game
        curses = self.game.curses
        
        # Save current state
        self.game.in_menu = False
        self.game.needs_redraw = True
        
        # Main loop for settings menu
        while in_settings_menu and self.game.running:
            # Clear screen
            self.game.screen.clear()
            
            # Draw header
            max_y, max_x = self.game.screen.getmaxyx()
            self.game.screen.addstr(0, 0, "3D Polygraph Settings", curses.A_BOLD)
            self.game.screen.addstr(1, 0, "═" * (max_x - 1))
            
            # Draw instructions
            self.game.screen.addstr(2, 0, "Use ↑/↓ to select a setting, ←/→ to change values")
            self.game.screen.addstr(3, 0, "Press ENTER to apply changes, ESC to cancel")
            self.game.screen.addstr(4, 0, "═" * (max_x - 1))
            
            # Draw settings
            for i, setting in enumerate(settings):
                # Highlight the selected item
                if i == current_selection:
                    attr = curses.A_REVERSE | curses.A_BOLD
                else:
                    attr = 0
                
                # Draw the item
                self.game.screen.addstr(i + 6, 2, f"{setting['name']}: {setting['value']}", attr)
                
                # Draw range information
                range_info = f"(Range: {setting['min']} to {setting['max']})"
                self.game.screen.addstr(i + 6, 40, range_info)
            
            # Draw footer
            self.game.screen.addstr(max_y - 2, 0, "═" * (max_x - 1))
            self.game.screen.addstr(max_y - 1, 0, "R: Reset to defaults")
            
            # Refresh screen
            self.game.screen.refresh()
            
            # Get input
            key = self.game.screen.getch()
            
            # Handle input
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(settings)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(settings)
            elif key == curses.KEY_LEFT:
                # Decrease value
                setting = settings[current_selection]
                setting['value'] = max(setting['min'], setting['value'] - setting['step'])
            elif key == curses.KEY_RIGHT:
                # Increase value
                setting = settings[current_selection]
                setting['value'] = min(setting['max'], setting['value'] + setting['step'])
            elif key == ord('r') or key == ord('R'):
                # Reset to defaults
                settings[0]['value'] = -10  # min_height
                settings[1]['value'] = 10   # max_height
                settings[2]['value'] = 4.0  # height_scale
            elif key == 10:  # Enter key
                # Apply changes
                self.min_height = settings[0]['value']
                self.max_height = settings[1]['value']
                self.height_scale = settings[2]['value']
                
                # Save settings
                self.save_settings()
                
                # Clear height cache to apply new settings
                self.height_map = {}
                
                # Exit menu
                in_settings_menu = False
            elif key == 27:  # Escape key
                # Restore original settings
                self.min_height = original_min_height
                self.max_height = original_max_height
                self.height_scale = original_height_scale
                
                # Exit without saving
                in_settings_menu = False
        
        # Restore game state
        self.game.in_menu = True
        self.game.needs_redraw = True
    
    def activate(self):
        """Activate the plugin."""
        super().activate()
        
        # Initialize the classifier if needed
        if not self.classifier:
            self.classifier = Polygraph3DClassifier()
        
        # Try to integrate with the GUI3D plugin if it's available
        gui3d_plugin = None
        for plugin in self.game.plugins:
            if plugin.name == "3D Visualization" and plugin.active:
                gui3d_plugin = plugin
                break
                
        if gui3d_plugin:
            # Integrate with the GUI3D plugin
            self.integrate_with_gui3d(gui3d_plugin)
        else:
            # If GUI3D plugin is not available, try to activate it
            for plugin in self.game.plugins:
                if plugin.name == "3D Visualization" and not plugin.active:
                    plugin.activate()
                    self.integrate_with_gui3d(plugin)
                    break
    
    def deactivate(self):
        """
        Deactivate the plugin by restoring the original character generation.
        """
        super().deactivate()
        
        # Restore the original method if we replaced it
        if self.original_get_char is not None:
            self.game.get_char_at = self.original_get_char
            self.original_get_char = None
            
        # Find the GUI3D plugin and restore its original update_character_map method
        if hasattr(self, 'gui_plugin_ref') and self.gui_plugin_ref:
            # If we have a reference to the GUI plugin, restore its original method
            if hasattr(self.gui_plugin_ref, 'original_update_character_map'):
                self.gui_plugin_ref.update_character_map = self.gui_plugin_ref.original_update_character_map
