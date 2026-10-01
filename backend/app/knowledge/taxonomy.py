from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyNode:
    id: str
    name: str
    level: str
    parent_id: str | None = None


class Taxonomy:
    def __init__(self, nodes: list[TaxonomyNode]) -> None:
        self._nodes: dict[str, TaxonomyNode] = {}
        for node in nodes:
            if not node.id or node.id in self._nodes:
                raise ValueError(f"Duplicate or empty taxonomy node id: {node.id!r}")
            if not node.name.strip():
                raise ValueError(f"Taxonomy node {node.id!r} has an empty name")
            self._nodes[node.id] = node

        for node in self._nodes.values():
            if node.parent_id is not None and node.parent_id not in self._nodes:
                raise ValueError(
                    f"Taxonomy node {node.id!r} references missing parent {node.parent_id!r}"
                )

        for node_id in self._nodes:
            self._validate_acyclic(node_id)

    def _validate_acyclic(self, node_id: str) -> None:
        seen: set[str] = set()
        current = self._nodes[node_id]
        while current.parent_id is not None:
            if current.id in seen:
                raise ValueError(f"Taxonomy cycle detected at {current.id!r}")
            seen.add(current.id)
            current = self._nodes[current.parent_id]

    def get(self, node_id: str) -> TaxonomyNode | None:
        return self._nodes.get(node_id)

    def children(self, parent_id: str | None) -> list[TaxonomyNode]:
        return sorted(
            (node for node in self._nodes.values() if node.parent_id == parent_id),
            key=lambda node: node.name.lower(),
        )

    def all(self) -> list[TaxonomyNode]:
        return sorted(
            self._nodes.values(),
            key=lambda node: (node.level, node.name.lower(), node.id),
        )

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
