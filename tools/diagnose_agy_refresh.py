"""One bounded read-only diagnosis; print no tokens or OAuth URLs."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview.store import Store
from tokenview.providers import Provider, cli_program
import tokenview.agy_accounts as independent

root = Path(r'D:\myagent\TokenView\app-data')
fd, logname = tempfile.mkstemp(prefix='agy-diagnostic-',suffix='.log',dir=root)
os.close(fd)
process = subprocess.Popen([str(cli_program('antigravity')),'-p','/usage','--output-format','json','--log-file',logname],
    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    creationflags=0x08000000,cwd=root,env=dict(os.environ,AGY_CLI_DISABLE_AUTO_UPDATE='1'))
try:
    try:
        output, error = process.communicate(timeout=20)
        print('cli_returncode',process.returncode)
    except subprocess.TimeoutExpired:
        print('cli_usage_timeout_after_20_seconds')
        process.terminate()
        process.communicate(timeout=5)
    log = Path(logname).read_text('utf-8',errors='replace')
    for line in log.splitlines():
        for phrase in re.findall(r'(?i).{0,35}(?:opening.{0,20}browser|browser.{0,30}|oauth.{0,35}|auth.{0,35}|refresh.{0,35}|login.{0,35}|expired.{0,35}|invalid_grant.{0,20}).{0,25}',line):
            safe = re.sub(r'https?://\S+','[URL omitted]',phrase)
            safe = re.sub(r'(?i)(token|secret|code|state)[=:]\s*\S+',r'\1=[omitted]',safe)
            print('cli_log',safe[:180])
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    Path(logname).unlink(missing_ok=True)

store=Store(root)
provider=Provider(store)
original=independent.parse_summary
def inspect_summary(data):
    for group in data.get('quotaGroups',data.get('groups',[])):
        print('quota_group',group.get('displayName'))
        for bucket in group.get('buckets',[]):
            print('quota_bucket',{k:bucket.get(k) for k in ('displayName','window','disabled','remainingFraction')})
    return original(data)
independent.parse_summary=inspect_summary
try:
    target=next(a for a in store.accounts.values() if a.product=='antigravity' and a.name=='weiguo.lofree@gmail.com' and a.connection!='myagents')
    result=provider.fetch(target)
    print('independent_metrics',[(m.get('group'),m.get('period'),m.get('value')) for m in result['metrics']])
finally:
    provider.close()
