#!/usr/bin/env python3
#First version on github!!!
import random
import nethack_map_generator  # Ensure this file is in the same directory.
import bot_pathfinding
import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import numpy as np
import glm
from PIL import Image
import math
import ctypes
import sys
import time
from collections import deque

# --- Global Variables for 3D Maze Geometry ---
floor_vbo = None
floor_vertex_count = 0
ceiling_vbo = None
ceiling_vertex_count = 0
wall_brick_vbo = None
wall_brick_vertex_count = 0
wall_exit_vbo = None
wall_exit_vertex_count = 0

# --- Maze Data from nethack_map_generator ---
maze = []      # Maze is a list of strings (each cell is a character)
rooms = []

# --- Player State (player_pos.x = column, player_pos.z = row) ---
player_pos = None
player_angle_deg = 0
is_moving = False
start_pos = None
target_pos = None
move_progress = 0.0
move_duration = 0.2
is_turning = False
start_angle = 0.0
target_angle = 0.0
turn_progress = 0.0
turn_duration = 0.15  # Duration for turning

# --- Full Map Toggle State ---
show_full_map = False
m_toggle_pressed = False

# --- Help Toggle State (always on at startup) ---
show_help = True
h_toggle_pressed = False

# --- Pause State ---
paused = False
p_toggle_pressed = False

# --- Discovery Globals ---
discovery_range = 1  # cells around the player that become discovered (3x3 area)
discovered = []      # 2D boolean array; same dimensions as maze

# --- Corridor Discovery Depth Variable ---
max_corridor_discovery_depth = 20  # maximum number of cells ahead to reveal in a corridor

# --- Bot Variables ---
bot_mode = False
b_toggle_pressed = False
selected_algorithm = "bfs"  # Options: "bfs", "dfs", "astar", "explore"
bot_path = []
bot_path_index = 0
unstuck_mode = False
unstuck_attempts = 0

# --- Map Panning Globals for Full Map Overlay ---
full_map_offset_x = 0
full_map_offset_y = 0
full_map_dragging = False
full_map_panned = False  # Indicates if user has manually panned the full map.
prev_mouse_x = 0
prev_mouse_y = 0

# --- Helper: Compute the Largest Connected Component (LCC) of floor cells ---
def compute_largest_component(maze):
    rows = len(maze)
    cols = len(maze[0])
    visited = [[False]*cols for _ in range(rows)]
    largest = set()
    for y in range(rows):
        for x in range(cols):
            if maze[y][x] == ' ' and not visited[y][x]:
                comp = set()
                queue = deque()
                queue.append((x, y))
                visited[y][x] = True
                while queue:
                    cx, cy = queue.popleft()
                    comp.add((cx, cy))
                    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                        nx, ny = cx+dx, cy+dy
                        if 0 <= nx < cols and 0 <= ny < rows and not visited[ny][nx] and maze[ny][nx] == ' ':
                            visited[ny][nx] = True
                            queue.append((nx, ny))
                if len(comp) > len(largest):
                    largest = comp
    return largest

# --- Helper: Find the nearest valid floor cell using BFS ---
def find_nearest_floor(x, y, maze):
    rows = len(maze)
    cols = len(maze[0])
    queue = deque()
    queue.append((x, y))
    visited = set()
    visited.add((x, y))
    while queue:
        cx, cy = queue.popleft()
        if maze[cy][cx] == ' ':
            return cx, cy
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
    return x, y  # fallback

# --- Helper: Determine area type (room vs. corridor) ---
def get_area_type(x, y, rooms):
    for room in rooms:
        if room.x1 <= x < room.x2 and room.y1 <= y < room.y2:
            return "room"
    return "corridor"

# --- Texture Loading (for 3D view) ---
def load_texture(path):
    try:
        img = Image.open(path).transpose(Image.FLIP_TOP_BOTTOM)
    except Exception as e:
        print("Error loading texture:", e)
        sys.exit(1)
    img_data = img.convert("RGB").tobytes()
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0,
                 GL_RGB, GL_UNSIGNED_BYTE, img_data)
    return tex

# --- Mouse Callbacks for Full Map Panning ---
def mouse_button_callback(window, button, action, mods):
    global full_map_dragging, prev_mouse_x, prev_mouse_y, full_map_panned
    if button == glfw.MOUSE_BUTTON_LEFT and show_full_map:
        if action == glfw.PRESS:
            full_map_dragging = True
            full_map_panned = True
            prev_mouse_x, prev_mouse_y = glfw.get_cursor_pos(window)
        elif action == glfw.RELEASE:
            full_map_dragging = False

