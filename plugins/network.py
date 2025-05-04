import socket
import threading
import json
import time
import random
import curses
from plugins.base import Plugin

class NetworkPlayer:
    """Represents a remote player in the game."""
    
    def __init__(self, player_id, x, y, name="Remote Player"):
        self.player_id = player_id
        self.x = x
        self.y = y
        self.name = name
        self.last_update = time.time()
        self.color = None  # Will be set later
        
    def update_position(self, x, y):
        """Update the player's position."""
        self.x = x
        self.y = y
        self.last_update = time.time()
        
    def is_active(self):
        """Check if the player is still active (has sent updates recently)."""
        return time.time() - self.last_update < 10.0  # Consider inactive after 10 seconds


class NetworkServer(threading.Thread):
    """Server thread that handles connections from clients."""
    
    def __init__(self, plugin, host='0.0.0.0', port=5555):
        super().__init__(daemon=True)
        self.plugin = plugin
        self.host = host
        self.port = port
        self.running = True
        self.clients = {}
        self.lock = threading.Lock()
        
    def run(self):
        """Run the server thread."""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.settimeout(1.0)  # 1 second timeout for accept
            self.server_socket.listen(5)
            
            self.plugin.game.message = f"Network server started on port {self.port}"
            self.plugin.game.message_timeout = 3.0
            
            while self.running:
                try:
                    # Accept new connections
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    # Timeout on accept, just continue the loop
                    pass
                except Exception as e:
                    if self.running:
                        self.plugin.game.message = f"Server error: {e}"
                        self.plugin.game.message_timeout = 3.0
        except Exception as e:
            self.plugin.game.message = f"Server startup error: {e}"
            self.plugin.game.message_timeout = 3.0
        finally:
            self.stop()
            
    def stop(self):
        """Stop the server thread."""
        self.running = False
        if hasattr(self, 'server_socket'):
            try:
                self.server_socket.close()
            except:
                pass
                
    def handle_client(self, client_socket, addr):
        """Handle communication with a client."""
        player_id = None
        try:
            # Set a timeout for client operations
            client_socket.settimeout(5.0)
            
            # Receive initial message with player name
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return
                
            # Parse the initial message
            try:
                message = json.loads(data)
                player_name = message.get('name', f"Player-{addr[0]}")
                player_id = f"{addr[0]}:{addr[1]}"
                
                # Create a new player
                with self.lock:
                    self.plugin.add_player(player_id, self.plugin.game.world_x, self.plugin.game.world_y, player_name)
                    self.clients[player_id] = client_socket
                
                # Send welcome message
                welcome = {
                    'type': 'welcome',
                    'player_id': player_id,
                    'message': f"Welcome to TextWarp, {player_name}!"
                }
                client_socket.sendall(json.dumps(welcome).encode('utf-8'))
                
                # Main client loop
                while self.running:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                        
                    # Parse the message
                    message = json.loads(data)
                    message_type = message.get('type')
                    
                    if message_type == 'position':
                        # Update player position
                        x = message.get('x')
                        y = message.get('y')
                        with self.lock:
                            if player_id in self.plugin.players:
                                self.plugin.players[player_id].update_position(x, y)
                    
                    # Broadcast game state to this client
                    self.send_game_state(client_socket)
            except json.JSONDecodeError:
                pass
        except Exception as e:
            if self.running:
                self.plugin.game.message = f"Client error: {e}"
                self.plugin.game.message_timeout = 3.0
        finally:
            # Clean up
            try:
                client_socket.close()
            except:
                pass
                
            # Remove player
            if player_id:
                with self.lock:
                    if player_id in self.plugin.players:
                        del self.plugin.players[player_id]
                    if player_id in self.clients:
                        del self.clients[player_id]
                        
    def send_game_state(self, client_socket):
        """Send the current game state to a client."""
        try:
            # Prepare game state
            game_state = {
                'type': 'game_state',
                'players': {},
                'snakes': []
            }
            
            # Add player positions
            with self.lock:
                for pid, player in self.plugin.players.items():
                    if player.is_active():
                        game_state['players'][pid] = {
                            'name': player.name,
                            'x': player.x,
                            'y': player.y
                        }
                
                # Add snake positions
                for plugin in self.plugin.game.plugins:
                    if hasattr(plugin, 'snakes'):
                        for snake in plugin.snakes:
                            if snake.body:
                                game_state['snakes'].append({
                                    'head': snake.body[0],
                                    'length': len(snake.body)
                                })
            
            # Send the game state
            client_socket.sendall(json.dumps(game_state).encode('utf-8'))
        except:
            pass
            
    def broadcast(self, message):
        """Broadcast a message to all clients."""
        with self.lock:
            for client_socket in list(self.clients.values()):
                try:
                    client_socket.sendall(json.dumps(message).encode('utf-8'))
                except:
                    pass


