# simulink_mcp.py
import os, tempfile, uuid, matlab.engine, matlab
import mimetypes, base64
from pathlib import Path
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, constr

MODEL_DIR = Path.home() / "SimMCP-models"   # ~/SimMCP-models
MODEL_DIR.mkdir(exist_ok=True)


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
    def __init__(self, gui: bool = False):
        flags = [] if gui else ["-nodisplay", "-nosplash", "-nodesktop"]
        self.eng = matlab.engine.start_matlab(*flags)
        self.mdl   = f"job_{uuid.uuid4().hex[:8]}"
        self.eng.new_system(self.mdl, nargout=0)

    # low-level helpers
    # ────────────────────────────────────────────────────────────────────
    # 1  add_block  – refuse duplicates; autoroute position if omitted
    # revised add_block  ──────────────────────────────────────────────
    def add_block(self, block_path, name, position=None, value=None):
        dest = f"{self.mdl}/{name}"

        # duplicate-name guard (root level only)
        exists = self.eng.find_system(
            self.mdl, "SearchDepth", 1, "Name", name, nargout=1)
        if exists:                                             # list non-empty ➜ duplicate
            raise ValueError(f"Block name '{name}' already exists.")

        # auto-grid position if none supplied
        if position is None:
            idx = len(self.eng.find_system(self.mdl, "SearchDepth", 1, nargout=1))
            position = [40 + 80*idx, 40, 80 + 80*idx, 90]

        self.eng.add_block(block_path, dest, "Position",
                        matlab.double(position), nargout=0)

        if value is not None:
            self.eng.set_param(dest, "Value", str(value), nargout=0)

    # ────────────────────────────────────────────────────────────────────
    # 2  add_line  – autorouting avoids crossing lines
    def add_line(self, src, dst):
        self.eng.add_line(self.mdl, src, dst, "autorouting","on", nargout=0)

    # ────────────────────────────────────────────────────────────────────
    # 3  sim  – auto-insert Outport if none exists
    def sim(self, stop_time: str):
        if not self.eng.find_system(self.mdl, 'SearchDepth',1,
                                    'BlockType','Outport', nargout=1):
            # pick first root block’s first port
            blk = self.eng.find_system(self.mdl, 'SearchDepth',1,
                                    'Type','block', nargout=1)[0]
            self.eng.add_block("simulink/Sinks/Out1",
                            f"{self.mdl}/AUTO_OUT", nargout=0)
            self.eng.add_line(self.mdl, f"{blk}/1", "AUTO_OUT/1",
                            "autorouting","on", nargout=0)

        self.eng.set_param(self.mdl, "SaveTime","on", "SaveOutput","on",
                        "SaveFormat","Array", nargout=0)
        self.simout = self.eng.sim(self.mdl, "StopTime", stop_time,
                                "ReturnWorkspaceOutputs","on", nargout=1)

    # ────────────────────────────────────────────────────────────────────
    # 4  set_param  – apply multiple mask parameters to a block in one call
    def set_param(self, target: str, params: dict[str, str]):
        """
        Apply multiple mask parameters to a block in one call.
        Example: target='Gain', params={'Gain':'5','SampleTime':'0.1'}
        """
        dest = f"{self.mdl}/{target}"

        # --- safe duplicate / existence check (no blockExists) -------------
        exist = self.eng.find_system(self.mdl, "SearchDepth", 1,
                                    "Name", target, nargout=1)
        if not exist:
            raise ValueError(f"Block '{target}' not found at top level.")

        # flatten {'Param':'Val', ...} -> ['Param','Val', ...]
        kv = sum([[k, str(v)] for k, v in params.items()], [])
        self.eng.set_param(dest, *kv, nargout=0)


    # ────────────────────────────────────────────────────────────────────
    # 5  export_plot  – three-level fallback
    def export_plot(self,
                signal: str = "yout",
                filename: str | None = None,
                dataset_index: int = 1) -> dict:
        """
        Return a PNG plot of the main output signal.

        Parameters
        ----------
        signal : str
            'yout' (default) or 'logsout' to pick a dataset.
        filename : str | None
            Suggested file name for the PNG.
        dataset_index : int
            If signal='logsout', choose the N-th dataset (1-based).

        Returns
        -------
        dict
            Rich-content payload Claude will display inline.
        """
        eng = self.eng

        # ── ① try classic arrays ─────────────────────────────────────────
        try:
            tout = eng.get(self.simout, 'tout', nargout=1)
            yout = eng.get(self.simout, signal, nargout=1)

        # ── ② fall back to first dataset in logsout ─────────────────────
        except matlab.engine.MatlabExecutionError:
            logs = eng.get(self.simout, 'logsout', nargout=1)
            ds   = eng.get(logs, 'get', dataset_index, nargout=1)
            vals = eng.get(ds, 'Values', nargout=1)
            tout = vals['Time']
            yout = vals['Data']

        # ── flatten 2-D matlab.double → 1-D Python list/array ────────────
        def _to_1d(arr):
            if len(arr) and isinstance(arr[0], list):
                return [row[0] for row in arr]   # N×1
            return arr                           # already 1-D

        tout = _to_1d(tout)
        yout = _to_1d(yout)

        # ── generate the plot ────────────────────────────────────────────
        fig = eng.figure(nargout=1)
        eng.plot(tout, yout, nargout=0)
        eng.xlabel("Time (s)", nargout=0)
        eng.ylabel(signal,      nargout=0)

        fname = filename or f"plot_{uuid.uuid4().hex[:6]}.png"
        path  = os.path.join(tempfile.gettempdir(), fname)
        eng.exportgraphics(fig, path, nargout=0)

        # archive the model for later inspection
        model_path = MODEL_DIR / f"{self.mdl}.slx"
        eng.save_system(self.mdl, str(model_path), nargout=0)

        import base64, pathlib
        return {
            "content"  : base64.b64encode(open(path, "rb").read()).decode(),
            "mime_type": "image/png",
            "encoding" : "base64",
            "filename" : pathlib.Path(path).name
        }

    
    # ────────────────────────────────────────────────────────────────────
    # 6  screenshot  – capture a PNG image of the current Simulink diagram
    def screenshot(self, filename: str = "diagram.png") -> dict:
        """
        Capture a PNG image of the current Simulink top-level diagram and
        return it as a rich-image payload Claude can display inline.
        """
        # 1. Ensure the diagram window exists (hidden if -nodisplay)
        self.eng.open_system(self.mdl, nargout=0)

        # 2. Build an absolute filename in /tmp or your model dir
        fname = filename or f"diagram_{uuid.uuid4().hex[:6]}.png"
        path  = os.path.join(tempfile.gettempdir(), fname)

        # 3. Use MATLAB's print with -s<model> to snapshot the canvas
        cmd = f"print('-s{self.mdl}', '-dpng', '{path}', '-r150');"
        self.eng.eval(cmd, nargout=0)          # 150 DPI; tweak if you like

        # 4. Optionally keep a copy alongside the .slx
        (MODEL_DIR / fname).write_bytes(Path(path).read_bytes())

        # 5. Return a rich-content dict so Claude inlines the image
        return {
            "content"  : base64.b64encode(open(path, "rb").read()).decode(),
            "mime_type": "image/png",
            "encoding" : "base64",
            "filename" : fname
        }

    # ────────────────────────────────────────────────────────────────────
    # 7  close  – close the MATLAB engine
    def close(self):
        self.eng.quit()