def cursor_position_callback(window, xpos, ypos):
    global full_map_dragging, prev_mouse_x, prev_mouse_y, full_map_offset_x, full_map_offset_y
    if full_map_dragging and show_full_map:
        dx = xpos - prev_mouse_x
        dy = ypos - prev_mouse_y
        full_map_offset_x += dx
        full_map_offset_y -= dy
        prev_mouse_x, prev_mouse_y = xpos, ypos

# --- Build Maze Geometry into Vertex Arrays ---
def build_maze_geometry():
    global maze
    floor_vertices = []
    ceiling_vertices = []
    wall_brick_vertices = []
    wall_exit_vertices = []
    rows = len(maze)
    cols = len(maze[0])
    for z in range(rows):
        for x in range(cols):
            floor_vertices.extend([
                x, 0.0, z,   0.0, 0.0,
                x+1, 0.0, z, 1.0, 0.0,
                x+1, 0.0, z+1, 1.0, 1.0,
                x, 0.0, z,   0.0, 0.0,
                x+1, 0.0, z+1, 1.0, 1.0,
                x, 0.0, z+1, 0.0, 1.0,
            ])
            ceiling_vertices.extend([
                x, 1.0, z,   0.0, 0.0,
                x+1, 1.0, z, 1.0, 0.0,
                x+1, 1.0, z+1, 1.0, 1.0,
                x, 1.0, z,   0.0, 0.0,
                x+1, 1.0, z+1, 1.0, 1.0,
                x, 1.0, z+1, 0.0, 1.0,
            ])
            cell = maze[z][x]
            if cell in "#E":
                if z == 0 or maze[z-1][x] not in "#E":
                    target_list = wall_exit_vertices if cell == "E" else wall_brick_vertices
                    target_list.extend([
                        x, 0.0, z,   0.0, 0.0,
                        x+1, 0.0, z, 1.0, 0.0,
                        x+1, 1.0, z, 1.0, 1.0,
                        x, 0.0, z,   0.0, 0.0,
                        x+1, 1.0, z, 1.0, 1.0,
                        x, 1.0, z,   0.0, 1.0,
                    ])
                if z == len(maze)-1 or maze[z+1][x] not in "#E":
                    target_list = wall_exit_vertices if cell == "E" else wall_brick_vertices
                    target_list.extend([
                        x, 0.0, z+1,   0.0, 0.0,
                        x+1, 0.0, z+1, 1.0, 0.0,
                        x+1, 1.0, z+1, 1.0, 1.0,
                        x, 0.0, z+1,   0.0, 0.0,
                        x+1, 1.0, z+1, 1.0, 1.0,
                        x, 1.0, z+1,   0.0, 1.0,
                    ])
                if x == 0 or maze[z][x-1] not in "#E":
                    target_list = wall_exit_vertices if cell == "E" else wall_brick_vertices
                    target_list.extend([
                        x, 0.0, z,   0.0, 0.0,
                        x, 0.0, z+1, 1.0, 0.0,
                        x, 1.0, z+1, 1.0, 1.0,
                        x, 0.0, z,   0.0, 0.0,
                        x, 1.0, z+1, 1.0, 1.0,
                        x, 1.0, z,   0.0, 1.0,
                    ])
                if x == len(maze[0])-1 or maze[z][x+1] not in "#E":
                    target_list = wall_exit_vertices if cell == "E" else wall_brick_vertices
                    target_list.extend([
                        x+1, 0.0, z,   0.0, 0.0,
                        x+1, 0.0, z+1, 1.0, 0.0,
                        x+1, 1.0, z+1, 1.0, 1.0,
                        x+1, 0.0, z,   0.0, 0.0,
                        x+1, 1.0, z+1, 1.0, 1.0,
                        x+1, 1.0, z,   0.0, 1.0,
                    ])
    return (floor_vertices, ceiling_vertices, wall_brick_vertices, wall_exit_vertices)

