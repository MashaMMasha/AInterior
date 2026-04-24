floor_plan_prompt = """You are an experienced room designer. Please assist me in crafting a floor plan. Each room is a rectangle. You need to define the four coordinates and specify an appropriate design scheme, including each room's color, material, and texture.
Assume the wall thickness is zero. Please ensure that all rooms are connected, not overlapped, and do not contain each other.
Note: the units for the coordinates are meters.

Here are some guidelines for you:
1. A room's size range (length or width) is 3m to 8m. The maximum area of a room is 48 m$^2$. Please provide a floor plan within this range and ensure the room is not too small or too large.
2. It is okay to have one room in the floor plan if you think it is reasonable.
3. The room name should be unique.

Now, I need a design for: "{query}".
Additional requirements: {additional_requirements}.
Your response should be direct and without additional text at the beginning or end."""
# For example:
# living room | maple hardwood, matte | light grey drywall, smooth | [(0, 0), (0, 8), (5, 8), (5, 0)]
# kitchen | white hex tile, glossy | light grey drywall, smooth | [(5, 0), (5, 5), (8, 5), (8, 0)]

wall_height_prompt = """I am now designing: "{query}". Please help me decide the wall height in meters.

Additional requirements: {additional_requirements}.
Answer with a number, for example, 3.0. Do not add additional text at the beginning or in the end."""


doorway_prompt = """I need assistance in designing the connections between rooms. The connections could be of three types: doorframe (no door installed), doorway (with a door), or open (no wall separating rooms). The sizes available for doorframes and doorways are single (1m wide) and double (2m wide).

Ensure that the door style complements the design of the room.

The design under consideration is: "{query}", which includes these rooms: {rooms}. The length, width and height of each room in meters are:
{room_sizes}
Certain pairs of rooms share a wall: {room_pairs}. There must be an openable door to the exterior.
Adhere to these additional requirements: {additional_requirements}.
Provide your response succinctly, without additional text at the beginning or end."""


window_prompt = """Guide me in designing the windows for each room. The window types are: fixed, hung, and slider.
The available sizes (width x height in cm) are:
fixed: (92, 120), (150, 92), (150, 120), (150, 180), (240, 120), (240, 180)
hung: (87, 160), (96, 91), (120, 160), (130, 67), (130, 87), (130, 130)
slider: (91, 92), (120, 61), (120, 91), (120, 120), (150, 92), (150, 120)

Your task is to determine the appropriate type, size, and quantity of windows for each room, bearing in mind the room's design, dimensions, and function.

I am now designing: "{query}". The wall height is {wall_height} cm. The walls available for window installation (direction, width in cm) in each room are:
{walls}
Please note: It is not mandatory to install windows on every available wall. Within the same room, all windows must be the same type and size.
Also, adhere to these additional requirements: {additional_requirements}.

Provide a concise response, omitting any additional text at the beginning or end. """


object_selection_prompt = """Assist me in selecting large, floor-based objects to furnish each room, excluding mats, carpets, and rugs. Provide a comprehensive description since I will use it to retrieve object. If multiple identical items are to be placed in the room, please indicate the quantity.

Currently, the design in progress is: "{query}", featuring these rooms: {rooms}. Please also consider the following additional requirements: {additional_requirements}.

Your response should be precise, without additional text at the beginning or end."""


object_constraints_prompt = """You are an experienced room designer.
Please help me arrange objects in the room by assigning constraints to each object.
Here are the constraints and their definitions:
1. global constraint:
    1) edge: at the edge of the room, close to the wall, most of the objects are placed here.
    2) middle: not close to the edge of the room.

2. distance constraint:
    1) near, object: near to the other object, but with some distance, 50cm < distance < 150cm.
    2) far, object: far away from the other object, distance >= 150cm.
    
3. position constraint:
    1) in front of, object: in front of another object.
    2) around, object: around another object, usually used for chairs.
    3) side of, object: on the side (left or right) of another object.
    4) left of, object: to the left of another object.
    5) right of, object: to the right of another object.

4. alignment constraint:
    1) center aligned, object: align the center of the object with the center of another object.

5. Rotation constraint:
    1) face to, object: face to the center of another object.

For each object, you must have one global constraint and you can select various numbers of constraints and any combinations
Here are some guidelines for you:
1. I will use your guideline to arrange the objects *iteratively*, so please start with an anchor object which doesn't depend on the other objects (with only one global constraint).
2. Place the larger objects first.
3. The latter objects could only depend on the former objects.
4. The objects of the *same type* are usually *aligned*.
5. I prefer objects to be placed at the edge (the most important constraint) of the room if possible which makes the room look more spacious.
6. When handling chairs, you should use the around position constraint. Chairs must be placed near to the table/desk and face to the table/desk.

Now I want you to design {room_type} and the room size is {room_size}.
Here are the objects that I want to place in the {room_type}:
{objects}
"""


