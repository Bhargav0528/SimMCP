# sim_chat.py ──────────────────────────────────────────────────────────────
import os, json, base64, tempfile, subprocess, webbrowser, textwrap
from pathlib import Path
from typing import Any
import openai, fastmcp                                     # pip install …

# ── 1  Launch MCP server over stdio ───────────────────────────────────────
SERVER = ["fastmcp", "run", "simulink_server.py", "--stdio"]
mcp = fastmcp.MCPClient.open_stdio(SERVER)

# ── 2  Convert MCP tools → OpenAI function-schema list ────────────────────
def tool_to_schema(t: fastmcp.Tool) -> dict[str, Any]:
    schema = t.schema                                    # already JSONSchema
    return {"name": t.name, "description": t.description, "parameters": schema}

OAI_FUNCS = [tool_to_schema(t) for t in mcp.list_tools()]

# helper to execute tool calls
def call_tool(name: str, args: dict[str, Any]) -> str:
    result = getattr(mcp, name)(**args)
    return json.dumps(result)

# ── 3  Chat wrapper with function-calling loop ────────────────────────────
def ask_system(prompt: str):
    msgs = [
        {"role": "system", "content": "You are Simulink-GPT. Use the MCP "
         "tools to create, simulate and visualise models."},
        {"role": "user", "content": prompt}
    ]
    while True:
        rsp = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # or gpt-4o/gpt-4o-mini/gpt-3.5-turbo
            messages=msgs,
            tools=OAI_FUNCS,
            tool_choice="auto"
        )
        msg = rsp.choices[0].message
        if msg.get("tool_calls"):
            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                print(f"\n→ {name}({args})")
                result = call_tool(name, args)
                msgs.append({
                    "role": "assistant",
                    "tool_calls": [call.to_dict()],
                    "content": None
                })
                msgs.append({"role": "tool", "name": name, "content": result})
        else:                                    # final textual answer
            print("\n" + textwrap.fill(msg.content, 80))
            break

# ── 4  Pretty-print images returned as base-64 ────────────────────────────
def tool_result_hook(result_json: str):
    try:
        data = json.loads(result_json)
        if isinstance(data, dict) and "content" in data:
            fn = Path(tempfile.gettempdir()) / data.get("filename", "tmp.png")
            fn.write_bytes(base64.b64decode(data["content"]))
            print(f"[image:{fn}]")
            webbrowser.open(fn.as_uri())
    except Exception:
        pass

# monkey-patch MCPClient → intercept every tool response
old_call = fastmcp.MCPClient.call
def new_call(self, name, payload):
    res = old_call(self, name, payload)
    tool_result_hook(res)
    return res
fastmcp.MCPClient.call = new_call

# ── 5  Run from CLI argument or REPL ──────────────────────────────────────
if __name__ == "__main__":
    import sys
    user_prompt = " ".join(sys.argv[1:]) or "simulate a damped oscillator 10 s"
    ask_system(user_prompt)
