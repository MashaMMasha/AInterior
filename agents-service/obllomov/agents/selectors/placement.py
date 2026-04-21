import copy
import random
import time
from dataclasses import dataclass, fields

import numpy as np
from rtree import index
from scipy.interpolate import interp1d
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring

from obllomov.shared.geometry import Box3D, Polygon2D, Vertex3D
from obllomov.shared.log import logger

MIN_FRONT_WALL_DISTANCE = 30
WALL_OFFSET = 4.5
NEAR_DISTANCE_THRESHOLD = 80
ALIGNMENT_EPSILON = 5
DEFAULT_BRANCH_FACTOR = 30


class SolutionFound(Exception):
    def __init__(self, solution):
        self.solution = solution


@dataclass
class FloorPlacement:
    center: tuple
    rotation: int
    coords: tuple
    score: float

    def __getitem__(self, idx):
        return list(self.__iter__())[idx]

    def __setitem__(self, idx, value):
        f = fields(self)
        setattr(self, f[idx].name, value)

    def __iter__(self):
        return iter((self.center, self.rotation, self.coords, self.score))


@dataclass
class WallPlacement:
    vertex_min: tuple
    vertex_max: tuple
    rotation: int
    coords: tuple
    score: float

    def __getitem__(self, idx):
        return list(self.__iter__())[idx]

    def __setitem__(self, idx, value):
        f = fields(self)
        setattr(self, f[idx].name, value)

    def __iter__(self):
        return iter((self.vertex_min, self.vertex_max, self.rotation, self.coords, self.score))


class BaseDFSSolver:
    def __init__(self, grid_size, random_seed=0, max_duration=5, constraint_bouns=0.2):
        self.grid_size = grid_size
        self.random_seed = random_seed
        self.max_duration = max_duration
        self.constraint_bouns = constraint_bouns
        self.start_time = None
        self.solutions = []

    def get_max_solution(self, solutions):
        path_weights = [sum(obj.score for obj in sol.values()) for sol in solutions]
        return solutions[int(np.argmax(path_weights))]

    def _check_timeout(self):
        if time.time() - self.start_time > self.max_duration:
            logger.debug("Time limit reached.")
            raise SolutionFound(self.solutions)


