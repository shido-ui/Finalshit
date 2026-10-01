from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyNode:
    id: str
    name: str
    level: str
    parent_id: str | None = None


class Taxonomy:
    def __init__(self, nodes: list[TaxonomyNode]) -> None:
        self._nodes = {node.id: node for node in nodes}

    def get(self, node_id: str) -> TaxonomyNode | None:
        return self._nodes.get(node_id)

    def children(self, parent_id: str | None) -> list[TaxonomyNode]:
        return [node for node in self._nodes.values() if node.parent_id == parent_id]

    def all(self) -> list[TaxonomyNode]:
        return sorted(self._nodes.values(), key=lambda node: (node.level, node.name.lower()))

    def resolve_path(self, node_id: str) -> list[TaxonomyNode]:
        path: list[TaxonomyNode] = []
        current = self.get(node_id)
        seen: set[str] = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            path.append(current)
            current = self.get(current.parent_id) if current.parent_id else None
        return list(reversed(path))


DEFAULT_TAXONOMY = Taxonomy([
    TaxonomyNode("physics", "Physics", "subject"),
    TaxonomyNode("chemistry", "Chemistry", "subject"),
    TaxonomyNode("mathematics", "Mathematics", "subject"),
])