# --- Create a VBO from Vertex Data ---
def create_vbo(vertex_data):
    arr = np.array(vertex_data, dtype=np.float32)
    vbo_id = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_STATIC_DRAW)
    glBindBuffer(GL_ARRAY_BUFFER, 0)
    vertex_count = len(vertex_data) // 5
    return vbo_id, vertex_count

# --- Rebuild Geometry VBOs ---
def rebuild_geometry():
    global floor_vbo, floor_vertex_count, ceiling_vbo, ceiling_vertex_count
    global wall_brick_vbo, wall_brick_vertex_count, wall_exit_vbo, wall_exit_vertex_count
    floor_data, ceiling_data, wall_brick_data, wall_exit_data = build_maze_geometry()
    if floor_vbo:
        glDeleteBuffers(1, [floor_vbo])
    floor_vbo, floor_vertex_count = create_vbo(floor_data)
    if ceiling_vbo:
        glDeleteBuffers(1, [ceiling_vbo])
    ceiling_vbo, ceiling_vertex_count = create_vbo(ceiling_data)
    if wall_brick_vbo:
        glDeleteBuffers(1, [wall_brick_vbo])
    wall_brick_vbo, wall_brick_vertex_count = create_vbo(wall_brick_data)
    if wall_exit_vbo:
        glDeleteBuffers(1, [wall_exit_vbo])
    wall_exit_vbo, wall_exit_vertex_count = create_vbo(wall_exit_data)
    print("Geometry rebuilt: floor =", floor_vertex_count, "walls =", wall_brick_vertex_count + wall_exit_vertex_count)

# --- Helper Function to Draw Bitmap Text ---
def draw_text(x, y, text):
    glWindowPos2i(int(x), int(y))
    for ch in text:
        glutBitmapCharacter(GLUT_BITMAP_8_BY_13, ord(ch))

# --- Help Overlay ---
def draw_help(window_width, window_height):
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, window_width, 0, window_height, -1, 1)
    
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    help_lines = [
        "Help - Controls:",
        "W: Move forward",
        "S: Move backward",
        "A: Turn left",
        "D: Turn right",
        "P: Pause/Unpause",
        "M: Toggle full map (auto-centers on player when opened)",
        "B: Toggle bot mode",
        "1: Select BFS pathfinding",
        "2: Select DFS pathfinding",
        "3: Select A* pathfinding",
        "4: Select EXPLORE mode (visit all rooms then exit)",
        "H: Toggle help screen (always on at start)",
        "R: Reset game",
        "Esc: Exit game",
        "Mouse Button 1 + Drag (when full map open): Pan the map"
    ]
    x = 20
    y = window_height - 20
    glColor3f(1, 1, 1)
    for line in help_lines:
        draw_text(x, y, line)
        y -= 15
    
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

# --- Full Map Overlay ---
def draw_full_map(window_width, window_height):
    global full_map_offset_x, full_map_offset_y
    if not full_map_panned:
        cell_size = 12
        cols = len(maze[0])
        rows = len(maze)
        map_width = cols * cell_size
        map_height = rows * cell_size
        player_cell_x = int(player_pos.x)
        player_cell_z = int(player_pos.z)
        full_map_offset_x = (map_width) / 2 - (player_cell_x * cell_size + cell_size/2)
        full_map_offset_y = (map_height) / 2 - (((rows - 1 - player_cell_z) * cell_size) + cell_size/2)
    
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, window_width, 0, window_height, -1, 1)
    
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    cell_size = 12
    rows = len(maze)
    cols = len(maze[0])
    map_width = cols * cell_size
    map_height = rows * cell_size
    start_x = (window_width - map_width) / 2 + full_map_offset_x
    start_y = (window_height - map_height) / 2 + full_map_offset_y
    
    glColor3f(0, 0, 0)
    glBegin(GL_QUADS)
    glVertex2f(start_x - 2, start_y - 2)
    glVertex2f(start_x + map_width + 2, start_y - 2)
    glVertex2f(start_x + map_width + 2, start_y + map_height + 2)
    glVertex2f(start_x - 2, start_y + map_height + 2)
    glEnd()
    
    for i in range(rows):
        for j in range(cols):
            x = start_x + j * cell_size
            y = start_y + (rows - 1 - i) * cell_size
            if discovered[i][j]:
                cell = maze[i][j]
                if cell == "#":
                    glColor3f(0.3, 0.3, 0.3)
                elif cell == "E":
                    glColor3f(1, 0, 0)
                else:
                    glColor3f(1, 1, 1)
            else:
                glColor3f(0, 0, 0)
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + cell_size, y)
            glVertex2f(x + cell_size, y + cell_size)
            glVertex2f(x, y + cell_size)
            glEnd()
    
    player_cell_x = int(player_pos.x)
    player_cell_z = int(player_pos.z)
    x = start_x + player_cell_x * cell_size
    y = start_y + (rows - 1 - player_cell_z) * cell_size
    blink = (int(glfw.get_time() * 2) % 2 == 0)
    if blink:
        glColor3f(0, 1, 0)
        draw_text(x, y, "@")
    
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

