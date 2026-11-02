"""Private JSON-lines transport for a single game's isolated worker."""
from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path
import sys


def main() -> None:
    worker_path = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(worker_path.parent))
    spec = importlib.util.spec_from_file_location("_persistent_solver", worker_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with contextlib.redirect_stdout(sys.stderr):
        spec.loader.exec_module(module)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            image_path = Path(request["image_path"])
            board = request.get("parsed_board")
            with contextlib.redirect_stdout(sys.stderr):
                response = module.solve(image_path) if board is None else module.solve(image_path, parsed_board=board)
            payload = {"response": response}
        except Exception as exc:
            payload = {"error": str(exc)}
        print(json.dumps(payload), flush=True)


if __name__ == "__main__":
    main()
