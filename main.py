from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from schemas import Recipe
from planner import nl_to_recipe
from executor import EXECUTOR
 
app = FastAPI(title="MCP demo")
 
class NLRequest(BaseModel):
    prompt: str
 
@app.post("/simulate")
def simulate(req: NLRequest):
    try:
        recipe: Recipe = nl_to_recipe(req.prompt.lower())
    except Exception as e:
        raise HTTPException(400, f"Planner error: {e}")
 
    try:
        result = EXECUTOR.execute(recipe)
    except Exception as e:
        raise HTTPException(500, f"Execution error: {e}")
 
    return {
        "status": "ok",
        **result
    }