from __future__ import annotations

from typing import Any

from .settings import Settings


def make_model_object(model_id: str, root: str, created: int = 0) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "created": created,
        "owned_by": "local",
        "root": root,
        "permission": [],
    }


def available_models_payload(settings: Settings) -> dict[str, Any]:
    models = []
    for public_id, root in settings.public_model_roots().items():
        models.append(make_model_object(model_id=public_id, root=root))
    return {"object": "list", "data": models}