class NetworkClient(threading.Thread):
    """Client thread that connects to a server."""
    
    def __init__(self, plugin, host, port=5555, player_name="Player"):
        super().__init__(daemon=True)
        self.plugin = plugin
        self.host = host
        self.port = port
        self.player_name = player_name
        self.running = True
        self.connected = False
        self.player_id = None
        self.remote_players = {}
        self.remote_snakes = []
        self.lock = threading.Lock()
        
    def run(self):
        """Run the client thread."""
        try:
            # Connect to server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5.0)
            self.client_socket.connect((self.host, self.port))
            
            # Send initial message with player name
            initial_message = {
                'type': 'hello',
                'name': self.player_name
            }
            self.client_socket.sendall(json.dumps(initial_message).encode('utf-8'))
            
            # Receive welcome message
            data = self.client_socket.recv(1024).decode('utf-8')
            welcome = json.loads(data)
            if welcome.get('type') == 'welcome':
                self.player_id = welcome.get('player_id')
                self.plugin.game.message = welcome.get('message')
                self.plugin.game.message_timeout = 3.0
                self.connected = True
                
                # Start a thread to receive game state updates
                receiver_thread = threading.Thread(
                    target=self.receive_updates,
                    daemon=True
                )
                receiver_thread.start()
                
                # Main client loop - send position updates
                while self.running and self.connected:
                    # Send position update
                    position = {
                        'type': 'position',
                        'x': self.plugin.game.world_x,
                        'y': self.plugin.game.world_y
                    }
                    try:
                        self.client_socket.sendall(json.dumps(position).encode('utf-8'))
                    except:
                        self.connected = False
                        break
                        
                    # Sleep to avoid flooding the server
                    time.sleep(0.1)
        except Exception as e:
            self.plugin.game.message = f"Connection error: {e}"
            self.plugin.game.message_timeout = 3.0
        finally:
            self.stop()
            
    def stop(self):
        """Stop the client thread."""
        self.running = False
        self.connected = False
        if hasattr(self, 'client_socket'):
            try:
                self.client_socket.close()
            except:
                pass
                
    def receive_updates(self):
        """Receive game state updates from the server."""
        try:
            while self.running and self.connected:
                try:
                    data = self.client_socket.recv(1024).decode('utf-8')
                    if not data:
                        self.connected = False
                        break
                        
                    # Parse the game state
                    game_state = json.loads(data)
                    if game_state.get('type') == 'game_state':
                        with self.lock:
                            # Update remote players
                            self.remote_players = {}
                            for pid, player_data in game_state.get('players', {}).items():
                                if pid != self.player_id:  # Don't include ourselves
                                    self.remote_players[pid] = NetworkPlayer(
                                        pid,
                                        player_data.get('x'),
                                        player_data.get('y'),
                                        player_data.get('name')
                                    )
                                    
                            # Update remote snakes
                            self.remote_snakes = game_state.get('snakes', [])
                except socket.timeout:
                    # Timeout on receive, just continue the loop
                    pass
                except json.JSONDecodeError:
                    # Invalid JSON, just continue
                    pass
        except Exception as e:
            if self.running:
                self.plugin.game.message = f"Receive error: {e}"
                self.plugin.game.message_timeout = 3.0
            self.connected = False


