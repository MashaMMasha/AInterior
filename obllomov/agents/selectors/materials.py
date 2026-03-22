from difflib import SequenceMatcher

import matplotlib.colors as mcolors

from obllomov.agents.retrievers import BaseRetriever
from obllomov.storage.assets import BaseAssets

from .base import BaseSelector


class MaterialSelector(BaseSelector):

    def __init__(
        self,
        material_retriever: BaseRetriever,   
        color_retriever: BaseRetriever,      
        selected_materials: list[str],
    ):
        super().__init__()
        self.material_retriever = material_retriever
        self.color_retriever = color_retriever
        self.selected_materials = material_retriever
        self.colors = list(mcolors.CSS4_COLORS.keys())

    def select(self, queries: list[str], **kwargs) -> list[str]:
        topk = kwargs.get("topk", 5)
        candidates_per_query = self.match_material(queries, topk=topk)

        selected = []
        for candidates in candidates_per_query:

            top = candidates[0]
            filtered = [c for c in candidates if c not in self.used_assets]
            chosen = filtered[0] if filtered else top
            selected.append(chosen)

        return selected

    def match_material(
        self,
        queries: list[str],
        topk: int = 5,
    ) -> list[list[str]]:
        material_results = self.material_retriever.score(queries)

        string_bonus = self._string_similarity_matrix(queries, self.selected_materials)

        material_results = []
        for q_idx, row in enumerate(material_results):
            scored = [
                (asset_id, score + string_bonus[q_idx][self.selected_materials.index(asset_id)])
                for asset_id, score in row
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            material_results.append([asset_id for asset_id, _ in scored[:topk]])

        return material_results

    def select_color(
        self,
        queries: list[str],
        topk: int = 5,
    ) -> list[list[str]]:
        color_results = self.color_retriever.retrieve(queries, k=topk)
        return [
            [asset_id for asset_id, _ in row]
            for row in color_results
        ]

    def _string_similarity_matrix(
        self,
        queries: list[str],
        materials: list[str],
    ) -> list[list[float]]:
        return [
            [SequenceMatcher(None, q, m).ratio() for m in materials]
            for q in queries
        ]
