from datetime import datetime
from pathlib import Path

import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]      # not Path().resolve()

SPM_MCP_SERVER_CONFIG = {
    "spm": {"transport": "streamable-http", "url": "http://127.0.0.1:8000/mcp"},
}

# --- bounds (loop_plan.py imports this) ---
LOOP_BOUNDS = {
    "v_dc_max_v":       (1.0, 30.0),
    "frequency_hz":     (0.1, 1.0),
    "var0_phase":       (0.0, 1.0),
    "var1_pulsetime_s": (1.0e-3, 0.1),
    "n_cycles":         (1, 3),
}

# --- ensure_* tolerances: below this, the position is already correct ---
STAGE_TOL_M = 300.0e-6      # open-loop stage; must exceed the backlash you measured
FRAME_TOL_M = 100.0e-9
TIP_TOL_M   = 50.0e-9

# --- run-scoped artifacts ---
RUNS_ROOT = PROJECT_ROOT / "runs"
_run_dir: Path | None = None

def new_run(tag: str = "") -> Path:
    global _run_dir
    name = datetime.now().strftime("%Y%m%d_%H%M%S") + (f"_{tag}" if tag else "")
    _run_dir = RUNS_ROOT / name
    _run_dir.mkdir(parents=True, exist_ok=True)
    return _run_dir

def _scifireaders_command() -> str:
    """Path to the SciFiReaders MCP entry point. On Windows the entry-point .exe
    sits next to the interpreter, which is more reliable than a CWD-relative
    guess — notebooks run from notebooks/, not the repo root."""
    exe = shutil.which("scifireaders_mcp")
    if exe:
        return exe
    return Path(".venv") / "Scripts" / "scifireaders_mcp.exe"#str(Path(sys.executable).parent / "scifireaders_mcp.exe")

SCIFIREADERS_MCP_COMMAND = _scifireaders_command()

def run_dir() -> Path:
    return _run_dir if _run_dir is not None else new_run()

def records_dir() -> Path: return run_dir() / "records"
def loops_dir()   -> Path: return run_dir() / "loops"
def cache_dir() -> Path: return run_dir() / "cache"