class NetworkPlugin(Plugin):
    """Plugin that enables network multiplayer."""
    
    def __init__(self, game):
        super().__init__(game)
        self.server = None
        self.client = None
        self.is_server = False
        self.is_client = False
        self.players = {}  # Remote players (when server)
        self.player_color = None  # Will be set in activate()
        
    def update(self, dt):
        """Update the plugin state."""
        if not self.active:
            return
            
        # Remove inactive players
        to_remove = []
        for player_id, player in self.players.items():
            if not player.is_active():
                to_remove.append(player_id)
                
        for player_id in to_remove:
            del self.players[player_id]
            
        # If we're a client, update our remote players from the client thread
        if self.is_client and self.client:
            with self.client.lock:
                self.players = self.client.remote_players
                
                # Make sure all players have a color set
                for player in self.players.values():
                    if player.color is None:
                        player.color = curses.color_pair(random.randint(1, 5))
        
    def render(self, screen):
        """Render remote players."""
        if not self.active:
            return
            
        # Render remote players
        for player in self.players.values():
            # Calculate screen position
            screen_x = int(player.x - self.game.world_x + self.game.max_x // 2)
            screen_y = int(player.y - self.game.world_y + self.game.max_y // 2)
            
            # Only render if on screen
            if 0 <= screen_y < self.game.max_y and 0 <= screen_x < self.game.max_x:
                try:
                    # Draw the player (as a different character than the local player)
                    screen.addstr(screen_y, screen_x, 'O', player.color)
                    
                    # Draw player name above
                    if screen_y > 0:
                        name_x = max(0, screen_x - len(player.name) // 2)
                        name_x = min(name_x, self.game.max_x - len(player.name))
                        if 0 <= name_x < self.game.max_x:
                            screen.addstr(screen_y - 1, name_x, player.name[:self.game.max_x - name_x], player.color)
                except:
                    # Ignore errors from writing to the bottom-right corner
                    pass
    
    def activate(self):
        """Activate the plugin."""
        super().activate()
        # Initialize colors now that curses is set up
        self.player_color = curses.color_pair(1)  # Red for remote players
        
    def deactivate(self):
        """Deactivate the plugin."""
        self.stop_server()
        self.disconnect()
        super().deactivate()
        
    def start_server(self, port=5555):
        """Start a server to host a game."""
        if self.server:
            self.stop_server()
            
        self.server = NetworkServer(self, port=port)
        self.server.start()
        self.is_server = True
        
    def stop_server(self):
        """Stop the server."""
        if self.server:
            self.server.stop()
            self.server = None
        self.is_server = False
        
    def connect_to_server(self, host, port=5555, player_name="Player"):
        """Connect to a server as a client."""
        if self.client:
            self.disconnect()
            
        self.client = NetworkClient(self, host, port, player_name)
        self.client.start()
        self.is_client = True
        
    def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            self.client.stop()
            self.client = None
        self.is_client = False
        
    def add_player(self, player_id, x, y, name="Remote Player"):
        """Add a new remote player."""
        self.players[player_id] = NetworkPlayer(player_id, x, y, name)
        
    def show_network_menu(self):
        """Show a menu for network options."""
        options = [
            "Start Server",
            "Connect to Server",
            "Disconnect",
            "Back"
        ]
        
        selected = 0
        running = True
        
        while running:
            # Draw menu
            self.game.screen.clear()
            self.game.screen.addstr(0, 0, "Network Options", curses.A_BOLD)
            
            for i, option in enumerate(options):
                if i == selected:
                    self.game.screen.addstr(i + 2, 2, f"> {option} <", curses.A_BOLD)
                else:
                    self.game.screen.addstr(i + 2, 4, option)
                    
            # Show status
            status = "Not connected"
            if self.is_server:
                status = "Server running"
            elif self.is_client and self.client and self.client.connected:
                status = f"Connected to {self.client.host}"
                
            self.game.screen.addstr(len(options) + 3, 0, f"Status: {status}")
            
            # Show connected players
            if self.players:
                self.game.screen.addstr(len(options) + 5, 0, "Connected players:")
                for i, (pid, player) in enumerate(self.players.items()):
                    if i < 10:  # Show at most 10 players
                        self.game.screen.addstr(len(options) + 6 + i, 2, f"{player.name} ({player.x}, {player.y})")
            
            self.game.screen.refresh()
            
            # Handle input
            key = self.game.screen.getch()
            
            if key == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif key == 10 or key == 13:  # Enter
                if options[selected] == "Start Server":
                    # Get port
                    port = self.get_input("Enter port (default: 5555): ")
                    try:
                        port = int(port) if port else 5555
                        self.start_server(port)
                    except ValueError:
                        self.game.message = "Invalid port number"
                        self.game.message_timeout = 2.0
                elif options[selected] == "Connect to Server":
                    # Get host and port
                    host = self.get_input("Enter host: ")
                    port = self.get_input("Enter port (default: 5555): ")
                    name = self.get_input("Enter your name: ")
                    
                    if host:
                        try:
                            port = int(port) if port else 5555
                            name = name if name else "Player"
                            self.connect_to_server(host, port, name)
                        except ValueError:
                            self.game.message = "Invalid port number"
                            self.game.message_timeout = 2.0
                elif options[selected] == "Disconnect":
                    self.stop_server()
                    self.disconnect()
                elif options[selected] == "Back":
                    running = False
            elif key == 27:  # ESC
                running = False
                
        # Redraw game
        self.game.needs_redraw = True
        
    def get_input(self, prompt):
        """Get text input from the user."""
        self.game.screen.clear()
        self.game.screen.addstr(0, 0, prompt)
        curses.echo()
        curses.curs_set(1)
        
        # Create a window for input
        input_win = curses.newwin(1, 30, 2, 0)
        input_win.refresh()
        
        # Get input
        input_str = input_win.getstr(0, 0, 29).decode('utf-8')
        
        # Restore curses settings
        curses.noecho()
        curses.curs_set(0)
        
        return input_str
