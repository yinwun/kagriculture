#!/usr/bin/env python
"""Execute a Kaggle notebook locally, honouring %%writefile cells.

Usage:
    python scripts/run_notebook.py <notebook.ipynb> <workdir>

Cells are run in order in a shared namespace. `%%writefile name` cells are
written to <workdir>/name instead of being executed. This lets us reproduce a
public notebook's build (and therefore verify artifact hashes) offline.
"""
import json
import os
import re
import sys
import traceback
from pathlib import Path


def main() -> int:
    nb_path, workdir = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    os.chdir(workdir)
    sys.path.insert(0, str(workdir))

    nb = json.loads(nb_path.read_text())
    ns = {"__name__": "__main__", "__file__": str(workdir / "driver.py")}
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        m = re.match(r"%%writefile\s+(\S+)\s*\n", src)
        if m:
            target = workdir / m.group(1)
            target.write_text(src[m.end():])
            print(f"[cell {i}] wrote {m.group(1)} ({target.stat().st_size} bytes)", flush=True)
            continue
        if src.lstrip().startswith("%%"):
            print(f"[cell {i}] skipped magic cell", flush=True)
            continue
        # strip ipython line-magics / shell escapes so plain python can run
        if any(ln.lstrip().startswith(("%", "!")) for ln in src.splitlines()):
            src = "\n".join("pass  # stripped magic" if ln.lstrip().startswith(("%", "!")) else ln
                            for ln in src.splitlines())
        print(f"[cell {i}] exec ({len(src)} chars)", flush=True)
        try:
            exec(compile(src, f"<cell {i}>", "exec"), ns)
        except Exception:
            print(f"[cell {i}] FAILED", flush=True)
            traceback.print_exc()
            return 1
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