class DFS_Solver_Floor(BaseDFSSolver):
    def __init__(self, grid_size, random_seed=0, max_duration=5, constraint_bouns=0.2):
        super().__init__(grid_size, random_seed, max_duration, constraint_bouns)

        self.func_dict = {
            "relative": self.place_relative,
            "direction": self.place_face,
            "alignment": self.place_alignment_center,
            "distance": self.place_distance,
        }

        self.constraint_type2weight = {
            "global": 1.0,
            "relative": 0.5,
            "direction": 0.5,
            "alignment": 0.5,
            "distance": 1.8,
        }

        self.edge_bouns = 0.0

    @staticmethod
    def _convert_initial_state(initial_state):
        return {
            k: FloorPlacement(center=v[0], rotation=v[1], coords=v[2], score=v[3])
            if not isinstance(v, FloorPlacement) else v
            for k, v in initial_state.items()
        }

    def get_solution(self, bounds, objects_list, constraints, initial_state, use_milp=False):
        initial_state = self._convert_initial_state(initial_state)
        self.start_time = time.time()
        grid_points = self.create_grids(bounds)
        grid_points = self.remove_points(grid_points, initial_state)
        try:
            self.dfs(bounds, objects_list, constraints, grid_points, initial_state, DEFAULT_BRANCH_FACTOR)
        except SolutionFound:
            logger.info(f"Time taken: {time.time() - self.start_time:.2f}s")

        logger.info(f"Number of solutions found: {len(self.solutions)}")
        return self.get_max_solution(self.solutions)

    def dfs(self, room_poly, objects_list, constraints, grid_points, placed_objects, branch_factor):
        if len(objects_list) == 0:
            self.solutions.append(placed_objects)
            return placed_objects

        self._check_timeout()

        object_name, object_dim = objects_list[0]
        placements = self.get_possible_placements(
            room_poly, object_dim, constraints[object_name], grid_points, placed_objects
        )

        if len(placements) == 0 and len(placed_objects) != 0:
            self.solutions.append(placed_objects)

        paths = []
        if branch_factor > 1:
            random.shuffle(placements)

        for placement in placements[:branch_factor]:
            placed_objects_updated = {**placed_objects, object_name: placement}
            grid_points_updated = self.remove_points(grid_points, placed_objects_updated)

            sub_paths = self.dfs(
                room_poly, objects_list[1:], constraints,
                grid_points_updated, placed_objects_updated, 1,
            )
            paths.extend(sub_paths)

        return paths

    def get_possible_placements(self, room_poly, object_dim, constraints, grid_points, placed_objects):
        solutions = self.filter_collision(
            placed_objects, self.get_all_solutions(room_poly, grid_points, object_dim)
        )
        solutions = self.filter_facing_wall(room_poly, solutions, object_dim)
        edge_solutions = self.place_edge(room_poly, list(solutions), object_dim)

        if not edge_solutions:
            return edge_solutions

        global_constraint = next(
            (c for c in constraints if c["type"] == "global"), None
        )
        if global_constraint is None:
            global_constraint = {"type": "global", "constraint": "edge"}

        if global_constraint["constraint"] == "edge":
            candidate_solutions = list(edge_solutions)
        elif len(constraints) > 1:
            candidate_solutions = solutions + edge_solutions
        else:
            candidate_solutions = list(solutions)

        candidate_solutions = self.filter_collision(placed_objects, candidate_solutions)
        if not candidate_solutions:
            return candidate_solutions

        random.shuffle(candidate_solutions)
        placement2score = {
            (p.center, p.rotation, p.coords): p.score for p in candidate_solutions
        }

        for p in candidate_solutions:
            if p in edge_solutions and len(constraints) >= 1:
                placement2score[(p.center, p.rotation, p.coords)] += self.edge_bouns

        for constraint in constraints:
            if "target" not in constraint:
                continue

            func = self.func_dict.get(constraint["type"])
            if func is None:
                continue
            valid_solutions = func(
                constraint["constraint"],
                placed_objects[constraint["target"]],
                candidate_solutions,
            )

            weight = self.constraint_type2weight.get(constraint["type"], 0.5)
            if constraint["type"] == "distance":
                for p in valid_solutions:
                    placement2score[(p.center, p.rotation, p.coords)] += p.score * weight
            else:
                for p in valid_solutions:
                    placement2score[(p.center, p.rotation, p.coords)] += self.constraint_bouns * weight

        for key in placement2score:
            placement2score[key] /= max(len(constraints), 1)

        sorted_keys = sorted(placement2score, key=placement2score.get, reverse=True)
        return [
            FloorPlacement(center=k[0], rotation=k[1], coords=k[2], score=placement2score[k])
            for k in sorted_keys
        ]

    def create_grids(self, room_poly: Polygon2D):
        min_x, min_z, max_x, max_z = room_poly.bounds
        grid_points = []
        for x in range(int(min_x), int(max_x), self.grid_size):
            for y in range(int(min_z), int(max_z), self.grid_size):
                if room_poly.contains(Point(x, y)):
                    grid_points.append((x, y))
        return grid_points

    def remove_points(self, grid_points, objects_dict):
        idx = index.Index()
        polygons = []
        for i, obj in enumerate(objects_dict.values()):
            poly = Polygon(obj.coords)
            idx.insert(i, poly.bounds)
            polygons.append(poly)

        valid_points = []
        for point in grid_points:
            p = Point(point)
            candidates = [polygons[i] for i in idx.intersection(p.bounds)]
            if not any(c.contains(p) for c in candidates):
                valid_points.append(point)
        return valid_points

    def get_all_solutions(self, room_poly, grid_points, object_dim):
        obj_length, obj_width = object_dim
        obj_half_length, obj_half_width = obj_length / 2, obj_width / 2

        rotation_adjustments = {
            0: ((-obj_half_length, -obj_half_width), (obj_half_length, obj_half_width)),
            90: ((-obj_half_width, -obj_half_length), (obj_half_width, obj_half_length)),
            180: ((-obj_half_length, obj_half_width), (obj_half_length, -obj_half_width)),
            270: ((obj_half_width, -obj_half_length), (-obj_half_width, obj_half_length)),
        }

        solutions = []
        for rotation in [0, 90, 180, 270]:
            for point in grid_points:
                cx, cy = point
                ll, ur = rotation_adjustments[rotation]
                lower_left = (cx + ll[0], cy + ll[1])
                upper_right = (cx + ur[0], cy + ur[1])
                obj_box = box(*lower_left, *upper_right)

                if room_poly.contains(obj_box):
                    solutions.append(FloorPlacement(
                        center=point,
                        rotation=rotation,
                        coords=tuple(obj_box.exterior.coords[:]),
                        score=1,
                    ))
        return solutions

    def filter_collision(self, objects_dict, solutions):
        object_polygons = [Polygon(obj.coords) for obj in objects_dict.values()]

        valid = []
        for sol in solutions:
            sol_poly = Polygon(sol.coords)
            if not any(sol_poly.intersects(op) for op in object_polygons):
                valid.append(sol)
        return valid

    def filter_facing_wall(self, room_poly, solutions, obj_dim):
        obj_half_width = obj_dim[1] / 2
        front_center_adjustments = {
            0: (0, obj_half_width),
            90: (obj_half_width, 0),
            180: (0, -obj_half_width),
            270: (-obj_half_width, 0),
        }

        valid = []
        for sol in solutions:
            cx, cy = sol.center
            dx, dy = front_center_adjustments[sol.rotation]
            front_dist = room_poly.boundary.distance(Point(cx + dx, cy + dy))
            if front_dist >= MIN_FRONT_WALL_DISTANCE:
                valid.append(sol)
        return valid

    def place_edge(self, room_poly, solutions, obj_dim):
        obj_half_width = obj_dim[1] / 2
        back_center_adjustments = {
            0: (0, -obj_half_width),
            90: (-obj_half_width, 0),
            180: (0, obj_half_width),
            270: (obj_half_width, 0),
        }

        valid = []
        for sol in solutions:
            cx, cy = sol.center
            dx, dy = back_center_adjustments[sol.rotation]
            back_x, back_y = cx + dx, cy + dy

            back_dist = room_poly.boundary.distance(Point(back_x, back_y))
            center_dist = room_poly.boundary.distance(Point(cx, cy))

            if back_dist <= self.grid_size and back_dist < center_dist:
                center2back = np.array([back_x - cx, back_y - cy])
                center2back /= np.linalg.norm(center2back)
                offset = center2back * (back_dist + WALL_OFFSET)

                new_center = (cx + offset[0], cy + offset[1])
                new_coords = tuple(
                    (c[0] + offset[0], c[1] + offset[1]) for c in sol.coords
                )
                valid.append(FloorPlacement(
                    center=new_center,
                    rotation=sol.rotation,
                    coords=new_coords,
                    score=sol.score + self.constraint_bouns,
                ))
        return valid

    def place_relative(self, place_type, target_object, solutions):
        target_polygon = Polygon(target_object.coords)
        min_x, min_y, max_x, max_y = target_polygon.bounds
        mean_x = (min_x + max_x) / 2
        mean_y = (min_y + max_y) / 2
        target_rotation = target_object.rotation

        comparison_dict = {
            "left of": {
                0: lambda s: s[0] < min_x and min_y <= s[1] <= max_y,
                90: lambda s: s[1] > max_y and min_x <= s[0] <= max_x,
                180: lambda s: s[0] > max_x and min_y <= s[1] <= max_y,
                270: lambda s: s[1] < min_y and min_x <= s[0] <= max_x,
            },
            "right of": {
                0: lambda s: s[0] > max_x and min_y <= s[1] <= max_y,
                90: lambda s: s[1] < min_y and min_x <= s[0] <= max_x,
                180: lambda s: s[0] < min_x and min_y <= s[1] <= max_y,
                270: lambda s: s[1] > max_y and min_x <= s[0] <= max_x,
            },
            "in front of": {
                0: lambda s: s[1] > max_y and mean_x - self.grid_size < s[0] < mean_x + self.grid_size,
                90: lambda s: s[0] > max_x and mean_y - self.grid_size < s[1] < mean_y + self.grid_size,
                180: lambda s: s[1] < min_y and mean_x - self.grid_size < s[0] < mean_x + self.grid_size,
                270: lambda s: s[0] < min_x and mean_y - self.grid_size < s[1] < mean_y + self.grid_size,
            },
            "behind": {
                0: lambda s: s[1] < min_y and min_x <= s[0] <= max_x,
                90: lambda s: s[0] < min_x and min_y <= s[1] <= max_y,
                180: lambda s: s[1] > max_y and min_x <= s[0] <= max_x,
                270: lambda s: s[0] > max_x and min_y <= s[1] <= max_y,
            },
            "side of": {
                0: lambda s: min_y <= s[1] <= max_y,
                90: lambda s: min_x <= s[0] <= max_x,
                180: lambda s: min_y <= s[1] <= max_y,
                270: lambda s: min_x <= s[0] <= max_x,
            },
        }

        compare_func = comparison_dict.get(place_type, {}).get(target_rotation)
        if compare_func is None:
            return []

        valid = []
        for sol in solutions:
            if compare_func(sol.center):
                sol.score += self.constraint_bouns
                valid.append(sol)
        return valid

    def place_distance(self, distance_type, target_object, solutions):
        target_poly = Polygon(target_object.coords)
        valid = []
        distances = []

        for sol in solutions:
            sol_poly = Polygon(sol.coords)
            dist = target_poly.distance(sol_poly)
            distances.append(dist)
            sol.score = dist
            valid.append(sol)

        if not distances:
            return valid

        min_d, max_d = min(distances), max(distances)
        if min_d == max_d:
            for sol in valid:
                sol.score = 0.5
            return valid

        if distance_type == "near":
            if min_d < NEAR_DISTANCE_THRESHOLD:
                points = [(min_d, 1), (NEAR_DISTANCE_THRESHOLD, 0), (max_d, 0)]
            else:
                points = [(min_d, 0), (max_d, 0)]
        elif distance_type == "far":
            points = [(min_d, 0), (max_d, 1)]
        else:
            return valid

        f = interp1d(
            [p[0] for p in points], [p[1] for p in points],
            kind="linear", fill_value="extrapolate",
        )
        for sol in valid:
            sol.score = float(f(sol.score))
        return valid

    def place_face(self, face_type, target_object, solutions):
        if face_type == "face to":
            return self._place_face_to(target_object, solutions)
        elif face_type == "face same as":
            return self._place_face_same(target_object, solutions)
        elif face_type == "face opposite to":
            return self._place_face_opposite(target_object, solutions)
        return []

    def _place_face_to(self, target_object, solutions):
        unit_vectors = {
            0: np.array([0.0, 1.0]),
            90: np.array([1.0, 0.0]),
            180: np.array([0.0, -1.0]),
            270: np.array([-1.0, 0.0]),
        }
        target_poly = Polygon(target_object.coords)
        valid = []
        for sol in solutions:
            far_point = np.array(sol.center) + 1e6 * unit_vectors[sol.rotation]
            half_line = LineString([sol.center, far_point])
            if half_line.intersects(target_poly):
                sol.score += self.constraint_bouns
                valid.append(sol)
        return valid

    def _place_face_same(self, target_object, solutions):
        valid = []
        for sol in solutions:
            if sol.rotation == target_object.rotation:
                sol.score += self.constraint_bouns
                valid.append(sol)
        return valid

    def _place_face_opposite(self, target_object, solutions):
        opposite = (target_object.rotation + 180) % 360
        valid = []
        for sol in solutions:
            if sol.rotation == opposite:
                sol.score += self.constraint_bouns
                valid.append(sol)
        return valid

    def place_alignment_center(self, alignment_type, target_object, solutions):
        tx, ty = target_object.center
        valid = []
        for sol in solutions:
            sx, sy = sol.center
            if abs(sx - tx) < ALIGNMENT_EPSILON or abs(sy - ty) < ALIGNMENT_EPSILON:
                sol.score += self.constraint_bouns
                valid.append(sol)
        return valid

    @staticmethod
    def _get_room_size(polygon, wall_height):
        min_x, min_z, max_x, max_z = polygon.bounds
        w, d = max_x - min_x, max_z - min_z
        return (max(w, d), wall_height, min(w, d))