# ──────────────────────────────────────────────────────────────────────
# 2.  In-memory session registry
# ----------------------------------------------------------------------
_SESS: dict[str, SimulinkSession] = {}

def _create_session(gui: bool = False) -> str:
    sid = uuid.uuid4().hex[:8]

    # 2️⃣  Pass the flag when you instantiate SimulinkSession
    _SESS[sid] = SimulinkSession(gui=gui)
    return sid

def _get(sid: str) -> SimulinkSession:
    if sid not in _SESS:
        raise ValueError("invalid session id")
    return _SESS[sid]

# ───────────────────────────────────────────────────────────────
#  Pydantic argument models
# ───────────────────────────────────────────────────────────────
class NewModelArgs(BaseModel):
    """Create a fresh model; gui=True launches MATLAB desktop."""
    gui: bool = False


class Sid(BaseModel):
    session_id: str


class BlockArgs(Sid):
    """Add a block.  If position is omitted the server auto-grids it."""
    block_path: str
    name: str
    position: list[int] | None = None
    value: str | None = None


class LineArgs(Sid):
    """Wire two ports, e.g. src='A/1', dst='B/1'."""
    src: str
    dst: str


class ParamArgs(Sid):
    """Set multiple mask parameters at once."""
    target: str
    params: dict[str, str]


class SimArgs(Sid):
    stop_time: str = Field(..., examples=["10"])


class ExportArgs(Sid):
    """Plot a signal and return a PNG.

    signal :
        'yout'   – main outport array (default)  
        'logsout' – choose from logged datasets
    dataset_index :
        if signal='logsout', which dataset (1-based)
    """
    signal: str = "yout"
    filename: str | None = None
    dataset_index: int = 1


class ShotArgs(Sid):
    filename: str | None = None


# ───────────────────────────────────────────────────────────────
#  Tool definitions
# ───────────────────────────────────────────────────────────────
@mcp.tool(name="new_model",
          description="Create a blank Simulink model and return session_id.")
def new_model(args: NewModelArgs = NewModelArgs()) -> str:
    return _create_session(gui=args.gui)


@mcp.tool(name="add_block", description="Add a block to the model.")
def add_block(args: BlockArgs) -> str:
    _get(args.session_id).add_block(
        args.block_path, args.name, args.position, args.value)
    return "ok"


@mcp.tool(name="add_line", description="Connect two ports.")
def add_line(args: LineArgs) -> str:
    _get(args.session_id).add_line(args.src, args.dst)
    return "ok"


@mcp.tool(name="set_param", description="Set block parameters.")
def set_param(args: ParamArgs) -> str:
    _get(args.session_id).set_param(args.target, args.params)
    return "ok"


@mcp.tool(name="sim",
          description="Run the simulation for the given stop time (s).")
def sim(args: SimArgs) -> str:
    _get(args.session_id).sim(args.stop_time)
    return "done"


@mcp.tool(
    name="export_plot",
    description=(
        "Generate a PNG plot of a logged signal and return it as "
        "inline image content.  By default plots the main Outport ('yout')."
    ),
)
def export_plot(args: ExportArgs) -> dict:
    return _get(args.session_id).export_plot(
        signal=args.signal,
        filename=args.filename,
        dataset_index=args.dataset_index
    )


@mcp.tool(name="screenshot",
          description="Capture a PNG of the current Simulink diagram.")
def screenshot(args: ShotArgs) -> dict:
    return _get(args.session_id).screenshot(
        args.filename or "diagram.png"
    )


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
