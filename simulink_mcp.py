# simulink_mcp.py

from pathlib import Path
from fastmcp import FastMCP, Context
import json

from tools.core_tools.functions import new_model, add_block, add_line, set_param, sim, export_plot, close_session

# ──────────────────────────────────────────────────────────────────────
# Fast-MCP host
# ----------------------------------------------------------------------
mcp = FastMCP("Simulink Toolbox (iterative)")

RES_DIR = Path(__file__).parent / "resources"

# ────────────────────────────────────────────────────────────────
# ⬦ 2. dynamic resource template


@mcp.resource("simulink://blocks")
def get_simulink_blocks_json() -> dict:
    """
    Serve the entire Simulink blocks JSON data as a resource.
    """
    JSON_PATH = Path(__file__).parent / "resources/SimulinkCore/core_blocks.json"
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        SIMULINK_BLOCKS_DATA = json.load(f)
    return SIMULINK_BLOCKS_DATA


# ──────────────────────────────────────────────────────────────────────
# 4.  Fast-MCP tool definitions
# ----------------------------------------------------------------------


mcp.tool(name="new_model",
         description="Create a blank Simulink model; returns a session_id.")(new_model)
mcp.tool(name="add_block",
         description="Add a block to the model.")(add_block)
mcp.tool(name="add_line",
         description="Connect two ports, e.g. src='A/1' dst='B/1'.")(add_line)
mcp.tool(name="set_param",
         description="Set block parameters.")(set_param)
mcp.tool(name="sim",
         description="Run the simulation for the given stop time (seconds).")(sim)
mcp.tool(name="export_plot",
         description="Generate a PNG plot of the main output signal.")(export_plot)
mcp.tool(name="close_session",
         description="Close the MATLAB session and free resources.")(close_session)
# ──────────────────────────────────────────────────────────────────────



if __name__ == "__main__":
    mcp.run(transport="stdio")
