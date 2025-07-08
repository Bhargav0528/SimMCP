"""
Very thin “planner”: maps key phrases to canned recipes.
Swap for an LLM or proper prompt/grammar later.
"""
import json, pathlib
from schemas import Recipe
 
TEMPLATE_DIR = pathlib.Path(__file__).with_suffix('').parent / "templates"
 
def nl_to_recipe(user_request: str) -> Recipe:
    # naïve match
    if "mass" in user_request and "spring" in user_request:
        with open(TEMPLATE_DIR / "msd.json") as fp:
            data = json.load(fp)
        return Recipe.model_validate(data)
    raise ValueError("unsupported request")