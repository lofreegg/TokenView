"""User-authorized quota-only queries. No inference, no credential output."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview.store import Store
from tokenview.integrated import connect_existing
from tokenview.providers import Provider,ProviderError

store=Store(Path(__file__).resolve().parents[1]/'app-data')
connect_existing(store)
provider=Provider(store)
try:
    for account in list(store.accounts.values()):
        if account.connection!='myagents':
            continue
        try:
            result=provider.fetch(account)
            store.update_snapshot(account.id,account.generation,result)
            print(account.product,[(m['label'],m['value'],m['unit']) for m in result['metrics']],flush=True)
        except ProviderError as error:
            store.update_snapshot(account.id,account.generation,None,str(error))
            print(account.product,str(error),flush=True)
finally:
    provider.close()
