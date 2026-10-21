from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview.providers import cli_program, profile_env
from tokenview.integrated import myagents_home
from tokenview.rpc import CodexRpc

profile=myagents_home()/'codex'
stage='initialize'
try:
    with CodexRpc(cli_program('codex'),profile_env('codex',profile),profile,credential_store='auto') as rpc:
        print('initialized',flush=True)
        stage='account/read'
        result=rpc.request(stage,{'refreshToken':False},timeout=15)
        print('account-present',bool(result.get('account')),flush=True)
        stage='account/rateLimits/read'
        result=rpc.request(stage,timeout=20)
        print('limits-present',bool(result.get('rateLimits') or result.get('rateLimitsByLimitId')),flush=True)
except Exception as error:
    print('failed-stage',stage,'exception-type',type(error).__name__,flush=True)
