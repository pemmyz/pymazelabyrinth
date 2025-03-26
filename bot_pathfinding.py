from collections import deque
import heapq

def neighbors(cell, maze):
    # Only allow cells that are floor (' ') or the exit ('E').
    x, y = cell
    potential = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    valid = []
    rows = len(maze)
    cols = len(maze[0])
    for nx, ny in potential:
        if 0 <= nx < cols and 0 <= ny < rows:
            if maze[ny][nx] in (' ', 'E'):
                valid.append((nx, ny))
    return valid

def bfs_path(start, goal, maze):
    queue = deque([start])
    came_from = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        for n in neighbors(current, maze):
            if n not in came_from:
                came_from[n] = current
                queue.append(n)
    return []  # No path found

def bfs_path_no_exit(start, goal, maze, exit_cell):
    """
    BFS that avoids passing through the exit cell if the goal is not the exit.
    """
    queue = deque([start])
    came_from = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        for n in neighbors(current, maze):
            if n == exit_cell and goal != exit_cell:
                continue  # Skip the exit if not the target.
            if n not in came_from:
                came_from[n] = current
                queue.append(n)
    return []

def find_exit_bfs(player_pos, maze):
    start = (int(player_pos.x), int(player_pos.z))
    exit_cell = None
    rows = len(maze)
    cols = len(maze[0])
    for y in range(rows):
        for x in range(cols):
            if maze[y][x] == "E":
                exit_cell = (x, y)
                break
        if exit_cell is not None:
            break
    if exit_cell is None:
        return []
    return bfs_path(start, exit_cell, maze)

def find_exit_dfs(player_pos, maze):
    start = (int(player_pos.x), int(player_pos.z))
    exit_cell = None
    rows = len(maze)
    cols = len(maze[0])
    for y in range(rows):
        for x in range(cols):
            if maze[y][x] == "E":
                exit_cell = (x, y)
                break
        if exit_cell is not None:
            break
    if exit_cell is None:
        return []
    stack = [start]
    came_from = {start: None}
    while stack:
        current = stack.pop()
        if current == exit_cell:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
        for n in neighbors(current, maze):
            if n not in came_from:
                came_from[n] = current
                stack.append(n)
    return []

def heuristic(a, b):
    # Manhattan distance.
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def find_exit_astar(player_pos, maze):
    start = (int(player_pos.x), int(player_pos.z))
    exit_cell = None
    rows = len(maze)
    cols = len(maze[0])
    for y in range(rows):
        for x in range(cols):
            if maze[y][x] == "E":
                exit_cell = (x, y)
                break
        if exit_cell is not None:
            break
    if exit_cell is None:
        return []
    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}
    while frontier:
        current_priority, current = heapq.heappop(frontier)
        if current == exit_cell:
            break
        for n in neighbors(current, maze):
            new_cost = cost_so_far[current] + 1
            if n not in cost_so_far or new_cost < cost_so_far[n]:
                cost_so_far[n] = new_cost
                priority = new_cost + heuristic(n, exit_cell)
                heapq.heappush(frontier, (priority, n))
                came_from[n] = current
    if exit_cell not in came_from:
        return []
    path = []
    current = exit_cell
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path

def cell_in_room(cell, room):
    """
    Helper to determine if a given cell (x, y) is inside a room.
    Assumes room has attributes x1, y1 (inclusive) and x2, y2 (exclusive).
    """
    x, y = cell
    return room.x1 <= x < room.x2 and room.y1 <= y < room.y2

def find_exit_explore(player_pos, maze, rooms):
    """
    Exploration mode: visit all room centers before heading to the exit.
    """
    start = (int(player_pos.x), int(player_pos.z))
    exit_cell = None
    rows = len(maze)
    cols = len(maze[0])
    for y in range(rows):
        for x in range(cols):
            if maze[y][x] == "E":
                exit_cell = (x, y)
                break
        if exit_cell is not None:
            break
    if exit_cell is None:
        return []
    
    # Identify the room that contains the exit.
    exit_room = None
    for room in rooms:
        if cell_in_room(exit_cell, room):
            exit_room = room
            break

    # Collect centers of all rooms.
    exit_room_center = None
    other_room_centers = []
    for room in rooms:
        center = (int(room.center[0]), int(room.center[1]))
        if room == exit_room:
            exit_room_center = center
        else:
            other_room_centers.append(center)
    other_room_centers = list(set(other_room_centers))
    
    overall_path = []
    current = start

    # If the exit room center exists and is more than 1 cell away, go there first.
    if exit_room_center is not None and heuristic(start, exit_room_center) > 1:
        segment = bfs_path_no_exit(current, exit_room_center, maze, exit_cell)
        if not segment:
            segment = bfs_path(current, exit_room_center, maze)
        overall_path.extend(segment)
        current = exit_room_center
    else:
        if exit_room_center is not None and exit_room_center not in other_room_centers:
            other_room_centers.append(exit_room_center)
            exit_room_center = None

    # Explore all other room centers.
    while other_room_centers:
        if exit_room is not None and cell_in_room(current, exit_room) and heuristic(current, exit_cell) <= 1:
            other_room_centers.sort(key=lambda p: heuristic(p, exit_cell), reverse=True)
        else:
            other_room_centers.sort(key=lambda p: heuristic(current, p))
        target = other_room_centers.pop(0)
        segment = bfs_path(current, target, maze)
        if segment:
            if overall_path and segment[0] == overall_path[-1]:
                overall_path.extend(segment[1:])
            else:
                overall_path.extend(segment)
            current = target

    # Finally, go from last visited room to the exit.
    segment = bfs_path(current, exit_cell, maze)
    if segment:
        if overall_path and segment[0] == overall_path[-1]:
            overall_path.extend(segment[1:])
        else:
            overall_path.extend(segment)
    return overall_path

if __name__ == "__main__":
    # Simple test for A* on a small maze.
    class DummyPos:
        def __init__(self, x, z):
            self.x = x
            self.z = z
    maze = [
        "##########",
        "#   #    #",
        "# ## # ##E",
        "#    #   #",
        "##########"
    ]
    dummy_pos = DummyPos(1, 1)
    path = find_exit_astar(dummy_pos, maze)
    print("Path to exit:", path)
