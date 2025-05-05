import math
import random
import numpy as np
from plugins.base import Plugin

class GraphClassifier:
    """
    A polymorphic graph classifier that takes coordinates and outputs an ASCII byte.
    This creates more interesting and structured patterns in the game world.
    """
    
    def __init__(self, seed=42):
        """Initialize the graph classifier with a specific seed for reproducibility."""
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        
        # Create different classification regions
        self.classifiers = [
            self.perlin_noise_classifier,
            self.sine_wave_classifier,
            self.cellular_automaton_classifier,
            self.voronoi_classifier,
            self.fractal_classifier
        ]
        
        # Create region boundaries
        self.region_centers = []
        for _ in range(10):
            self.region_centers.append((
                random.randint(-1000, 1000),
                random.randint(-1000, 1000)
            ))
            
        # Precompute some values for perlin noise
        self.gradients = {}
        for i in range(-10, 10):
            for j in range(-10, 10):
                self.gradients[(i, j)] = np.array([
                    np.cos(random.random() * 2 * np.pi),
                    np.sin(random.random() * 2 * np.pi)
                ])
                
        # Precompute cellular automaton rules
        self.ca_rules = np.random.randint(0, 2, 256)
        
        # Precompute voronoi points
        self.voronoi_points = []
        for _ in range(20):
            self.voronoi_points.append((
                random.randint(-500, 500),
                random.randint(-500, 500)
            ))
    
    def classify(self, x, y):
        """
        Classify coordinates (x, y) to determine an ASCII character.
        Returns a byte value between 33 and 126 (printable ASCII).
        """
        # Convert coordinates to floats
        x_float = float(x) if not isinstance(x, float) else x
        y_float = float(y) if not isinstance(y, float) else y
        
        # Determine which region the point belongs to
        region_idx = self.get_region(x_float, y_float)
        
        # Use the appropriate classifier for this region
        classifier = self.classifiers[region_idx % len(self.classifiers)]
        value = classifier(x_float, y_float)
        
        # Ensure the value is in the printable ASCII range (33-126)
        return 33 + (value % 94)
    
    def get_region(self, x, y):
        """Determine which region the coordinates belong to."""
        min_dist = float('inf')
        min_idx = 0
        
        for i, (cx, cy) in enumerate(self.region_centers):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            if dist < min_dist:
                min_dist = dist
                min_idx = i
                
        return min_idx
    
    def perlin_noise_classifier(self, x, y):
        """Classifier based on Perlin noise."""
        # Convert coordinates to floats
        x_float = float(x) if not isinstance(x, float) else x
        y_float = float(y) if not isinstance(y, float) else y
        
        # Scale down coordinates
        x_float, y_float = x_float / 50.0, y_float / 50.0
        
        # Get grid cell coordinates
        x0, y0 = int(math.floor(x_float)), int(math.floor(y_float))
        x1, y1 = x0 + 1, y0 + 1
        
        # Get interpolation weights
        sx = x_float - x0
        sy = y_float - y0
        
        # Interpolate between grid point gradients
        n0 = self.dot_grid_gradient(x0, y0, x_float, y_float)
        n1 = self.dot_grid_gradient(x1, y0, x_float, y_float)
        ix0 = self.interpolate(n0, n1, sx)
        
        n0 = self.dot_grid_gradient(x0, y1, x_float, y_float)
        n1 = self.dot_grid_gradient(x1, y1, x_float, y_float)
        ix1 = self.interpolate(n0, n1, sx)
        
        value = self.interpolate(ix0, ix1, sy)
        
        # Scale to 0-255 range
        return int((value + 1) * 127.5)
    
    def dot_grid_gradient(self, ix, iy, x, y):
        """Compute the dot product of the gradient and distance vectors."""
        if (ix, iy) not in self.gradients:
            self.gradients[(ix, iy)] = np.array([
                np.cos(random.random() * 2 * np.pi),
                np.sin(random.random() * 2 * np.pi)
            ])
            
        gradient = self.gradients[(ix, iy)]
        dx, dy = x - ix, y - iy
        
        return dx * gradient[0] + dy * gradient[1]
    
    def interpolate(self, a0, a1, w):
        """Smooth interpolation between values."""
        return a0 + (a1 - a0) * (3.0 - 2.0 * w) * w * w
    
    def sine_wave_classifier(self, x, y):
        """Classifier based on sine waves."""
        # Convert coordinates to floats
        x_float = float(x) if not isinstance(x, float) else x
        y_float = float(y) if not isinstance(y, float) else y
        
        # Use sine waves with different frequencies and phases
        value = (
            math.sin(x_float / 10.0) * 50 +
            math.sin(y_float / 15.0) * 50 +
            math.sin((x_float + y_float) / 20.0) * 50 +
            math.sin(math.sqrt(x_float**2 + y_float**2) / 10.0) * 50
        )
        
        # Scale to 0-255 range
        return int((value + 200) % 256)
    
    def cellular_automaton_classifier(self, x, y):
        """Classifier based on cellular automaton patterns."""
        # Convert coordinates to integers if they are floats
        x_int = int(round(x)) if isinstance(x, float) else x
        y_int = int(round(y)) if isinstance(y, float) else y
        
        # Use coordinates to seed a simple 1D cellular automaton
        cell_x = abs(x_int) % 256
        
        # Run the automaton for y steps
        state = cell_x
        for _ in range(abs(y_int) % 100):
            # Apply rule
            left = (state << 1) % 256
            right = (state >> 1) % 256
            idx = (left ^ state ^ right) % 256
            state = self.ca_rules[idx]
            
        return state
    
    def voronoi_classifier(self, x, y):
        """Classifier based on Voronoi cells."""
        # Convert coordinates to floats
        x_float = float(x) if not isinstance(x, float) else x
        y_float = float(y) if not isinstance(y, float) else y
        
        # Find the closest point
        min_dist = float('inf')
        closest_idx = 0
        
        for i, (px, py) in enumerate(self.voronoi_points):
            dist = (x_float - px)**2 + (y_float - py)**2
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
                
        # Use the index of the closest point as the value
        return closest_idx % 256
    
    def fractal_classifier(self, x, y):
        """Classifier based on fractal patterns (simplified Mandelbrot)."""
        # Convert coordinates to floats
        x_float = float(x) if not isinstance(x, float) else x
        y_float = float(y) if not isinstance(y, float) else y
        
        # Scale coordinates to the appropriate range for Mandelbrot
        c_real = x_float / 100.0
        c_imag = y_float / 100.0
        
        # Initialize z
        z_real, z_imag = 0.0, 0.0
        
        # Iterate
        iteration = 0
        max_iteration = 20
        
        while z_real*z_real + z_imag*z_imag < 4 and iteration < max_iteration:
            # z = z^2 + c
            temp = z_real*z_real - z_imag*z_imag + c_real
            z_imag = 2*z_real*z_imag + c_imag
            z_real = temp
            iteration += 1
            
        # Map iteration count to a value
        return int((iteration * 12) % 256)