wall_object_selection_prompt = """Assist me in selecting wall-based objects to furnish each room.
Provide the following infrotmation: room type, object category, object description, quantity

Now I want you to design: "{query}", which has these rooms: {rooms}.
Please also consider the following additional requirements: {additional_requirements}.
Your response should be precise, without additional text at the beginning or end."""


wall_object_constraints_prompt = """You are an experienced room designer.
Please help me arrange wall objects in the room by providing their relative position and distance from the floor.

Note the distance is the distance from the *bottom* of the wall object to the floor. The second column is optional and can be N/A. The object of the same type should be placed at the same height.
Now I am designing {room_type} of which the wall height is {wall_height} cm, and the floor objects in the room are: {floor_objects}.
The wall objects I want to place in the {room_type} are: {wall_objects}.
"""


ceiling_selection_prompt = """Assist me in selecting ceiling objects (light/fan) to furnish each room.

Currently, the design in progress is "{query}", featuring these rooms: {rooms}. You need to provide one ceiling object for each room.
Please also consider the following additional requirements: {additional_requirements}.
"""


small_object_selection_prompt = """As an experienced room designer, you are tasked to bring life into the room by strategically placing more *small* objects. Those objects should only be arranged *on top of* large objects which serve as receptacles. 

Now, we are designing: "{query}" and the available receptacles in the room include: {receptacles}. Additional requirements for this design project are as follows: {additional_requirements}.
Your response should solely contain the information about the placement of objects and should not include any additional text before or after the main content."""

object_selection_prompt_1 = """You are an experienced room designer, please assist me in selecting large *floor*/*wall* objects and small objects on top of them to furnish the room. You need to select appropriate objects to satisfy the customer's requirements.
You must provide a description and desired size for each object since I will use it to retrieve object. If multiple items are to be placed in the room with the same description, please indicate the quantity and variance_type ("same" if they should be identical, otherwise "varied").

Currently, the design in progress is: "{query}", and we are working on the *{room_type}* with the size of {room_size}.
Please also consider the following additional requirements: {additional_requirements}.

Here are some guidelines for you:
1. Provide reasonable type/style/quantity of objects for each room based on the room size to make the room not too crowded or empty.
2. Do not provide rug/mat, windows, doors, curtains, and ceiling objects which have been installed for each room.
3. I want more types of large objects and more types of small objects on top of the large objects to make the room look more vivid.

"""
# Please first use natural language to explain your high-level design strategy for *ROOM_TYPE*, and then follow the desired JSON format *strictly* (do not add any additional text at the beginning or end).

object_selection_prompt_messages = [
    {"user": "{object_selection_prompt_new_1}"},
    {"ai": "{object_selection_1}"},
    {"user": """
     Thanks! After following your suggestions to retrieve objects, I found the *{room}* is still too empty. To enrich the *{room}*, you could:
1. Add more *floor* objects to the *{room}* (excluding rug, carpet, windows, doors, curtains, and *ignore ceiling objects*).
2. Increase the size and quantity of the objects.
3. Add more *types* of small objects on top of the large objects.
Could you update the entire JSON file with the same format as before and answer without additional text at the beginning or end?
     """}
]

object_selection_prompt_2 = """User: {object_selection_prompt_new_1}

AI: {object_selection_1}

User: Thanks! After following your suggestions to retrieve objects, I found the *{room}* is still too empty. To enrich the *{room}*, you could:
1. Add more *floor* objects to the *{room}* (excluding rug, carpet, windows, doors, curtains, and *ignore ceiling objects*).
2. Increase the size and quantity of the objects.
3. Add more *types* of small objects on top of the large objects.
Could you update the entire JSON file with the same format as before and answer without additional text at the beginning or end?

AI: """
