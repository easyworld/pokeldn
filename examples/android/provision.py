import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

parser = argparse.ArgumentParser(description='Validate a PK3 on desktop and provision private Android inputs.')
parser.add_argument('--device', required=True, help='ADB serial or connection address')
parser.add_argument('--keys', type=Path, required=True)
parser.add_argument('--offer', type=Path, required=True, help='Desktop PK3 to offer')
args = parser.parse_args()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pokeldn import pokemon

if args.offer.suffix.lower() != '.pk3':
    parser.error('--offer must be a .pk3 file')
record = args.offer.expanduser().read_bytes()
validation = pokemon.SERVICE.check_bytes('frlg', record)
if not validation['legal']:
    parser.error('Offer failed PKHeX validation: ' + validation['report'])
manifest = {'sha256': hashlib.sha256(record).hexdigest(), 'legal': True,
            'species': validation['species'], 'level': validation['level'], 'ot': validation['ot']}
adb = ['adb', '-s', args.device, 'shell', '-T']
package = 'org.pokeldn.usbprobe'
subprocess.run(adb + [f'run-as {package} mkdir -p files/trade'], check=True)
for name, data in (('prod.keys', args.keys.expanduser().read_bytes()), ('offer.pk3', record),
                   ('offer.json', json.dumps(manifest).encode()), ('crypto_hold_gil', b'')):
    command = f'umask 077; cat > files/trade/{name}'
    subprocess.run(adb + [f'run-as {package} sh -c {shlex.quote(command)}'], input=data, check=True)
    print('Provisioned private app file:', name)