class GraphClassifierPlugin(Plugin):
    """
    A plugin that uses the GraphClassifier to generate the game world.
    This replaces the default character generation with more complex patterns.
    """
    
    def __init__(self, game):
        super().__init__(game)
        self.classifier = GraphClassifier()
        self.original_get_char = None
        
    def update(self, dt):
        """Update the plugin state."""
        # No updates needed for this plugin
        pass
        
    def render(self, screen):
        """No additional rendering needed."""
        pass
    
    def activate(self):
        """
        Activate the plugin by replacing the default character generation
        with the graph classifier.
        """
        super().activate()
        
        # Store the original method for later restoration
        if self.original_get_char is None:
            self.original_get_char = self.game.get_char_at
            
            # Replace with our classifier method
            def new_get_char_at(x, y):
                # Check if there's a space at this location
                space_key = self.game.get_space_key(x, y)
                if space_key in self.game.spaces:
                    return ' '
                    
                # Use the classifier to determine the character
                char_code = self.classifier.classify(x, y)
                return chr(char_code)
                
            self.game.get_char_at = new_get_char_at
    
    def deactivate(self):
        """
        Deactivate the plugin by restoring the original character generation.
        """
        super().deactivate()
        
        # Restore the original method
        if self.original_get_char is not None:
            self.game.get_char_at = self.original_get_char
            self.original_get_char = None
