from pydantic import BaseModel


class ModeSpec(BaseModel, frozen=True):
    """What afm_lib needs to know about one Mode Master preset.
    Nodes look mode-specific facts up here instead of hard-coding them."""
    name: str                    # exact string the MCP server reads from the Igor title bar
    setpoint_key: str            # get_experiment_status field the Z feedback uses in this mode
    scan_tool: str               # MCP tool that acquires one frame
    loop_tool: str | None = None # MCP tool for hysteresis loops; None = not available in this mode