class DFS_Solver_Wall(BaseDFSSolver):
    def __init__(self, grid_size, random_seed=0, max_duration=5, constraint_bouns=100):
        super().__init__(grid_size, random_seed, max_duration, constraint_bouns)

    @staticmethod
    def _convert_initial_state(initial_state):
        return {
            k: WallPlacement(vertex_min=v[0], vertex_max=v[1], rotation=v[2], coords=v[3], score=v[4])
            if not isinstance(v, WallPlacement) else v
            for k, v in initial_state.items()
        }

    def get_solution(self, room_poly, wall_objects_list, constraints, initial_state):
        initial_state = self._convert_initial_state(initial_state)
        grid_points = self.create_grids(room_poly)
        self.start_time = time.time()
        try:
            self.dfs(room_poly, wall_objects_list, constraints, grid_points, initial_state)
        except SolutionFound:
            logger.info(f"Time taken: {time.time() - self.start_time:.2f}s")

        return self.get_max_solution(self.solutions)

    def dfs(self, room_poly, wall_objects_list, constraints, grid_points, placed_objects):
        if len(wall_objects_list) == 0:
            self.solutions.append(placed_objects)
            return placed_objects

        self._check_timeout()

        object_name, object_dim = wall_objects_list[0]
        placements = self.get_possible_placements(
            room_poly, object_dim, constraints[object_name], grid_points, placed_objects
        )

        if len(placements) == 0:
            self.solutions.append(placed_objects)

        paths = []
        for placement in placements:
            placed_objects_updated = {**placed_objects, object_name: placement}
            sub_paths = self.dfs(
                room_poly, wall_objects_list[1:], constraints,
                grid_points, placed_objects_updated,
            )
            paths.extend(sub_paths)
        return paths

    def get_possible_placements(self, room_poly, object_dim, constraint, grid_points, placed_objects):
        all_solutions = self.filter_collision(
            placed_objects,
            self.get_all_solutions(room_poly, grid_points, object_dim, constraint["height"]),
        )
        random.shuffle(all_solutions)

        target_name = constraint["target_floor_object_name"]
        if target_name is not None and target_name in placed_objects:
            all_solutions = self.score_solution_by_distance(
                all_solutions, placed_objects[target_name]
            )
            all_solutions.sort(key=lambda p: p.score, reverse=True)
        return all_solutions

    def create_grids(self, room_poly):
        poly_coords = list(room_poly.exterior.coords)
        grid_points = []
        for i in range(len(poly_coords) - 1):
            line = LineString([poly_coords[i], poly_coords[i + 1]])
            for j in range(0, int(line.length), self.grid_size):
                point_on_line = substring(line, j, j)
                if point_on_line:
                    grid_points.append((point_on_line.x, point_on_line.y))
        return grid_points

    def get_all_solutions(self, room_poly, grid_points, object_dim, height):
        obj_length, obj_height, obj_width = object_dim
        obj_half_length = obj_length / 2

        rotation_adjustments = {
            0: ((-obj_half_length, 0), (obj_half_length, obj_width)),
            90: ((0, -obj_half_length), (obj_width, obj_half_length)),
            180: ((-obj_half_length, -obj_width), (obj_half_length, 0)),
            270: ((-obj_width, -obj_half_length), (0, obj_half_length)),
        }

        solutions = []
        for rotation in [0, 90, 180, 270]:
            for point in grid_points:
                cx, cy = point
                ll, ur = rotation_adjustments[rotation]
                lower_left = (cx + ll[0], cy + ll[1])
                upper_right = (cx + ur[0], cy + ur[1])
                obj_box = box(*lower_left, *upper_right)

                if room_poly.contains(obj_box):
                    obj_coords = obj_box.exterior.coords[:]
                    on_edge = [
                        c for c in obj_coords
                        if room_poly.boundary.contains(Point(c))
                    ]
                    if len(set(on_edge)) >= 2:
                        solutions.append(WallPlacement(
                            vertex_min=(lower_left[0], height, lower_left[1]),
                            vertex_max=(upper_right[0], height + obj_height, upper_right[1]),
                            rotation=rotation,
                            coords=tuple(obj_coords),
                            score=1,
                        ))
        return solutions

    def filter_collision(self, placed_objects, solutions):
        boxes = [
            Box3D(
                min_point=Vertex3D(x=obj.vertex_min[0], y=obj.vertex_min[1], z=obj.vertex_min[2]),
                max_point=Vertex3D(x=obj.vertex_max[0], y=obj.vertex_max[1], z=obj.vertex_max[2]),
            )
            for obj in placed_objects.values()
        ]

        valid = []
        for sol in solutions:
            sol_box = Box3D(
                min_point=Vertex3D(x=sol.vertex_min[0], y=sol.vertex_min[1], z=sol.vertex_min[2]),
                max_point=Vertex3D(x=sol.vertex_max[0], y=sol.vertex_max[1], z=sol.vertex_max[2]),
            )
            if not any(b.intersects(sol_box) for b in boxes):
                valid.append(sol)
        return valid

    def score_solution_by_distance(self, solutions, target_object):
        tx = (target_object.vertex_min[0] + target_object.vertex_max[0]) / 2
        ty = (target_object.vertex_min[1] + target_object.vertex_max[1]) / 2
        tz = (target_object.vertex_min[2] + target_object.vertex_max[2]) / 2

        scored = []
        for sol in solutions:
            sx = (sol.vertex_min[0] + sol.vertex_max[0]) / 2
            sy = (sol.vertex_min[1] + sol.vertex_max[1]) / 2
            sz = (sol.vertex_min[2] + sol.vertex_max[2]) / 2
            dist = np.sqrt((sx - tx) ** 2 + (sy - ty) ** 2 + (sz - tz) ** 2)
            scored.append(WallPlacement(
                vertex_min=sol.vertex_min,
                vertex_max=sol.vertex_max,
                rotation=sol.rotation,
                coords=sol.coords,
                score=sol.score + self.constraint_bouns * (1 / dist) if dist > 0 else sol.score,
            ))
        return scored
