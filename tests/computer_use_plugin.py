"""Load Computer Use tests through the same package namespace as the host."""
from importlib import import_module
from pathlib import Path

from plugins import load_plugin
from plugins.host import _module

host = _module(load_plugin(Path(__file__).resolve().parents[1] / "plugins" / "computer-use"))
computer = import_module(host.__name__ + ".computer_use.computer")
computer_policy = import_module(host.__name__ + ".computer_use.computer_policy")
computer_results = import_module(host.__name__ + ".computer_use.computer_results")
