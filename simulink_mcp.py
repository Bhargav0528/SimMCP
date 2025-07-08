# simulink_mcp.py
import os, tempfile, uuid, matlab.engine, matlab
from pathlib import Path
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, constr

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
# ──────────────────────────────────────────────────────────────────────
# 1.  Session container around a single MATLAB Engine
# ----------------------------------------------------------------------
class SimulinkSession:
    def __init__(self):
        self.mdl   = f"job_{uuid.uuid4().hex[:8]}"
        # self.eng   = matlab.engine.start_matlab(
        #     "-nodisplay -nosplash -nodesktop")
        self.eng   = matlab.engine.start_matlab(
            "-nosplash")
        self.eng.new_system(self.mdl, nargout=0)

    # low-level helpers
    def add_block(self, block_path, name, position=None, value=None):
        dest = f"{self.mdl}/{name}"
        self.eng.add_block(block_path, dest, nargout=0)
        if position:
            self.eng.set_param(dest, "Position",
                               matlab.double(position), nargout=0)
        if value is not None:
            self.eng.set_param(dest, "Value", str(value), nargout=0)

    def add_line(self, src, dst):
        self.eng.add_line(self.mdl, src, dst, nargout=0)

    def set_param(self, target, params: dict[str, str]):
        kv = sum(params.items(), ())
        self.eng.set_param(f"{self.mdl}/{target}", *kv, nargout=0)

    def sim(self, stop_time: str):
        self.eng.set_param(self.mdl,
                           "SaveTime","on","SaveOutput","on",
                           "SaveFormat","Array",
                           nargout=0)
        self.simout = self.eng.sim(
            self.mdl, "StopTime", stop_time,
            "ReturnWorkspaceOutputs","on",
            nargout=1)

    def export_plot(self, signal, filename):
        tout = self.eng.get(self.simout, 'tout', nargout=1)
        yout = self.eng.get(self.simout, 'yout', nargout=1)
        fig  = self.eng.figure(nargout=1)
        self.eng.plot(tout, yout, nargout=0)
        self.eng.xlabel("Time (s)", nargout=0)
        self.eng.ylabel(signal,    nargout=0)

        fname = filename or "result.png"
        path  = os.path.join(tempfile.gettempdir(), fname)
        self.eng.exportgraphics(fig, path, nargout=0)
        return path

    def close(self):
        self.eng.quit()

# ──────────────────────────────────────────────────────────────────────
# 2.  In-memory session registry
# ----------------------------------------------------------------------
_SESS: dict[str, SimulinkSession] = {}

def _create_session() -> str:
    sid = uuid.uuid4().hex[:8]
    _SESS[sid] = SimulinkSession()
    return sid

def _get(sid: str) -> SimulinkSession:
    if sid not in _SESS:
        raise ValueError("invalid session id")
    return _SESS[sid]

# ──────────────────────────────────────────────────────────────────────
# 3.  Pydantic argument models
# ----------------------------------------------------------------------
class Sid(BaseModel):
    session_id: constr(min_length=6, max_length=12)

class BlockArgs(Sid):
    block_path: str
    name: str
    position: list[int] | None = None
    value: str | None = None

class LineArgs(Sid):
    src: str
    dst: str

class ParamArgs(Sid):
    target: str
    params: dict[str, str]

class SimArgs(Sid):
    stop_time: str = Field(examples=["10"])

class ExportArgs(Sid):
    signal: str
    filename: str | None = None

# ──────────────────────────────────────────────────────────────────────
# 4.  Fast-MCP tool definitions
# ----------------------------------------------------------------------
@mcp.tool(name="new_model",
          description="Create a blank Simulink model; returns a session_id.")
def new_model() -> str:
    return _create_session()

@mcp.tool(name="add_block",
          description="Add a block to the model.")
def add_block(args: BlockArgs) -> str:
    _get(args.session_id).add_block(
        args.block_path, args.name, args.position, args.value)
    return "ok"

@mcp.tool(name="add_line",
          description="Connect two ports, e.g. src='A/1' dst='B/1'.")
def add_line(args: LineArgs) -> str:
    _get(args.session_id).add_line(args.src, args.dst)
    return "ok"

@mcp.tool(name="set_param",
          description="Set block parameters.")
def set_param(args: ParamArgs) -> str:
    _get(args.session_id).set_param(args.target, args.params)
    return "ok"

@mcp.tool(name="sim",
          description="Run the simulation for the given stop time (seconds).")
def sim(args: SimArgs) -> str:
    _get(args.session_id).sim(args.stop_time)
    return "done"

@mcp.tool(name="export_plot",
          description="Generate a PNG plot of the main output signal.")
def export_plot(args: ExportArgs) -> str:
    return _get(args.session_id).export_plot(args.signal, args.filename)

@mcp.tool(name="close_session",
          description="Close the MATLAB session and free resources.")
def close_session(args: Sid) -> str:
    _get(args.session_id).close()
    _SESS.pop(args.session_id, None)
    return "closed"

# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Claude Desktop discovers stdio servers automatically
    mcp.run_stdio()
