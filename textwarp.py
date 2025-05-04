#!/usr/bin/env python3
import curses
import time
import math

class TextAdventure:
    def __init__(self):
        self.screen = None
        self.running = True
        self.player_char = 'X'
        self.player_color = None
        self.background_color = None
        self.at_symbol_color = None
        self.panel_color = None
        self.max_y = 0
        self.max_x = 0
        self.last_update = time.time()
        self.move_speed = 5  # Integer cells per second
        self.dx = 0  # Horizontal movement direction
        self.dy = 0  # Vertical movement direction
        # World coordinates (player is always at center of screen)
        self.world_x = 0
        self.world_y = 0
        # Accumulated movement that hasn't been applied yet
        self.acc_x = 0
        self.acc_y = 0

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
        
        # Setup colors
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)    # Player color
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Background color
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # @ symbol color
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLUE)  # Panel color
        self.player_color = curses.color_pair(1)
        self.background_color = curses.color_pair(2)
        self.at_symbol_color = curses.color_pair(3)
        self.panel_color = curses.color_pair(4)

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
        
        # Accumulate movement
        self.acc_x += self.dx * self.move_speed * dt
        self.acc_y += self.dy * self.move_speed * dt
        
        # Apply accumulated movement when it reaches at least 1 cell
        if abs(self.acc_x) >= 1:
            move_x = int(self.acc_x)
            self.world_x += move_x
            self.acc_x -= move_x  # Keep remainder for next update
            
        if abs(self.acc_y) >= 1:
            move_y = int(self.acc_y)
            self.world_y += move_y
            self.acc_y -= move_y  # Keep remainder for next update

    def render(self):
        self.screen.clear()
        
        # Calculate player position at center of screen
        player_screen_y = self.max_y // 2
        player_screen_x = self.max_x // 2
        
        # Calculate top-left corner world coordinates
        top_left_world_y = self.world_y - player_screen_y
        top_left_world_x = self.world_x - player_screen_x
        
        # Reserve the bottom line for the panel
        drawable_height = self.max_y - 2  # -2 to leave space for panel and avoid bottom line issues
        
        # Draw background relative to player position
        for y in range(drawable_height):
            for x in range(self.max_x - 1):  # -1 to avoid right edge issues
                # Calculate world coordinates for this screen position
                world_y = y - player_screen_y + self.world_y
                world_x = x - player_screen_x + self.world_x
                
                # Calculate location ID and convert to ASCII
                # Use a consistent formula for both x and y coordinates
                loc_id = abs(world_y * 100 + world_x) % 127
                char_code = (loc_id % 94) + 33  # 33-126 are printable ASCII
                
                # Get the character to draw
                char = chr(char_code)
                
                # Choose color based on character
                if char == '@':
                    color = self.at_symbol_color
                else:
                    color = self.background_color
                
                # Draw the character
                self.screen.addch(y, x, char, color)
        
        # Draw player at center of screen
        if 0 <= player_screen_y < drawable_height and 0 <= player_screen_x < self.max_x - 1:
            self.screen.addch(player_screen_y, player_screen_x, self.player_char, self.player_color)
        
        # Draw panel at the bottom
        panel_y = self.max_y - 2
        panel_text = f"Top-Left: ({top_left_world_x}, {top_left_world_y}) | X Position: ({self.world_x}, {self.world_y})"
        
        # Fill panel background
        for x in range(self.max_x - 1):
            self.screen.addch(panel_y, x, ' ', self.panel_color)
        
        # Draw panel text
        self.screen.addstr(panel_y, 1, panel_text[:self.max_x - 3], self.panel_color)
        
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
