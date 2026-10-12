"""Basic guardrails on plugin code: while a plugin's code is on the call stack, it may not delete,
move or overwrite a file outside the folders it owns, nor start a program that deletes or erases.
An audit hook (PEP 578): it stops mistakes and plain scripts, not code written to get around it
(ctypes, a compiled module). docs/plugins.md, Guardrails.
"""
import os
import re
import sys

# A program that deletes, erases or takes over the machine, by its name without .exe.
DESTRUCTIVE = frozenset((
    "rm", "rmdir", "unlink", "del", "erase", "rd", "rimraf", "shred", "srm", "wipe", "wipefs", "dd",
    "format", "mkfs", "fdisk", "diskpart", "diskutil", "newfs", "cipher", "vssadmin", "bcdedit",
    "remove-item", "ri", "rmtree", "sudo", "doas", "su", "runas", "pkexec",
))
DESTRUCTIVE_FLAGS = frozenset(("-delete", "--no-preserve-root"))
SHELLS = frozenset(("sh", "bash", "zsh", "dash", "fish", "ksh", "csh", "cmd", "powershell", "pwsh"))
PREFIXES = frozenset(("env", "exec", "nohup", "command", "time", "xargs", "nice", "start", "call", "&"))
EVENTS = frozenset(("open", "os.remove", "os.rmdir", "shutil.rmtree", "os.rename", "os.truncate",
                    "subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn"))
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC

_code: tuple[str, ...] = ()      # folders holding plugin code
_free: tuple[str, ...] = ()      # folders plugin code may change
_installed = False


def _norm(path) -> str:
    return os.path.normcase(os.path.realpath(os.fsdecode(path)))


def _inside(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root.rstrip(os.sep) + os.sep) for root in roots)


def install(code: list, free: list) -> None:
    """Guards code under the `code` folders; it may change files only under `free`. Called again,
    replaces both lists; the hook itself stays for the life of the process."""
    global _code, _free, _installed
    _code = tuple(_norm(p) for p in code)
    _free = tuple(_norm(p) for p in free)
    if not _installed:
        sys.addaudithook(_hook)
        _installed = True


def clear() -> None:
    global _code, _free
    _code, _free = (), ()


def _plugin_file() -> str:
    """The plugin file on the call stack, or ""."""
    frame = sys._getframe(2)
    while frame is not None:
        name = frame.f_code.co_filename
        if not name.startswith("<") and _inside(os.path.normcase(name), _code):
            return name
        frame = frame.f_back
    return ""


def _program_words(argv) -> list[list[str]]:
    """Each command line a process would run, as words; a shell's -c string split into its commands."""
    if isinstance(argv, (str, bytes)):
        return _shell_commands(os.fsdecode(argv))
    words = [os.fsdecode(a) for a in argv if isinstance(a, (str, bytes, os.PathLike))]
    if not words:
        return []
    out = [words]
    if _name(words[0]) in SHELLS:
        for i, word in enumerate(words[1:], 1):
            if word.lower() in ("-c", "/c", "/k", "-command", "-encodedcommand") and i + 1 < len(words):
                out += _shell_commands(" ".join(words[i + 1:]))
                break
    return out


def _shell_commands(text: str) -> list[list[str]]:
    commands = []
    for segment in re.split(r"[;&|()`\n]+|\$\(", text):
        words = [w.strip("'\"") for w in segment.split()]
        while words and (words[0].lower() in PREFIXES or re.fullmatch(r"\w+=.*", words[0])):
            words = words[1:]
        if words:
            commands.append(words)
    return commands


def _name(word: str) -> str:
    base = re.split(r"[\\/]", word)[-1].lower()
    return base[:-4] if base.endswith((".exe", ".com", ".bat", ".cmd")) else base


def _destructive(argv) -> str:
    for words in _program_words(argv):
        program = _name(words[0])
        if program in SHELLS:
            continue
        if program in DESTRUCTIVE or program.startswith("mkfs") or DESTRUCTIVE_FLAGS & {w.lower() for w in words}:
            return " ".join(words)[:120]
    return ""


def _bytecode(path: str) -> bool:
    return path.endswith(".pyc") and os.path.basename(os.path.dirname(path)) == "__pycache__"


def _deny(what: str, target: str, plugin: str) -> None:
    raise PermissionError(f"pokeldn's plugin guardrails stopped {what} {target} "
                          f"(from {os.path.basename(plugin)}). docs/plugins.md, Guardrails.")


def _hook(event: str, args: tuple) -> None:
    if event not in EVENTS or not _code:
        return
    if event == "open":
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        writes = any(c in mode for c in "wa+") if isinstance(mode, str) else bool(flags & WRITE_FLAGS)
        if not writes or not os.path.isfile(path):
            return
        path = _norm(path)
        if _inside(path, _free) or _bytecode(path) or not (plugin := _plugin_file()):
            return
        _deny("a change to", path, plugin)
    elif event in ("os.remove", "os.rmdir", "shutil.rmtree", "os.truncate"):
        path, extra = args[0], args[1]
        if not isinstance(path, (str, bytes, os.PathLike)) or (event != "os.truncate" and extra not in (None, -1)):
            return     # a dir_fd-relative name inside a tree whose own removal was checked
        path = _norm(path)
        if _inside(path, _free) or not (plugin := _plugin_file()):
            return
        _deny("the deletion of" if event != "os.truncate" else "the emptying of", path, plugin)
    elif event == "os.rename":
        src, dst = args[0], args[1]
        if not isinstance(src, (str, bytes, os.PathLike)) or args[2] not in (None, -1):
            return
        src, dst = _norm(src), _norm(dst)
        moved = not _inside(src, _free)
        replaced = os.path.exists(dst) and not _inside(dst, _free) and not _bytecode(dst)
        if (moved or replaced) and (plugin := _plugin_file()):
            _deny("moving", src if moved else dst, plugin)
    else:
        argv = {"subprocess.Popen": lambda: args[1] if args[1] is not None else [args[0]],
                "os.system": lambda: args[0],
                "os.exec": lambda: args[1], "os.posix_spawn": lambda: args[1],
                "os.spawn": lambda: args[2]}[event]()
        if (command := _destructive(argv)) and (plugin := _plugin_file()):
            _deny("the command", repr(command), plugin)
