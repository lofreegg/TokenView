"""Probe only empty TokenView profiles; never prints authentication material."""
import os
import subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

root = Path(__file__).resolve().parents[1] / 'test-artifacts' / 'empty-agy'
root.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env.update(USERPROFILE=str(root), APPDATA=str(root / 'AppData' / 'Roaming'),
           LOCALAPPDATA=str(root / 'AppData' / 'Local'), XDG_CONFIG_HOME=str(root / '.config'),
           AGY_CLI_DISABLE_AUTO_UPDATE='1')
for name in ('AppData/Roaming', 'AppData/Local', '.config'):
    (root / name).mkdir(parents=True, exist_ok=True)
try:
    p = subprocess.run([r'D:\myagent\codex-tools\antigravity-cli\agy.exe', '-p', '/usage', '--output-format', 'json'],
                       cwd=root, env=env, capture_output=True, timeout=15, creationflags=0x08000000)
    text = p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')
    print('exit=', p.returncode)
    print('has_auth_prompt=', any(x in text.lower() for x in ('login', 'log in', 'sign in', 'authentication', 'authorize')))
    print('has_usage=', 'Five Hour Limit Remaining' in text)
    print('output_bytes=', len(p.stdout) + len(p.stderr))
except subprocess.TimeoutExpired:
    print('timeout_no_auth_result')
print('profile_files=', [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()][:20])
