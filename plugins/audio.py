import os
import time
import random
import threading
import pygame
import numpy as np
from plugins.base import Plugin

class AudioPlugin(Plugin):
    """Plugin that plays MOD music files from the audio-out folder."""
    
    def __init__(self, game):
        super().__init__(game)
        self.music_folder = "./audio-out"
        self.current_track = None
        self.playlist = []
        self.initialized = False
        self.volume = 0.7  # Default volume (0.0 to 1.0)
        self.is_playing = False
        self.auto_play = True  # Auto-play next track when current one finishes
        self.play_on_start = False  # Play random track when plugin is activated
        self.show_track_info = True  # Show track info in the game UI
        self.track_info_timeout = 0.0  # Timeout for displaying track info
        self.track_info_duration = 5.0  # How long to display track info
        self.last_played_track = None  # Remember the last played track
        
        # Audio analysis for visualization
        self.beat_intensity = 0.0  # Current beat intensity (0.0 to 1.0)
        self.beat_history = [0.0] * 10  # History of recent beat intensities
        self.sample_buffer = None  # Buffer for audio samples
        self.sample_rate = 44100
        self.buffer_size = 1024
        self.fft_data = None  # FFT data for frequency analysis
        self.frequency_bands = [
            (60, 250),    # Bass
            (250, 500),   # Low mids
            (500, 2000),  # Mids
            (2000, 4000), # High mids
            (4000, 8000)  # Highs
        ]
        self.band_intensities = [0.0] * len(self.frequency_bands)
        
        # Create audio-out directory if it doesn't exist
        os.makedirs(self.music_folder, exist_ok=True)
        
        # Load settings if they exist
        self.load_settings()
        
        # Initialize pygame mixer if not already initialized
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.sample_rate, -16, 2, self.buffer_size)
            self.initialized = True
        except Exception as e:
            print(f"Error initializing audio mixer: {e}")
            self.initialized = False
        
    @property
    def name(self):
        """Return the name of the plugin."""
        return "Audio Player"
        
    def activate(self):
        """Activate the plugin."""
        super().activate()
        
        # Scan for music files
        self.refresh_playlist()
        
        # Start playing if play_on_start is enabled
        if self.play_on_start and self.playlist:
            # If we have a last played track, use that
            if self.last_played_track and os.path.exists(self.last_played_track) and self.last_played_track in self.playlist:
                self.play(self.last_played_track)
                track_name = os.path.basename(self.last_played_track)
                self.game.message = f"Resuming: {track_name}"
                self.game.message_timeout = 3.0
            else:
                # Otherwise play a random track
                self.play_random()
                    
        # Start a thread for audio analysis
        self.analysis_thread = threading.Thread(target=self.analyze_audio_thread, daemon=True)
        self.analysis_thread.start()
        
    def deactivate(self):
        """Deactivate the plugin."""
        if self.initialized and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        self.is_playing = False
        super().deactivate()
        
    def update(self, dt):
        """Update the audio plugin state."""
        try:
            if not self.active or not pygame.mixer.get_init():
                return
                
            # Update track info timeout
            if self.track_info_timeout > 0:
                self.track_info_timeout -= dt
                
            # Check if a track has finished playing
            if self.is_playing and not pygame.mixer.music.get_busy():
                self.is_playing = False
                
                # Auto-play next track if enabled
                if self.auto_play and self.playlist:
                    self.play_next_track()
        except Exception as e:
            # Ignore errors if mixer is not initialized
            pass
            
    def render(self, screen):
        """Render the plugin on the curses screen."""
        if not self.active or not self.initialized or not self.show_track_info or self.track_info_timeout <= 0:
            return
            
        # Get screen dimensions
        max_y, max_x = screen.getmaxyx()
        
        # Display current track info at the top of the screen
        if self.current_track:
            track_name = os.path.basename(self.current_track)
            info_text = f"♫ Now Playing: {track_name} ♫"
            
            # Truncate if too long
            if len(info_text) > max_x - 2:
                info_text = info_text[:max_x - 5] + "..."
                
            # Center the text
            x_pos = max(0, (max_x - len(info_text)) // 2)
            
            # Set color attributes
            try:
                screen.addstr(0, x_pos, info_text, self.game.curses.color_pair(3) | self.game.curses.A_BOLD)
            except:
                # Fallback if color pair 3 is not available
                screen.addstr(0, x_pos, info_text)
                
    def refresh_playlist(self):
        """Scan the music folder for MOD files and update the playlist."""
        self.playlist = []
        
        if not os.path.exists(self.music_folder):
            return
            
        # Look for MOD files (common extensions)
        mod_extensions = ['.mod', '.xm', '.s3m', '.it', '.669', '.med', '.mtm', '.stm', '.far', '.ult', '.wow']
        
        for file in os.listdir(self.music_folder):
            file_path = os.path.join(self.music_folder, file)
            if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in mod_extensions):
                self.playlist.append(file_path)
                
        # Sort playlist alphabetically
        self.playlist.sort()
        
    def play(self, track_path):
        """Play a specific track."""
        if not self.initialized or not os.path.exists(track_path):
            return False
            
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()
            self.current_track = track_path
            self.is_playing = True
            
            # Show track info
            if self.show_track_info:
                self.track_info_timeout = self.track_info_duration
                self.game.needs_redraw = True
                
            return True
        except Exception as e:
            self.game.message = f"Error playing track: {e}"
            self.game.message_timeout = 3.0
            return False
            
    def play_random(self):
        """Play a random track from the playlist."""
        if not self.playlist:
            self.refresh_playlist()
            
        if self.playlist:
            # Choose a random track that's different from the current one
            if len(self.playlist) > 1 and self.current_track in self.playlist:
                new_playlist = [t for t in self.playlist if t != self.current_track]
                track = random.choice(new_playlist)
            else:
                track = random.choice(self.playlist)
                
            return self.play(track)
        return False
        
    def stop(self):
        """Stop the currently playing track."""
        if self.initialized and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.is_playing = False
            
    def pause(self):
        """Pause or unpause the currently playing track."""
        if not self.initialized:
            return
            
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.is_playing = False
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True
            
    def set_volume(self, volume):
        """Set the music volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        if self.initialized:
            pygame.mixer.music.set_volume(self.volume)
            
    def analyze_audio_thread(self):
        """Thread function for analyzing audio in real-time."""
        try:
            while True:
                if self.initialized and self.is_playing and pygame.mixer.music.get_busy():
                    self.analyze_audio()
                time.sleep(0.05)  # 50ms update rate (20 Hz)
        except Exception as e:
            print(f"Audio analysis error: {e}")
            
    def analyze_audio(self):
        """Analyze the currently playing audio to extract beat and frequency information."""
        try:
            # Since pygame doesn't provide direct access to the audio buffer,
            # we'll use a simple approach based on the current volume level
            if pygame.mixer.music.get_busy():
                # Get the current position in the track (in seconds)
                pos = pygame.mixer.music.get_pos() / 1000.0
                
                # Create a simple oscillating value based on time
                # This is a fallback since we can't directly access the audio data
                t = time.time() * 5.0  # Scale time for faster oscillation
                
                # Create different oscillation patterns for different frequency bands
                self.band_intensities[0] = 0.5 + 0.5 * np.sin(t * 1.0)  # Bass (slower)
                self.band_intensities[1] = 0.5 + 0.5 * np.sin(t * 1.5)  # Low mids
                self.band_intensities[2] = 0.5 + 0.5 * np.sin(t * 2.0)  # Mids
                self.band_intensities[3] = 0.5 + 0.5 * np.sin(t * 2.5)  # High mids
                self.band_intensities[4] = 0.5 + 0.5 * np.sin(t * 3.0)  # Highs (faster)
                
                # Calculate overall beat intensity (weighted average of bands)
                weights = [0.5, 0.3, 0.1, 0.05, 0.05]  # More weight to bass for beats
                self.beat_intensity = sum(i * w for i, w in zip(self.band_intensities, weights))
                
                # Add some randomness to make it more interesting
                self.beat_intensity = min(1.0, self.beat_intensity * (0.8 + 0.4 * random.random()))
        except Exception as e:
            print(f"Audio analysis error: {e}")
            self.beat_intensity = 0.5  # Default fallback value
            
    def get_snake_head_intensity(self, snake_index=0):
        """Get the intensity level for a snake head based on audio analysis.
        
        Different snakes can respond to different frequency bands.
        """
        if not self.initialized or not self.is_playing:
            return 0.5  # Default medium intensity when not playing
            
        # Use different frequency bands for different snakes
        band_index = snake_index % len(self.band_intensities)
        return self.band_intensities[band_index]
        
    def show_audio_menu(self):
        """Show the audio settings menu."""
        # Store original settings in case user cancels
        original_volume = self.volume
        original_auto_play = self.auto_play
        original_show_track_info = self.show_track_info
        original_play_on_start = self.play_on_start
        
        # Get curses module from the game
        curses = self.game.curses
        
        # Variables for menu navigation
        current_selection = 0
        in_audio_menu = True
        
        # Refresh playlist
        self.refresh_playlist()
        
        # Menu options
        menu_options = [
            f"Volume: {int(self.volume * 100)}%",
            f"Auto-Play: {'Yes' if self.auto_play else 'No'}",
            f"Play on Start: {'Yes' if self.play_on_start else 'No'}",
            f"Show Track Info: {'Yes' if self.show_track_info else 'No'}",
            f"{'Pause' if self.is_playing else 'Play'}",
            "Play Next Track",
            "Play Previous Track",
            "Play Random Track",
            "Refresh Playlist",
            f"Tracks: {len(self.playlist)}",
            "Back"
        ]
        
        # Handle menu input
        while in_audio_menu:
            # Clear the screen
            self.game.screen.clear()
            
            # Draw menu title
            self.game.screen.addstr(2, 2, "Audio Settings", curses.A_BOLD)
            
            # Draw menu options
            for i, option in enumerate(menu_options):
                y = 4 + i
                x = 4
                
                if i == current_selection:
                    self.game.screen.addstr(y, x, f"> {option} <", self.game.selected_menu_color)
                else:
                    self.game.screen.addstr(y, x, f"  {option}  ", self.game.menu_color)
                    
            # Draw current track info
            if self.current_track:
                track_name = os.path.basename(self.current_track)
                self.game.screen.addstr(4 + len(menu_options) + 2, 4, f"Now Playing: {track_name}", curses.A_BOLD)
                
            # Refresh the screen
            self.game.screen.refresh()
            
            # Get user input
            key = self.game.screen.getch()
            
            if key == curses.KEY_UP:
                current_selection = (current_selection - 1) % len(menu_options)
            elif key == curses.KEY_DOWN:
                current_selection = (current_selection + 1) % len(menu_options)
            elif key == 10:  # Enter key
                if current_selection == 0:  # Volume
                    # Cycle through volume levels (0%, 25%, 50%, 75%, 100%)
                    volumes = [0.0, 0.25, 0.5, 0.75, 1.0]
                    current_vol_idx = volumes.index(min(volumes, key=lambda x: abs(x - self.volume)))
                    next_vol_idx = (current_vol_idx + 1) % len(volumes)
                    self.set_volume(volumes[next_vol_idx])
                    menu_options[0] = f"Volume: {int(self.volume * 100)}%"
                elif current_selection == 1:  # Auto-Play
                    self.auto_play = not self.auto_play
                    menu_options[1] = f"Auto-Play: {'Yes' if self.auto_play else 'No'}"
                elif current_selection == 2:  # Play on Start
                    self.play_on_start = not self.play_on_start
                    menu_options[2] = f"Play on Start: {'Yes' if self.play_on_start else 'No'}"
                elif current_selection == 3:  # Show Track Info
                    self.show_track_info = not self.show_track_info
                    menu_options[3] = f"Show Track Info: {'Yes' if self.show_track_info else 'No'}"
                elif current_selection == 4:  # Play/Pause
                    if self.is_playing:
                        self.pause()
                    else:
                        if self.current_track and os.path.exists(self.current_track):
                            self.play(self.current_track)
                        else:
                            self.play_random()
                    menu_options[4] = f"{'Pause' if self.is_playing else 'Play'}"
                elif current_selection == 5:  # Play Next Track
                    self.play_next_track()
                    menu_options[4] = "Pause" if self.is_playing else "Play"
                elif current_selection == 6:  # Play Previous Track
                    self.play_previous_track()
                    menu_options[4] = "Pause" if self.is_playing else "Play"
                elif current_selection == 7:  # Play Random
                    self.play_random()
                    menu_options[4] = "Pause" if self.is_playing else "Play"
                elif current_selection == 8:  # Refresh Playlist
                    self.refresh_playlist()
                    menu_options[9] = f"Tracks: {len(self.playlist)}"
                elif current_selection == 10:  # Back
                    # Save settings
                    self.save_settings()
                    in_audio_menu = False
            elif key == 27:  # Escape key
                # Restore original settings
                self.volume = original_volume
                self.auto_play = original_auto_play
                self.show_track_info = original_show_track_info
                self.play_on_start = original_play_on_start
                if self.initialized:
                    pygame.mixer.music.set_volume(self.volume)
                in_audio_menu = False
                
        # Force redraw
        self.game.needs_redraw = True
        
    def load_settings(self):
        """Load audio settings from a file."""
        try:
            import json
            if os.path.exists("audio_settings.json"):
                with open("audio_settings.json", "r") as f:
                    settings = json.load(f)
                    self.volume = settings.get("volume", 0.5)
                    self.auto_play = settings.get("auto_play", True)
                    self.show_track_info = settings.get("show_track_info", True)
                    self.play_on_start = settings.get("play_on_start", True)
                    self.last_played_track = settings.get("last_played_track", None)
                    
                    # Validate last_played_track exists
                    if self.last_played_track and not os.path.exists(self.last_played_track):
                        self.last_played_track = None
        except:
            # Use default settings if file doesn't exist or is invalid
            pass
            
    def save_settings(self):
        """Save audio settings to a file."""
        try:
            import json
            settings = {
                "volume": self.volume,
                "auto_play": self.auto_play,
                "show_track_info": self.show_track_info,
                "play_on_start": self.play_on_start,
                "last_played_track": self.current_track
            }
            with open("audio_settings.json", "w") as f:
                json.dump(settings, f)
        except:
            # Ignore errors if the file can't be written
            pass

    def play_next_track(self):
        """Play the next track in the playlist or start from the beginning."""
        if not self.playlist:
            self.game.message = "No tracks available"
            self.game.message_timeout = 3.0
            return
            
        if not self.current_track:
            # No current track, play the first one
            self.play(self.playlist[0])
            return
            
        try:
            # Find the current track in the playlist
            current_index = self.playlist.index(self.current_track)
            # Get the next track (or loop back to the beginning)
            next_index = (current_index + 1) % len(self.playlist)
            next_track = self.playlist[next_index]
            
            # Play the next track
            self.play(next_track)
            
            # Show a message
            track_name = os.path.basename(next_track)
            self.game.message = f"Playing: {track_name}"
            self.game.message_timeout = 3.0
            self.track_info_timeout = 5.0
        except ValueError:
            # Current track not in playlist, play a random one
            self.play_random()

    def play_previous_track(self):
        """Play the previous track in the playlist or play the last track if at the beginning."""
        if not self.playlist:
            self.game.message = "No tracks available"
            self.game.message_timeout = 3.0
            return
            
        if not self.current_track:
            # No current track, play the last one in the playlist
            self.play(self.playlist[-1])
            return
            
        try:
            # Find the current track in the playlist
            current_index = self.playlist.index(self.current_track)
            # Get the previous track (or loop back to the end)
            prev_index = (current_index - 1) % len(self.playlist)
            prev_track = self.playlist[prev_index]
            
            # Play the previous track
            self.play(prev_track)
            
            # Show a message
            track_name = os.path.basename(prev_track)
            self.game.message = f"Playing: {track_name}"
            self.game.message_timeout = 3.0
            self.track_info_timeout = 5.0
        except ValueError:
            # Current track not in playlist, play a random one
            self.play_random()
