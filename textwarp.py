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
        # Debug info
        self.last_key = 0
        # Flag to indicate if redraw is needed
        self.needs_redraw = True
        # Key state tracking for diagonal movement
        self.key_states = {
            curses.KEY_UP: False,
            curses.KEY_DOWN: False,
            curses.KEY_LEFT: False,
            curses.KEY_RIGHT: False,
            ord('w'): False,
            ord('s'): False,
            ord('a'): False,
            ord('d'): False,
            # Numeric keypad
            ord('7'): False,  # NW
            ord('8'): False,  # N
            ord('9'): False,  # NE
            ord('4'): False,  # W
            ord('6'): False,  # E
            ord('1'): False,  # SW
            ord('2'): False,  # S
            ord('3'): False,  # SE
            # Numpad with numlock
            curses.KEY_A1: False,  # NW (7)
            curses.KEY_A2: False,  # N (8)
            curses.KEY_A3: False,  # NE (9)
            curses.KEY_B1: False,  # W (4)
            curses.KEY_B3: False,  # E (6)
            curses.KEY_C1: False,  # SW (1)
            curses.KEY_C2: False,  # S (2)
            curses.KEY_C3: False   # SE (3)
        }
        # Direction mapping for numeric keypad
        self.numpad_directions = {
            ord('7'): (-1, -1),  # NW
            ord('8'): (0, -1),   # N
            ord('9'): (1, -1),   # NE
            ord('4'): (-1, 0),   # W
            ord('5'): (0, 0),    # Center (no movement)
            ord('6'): (1, 0),    # E
            ord('1'): (-1, 1),   # SW
            ord('2'): (0, 1),    # S
            ord('3'): (1, 1),    # SE
            # Numpad with numlock
            curses.KEY_A1: (-1, -1),  # NW (7)
            curses.KEY_A2: (0, -1),   # N (8)
            curses.KEY_A3: (1, -1),   # NE (9)
            curses.KEY_B1: (-1, 0),   # W (4)
            curses.KEY_B2: (0, 0),    # Center (5)
            curses.KEY_B3: (1, 0),    # E (6)
            curses.KEY_C1: (-1, 1),   # SW (1)
            curses.KEY_C2: (0, 1),    # S (2)
            curses.KEY_C3: (1, 1)     # SE (3)
        }

    def setup(self):
        # Initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)  # Hide cursor
        self.screen.keypad(True)  # Enable keypad mode for special keys
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
        # Get input
        key = self.screen.getch()
        self.last_key = key  # Store for debugging
        
        # Reset all key states if Escape is pressed
        if key == 27:  # ESC key
            for k in self.key_states:
                self.key_states[k] = False
            return
            
        # Update key states based on key press/release
        if key != -1:  # A key was pressed
            if key in self.key_states:
                self.key_states[key] = True
        
        # Reset movement direction
        self.dx = 0
        self.dy = 0
        
        # Check for numpad input first (takes precedence)
        if key in self.numpad_directions:
            self.dx, self.dy = self.numpad_directions[key]
        else:
            # Check vertical movement
            if (self.key_states[curses.KEY_UP] or self.key_states[ord('w')] or 
                self.key_states[ord('8')] or self.key_states[curses.KEY_A2]):
                self.dy = -1
            elif (self.key_states[curses.KEY_DOWN] or self.key_states[ord('s')] or 
                  self.key_states[ord('2')] or self.key_states[curses.KEY_C2]):
                self.dy = 1
                
            # Check horizontal movement
            if (self.key_states[curses.KEY_LEFT] or self.key_states[ord('a')] or 
                self.key_states[ord('4')] or self.key_states[curses.KEY_B1]):
                self.dx = -1
            elif (self.key_states[curses.KEY_RIGHT] or self.key_states[ord('d')] or 
                  self.key_states[ord('6')] or self.key_states[curses.KEY_B3]):
                self.dx = 1
            
            # Check diagonal movement
            if self.key_states[ord('7')] or self.key_states[curses.KEY_A1]:  # NW
                self.dx = -1
                self.dy = -1
            elif self.key_states[ord('9')] or self.key_states[curses.KEY_A3]:  # NE
                self.dx = 1
                self.dy = -1
            elif self.key_states[ord('1')] or self.key_states[curses.KEY_C1]:  # SW
                self.dx = -1
                self.dy = 1
            elif self.key_states[ord('3')] or self.key_states[curses.KEY_C3]:  # SE
                self.dx = 1
                self.dy = 1
        
        # Handle quit
        if key == ord('q') or key == ord('Q'):
            self.running = False
            
        # If any movement is happening, force a redraw
        if self.dx != 0 or self.dy != 0:
            self.needs_redraw = True
            # Move the world immediately by 1 cell in the pressed direction
            self.world_x += self.dx
            self.world_y += self.dy
            
            # Display direction in panel
            direction = ""
            if self.dy < 0:
                direction += "N"
            elif self.dy > 0:
                direction += "S"
            if self.dx > 0:
                direction += "E"
            elif self.dx < 0:
                direction += "W"
            self.direction = direction

    def update(self):
        # Calculate time since last update
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Simulate key release after a short time
        # This allows for diagonal movement by pressing keys in sequence
        for key in self.key_states:
            if self.key_states[key]:
                self.key_states[key] = False  # Auto-release keys
        
        # Accumulate movement (for smooth continuous movement if needed)
        self.acc_x += self.dx * self.move_speed * dt
        self.acc_y += self.dy * self.move_speed * dt
        
        # Apply accumulated movement when it reaches at least 1 cell
        if abs(self.acc_x) >= 1:
            move_x = int(self.acc_x)
            self.world_x += move_x
            self.acc_x -= move_x  # Keep remainder for next update
            self.needs_redraw = True
            
        if abs(self.acc_y) >= 1:
            move_y = int(self.acc_y)
            self.world_y += move_y
            self.acc_y -= move_y  # Keep remainder for next update
            self.needs_redraw = True

    def render(self):
        # Only redraw if needed
        if not self.needs_redraw:
            return
            
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
        direction = getattr(self, 'direction', '')
        panel_text = f"Top-Left: ({top_left_world_x}, {top_left_world_y}) | X: ({self.world_x}, {self.world_y}) | Dir: {direction} | Key: {self.last_key}"
        
        # Fill panel background
        for x in range(self.max_x - 1):
            self.screen.addch(panel_y, x, ' ', self.panel_color)
        
        # Draw panel text
        self.screen.addstr(panel_y, 1, panel_text[:self.max_x - 3], self.panel_color)
        
        # Update screen
        self.screen.refresh()
        
        # Reset redraw flag
        self.needs_redraw = False

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
                
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
                
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
