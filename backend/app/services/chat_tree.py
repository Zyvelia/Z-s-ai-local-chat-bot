"""Pure chat-tree logic shared by API and unit tests."""

def path_to(tree: dict, leaf_id: str | None) -> list:
    if not leaf_id:
        return []
    path = []
    visited = set()
    node_id = leaf_id
    while node_id:
        if node_id in visited or node_id not in tree:
            raise ValueError("Broken or cyclic conversation tree")
        visited.add(node_id)
        current = tree[node_id]
        path.append(current)
        node_id = current.parent_id
    return list(reversed(path))


def active_path(tree: dict, leaf_id: str | None) -> list:
    return path_to(tree, leaf_id)


def siblings_for(tree: dict, message) -> list:
    return sorted((m for m in tree.values() if m.parent_id == message.parent_id and m.role == "assistant"), key=lambda m: (m.created_at, m.id))


def validate_alternation(path: list) -> bool:
    return all(a.role != b.role for a, b in zip(path, path[1:]))


def roleplay_prompt(enabled: bool) -> str:
    return ("Write immersive, character-consistent dialogue. Use *asterisks* for actions and narration, "
            "and quotation marks for spoken dialogue where natural. Do not control the user's character.\n"
            if enabled else "Use ordinary conversational prose rather than roleplay narration.\n")
