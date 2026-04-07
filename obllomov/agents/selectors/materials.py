from difflib import SequenceMatcher

import matplotlib.colors as mcolors

from obllomov.agents.retrievers import BaseRetriever
from obllomov.storage.assets import BaseAssets

from .base import BaseSelector

from obllomov.shared.log import logger

# from obllomov.agents.base import BaseAgent


class MaterialSelector(BaseSelector):
    def __init__(self, materials_retriever: BaseRetriever, colors_retriever: BaseRetriever):
        super().__init__()

        self.materials_retriever = materials_retriever
        self.colors_retriever = colors_retriever
        # self.used_assets = []

    def select_materials(self, designs: list[str], topk=5) -> dict:
        candidate_materials, _ = self.materials_retriever.retrieve(designs, topk=topk)
        logger.debug(f"candidate_materials: {candidate_materials}")
        candidate_colors, _ = self.colors_retriever.retrieve(designs, topk=topk)

        design2materials = {}
        for i, design in enumerate(designs):
            logger.debug(f"design: {design}")
            valid_materials = [m for m in candidate_materials[i] if m not in self.used_assets]
            logger.debug(f"valid_materials: {valid_materials}")
            
            selected_material = valid_materials[0] if valid_materials else candidate_materials[i][0]
            selected_color = candidate_colors[i][0]

            logger.debug(f"selected_material: {selected_material}")

            design2materials[design] = {
                "name": selected_material,
                # "color": self.color2rgb(selected_color)
            }
            
        return design2materials
    
    def color2rgb(self, color_name):
        rgb = mcolors.to_rgb(color_name)
        return {"r": rgb[0], "g": rgb[1], "b": rgb[2]}
    
    def string_match(self, a, b):
        return SequenceMatcher(None, a, b).ratio()
