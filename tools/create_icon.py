from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tokenview.painting import Painter
from System.Drawing import Bitmap,Graphics,Icon
from System.IO import FileStream,FileMode
import ctypes

root=Path(__file__).resolve().parents[1]/'assets'
root.mkdir(parents=True,exist_ok=True)
p=Painter()
bitmap=Bitmap(64,64)
g=Graphics.FromImage(bitmap)
p.box(g,2,2,60,60,17,'#09A783',None)
p.text(g,'T',2,2,60,60,44,True,'#FFFFFF',True)
handle=bitmap.GetHicon()
icon=Icon.FromHandle(handle)
stream=FileStream(str(root/'TokenView.ico'),FileMode.Create)
icon.Save(stream)
stream.Close()
icon.Dispose()
user32=ctypes.WinDLL('user32')
user32.DestroyIcon.argtypes=[ctypes.c_void_p]
user32.DestroyIcon(int(handle.ToInt64()))
g.Dispose()
bitmap.Dispose()
p.dispose()
print('icon-created')
