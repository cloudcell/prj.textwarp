import random
import hashlib
from plugins.base import Plugin
import curses

class Snake:
    """A snake that moves around the game world."""
    
    def __init__(self, x, y, game):
        self.x = x
        self.y = y
        self.length = 3
        self.max_length = 15  # Maximum length a snake can grow to
        self.body = [(x, y)]
        self.game = game
        self.direction = random.choice([(0, -1), (1, 0), (0, 1), (-1, 0)])
        self.time_to_move = 0
        self.move_interval = 0.5  # seconds between moves
        
    def update(self, dt):
        """Update the snake's position."""
        self.time_to_move -= dt
        if self.time_to_move <= 0:
            self.time_to_move = self.move_interval
            
            # Randomly change direction sometimes
            if random.random() < 0.3:
                self.direction = random.choice([(0, -1), (1, 0), (0, 1), (-1, 0)])
                
            # Move the snake
            head_x, head_y = self.body[0]
            dx, dy = self.direction
            new_head = (head_x + dx, head_y + dy)
            
            # Check if there's an egg at the new position
            world_x = new_head[0] + self.game.world_x
            world_y = new_head[1] + self.game.world_y
            location_id = (world_x + world_y * 1000) % 127
            if chr(location_id) == '0':  # Found an egg
                # Only grow if we haven't reached max length
                if self.length < self.max_length:
                    self.length += 1
                # Create a space where the egg was
                space_key = hashlib.md5(f"{world_x},{world_y}".encode()).hexdigest()
                self.game.spaces[space_key] = (world_x, world_y)
                self.game.save_spaces()
                
            # Add the new head
            self.body.insert(0, new_head)
            
            # Remove the tail if we're longer than our length
            while len(self.body) > self.length:
                self.body.pop()
                
    def render(self, screen):
        """Render the snake on the screen."""
        for i, (x, y) in enumerate(self.body):
            # Only render if the body segment is on screen
            screen_x = x + self.game.max_x // 2
            screen_y = y + self.game.max_y // 2
            
            if 0 <= screen_x < self.game.max_x and 0 <= screen_y < self.game.max_y:
                # Use different characters for head and body
                char = 'S' if i == 0 else 's'
                # Add a visual indicator when snake is at max length
                attr = curses.A_BOLD if self.length >= self.max_length else 0
                try:
                    screen.addstr(screen_y, screen_x, char, attr)
                except:
                    # Ignore errors from writing to the bottom-right corner
                    pass

class SnakePlugin(Plugin):
    """A plugin that adds snakes to the game world."""
    
    def __init__(self, game):
        super().__init__(game)
        self.snakes = []
        self.spawn_timer = 0
        self.spawn_interval = 10  # seconds between snake spawns
        
    def update(self, dt):
        """Update all snakes and potentially spawn new ones."""
        if not self.active:
            return
            
        # Update existing snakes
        for snake in self.snakes:
            snake.update(dt)
            
        # Maybe spawn a new snake
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = self.spawn_interval
            self.try_spawn_snake()
            
    def render(self, screen):
        """Render all snakes."""
        if not self.active:
            return
            
        for snake in self.snakes:
            snake.render(screen)
            
    def try_spawn_snake(self):
        """Try to spawn a new snake at a random @ character."""
        # Limit the number of snakes
        if len(self.snakes) >= 5:
            return
            
        # Find all @ characters on screen
        at_positions = []
        for y in range(self.game.max_y):
            for x in range(self.game.max_x):
                world_x = x - self.game.max_x // 2 + self.game.world_x
                world_y = y - self.game.max_y // 2 + self.game.world_y
                location_id = (world_x + world_y * 1000) % 127
                if chr(location_id) == '@':
                    at_positions.append((x - self.game.max_x // 2, y - self.game.max_y // 2))
                    
        if at_positions:
            # Choose a random @ position
            x, y = random.choice(at_positions)
            self.snakes.append(Snake(x, y, self.game))
            
            # Create a space where the snake spawned
            world_x = x + self.game.world_x
            world_y = y + self.game.world_y
            space_key = hashlib.md5(f"{world_x},{world_y}".encode()).hexdigest()
            self.game.spaces[space_key] = (world_x, world_y)
