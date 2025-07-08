from pydantic import BaseModel, Field, conlist, constr
from typing import List, Dict, Literal, Optional
 
class OpBase(BaseModel):
    cmd: Literal[
        "new_system", "add_block", "add_line",
        "set_param", "sim", "export"]
 
class AddBlockOp(OpBase):
    cmd: Literal["add_block"]
    block: str    
    name: str    
    position: conlist(int, min_length=4, max_length=4)
    value: Optional[str] = None
 
class AddLineOp(OpBase):
    cmd: Literal["add_line"]
    src: str    
    dst: str
 
class SetParamOp(OpBase):
    cmd: Literal["set_param"]
    target: str    
    params: Dict[str, str]
 
class SimOp(OpBase):
    cmd: Literal["sim"]
    stopTime: constr(pattern=r"^\d+(\.\d+)?$")
 
class ExportOp(OpBase):
    cmd: Literal["export"]
    signal: str    
    filename: str
 
Op = AddBlockOp | AddLineOp | SetParamOp | SimOp | ExportOp
 
class Recipe(BaseModel):
    modelName: str    
    ops: List[Op]