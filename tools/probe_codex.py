"""Verify empty-profile account isolation without initiating login."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview.providers import cli_program,profile_env
from tokenview.rpc import CodexRpc

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'test-artifacts') as d:
    path=Path(d)
    with CodexRpc(cli_program('codex'),profile_env('codex',path),path) as rpc:
        result=rpc.request('account/read',{'refreshToken':False},timeout=15)
        print('empty_profile_has_account=',result.get('account') is not None)
        assert result.get('account') is None, 'empty profile inherited existing account'
    print('plaintext_auth_created=',(path/'auth.json').exists())
