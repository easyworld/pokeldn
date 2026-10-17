"""The Android app's runner: a launcher on the app's own interpreter, as a child process would run it."""
import os
import threading

from pokeldn.app import runner


def _run(tmp_path, body, stop_after=None):
    script = tmp_path / "launcher.py"
    script.write_text(body)
    lines, done = [], threading.Event()
    codes = []
    before = dict(os.environ), os.getcwd()
    process = runner.InProcess(["--run", str(script), "--flag", "x"], str(tmp_path), {"ONLY": "this"},
                               lines.append, lambda code: (codes.append(code), done.set()))
    if stop_after:
        assert _wait_for(lines, stop_after)
        process.stop()
    assert done.wait(10)
    assert (dict(os.environ), os.getcwd()) == before and runner.InProcess.current is None
    return lines, codes[0], process


def _wait_for(lines, text):
    import time
    for _ in range(500):
        if text in lines:
            return True
        time.sleep(0.01)
    return False


def test_a_run_sees_its_arguments_environment_and_folder_then_exits_with_its_code(tmp_path):
    lines, code, process = _run(tmp_path, "import os, sys\n"
                                "print(sys.argv[1:], os.environ.get('ONLY'), os.getcwd() == %r)\n"
                                "print('partial', end='')\nsys.exit(3)\n" % str(tmp_path))
    assert lines == ["['--flag', 'x'] this True", "partial"] and code == 3 and not process.running


def test_a_failing_run_reports_its_traceback(tmp_path):
    lines, code, _ = _run(tmp_path, "raise ValueError('board gone')\n")
    assert code == 1 and lines[-1] == "ValueError: board gone"


def test_stop_interrupts_a_waiting_run_which_cleans_up(tmp_path):
    lines, code, _ = _run(tmp_path, "import time\nprint('up', flush=True)\ntry:\n    while True: time.sleep(0.01)\n"
                                    "finally:\n    print('left the network')\n", stop_after="up")
    assert lines == ["up", "left the network"] and code == 0


def test_a_launcher_runs_in_process_as_the_app_starts_it(tmp_path):
    """bin/swsh_gift_host.py --dump builds and writes its record with no radio: the whole entry point,
    argv, imports and output, on the app's own interpreter."""
    lines, done, codes = [], threading.Event(), []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = tmp_path / "gift"
    runner.InProcess(["--run", "bin/swsh_gift_host.py", "--keys", "unused", "--species", "25", "--level", "25",
                      "--dump", str(out)], root, dict(os.environ), lines.append,
                     lambda code: (codes.append(code), done.set()))
    assert done.wait(60)
    assert codes == [0], lines
    assert any(p.name.startswith("gift") for p in tmp_path.iterdir())
