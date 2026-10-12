"""The Plugin Test Kit: one of everything the plugin API offers, each safe to run with no console."""
import testkit_common as kit
from pokeldn.plugins import Field, Game, Tool

IDLE = ("Nothing to do on the console.", "Press Start and read the output.")


def register(api):
    api.add_game(Game("test-kit", "Plugin Test Kit", "Test", "", (
        Tool("test-kit-selftest", "Self-test", "selftest.py",
             "Checks that this plugin loads, gets its arguments and reaches its radio.", IDLE, fields=(
                 Field("--word", "A word", default="pikachu", help="Comes back in the output."),
                 Field("--number", "A number", "number", default="25"),
                 Field("--color", "A choice", "choice", default="red",
                       choices=(("red", "Red"), ("blue", "Blue"), ("green", "Green"))),
                 Field("--loud", "A switch", "switch", default=True),
             ), fixed=("--trainer", "{ot}")),
        Tool("test-kit-session", "Simulated session", "session.py",
             "Pretends to trade, one line per second, so the queue, Stop and the output can be watched.", IDLE,
             fields=(Field("--trades", "Trades", "number", default="3"),
                     Field("--pause", "Seconds per trade", "number", default="2"))),
        Tool("test-kit-fail", "Fail on purpose", "fail.py",
             "Ends with an error, to see how the app reports a plugin that fails.", IDLE,
             fields=(Field("--how", "How", "choice", default="error",
                           choices=(("error", "Raise an error"), ("exit", "Exit with code 3"))),)),
    )), icon="icon.png")
    api.add_tool("frlg", Tool("test-kit-hello", "Hello from a plugin", "hello.py",
                              "A plugin's tool next to the built-in ones; it only says hello.", IDLE,
                              fixed=("--trainer", "{ot}")))
    api.add_radio("testkit", kit.install_radio, "Test Kit radio (carries nothing)")
