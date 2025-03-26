#!/usr/bin/env python3
import random
from collections import deque

# A simple class representing a rectangular room.
class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
        # Compute the center of the room.
        self.center = ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def intersect(self, other):
        # Allow rooms that touch (strict inequality).
        return (self.x1 < other.x2 and self.x2 > other.x1 and
                self.y1 < other.y2 and self.y2 > other.y1)

def create_map(width, height, max_rooms, room_min_size, room_max_size, seed=None):
    """
    Creates a dungeon map as a list of strings and returns a list of rooms.
    
    - Open spaces (rooms and corridors) are ' '.
    - Walls that are immediately adjacent to a room or corridor remain '#'.
    - Other wall cells become 'B' (for black).
    - The exit is marked with an 'E'.
    
    Additionally, if the last generated room is smaller than 6x6,
    the generator will attempt to add one extra room with minimum size 6x6
    so that the exit is always located in a room of at least 6x6.
    """
    if seed is not None:
        print("Creating map with seed:", seed)
        # Do not re-seed here if you want external control over randomness.
        # random.seed(seed)

    # Initialize the map filled with walls ('#').
    map_grid = [['#' for _ in range(width)] for _ in range(height)]
    rooms = []

    # Generate up to max_rooms random rooms.
    for _ in range(max_rooms):
        # Random room size.
        w = random.randint(room_min_size, room_max_size)
        h = random.randint(room_min_size, room_max_size)
        # Random position within bounds (leaving a 1-cell border).
        x = random.randint(1, width - w - 1)
        y = random.randint(1, height - h - 1)
        new_room = Rect(x, y, w, h)
        
        # Check for intersection with any existing room.
        if any(new_room.intersect(other) for other in rooms):
            continue  # Skip this room if it overlaps.
        
        # "Carve" out this room in the map grid.
        for i in range(new_room.y1, new_room.y2):
            for j in range(new_room.x1, new_room.x2):
                map_grid[i][j] = ' '
        
        # Connect this room to the previous room with corridors.
        if rooms:
            (prev_x, prev_y) = rooms[-1].center
            (new_x, new_y) = new_room.center
            if random.randint(0, 1):
                # Horizontal corridor.
                for x_corr in range(min(prev_x, new_x), max(prev_x, new_x) + 1):
                    map_grid[prev_y][x_corr] = ' '
                # Vertical corridor.
                for y_corr in range(min(prev_y, new_y), max(prev_y, new_y) + 1):
                    map_grid[y_corr][new_x] = ' '
            else:
                # Vertical corridor.
                for y_corr in range(min(prev_y, new_y), max(prev_y, new_y) + 1):
                    map_grid[y_corr][prev_x] = ' '
                # Horizontal corridor.
                for x_corr in range(min(prev_x, new_x), max(prev_x, new_x) + 1):
                    map_grid[new_y][x_corr] = ' '
        
        rooms.append(new_room)
    
    # If the last room is smaller than 6x6, attempt to add an extra room with minimum size 6x6.
    if rooms:
        last_room = rooms[-1]
        room_w = last_room.x2 - last_room.x1
        room_h = last_room.y2 - last_room.y1
        if room_w < 6 or room_h < 6:
            for _ in range(100):
                w = 6
                h = 6
                x = random.randint(1, width - w - 1)
                y = random.randint(1, height - h - 1)
                new_room = Rect(x, y, w, h)
                if not any(new_room.intersect(other) for other in rooms):
                    for i in range(new_room.y1, new_room.y2):
                        for j in range(new_room.x1, new_room.x2):
                            map_grid[i][j] = ' '
                    rooms.append(new_room)
                    last_room = new_room
                    break

    # Mark the exit in the last room.
    if rooms:
        last_room = rooms[-1]
        room_w = last_room.x2 - last_room.x1
        room_h = last_room.y2 - last_room.y1
        if room_w >= 6 and room_h >= 6:
            candidates = [
                (last_room.x1 + 1, last_room.y1 + 1),
                (last_room.x2 - 2, last_room.y1 + 1),
                (last_room.x1 + 1, last_room.y2 - 2),
                (last_room.x2 - 2, last_room.y2 - 2)
            ]
            center = last_room.center
            exit_x, exit_y = max(candidates, key=lambda cell: abs(cell[0]-center[0]) + abs(cell[1]-center[1]))
        else:
            candidates = []
            if room_h > 2:
                for x in range(last_room.x1+1, last_room.x2-1):
                    candidates.append((x, last_room.y1+1))
                    candidates.append((x, last_room.y2-2))
            if room_w > 2:
                for y in range(last_room.y1+1, last_room.y2-1):
                    candidates.append((last_room.x1+1, y))
                    candidates.append((last_room.x2-2, y))
            if not candidates:
                exit_x, exit_y = last_room.center
            else:
                center = last_room.center
                exit_x, exit_y = min(candidates, key=lambda cell: abs(cell[0]-center[0]) + abs(cell[1]-center[1]))
        map_grid[exit_y][exit_x] = 'E'
    
    # Convert wall cells: keep as '#' only if adjacent to an open cell (' ' or 'E'); otherwise, mark as 'B'.
    for i in range(height):
        for j in range(width):
            if map_grid[i][j] == '#':
                # Check the four cardinal neighbors.
                adjacent = False
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = j + dx, i + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if map_grid[ny][nx] in (' ', 'E'):
                            adjacent = True
                            break
                if not adjacent:
                    map_grid[i][j] = 'B'
    
    maze = [''.join(row) for row in map_grid]
    return maze, rooms

def find_nearest_floor(x, y, maze):
    """
    A simple BFS to locate the nearest floor cell (one that is either ' ' or 'E').
    """
    rows = len(maze)
    cols = len(maze[0])
    queue = deque([(x, y)])
    visited = {(x, y)}
    while queue:
        cx, cy = queue.popleft()
        if maze[cy][cx] in (' ', 'E'):
            return cx, cy
        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
    return x, y  # Fallback if no floor found

def main():
    # Map parameters.
    width = 40
    height = 20
    max_rooms = 10
    room_min_size = 3
    room_max_size = 7
    seed = 42  # Fixed seed for testing.
    maze, rooms = create_map(width, height, max_rooms, room_min_size, room_max_size, seed)
    
    # Print the generated maze.
    for row in maze:
        print(row)
    
    # Determine a spawn location.
    # We'll try to use the center of the first room.
    if rooms:
        spawn_x, spawn_y = rooms[0].center
    else:
        spawn_x, spawn_y = (width // 2, height // 2)
    
    # Ensure the spawn is not in a wall (#) or black (B) area.
    if maze[spawn_y][spawn_x] not in (' ', 'E'):
        spawn_x, spawn_y = find_nearest_floor(spawn_x, spawn_y, maze)
    
    print("\nPlayer spawn location:", (spawn_x, spawn_y))

if __name__ == "__main__":
    main()
