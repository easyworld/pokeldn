"""The smallest plugin: one tool, one script. Copy this folder to start your own."""
from pokeldn.plugins import Field, Tool


def register(api):
    api.add_tool("frlg", Tool(
        "hello-greet",                          # unique among every tool
        "Say hello",                            # its name on the Games page
        "greet.py",                             # its script, next to this file
        "Greets your trainer in the output.",   # the line under its name
        ("Nothing to do on the console.", "Press Start and read the output."),
        fields=(Field("--greeting", "Greeting", default="Hello",
                      help="The word the tool starts with."),),
        fixed=("--trainer", "{ot}"),            # the trainer name from Settings
    ))
