"""`adb shell am start -n org.pokeldn.usbprobe/.PokeldnActivity --ez selftest true`: imports what the
app's runs need on this phone and checks the PKHeX helper answers. Results go to logcat (PokeLDN)."""
import importlib
import traceback

MODULES = ('Crypto.Cipher.AES', 'trio', 'zstandard', 'serial', 'esptool', 'websockets', 'ldn',
           'pokeldn.ldn.esp32_wlan', 'pokeldn.ldn.userspace_ip', 'pokeldn.frlg.link.host_app',
           'pokeldn.swsh.host_trade', 'pokeldn.online.gts', 'gui.board', 'gui.views.games',
           'gui.views.boards', 'gui.views.bank', 'gui.views.gts', 'gui.views.settings', 'unicorn')


def run(only=''):
    """`only`: a pytest -k expression; runs just those simulated-board tests, verbose."""
    lines = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            lines.append('PASS import ' + name)
        except Exception:
            lines.append('FAIL import ' + name + '\n' + traceback.format_exc())
    try:
        from pokeldn import pokemon
        species = pokemon.SERVICE.species('sv')
        lines.append('PASS PKHeX species: %d' % len(species))
    except Exception:
        lines.append('FAIL PKHeX\n' + traceback.format_exc())
    try:
        from pokeldn.frlg.rom import buffer_script
        lines.append(('PASS' if buffer_script.emulation_available() else 'FAIL') + ' unicorn emulation')
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
        uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.mem_map(0x1000, 0x1000)
        uc.mem_write(0x1000, bytes.fromhex('0100a0e3'))   # mov r0, #1
        uc.emu_start(0x1000, 0x1004)
        from unicorn.arm_const import UC_ARM_REG_R0
        lines.append(('PASS' if uc.reg_read(UC_ARM_REG_R0) == 1 else 'FAIL') + ' unicorn runs ARM code')
    except Exception:
        lines.append('FAIL unicorn\n' + traceback.format_exc())
    try:
        import os
        import pytest
        import android_test_esp32
        import android_test_host_end_to_end
        import sys
        import pkgutil
        import bin
        for found in pkgutil.iter_modules(bin.__path__):   # the desktop's conftest puts bin/ on sys.path
            sys.modules.setdefault(found.name, importlib.import_module('bin.' + found.name))
        os.environ['POKELDN_TEST_TIME_SCALE'] = '3'   # tests/test_esp32.py, the Let's Go queue
        here = os.path.dirname(android_test_esp32.__file__)
        # Three tests read desktop tools (tools/ldn) or another test module, which the app does not ship.
        code = pytest.main(['-q', '-p', 'no:cacheprovider', '-rA', '--tb=short', '-k',
                            only or 'not reconciles and not first_contact and not sword_host_and_joiner_trade',
                            os.path.join(here, 'android_test_esp32.py'),
                            os.path.join(here, 'android_test_host_end_to_end.py')])
        lines.append(('PASS' if code == 0 else 'FAIL') + ' simulated boards and host sessions (pytest exit %s)' % code)
    except Exception:
        lines.append('FAIL simulated stack\n' + traceback.format_exc())
    try:
        from pokeldn.app import catalog, command
        missing = [tool.key for game in catalog.GAMES for tool in game.tools
                   if '--keys' not in command.accepted(tool.script)]
        lines.append(('FAIL' if missing else 'PASS') + ' every tool reads its launcher flags %s' % missing)
    except Exception:
        lines.append('FAIL launcher flags\n' + traceback.format_exc())
    try:
        import os
        import tempfile
        import threading
        from pokeldn.app import runner
        done, out, codes = threading.Event(), [], []
        target = os.path.join(tempfile.mkdtemp(), 'gift')
        runner.InProcess(['--run', 'bin/swsh_gift_host.py', '--keys', 'unused', '--species', '25', '--level', '25',
                          '--dump', target], os.getcwd(), dict(os.environ), out.append,
                         lambda code: (codes.append(code), done.set()))
        done.wait(120)
        lines.append(('PASS' if codes == [0] else 'FAIL') + ' in-process launcher: %s %s' % (codes, out[-3:]))
    except Exception:
        lines.append('FAIL in-process launcher\n' + traceback.format_exc())
    try:
        import os
        import threading
        import android_compat
        cpu = android_compat.performance_cpu()
        if cpu is None:
            lines.append('PASS core clearing skipped: no cpu_capacity (emulator)')
        else:
            moved = android_compat.clear_core(cpu)
            me = threading.get_native_id()
            left = [t for t in map(int, os.listdir('/proc/self/task')) if t != me and t in moved
                    and cpu in os.sched_getaffinity(t)]
            android_compat.restore(moved)
            back = all(os.sched_getaffinity(t) == m for t, m in moved.items()
                       if os.path.exists('/proc/self/task/%d' % t))
            lines.append(('PASS' if moved and not left and back else 'FAIL')
                         + ' cpu %d cleared of %d threads and restored' % (cpu, len(moved)))
    except Exception:
        lines.append('FAIL core clearing\n' + traceback.format_exc())
    try:
        import time
        from pokeldn.app import android
        android.keep_awake(True)
        time.sleep(2)
        android.keep_awake(False)
        lines.append('PASS keep awake on and off')
    except Exception:
        lines.append('FAIL keep awake\n' + traceback.format_exc())
    return '\n'.join(lines)
