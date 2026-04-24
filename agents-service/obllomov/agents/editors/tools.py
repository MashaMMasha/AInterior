import uuid
from typing import Optional, Tuple

from langchain_core.tools import StructuredTool

from obllomov.agents.retrievers import ObjathorRetriever
from obllomov.agents.selectors import MaterialSelector
from obllomov.schemas.domain.annotations import AnnotationDict
from obllomov.schemas.domain.entries import FloorObjectEntry, RoomPlan
from obllomov.schemas.domain.scene import ScenePlan
from obllomov.shared.geometry import BBox3D, Polygon2D


class EditorToolkit:
    def __init__(
        self,
        material_selector: MaterialSelector,
        object_retriever: ObjathorRetriever,
        annotations: AnnotationDict,
    ):
        self.material_selector = material_selector
        self.object_retriever = object_retriever
        self.annotations: AnnotationDict = annotations
        self._scene: Optional[ScenePlan] = None

    def build(self, scene_plan: ScenePlan) -> list:
        self._scene = scene_plan
        return [
            StructuredTool.from_function(self.get_room_details, name="get_room_details"),
            StructuredTool.from_function(self.change_material, name="change_material"),
            StructuredTool.from_function(self.find_object, name="find_object"),
            StructuredTool.from_function(self.move_object, name="move_object"),
            StructuredTool.from_function(self.add_object, name="add_object"),
            StructuredTool.from_function(self.replace_object, name="replace_object"),
        ]

    def _room_poly_cm(self, room: RoomPlan) -> Polygon2D:
        return Polygon2D(vertices=[v.scaled(100) for v in room.vertices])

    def _object_box_cm(self, x_m: float, z_m: float, rotation_y: float, bbox: BBox3D) -> Polygon2D:
        bbox_cm = bbox.convert_m_to_cm()
        rot = int(rotation_y) % 360
        if 45 < rot % 180 < 135:
            half_l, half_w = bbox_cm.z / 2, bbox_cm.x / 2
        else:
            half_l, half_w = bbox_cm.x / 2, bbox_cm.z / 2
        cx, cz = x_m * 100, z_m * 100
        return Polygon2D.from_box(cx - half_l, cz - half_w, cx + half_l, cz + half_w)

    def _other_object_polys_cm(self, room_id: str, exclude_id: str = None) -> list[Polygon2D]:
        polys = []
        for obj in self._scene.floor_objects:
            if obj.id == exclude_id or obj.room_id != room_id:
                continue
            if obj.vertices:
                polys.append(Polygon2D.from_tuples(obj.vertices))
            else:
                ann = self.annotations.get(obj.asset_id)
                if ann is None:
                    continue
                polys.append(self._object_box_cm(
                    obj.position.x, obj.position.z, obj.rotation.y, ann.bbox,
                ))
        return polys

    def _validate_placement(
        self, room_id: str, x_m: float, z_m: float, rotation_y: float, bbox: BBox3D, exclude_id: str = None,
    ) -> Tuple[bool, str]:
        room = next((r for r in self._scene.rooms if r.id == room_id), None)
        if room is None:
            return False, f"Room '{room_id}' not found."

        obj_box = self._object_box_cm(x_m, z_m, rotation_y, bbox)
        room_poly = self._room_poly_cm(room)

        if not room_poly.contains_polygon(obj_box):
            return False, "Object would be outside the room boundaries."

        for other_poly in self._other_object_polys_cm(room_id, exclude_id):
            if obj_box.intersects_polygon(other_poly):
                return False, "Object would collide with another object."

        return True, ""

    def _compute_vertices_cm(self, x_m: float, z_m: float, rotation_y: float, bbox: BBox3D) -> list:
        obj_box = self._object_box_cm(x_m, z_m, rotation_y, bbox)
        return obj_box.exterior_coords()

    def get_room_details(self, room_id: str) -> str:
        """Get detailed information about a room: dimensions, materials, objects, doors, windows."""
        scene = self._scene
        room = next((r for r in scene.rooms if r.id == room_id), None)
        if room is None:
            available = [r.id for r in scene.rooms]
            return f"Room '{room_id}' not found. Available rooms: {available}"

        poly = Polygon2D(vertices=room.vertices)
        w, d = poly.bbox_size()

        lines = [
            f"Room: {room.room_type} ({room.id})",
            f"Size: {w:.1f}m x {d:.1f}m, wall height: {scene.wall_height}m",
            f"Floor: material={room.floor_material.get('name', '?')}, design='{room.floor_design}'",
            f"Walls: material={room.wall_material.get('name', '?')}, design='{room.wall_design}'",
        ]

        room_objects = [obj for obj in scene.floor_objects if obj.room_id == room_id]
        if room_objects:
            lines.append("Floor objects:")
            for obj in room_objects:
                lines.append(f"  - {obj.object_name} (id={obj.id}) at ({obj.position.x:.1f}, {obj.position.z:.1f})")

        wall_objs = [obj for obj in scene.wall_objects if obj.room_id == room_id]
        if wall_objs:
            lines.append("Wall objects:")
            for obj in wall_objs:
                lines.append(f"  - {obj.object_name} (id={obj.id}) at height {obj.position.y:.1f}m")

        doors = [d for d in scene.doors if d.room0 == room_id or d.room1 == room_id]
        if doors:
            lines.append("Doors:")
            for d in doors:
                other = d.room1 if d.room0 == room_id else d.room0
                lines.append(f"  - {d.asset_id} connecting to {other}")

        windows = [w for w in scene.windows if w.room_id == room_id]
        if windows:
            lines.append("Windows:")
            for w in windows:
                lines.append(f"  - {w.asset_id} on wall {w.wall0}")

        return "\n".join(lines)

    def change_material(self, room_id: str, surface: str, description: str) -> str:
        """Change floor or wall material for a room.

        Args:
            room_id: The room to modify.
            surface: Either 'floor' or 'wall'.
            description: Natural language description of desired material, e.g. 'dark oak parquet' or 'beige matte wallpaper'.
        """
        scene = self._scene
        room = next((r for r in scene.rooms if r.id == room_id), None)
        if room is None:
            return f"Room '{room_id}' not found."
        if surface not in ("floor", "wall"):
            return "Surface must be 'floor' or 'wall'."

        self.material_selector.used_assets = []
        new_material = self.material_selector.select_single_material(description, topk=5)

        if surface == "floor":
            old = room.floor_material.get("name", "N/A")
            room.floor_material = new_material
            room.floor_design = description
        else:
            old = room.wall_material.get("name", "N/A")
            room.wall_material = new_material
            room.wall_design = description
            for wall in scene.walls:
                if wall.room_id == room_id and "exterior" not in wall.id:
                    wall.material = new_material

        return f"Changed {surface} material in {room_id}: '{old}' -> '{new_material['name']}' (query: '{description}')"

    def find_object(self, description: str, top_k: int = 5) -> str:
        """Search for 3D objects by description. Returns top matching asset IDs with scores. Does NOT modify the scene.

        Args:
            description: What to search for, e.g. 'modern floor lamp', 'wooden bookshelf'.
            top_k: Number of results to return.
        """
        uids, scores = self.object_retriever.retrieve_single(
            f"a 3D model of {description}",
            threshold=15,
            topk=top_k,
        )
        if not uids:
            return f"No objects found for '{description}'."

        answer = [f"Results for '{description}':"]
        for uid, score in zip(uids, scores):
            ann = self.annotations.get(uid)
            if ann:
                bbox = ann.bbox
                answer.append(
                    f"  - {uid} (score={score:.1f}, "
                    f"size={bbox.x:.2f}x{bbox.y:.2f}x{bbox.z:.2f}m)"
                )
            else:
                answer.append(f"  - {uid} (score={score:.1f})")
        return "\n".join(answer)

    def move_object(self, object_id: str, x: float, z: float, rotation_y: float = -1) -> str:
        """Move an existing floor object to a new position within its room.

        Args:
            object_id: The id of the object to move.
            x: New x coordinate in meters.
            z: New z coordinate in meters.
            rotation_y: New Y-axis rotation in degrees. Pass -1 to keep current rotation.
        """
        scene = self._scene
        obj = next((o for o in scene.floor_objects if o.id == object_id), None)
        if obj is None:
            available = [o.id for o in scene.floor_objects]
            return f"Object '{object_id}' not found. Available: {available}"

        ann = self.annotations.get(obj.asset_id)
        if ann is None:
            return f"Asset '{obj.asset_id}' has no annotation data, cannot validate placement."

        effective_rotation = rotation_y if rotation_y >= 0 else obj.rotation.y
        ok, err = self._validate_placement(obj.room_id, x, z, effective_rotation, ann.bbox, exclude_id=obj.id)
        if not ok:
            return f"Cannot move '{obj.object_name}': {err}"

        old_pos = f"({obj.position.x:.1f}, {obj.position.z:.1f})"
        obj.position.x = x
        obj.position.z = z
        if rotation_y >= 0:
            obj.rotation.y = rotation_y
        obj.vertices = self._compute_vertices_cm(x, z, effective_rotation, ann.bbox)

        return f"Moved '{obj.object_name}' from {old_pos} to ({x:.1f}, {z:.1f})"

    def add_object(self, room_id: str, description: str, x: float, z: float, rotation_y: float = 0) -> str:
        """Add a new floor object to a room. Searches for the best matching 3D asset automatically.

        Args:
            room_id: The room to add the object to.
            description: Natural language description, e.g. 'modern floor lamp', 'wooden bookshelf'.
            x: X coordinate in meters.
            z: Z coordinate in meters.
            rotation_y: Y-axis rotation in degrees.
        """
        scene = self._scene
        room = next((r for r in scene.rooms if r.id == room_id), None)
        if room is None:
            available = [r.id for r in scene.rooms]
            return f"Room '{room_id}' not found. Available rooms: {available}"

        uids, scores = self.object_retriever.retrieve_single(
            f"a 3D model of {description}",
            threshold=15,
            topk=1,
        )
        if not uids:
            return f"No matching asset found for '{description}'."

        asset_id = uids[0]
        ann = self.annotations.get(asset_id)
        if ann is None:
            return f"Asset '{asset_id}' has no annotation data."

        ok, err = self._validate_placement(room_id, x, z, rotation_y, ann.bbox)
        if not ok:
            return f"Cannot place '{description}' at ({x:.1f}, {z:.1f}): {err}"

        obj_id = f"{description}-{uuid.uuid4().hex[:6]} ({room_id})"
        vertices = self._compute_vertices_cm(x, z, rotation_y, ann.bbox)
        entry = FloorObjectEntry(
            asset_id=asset_id,
            id=obj_id,
            position={"x": x, "y": ann.bbox.y / 2, "z": z},
            rotation={"x": 0, "y": rotation_y, "z": 0},
            room_id=room_id,
            object_name=description,
            vertices=vertices,
        )
        scene.floor_objects.append(entry)

        return (
            f"Added '{description}' to {room_id} at ({x:.1f}, {z:.1f}). "
            f"Asset: {asset_id}, size: {ann.bbox.x:.2f}x{ann.bbox.y:.2f}x{ann.bbox.z:.2f}m"
        )

    def replace_object(self, object_id: str, description: str) -> str:
        """Replace an existing floor object with a different 3D asset found by description. Keeps the same position and rotation.

        Args:
            object_id: The id of the object to replace.
            description: Natural language description of the new object, e.g. 'darker leather sofa'.
        """
        scene = self._scene
        obj = next((o for o in scene.floor_objects if o.id == object_id), None)
        if obj is None:
            available = [o.id for o in scene.floor_objects]
            return f"Object '{object_id}' not found. Available: {available}"

        uids, scores = self.object_retriever.retrieve_single(
            f"a 3D model of {description}",
            threshold=15,
            topk=1,
        )
        if not uids:
            return f"No matching asset found for '{description}'."

        new_asset_id = uids[0]
        ann = self.annotations.get(new_asset_id)
        if ann is None:
            return f"Asset '{new_asset_id}' has no annotation data."

        ok, err = self._validate_placement(
            obj.room_id, obj.position.x, obj.position.z, obj.rotation.y, ann.bbox, exclude_id=obj.id,
        )
        if not ok:
            return f"Cannot replace '{obj.object_name}' with '{description}': new asset doesn't fit. {err}"

        old_asset = obj.asset_id
        old_name = obj.object_name
        obj.asset_id = new_asset_id
        obj.object_name = description
        obj.position.y = ann.bbox.y / 2
        obj.vertices = self._compute_vertices_cm(obj.position.x, obj.position.z, obj.rotation.y, ann.bbox)

        return (
            f"Replaced '{old_name}' (asset={old_asset}) with '{description}' (asset={new_asset_id}, "
            f"size={ann.bbox.x:.2f}x{ann.bbox.y:.2f}x{ann.bbox.z:.2f}m) at same position"
        )
