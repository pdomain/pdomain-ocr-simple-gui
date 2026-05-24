"""Export the FastAPI app's OpenAPI schema to a file.

Used by `make openapi-export` so the frontend can regenerate
`src/api/types.gen.ts` from the live spec.

Why a script (not an inline `python -c`): the app's lifespan may install
handlers that would contaminate stdout. Writing the JSON directly to the
destination file sidesteps that.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pd_ocr_simple_gui.app import app


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: export_openapi.py <output-path>", file=sys.stderr)
        raise SystemExit(2)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    _ = out.write_text(json.dumps(app.openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
