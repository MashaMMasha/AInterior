floor_plan_prompt_template = """You are an experienced room designer. Please assist me in crafting a floor plan. Each room is a rectangle. You need to define the four coordinates and specify an appropriate design scheme, including each room's color, material, and texture.
Assume the wall thickness is zero. Please ensure that all rooms are connected, not overlapped, and do not contain each other.
Note: the units for the coordinates are meters.
For example:
living room | maple hardwood, matte | light grey drywall, smooth | [(0, 0), (0, 8), (5, 8), (5, 0)]
kitchen | white hex tile, glossy | light grey drywall, smooth | [(5, 0), (5, 5), (8, 5), (8, 0)]

Here are some guidelines for you:
1. A room's size range (length or width) is 3m to 8m. The maximum area of a room is 48 m$^2$. Please provide a floor plan within this range and ensure the room is not too small or too large.
2. It is okay to have one room in the floor plan if you think it is reasonable.
3. The room name should be unique.
"""
