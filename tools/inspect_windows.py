import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview import native
native.init_dpi()

parser=argparse.ArgumentParser()
parser.add_argument('--pid',type=int,required=True)
args=parser.parse_args()
result=[]
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
native.user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
native.user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
def inspect(hwnd,param):
    if native.process_id(hwnd)!=args.pid:
        return True
    title=ctypes.create_unicode_buffer(256)
    native.user32.GetWindowTextW(hwnd,title,256)
    if title.value.startswith('TokenView Python'):
        result.append({'title':title.value,'visible':bool(native.user32.IsWindowVisible(hwnd)),'rect':native.window_rect(hwnd)})
    return True
native.user32.EnumWindows(callback_type(inspect),0)
front=native.user32.GetForegroundWindow()
print(json.dumps({'windows':result,'foreground_process':native.process_name(native.process_id(front))}))
