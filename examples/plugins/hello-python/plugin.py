from myagent_plugin_sdk import Plugin


plugin = Plugin()
state = {"activated": False, "calls": 0}


@plugin.on_activate
def activate(_context: dict) -> None:
    state["activated"] = True


@plugin.tool(
    name="greet",
    description="Return a greeting for the supplied name.",
    effect="read",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name to greet.",
            }
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)
def greet(name: str) -> dict:
    state["calls"] += 1
    return {
        "message": f"Hello, {name}!",
        "plugin": "example.hello-python",
        "activated": state["activated"],
        "calls": state["calls"],
    }


@plugin.hook("SessionStart", hook_id="hello-session", priority=200)
def hello_session(_payload: dict) -> dict:
    return {"additional_context": "The hello-python example plugin is active."}


@plugin.command(
    name="hello",
    description="Create a greeting request.",
    usage="<name>",
)
def hello_command(arguments: str, _context: dict) -> dict:
    name = arguments.strip() or "world"
    return {"prompt": f"Use the greeting tool for {name}."}
