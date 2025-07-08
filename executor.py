"""
*M*odel-*C*ompute-*P*ublish executor.
Runs inside a machine/container that has MATLAB & Simulink installed.
"""
import tempfile, json, subprocess, os, shutil
import matlab.engine
from schemas import Recipe
 
class MCPExecutor:
    def __init__(self):
        # Start MATLAB once; keep engine warm
        self.eng = matlab.engine.start_matlab("-nodisplay -nosplash -nodesktop")
 
    def execute(self, recipe: Recipe) -> dict:
        mdl = recipe.modelName
        eng = self.eng
        eng.eval(f"new_system('{mdl}'); open_system('{mdl}')", nargout=0)
 
        for op in recipe.ops:
            match op.cmd:
                case "add_block":
                    dest = f"{mdl}/{op.name}"
                    eng.add_block(op.block, dest, nargout=0)
    
                    # convert to Matlab numeric vector
                    if op.position:
                        eng.set_param(dest, "Position",
                                    matlab.double(op.position), nargout=0)
                    if op.value:
                        eng.set_param(dest, "Value", op.value, nargout=0)
 
                case "add_line":
                    eng.add_line(mdl, op.src, op.dst, nargout=0)
 
                case "set_param":
                    eng.set_param(f"{mdl}/{op.target}", *sum(op.params.items(), ()), nargout=0)
 
                case "sim":
                    simout = eng.sim(
                        mdl,
                        "StopTime", op.stopTime,
                        "SaveTime",   "on",
                        "SaveOutput", "on",
                        "SaveFormat", "Array",          # ← key line
                        "ReturnWorkspaceOutputs", "on",
                        nargout=1)
                
                    self.tout = eng.get(simout, 'tout', nargout=1)
                    self.yout = eng.get(simout, 'yout', nargout=1)
 
                case "export":
                    fig = eng.figure(nargout=1)
                    eng.plot(self.tout, self.yout, nargout=0)
                    eng.xlabel("Time (s)", nargout=0)
                    eng.ylabel(op.signal, nargout=0)
                    tmp_png = os.path.join(tempfile.gettempdir(), op.filename)
                    eng.exportgraphics(fig, tmp_png, nargout=0)
        # For the demo, return local path; replace by S3 URL in prod
        return {"image_path": tmp_png}
 
# singleton
EXECUTOR = MCPExecutor()