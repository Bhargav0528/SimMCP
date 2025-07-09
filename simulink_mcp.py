# simulink_mcp.py

from pathlib import Path
from fastmcp import FastMCP, Context
from tools.core_tools.functions import *
from tools.uav_tools.functions import *
# ──────────────────────────────────────────────────────────────────────
# Fast-MCP host
# ----------------------------------------------------------------------
mcp = FastMCP("Simulink Toolbox (iterative)")

RES_DIR = Path(__file__).parent / "resources"

# ────────────────────────────────────────────────────────────────
# ⬦ 2. dynamic resource template


@mcp.resource("res://{filepath*}")
def get_static(filepath: str, ctx: Context):
    """
    Serve any file under ./resources/ as an MCP resource.

    Examples
    --------
    res://README.md
    res://examples/mass_spring_recipe.json
    """
    full = (RES_DIR / filepath).resolve()

    # security: keep access inside the folder
    if not str(full).startswith(str(RES_DIR)):
        raise FileNotFoundError("outside resources dir")

    if not full.exists():
        raise FileNotFoundError(filepath)

    # simple binary read
    data = full.read_bytes()

    # fastmcp figures out MIME type from return value,
    # but we can be explicit for images / pdf etc.
    mime, _ = mimetypes.guess_type(full.name)
    return {
        "content": base64.b64encode(data).decode(),
        "mime_type": mime or "application/octet-stream",
        "encoding": "base64",
        "filename": full.name,
    }


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

mcp.tool()(start_matlab_engine)
mcp.tool()(create_uav_scenario)
mcp.tool()(add_mesh)
mcp.tool()(create_platform)
mcp.tool()(update_platform_mesh)
mcp.tool()(load_uav_mission)
mcp.tool()(create_mission_parser)
mcp.tool()(parse_mission)
mcp.tool()(show_3d_scene)
mcp.tool()(setup_scenario)
mcp.tool()(advance_scenario)
mcp.tool()(query_trajectory)
mcp.tool()(move_platform)
mcp.tool()(update_camera_target)
mcp.tool()(drawnow_limitrate)
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
