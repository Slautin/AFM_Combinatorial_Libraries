import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel


def _jsonable(o):
    if isinstance(o, BaseModel):  return o.model_dump()
    if isinstance(o, Path):       return str(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return str(o)


def save_json(path, obj) -> Path:
    """Write a run artifact as UTF-8 JSON. Pydantic models are dumped; anything exotic
    falls back to str() — a serialization quirk must never kill a finished run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_jsonable),
                    encoding="utf-8")
    return path