# --- Minimap Overlay ---
def draw_minimap(window_width, window_height):
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, window_width, 0, window_height, -1, 1)
    
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    region_size = 12
    cell_size = 8
    player_cell_x = int(player_pos.x)
    player_cell_z = int(player_pos.z)
    start_cell_x = player_cell_x - region_size // 2
    start_cell_z = player_cell_z - region_size // 2
    
    map_width_pixels = region_size * cell_size
    map_height_pixels = region_size * cell_size
    margin = 10
    start_x = window_width - map_width_pixels - margin
    start_y = margin
    
    glColor3f(0, 0, 0)
    glBegin(GL_QUADS)
    glVertex2f(start_x - 2, start_y - 2)
    glVertex2f(start_x + map_width_pixels + 2, start_y - 2)
    glVertex2f(start_x + map_width_pixels + 2, start_y + map_height_pixels + 2)
    glVertex2f(start_x - 2, start_y + map_height_pixels + 2)
    glEnd()
    
    rows = len(maze)
    cols = len(maze[0])
    for i in range(region_size):
        for j in range(region_size):
            maze_i = start_cell_z + i
            maze_j = start_cell_x + j
            if maze_i < 0 or maze_i >= rows or maze_j < 0 or maze_j >= cols:
                continue
            x = start_x + j * cell_size
            y = start_y + (region_size - 1 - i) * cell_size
            if discovered[maze_i][maze_j]:
                cell = maze[maze_i][maze_j]
                if cell == "#":
                    glColor3f(0.3, 0.3, 0.3)
                elif cell == "E":
                    glColor3f(1, 0, 0)
                else:
                    glColor3f(1, 1, 1)
            else:
                glColor3f(0, 0, 0)
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + cell_size, y)
            glVertex2f(x + cell_size, y + cell_size)
            glVertex2f(x, y + cell_size)
            glEnd()
    
    center_x = start_x + (region_size // 2) * cell_size
    center_y = start_y + (region_size // 2) * cell_size - cell_size
    blink = (int(glfw.get_time() * 2) % 2 == 0)
    if blink:
        glColor3f(0, 1, 0)
        draw_text(center_x, center_y, "@")
    
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

# --- 3D Collision Check ---
def is_collision(x, z):
    maze_x, maze_z = int(x), int(z)
    return maze[maze_z][maze_x] == "#"

# --- Main Game Loop ---
def main():
    global maze, rooms, player_pos
    global player_angle_deg, is_moving, start_pos, target_pos, move_progress
    global is_turning, start_angle, target_angle, turn_progress, turn_duration
    global show_full_map, m_toggle_pressed, discovered
    global bot_mode, b_toggle_pressed, selected_algorithm, bot_path, bot_path_index
    global show_help, h_toggle_pressed, paused, p_toggle_pressed
    global full_map_offset_x, full_map_offset_y, full_map_panned
    global unstuck_mode, unstuck_attempts

    reset_requested = False
    exit_requested = False

    # Generate a new random seed between 1 and 99 for each new map.
    initial_seed = random.randint(1, 99)
    print("Initial seed:", initial_seed)
    maze, rooms = nethack_map_generator.create_map(
        width=100,
        height=100,
        max_rooms=40,
        room_min_size=3,
        room_max_size=7,
        seed=initial_seed
    )
    for row in maze[:5]:
        print(row)
    
    rows = len(maze)
    cols = len(maze[0])
    discovered = [[False for _ in range(cols)] for _ in range(rows)]
    
    # --- Modified Player Spawn Logic: Spawn inside a room
    if rooms:
        # Avoid the exit room if possible.
        if len(rooms) > 1:
            candidate_rooms = rooms[:-1]
        else:
            candidate_rooms = rooms
        chosen_room = random.choice(candidate_rooms)
        # Choose an inner candidate so that on at least one axis walls are close.
        if (chosen_room.x2 - chosen_room.x1) > 2 and (chosen_room.y2 - chosen_room.y1) > 2:
            inner_candidates = [
                (chosen_room.x1 + 1, chosen_room.y1 + 1),
                (chosen_room.x2 - 2, chosen_room.y1 + 1),
                (chosen_room.x1 + 1, chosen_room.y2 - 2),
                (chosen_room.x2 - 2, chosen_room.y2 - 2)
            ]
            spawn_x, spawn_y = random.choice(inner_candidates)
        else:
            spawn_x, spawn_y = chosen_room.center
    else:
        spawn_x, spawn_y = (cols // 2, rows // 2)
    
    # Safety check.
    if maze[spawn_y][spawn_x] != ' ':
        spawn_x, spawn_y = find_nearest_floor(spawn_x, spawn_y, maze)
    
    player_pos = glm.vec3(spawn_x + 0.5, 0.0, spawn_y + 0.5)
    area_type = get_area_type(spawn_x, spawn_y, rooms)
    print(f"Player starting cell: ({spawn_x}, {spawn_y}) is in a {area_type}.")
    print("Maze cell at player:", maze[int(player_pos.z)][int(player_pos.x)])
    
    if not glfw.init():
        return False
    window = glfw.create_window(800, 600, "Brick Labyrinth", None, None)
    if not window:
        glfw.terminate()
        return False
    glfw.make_context_current(window)
    glutInit()
    glViewport(0, 0, 800, 600)
    glClearColor(0.5, 0.5, 0.5, 1.0)
    
    brick_tex = load_texture("textures/brick.jpg")
    exit_tex = load_texture("textures/exit.jpg")
    ground_tex = load_texture("textures/ground.jpg")
    roof_tex = load_texture("textures/roof.jpg")
    
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glDisable(GL_CULL_FACE)
    
    rebuild_geometry()
    
    # --- Bot Initialization with Pause ---
    # If bot mode was enabled, pause for 3 seconds before resuming bot mode.
    if bot_mode:
        print("Bot mode is enabled. Pausing for 3 seconds before resuming bot pathfinding...")
        time.sleep(3)
        if selected_algorithm == "bfs":
            bot_path = bot_pathfinding.find_exit_bfs(player_pos, maze)
        elif selected_algorithm == "dfs":
            bot_path = bot_pathfinding.find_exit_dfs(player_pos, maze)
        elif selected_algorithm == "astar":
            bot_path = bot_pathfinding.find_exit_astar(player_pos, maze)
        elif selected_algorithm == "explore":
            bot_path = bot_pathfinding.find_exit_explore(player_pos, maze, rooms)
        bot_path_index = 0
        print("Bot mode resumed.")
    
    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_cursor_pos_callback(window, cursor_position_callback)
    
    last_time = glfw.get_time()
    
    full_map_offset_x = 0
    full_map_offset_y = 0
    full_map_panned = False

    while not glfw.window_should_close(window):
        now = glfw.get_time()
        delta = now - last_time
        last_time = now

        if glfw.get_key(window, glfw.KEY_P) == glfw.PRESS:
            if not p_toggle_pressed:
                paused = not paused
                p_toggle_pressed = True
                print("Paused" if paused else "Unpaused")
        else:
            p_toggle_pressed = False

        if paused:
            glfw.poll_events()
            glfw.swap_buffers(window)
            continue

        if glfw.get_key(window, glfw.KEY_ESCAPE) == glfw.PRESS:
            print("Exiting game...")
            exit_requested = True
            break

        if glfw.get_key(window, glfw.KEY_M) == glfw.PRESS:
            if not m_toggle_pressed:
                show_full_map = not show_full_map
                m_toggle_pressed = True
                if show_full_map:
                    full_map_panned = False
                    cell_size = 12
                    cols = len(maze[0])
                    rows = len(maze)
                    map_width = cols * cell_size
                    map_height = rows * cell_size
                    player_cell_x = int(player_pos.x)
                    player_cell_z = int(player_pos.z)
                    full_map_offset_x = (map_width)/2 - (player_cell_x * cell_size + cell_size/2)
                    full_map_offset_y = (map_height)/2 - (((rows - 1 - player_cell_z) * cell_size) + cell_size/2)
                else:
                    full_map_offset_x = 0
                    full_map_offset_y = 0
                    full_map_panned = False
                print("Full map toggled", "on" if show_full_map else "off")
        else:
            m_toggle_pressed = False

        if glfw.get_key(window, glfw.KEY_H) == glfw.PRESS:
            if not h_toggle_pressed:
                show_help = not show_help
                h_toggle_pressed = True
                print("Help toggled", "on" if show_help else "off")
        else:
            h_toggle_pressed = False

        if glfw.get_key(window, glfw.KEY_R) == glfw.PRESS:
            if not reset_requested:
                print("Resetting game...")
                reset_requested = True
                break

        if glfw.get_key(window, glfw.KEY_B) == glfw.PRESS:
            if not b_toggle_pressed:
                bot_mode = not bot_mode
                b_toggle_pressed = True
                print("Bot mode", "enabled" if bot_mode else "disabled")
                if bot_mode:
                    if selected_algorithm == "bfs":
                        bot_path = bot_pathfinding.find_exit_bfs(player_pos, maze)
                    elif selected_algorithm == "dfs":
                        bot_path = bot_pathfinding.find_exit_dfs(player_pos, maze)
                    elif selected_algorithm == "astar":
                        bot_path = bot_pathfinding.find_exit_astar(player_pos, maze)
                    elif selected_algorithm == "explore":
                        bot_path = bot_pathfinding.find_exit_explore(player_pos, maze, rooms)
                    bot_path_index = 0
                    print(f"Pathfinding algorithm: {selected_algorithm.upper()}")
        else:
            b_toggle_pressed = False

        if glfw.get_key(window, glfw.KEY_1) == glfw.PRESS:
            selected_algorithm = "bfs"
            print("Algorithm selected: BFS")
        elif glfw.get_key(window, glfw.KEY_2) == glfw.PRESS:
            selected_algorithm = "dfs"
            print("Algorithm selected: DFS")
        elif glfw.get_key(window, glfw.KEY_3) == glfw.PRESS:
            selected_algorithm = "astar"
            print("Algorithm selected: A*")
        elif glfw.get_key(window, glfw.KEY_4) == glfw.PRESS:
            selected_algorithm = "explore"
            print("Algorithm selected: EXPLORE (visit all rooms then exit)")

        current_angle = glm.mix(start_angle, target_angle, turn_progress if is_turning else 1.0)
        direction = glm.vec2(np.sin(np.radians(current_angle)), np.cos(np.radians(current_angle)))

        if not is_moving and not is_turning:
            if bot_mode and bot_path_index < len(bot_path):
                current_cell = (int(player_pos.x), int(player_pos.z))
                if maze[current_cell[1]][current_cell[0]] == "#":
                    if not unstuck_mode:
                        unstuck_mode = True
                        unstuck_attempts = 0
                    if not is_turning and not is_moving:
                        left_angle = (player_angle_deg + 90) % 360
                        dx_left = np.sin(np.radians(left_angle))
                        dz_left = np.cos(np.radians(left_angle))
                        left_cell = (int(player_pos.x + dx_left), int(player_pos.z + dz_left))
                        if maze[left_cell[1]][left_cell[0]] != "#":
                            start_angle = player_angle_deg
                            target_angle = left_angle
                            turn_progress = 0.0
                            is_turning = True
                            player_angle_deg = target_angle
                        else:
                            right_angle = (player_angle_deg - 90) % 360
                            dx_right = np.sin(np.radians(right_angle))
                            dz_right = np.cos(np.radians(right_angle))
                            right_cell = (int(player_pos.x + dx_right), int(player_pos.z + dz_right))
                            if maze[right_cell[1]][right_cell[0]] != "#":
                                start_angle = player_angle_deg
                                target_angle = right_angle
                                turn_progress = 0.0
                                is_turning = True
                                player_angle_deg = target_angle
                        unstuck_attempts += 1
                        if unstuck_attempts > 4:
                            if selected_algorithm == "bfs":
                                bot_path = bot_pathfinding.find_exit_bfs(player_pos, maze)
                            elif selected_algorithm == "dfs":
                                bot_path = bot_pathfinding.find_exit_dfs(player_pos, maze)
                            elif selected_algorithm == "astar":
                                bot_path = bot_pathfinding.find_exit_astar(player_pos, maze)
                            elif selected_algorithm == "explore":
                                bot_path = bot_pathfinding.find_exit_explore(player_pos, maze, rooms)
                            bot_path_index = 0
                            unstuck_mode = False
                else:
                    unstuck_mode = False
                    next_x, next_z = bot_path[bot_path_index]
                    dx = (next_x + 0.5) - player_pos.x
                    dz = (next_z + 0.5) - player_pos.z
                    raw_angle = math.degrees(math.atan2(dx, dz)) % 360
                    desired_angle = round(raw_angle / 90) * 90 % 360
                    angle_diff = (desired_angle - player_angle_deg + 360) % 360
                    if angle_diff != 0:
                        start_angle = player_angle_deg
                        target_angle = desired_angle
                        turn_progress = 0.0
                        is_turning = True
                        player_angle_deg = target_angle
                    else:
                        start_pos = glm.vec3(player_pos)
                        target_pos = glm.vec3(next_x + 0.5, 0.0, next_z + 0.5)
                        move_progress = 0.0
                        is_moving = True
                        bot_path_index += 1
            else:
                if glfw.get_key(window, glfw.KEY_W):
                    next_pos = player_pos + glm.vec3(direction.x, 0, direction.y)
                    if not is_collision(next_pos.x, next_pos.z):
                        start_pos = glm.vec3(player_pos)
                        target_pos = glm.vec3(next_pos)
                        move_progress = 0.0
                        is_moving = True
                elif glfw.get_key(window, glfw.KEY_S):
                    next_pos = player_pos - glm.vec3(direction.x, 0, direction.y)
                    if not is_collision(next_pos.x, next_pos.z):
                        start_pos = glm.vec3(player_pos)
                        target_pos = glm.vec3(next_pos)
                        move_progress = 0.0
                        is_moving = True
                elif glfw.get_key(window, glfw.KEY_A):
                    start_angle = player_angle_deg
                    target_angle = (player_angle_deg + 90) % 360
                    turn_progress = 0.0
                    is_turning = True
                    player_angle_deg = target_angle
                elif glfw.get_key(window, glfw.KEY_D):
                    start_angle = player_angle_deg
                    target_angle = (player_angle_deg - 90) % 360
                    turn_progress = 0.0
                    is_turning = True
                    player_angle_deg = target_angle

        if is_moving:
            move_progress += delta / move_duration
            if move_progress >= 1.0:
                move_progress = 1.0
                is_moving = False
            player_pos = glm.mix(start_pos, target_pos, move_progress)

        if is_turning:
            turn_progress += delta / turn_duration
            if turn_progress >= 1.0:
                turn_progress = 1.0
                is_turning = False

        player_cell_x = int(player_pos.x)
        player_cell_z = int(player_pos.z)
        for i in range(player_cell_z - discovery_range, player_cell_z + discovery_range + 1):
            for j in range(player_cell_x - discovery_range, player_cell_x + discovery_range + 1):
                if 0 <= i < rows and 0 <= j < cols:
                    discovered[i][j] = True

        if player_cell_x + 2 < cols and maze[player_cell_z][player_cell_x+2] == '#' and maze[player_cell_z][player_cell_x+1] != '#':
            discovered[player_cell_z][player_cell_x+2] = True
        if player_cell_x - 2 >= 0 and maze[player_cell_z][player_cell_x-2] == '#' and maze[player_cell_z][player_cell_x-1] != '#':
            discovered[player_cell_z][player_cell_x-2] = True
        if player_cell_z + 2 < rows and maze[player_cell_z+2][player_cell_x] == '#' and maze[player_cell_z+1][player_cell_x] != '#':
            discovered[player_cell_z+2][player_cell_x] = True
        if player_cell_z - 2 >= 0 and maze[player_cell_z-2][player_cell_x] == '#' and maze[player_cell_z-1][player_cell_x] != '#':
            discovered[player_cell_z-2][player_cell_x] = True

        for room in rooms:
            if (player_cell_x >= room.x1 and player_cell_x < room.x2 and
                player_cell_z >= room.y1 and player_cell_z < room.y2):
                for i in range(room.y1 - 1, room.y2 + 1):
                    for j in range(room.x1 - 1, room.x2 + 1):
                        if 0 <= i < rows and 0 <= j < cols:
                            discovered[i][j] = True

        in_room = False
        for room in rooms:
            if room.x1 <= player_cell_x < room.x2 and room.y1 <= player_cell_z < room.y2:
                in_room = True
                break
        if not in_room:
            step_x = int(round(np.sin(np.radians(player_angle_deg))))
            step_z = int(round(np.cos(np.radians(player_angle_deg))))
            cx, cz = player_cell_x, player_cell_z
            depth = 0
            while depth < max_corridor_discovery_depth:
                nx = cx + step_x
                nz = cz + step_z
                if nx < 0 or nx >= cols or nz < 0 or nz >= rows:
                    break
                if maze[nz][nx] == '#' or maze[nz][nx] == 'E':
                    break
                discovered[nz][nx] = True
                if step_x != 0:
                    if nz+1 < rows and maze[nz+1][nx] not in "#E":
                        discovered[nz+1][nx] = True
                    if nz-1 >= 0 and maze[nz-1][nx] not in "#E":
                        discovered[nz-1][nx] = True
                if step_z != 0:
                    if nx+1 < cols and maze[nz][nx+1] not in "#E":
                        discovered[nz][nx+1] = True
                    if nx-1 >= 0 and maze[nz][nx-1] not in "#E":
                        discovered[nz][nx-1] = True
                cx, cz = nx, nz
                depth += 1

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        gluPerspective(70, 800/600, 0.1, 50)
        eye = player_pos
        interp_angle = glm.mix(start_angle, target_angle, turn_progress if is_turning else 1.0)
        look_dir = glm.vec3(np.sin(np.radians(interp_angle)), 0, np.cos(np.radians(interp_angle)))
        center = player_pos + look_dir
        gluLookAt(eye.x, 0.5, eye.z, center.x, 0.5, center.z, 0, 1, 0)
        
        glDisable(GL_LIGHTING)
        glColor3f(1, 0, 0)
        glBegin(GL_QUADS)
        glVertex3f(2, 0.1, 2)
        glVertex3f(3, 0.1, 2)
        glVertex3f(3, 0.1, 3)
        glVertex3f(2, 0.1, 3)
        glEnd()
        glColor3f(1, 1, 1)
        
        glBindTexture(GL_TEXTURE_2D, ground_tex)
        glBindBuffer(GL_ARRAY_BUFFER, floor_vbo)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 5*4, ctypes.c_void_p(0))
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 5*4, ctypes.c_void_p(3*4))
        glDrawArrays(GL_TRIANGLES, 0, floor_vertex_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        glBindTexture(GL_TEXTURE_2D, roof_tex)
        glBindBuffer(GL_ARRAY_BUFFER, ceiling_vbo)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 5*4, ctypes.c_void_p(0))
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 5*4, ctypes.c_void_p(3*4))
        glDrawArrays(GL_TRIANGLES, 0, ceiling_vertex_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        glBindTexture(GL_TEXTURE_2D, brick_tex)
        glBindBuffer(GL_ARRAY_BUFFER, wall_brick_vbo)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 5*4, ctypes.c_void_p(0))
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 5*4, ctypes.c_void_p(3*4))
        glDrawArrays(GL_TRIANGLES, 0, wall_brick_vertex_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        glBindTexture(GL_TEXTURE_2D, exit_tex)
        glBindBuffer(GL_ARRAY_BUFFER, wall_exit_vbo)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 5*4, ctypes.c_void_p(0))
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 5*4, ctypes.c_void_p(3*4))
        glDrawArrays(GL_TRIANGLES, 0, wall_exit_vertex_count)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        glEnable(GL_LIGHTING)
        
        draw_minimap(800, 600)
        if show_full_map:
            draw_full_map(800, 600)
        if show_help:
            draw_help(800, 600)
        
        glfw.swap_buffers(window)
        glfw.poll_events()
        
        # When the player hits the exit, reset the game.
        if maze[int(player_pos.z)][int(player_pos.x)] == "E":
            print("You found the exit! Resetting game...")
            reset_requested = True
            break

    exit_reached = (maze[int(player_pos.z)][int(player_pos.x)] == "E")
    glfw.terminate()
    if exit_requested:
        return False
    if reset_requested or exit_reached:
        return True
    else:
        return False

if __name__ == "__main__":
    while True:
        result = main()
        if result:
            print("Restarting new game...")
            continue
        else:
            break
