def render_scene(self):
    """Render the scene using pygame."""
    try:
        # Fill the screen with black
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))
        
        # Draw title
        title = self.font.render("TextWarp Snake Visualization", True, (255, 255, 255))
        screen.blit(title, (10, 10))
        
        # Draw snake count
        snake_count = len(self.snakes)
        snakes_text = self.font.render(f"Snakes Detected: {snake_count}", True, (255, 255, 0))
        screen.blit(snakes_text, (10, 40))
        
        # Draw controls info
        controls_text = self.font.render("Controls: WASD=Move, ESC=Exit, F11=Fullscreen", True, (200, 200, 200))
        screen.blit(controls_text, (10, 70))
        
        # Draw snake information
        if self.snakes:
            y_pos = 100
            screen.blit(self.font.render("Snake Information:", True, (255, 255, 255)), (self.width - 300, y_pos))
            y_pos += 30
            
            for i, snake in enumerate(self.snakes):
                if i >= 5:  # Limit to 5 snakes to avoid cluttering
                    break
                    
                # Get snake position (head)
                if snake:
                    head = snake[0]
                    x, y, z = head["x"], head["y"], head["z"]
                    length = len(snake)
                    
                    # Determine snake type based on characters
                    snake_type = "Unknown"
                    for segment in snake:
                        char = segment["char"]
                        if char == "^":
                            snake_type = "Viper"
                            break
                        elif char == "~":
                            snake_type = "Python"
                            break
                        elif char == "*":
                            snake_type = "Rattlesnake"
                            break
                    
                    # Draw snake info
                    pos_text = self.font.render(f"Snake {i+1}: ({x}, {z})", True, (255, 255, 255))
                    len_text = self.font.render(f"Length: {length}", True, (255, 255, 255))
                    type_text = self.font.render(f"Type: {snake_type}", True, (255, 255, 255))
                    
                    screen.blit(pos_text, (self.width - 300, y_pos))
                    screen.blit(len_text, (self.width - 300, y_pos + 20))
                    screen.blit(type_text, (self.width - 300, y_pos + 40))
                    y_pos += 70
        
        # Draw a map
        map_width = 300
        map_height = 300
        map_x = self.width - map_width - 10
        map_y = self.height - map_height - 10
        
        # Draw map background
        pygame.draw.rect(screen, (20, 20, 20), (map_x, map_y, map_width, map_height))
        pygame.draw.rect(screen, (50, 50, 50), (map_x, map_y, map_width, map_height), 2)
        
        # Draw grid lines
        grid_step = 20
        for i in range(0, map_width, grid_step):
            # Vertical lines
            pygame.draw.line(screen, (40, 40, 40), (map_x + i, map_y), (map_x + i, map_y + map_height))
            # Horizontal lines
            pygame.draw.line(screen, (40, 40, 40), (map_x, map_y + i), (map_x + map_width, map_y + i))
        
        # Draw center point (player position)
        center_x = map_x + map_width // 2
        center_y = map_y + map_height // 2
        pygame.draw.circle(screen, (0, 255, 0), (center_x, center_y), 5)
        
        # Draw characters
        with self.lock:
            for row in self.character_map:
                for char_info in row:
                    if char_info is not None and not char_info["is_snake"]:
                        # Calculate position on map
                        x = center_x + char_info["x"] * 5
                        y = center_y + char_info["z"] * 5
                        
                        # Skip if outside map
                        if x < map_x or x > map_x + map_width or y < map_y or y > map_y + map_height:
                            continue
                        
                        # Draw character
                        color = (200, 200, 200)  # Default color
                        pygame.draw.circle(screen, color, (int(x), int(y)), 2)
        
        # Draw snakes
        with self.lock:
            for snake in self.snakes:
                for i, segment in enumerate(snake):
                    # Calculate position on map
                    x = center_x + segment["x"] * 5
                    y = center_y + segment["z"] * 5
                    
                    # Skip if outside map
                    if x < map_x or x > map_x + map_width or y < map_y or y > map_y + map_height:
                        continue
                    
                    # Draw snake segment with different colors for head, body, and tail
                    if i == 0:  # Head
                        color = (0, 255, 0)  # Green
                        size = 4
                    elif i == len(snake) - 1:  # Tail
                        color = (255, 0, 0)  # Red
                        size = 3
                    else:  # Body
                        color = (0, 0, 255)  # Blue
                        size = 3
                        
                    pygame.draw.circle(screen, color, (int(x), int(y)), size)
                    
                    # Draw line connecting segments
                    if i > 0:
                        prev_segment = snake[i-1]
                        prev_x = center_x + prev_segment["x"] * 5
                        prev_y = center_y + prev_segment["z"] * 5
                        
                        pygame.draw.line(screen, (100, 100, 100), (prev_x, prev_y), (x, y), 1)
        
        # Update the display
        pygame.display.flip()
        
    except Exception as e:
        self.add_debug_message(f"Error rendering scene: {str(e)}")
        traceback.print_exc()
