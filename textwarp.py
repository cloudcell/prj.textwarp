#!/usr/bin/env python3
import curses
import time
import math

class TextAdventure:
    def __init__(self):
        self.screen = None
        self.running = True
        self.player_x = 0  # Will be centered later
        self.player_y = 0  # Will be centered later
        self.player_char = 'X'
        self.player_color = None
        self.background_color = None
        self.max_y = 0
        self.max_x = 0
        self.last_update = time.time()
        self.move_speed = 1.0  # Cells per second
        self.dx = 0  # Horizontal movement direction
        self.dy = 0  # Vertical movement direction

    def setup(self):
        # Initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)  # Hide cursor
        self.screen.keypad(True)
        self.screen.timeout(50)  # Non-blocking input with 50ms timeout
        
        # Get screen dimensions
        self.max_y, self.max_x = self.screen.getmaxyx()
        
        # Center the player
        self.player_x = self.max_x // 2
        self.player_y = self.max_y // 2
        
        # Setup colors
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Player color
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Background color
        self.player_color = curses.color_pair(1)
        self.background_color = curses.color_pair(2)

    def handle_input(self):
        # Reset movement direction
        self.dx = 0
        self.dy = 0
        
        # Get input
        key = self.screen.getch()
        
        # Handle movement keys
        if key == curses.KEY_UP:
            self.dy = -1
        elif key == curses.KEY_DOWN:
            self.dy = 1
        elif key == curses.KEY_LEFT:
            self.dx = -1
        elif key == curses.KEY_RIGHT:
            self.dx = 1
        elif key == ord('q') or key == ord('Q'):
            self.running = False
        
        # Handle diagonal movement (combined keys)
        # Note: This is a simple approach that works with the limitations of terminal input
        # For better diagonal movement, we'd need to track key states
        if self.dx != 0 and self.dy != 0:
            # Normalize diagonal movement to avoid faster diagonal speed
            magnitude = math.sqrt(self.dx**2 + self.dy**2)
            self.dx = self.dx / magnitude
            self.dy = self.dy / magnitude

    def update(self):
        # Calculate time since last update
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Update player position
        new_x = self.player_x + self.dx * self.move_speed * dt
        new_y = self.player_y + self.dy * self.move_speed * dt
        
        # Clamp player position to screen bounds
        new_x = max(0, min(self.max_x - 1, new_x))
        new_y = max(0, min(self.max_y - 1, new_y))
        
        # Update player position
        self.player_x = new_x
        self.player_y = new_y

    def render(self):
        self.screen.clear()
        
        # Draw background
        for y in range(self.max_y - 1):  # -1 to avoid bottom line issues
            for x in range(self.max_x - 1):  # -1 to avoid right edge issues
                # Calculate location ID and convert to ASCII
                loc_id = (y * self.max_x + x)
                char_code = (loc_id % 94) + 33  # 33-126 are printable ASCII
                
                # Draw the character
                self.screen.addch(int(y), int(x), chr(char_code), self.background_color)
        
        # Draw player (ensuring coordinates are integers)
        player_y_int = int(self.player_y)
        player_x_int = int(self.player_x)
        if 0 <= player_y_int < self.max_y - 1 and 0 <= player_x_int < self.max_x - 1:
            self.screen.addch(player_y_int, player_x_int, self.player_char, self.player_color)
        
        # Update screen
        self.screen.refresh()

    def cleanup(self):
        # Clean up curses
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()

    def run(self):
        try:
            self.setup()
            
            while self.running:
                self.handle_input()
                self.update()
                self.render()
                
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

