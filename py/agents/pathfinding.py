import heapq
import math

class Node:
    def __init__(self, x, y, parent=None):
        self.x = x
        self.y = y
        self.parent = parent
        self.g = 0 
        self.h = 0  
        self.f = 0  

    def __lt__(self, other):
        return self.f < other.f

def heuristic(a, b):
    # Euclidean distance
    return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

def a_star_search(start, goal, grid_size=30, cell_size=500, obstacles=None):
    """
    A* Pathfinding Algorithm for grid based map.
    
    Args:
        start: tuple (world_x, world_y)
        goal: tuple (world_x, world_y)
        grid_size: Number of cells in grid (30)
        cell_size: Size of each cell in world units (500)
        obstacles: Set of blocked grid coordinates (x, y) - optional
        
    Returns:
        List of waypoints [(x, y), ...] including start and goal
    """
    
    # Convert world coordinates to grid coordinates
    start_grid = (int(start[0] // cell_size), int(start[1] // cell_size))
    goal_grid = (int(goal[0] // cell_size), int(goal[1] // cell_size))
    
    # Clamp to grid
    start_grid = (max(0, min(grid_size-1, start_grid[0])), max(0, min(grid_size-1, start_grid[1])))
    goal_grid = (max(0, min(grid_size-1, goal_grid[0])), max(0, min(grid_size-1, goal_grid[1])))
    
    if start_grid == goal_grid:
        return [goal]
        
    open_list = []
    closed_set = set()
    
    start_node = Node(start_grid[0], start_grid[1])
    goal_node = Node(goal_grid[0], goal_grid[1])
    
    heapq.heappush(open_list, start_node)
    
    # Store nodes by coordinate for quick lookup
    nodes = {(start_grid[0], start_grid[1]): start_node}
    
    while open_list:
        current_node = heapq.heappop(open_list)
        closed_set.add((current_node.x, current_node.y))
        
        # Check if we reached the goal
        if (current_node.x, current_node.y) == (goal_node.x, goal_node.y):
            path = []
            curr = current_node
            while curr:
                # Convert back to world center coordinates
                world_x = curr.x * cell_size + cell_size / 2
                world_y = curr.y * cell_size + cell_size / 2
                path.append((world_x, world_y))
                curr = curr.parent
            return path[::-1]  # Return reversed path (start -> end)
        
        # Generate children (neighbors)
        # 8 directions (including diagonals)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
            node_x = current_node.x + dx
            node_y = current_node.y + dy
            
            # Check bounds
            if node_x < 0 or node_x >= grid_size or node_y < 0 or node_y >= grid_size:
                continue
                
            # Check obstacles (if any)
            if obstacles and (node_x, node_y) in obstacles:
                continue
                
            if (node_x, node_y) in closed_set:
                continue
                
            # Create neighbor node
            neighbor = Node(node_x, node_y, current_node)
            
            # Cost calculation
            move_cost = math.sqrt(dx*dx + dy*dy) # 1 for straight, 1.414 for diagonal
            new_g = current_node.g + move_cost
            
            # If neighbor is already in open list with lower g, skip
            if (node_x, node_y) in nodes:
                 if nodes[(node_x, node_y)].g <= new_g:
                     continue
            
            neighbor.g = new_g
            neighbor.h = heuristic((node_x, node_y), (goal_grid[0], goal_grid[1]))
            neighbor.f = neighbor.g + neighbor.h
            
            nodes[(node_x, node_y)] = neighbor
            heapq.heappush(open_list, neighbor)
            
    # Fallback: Straight line if no path found (shouldn't happen in open grid)
    return [start, goal]
