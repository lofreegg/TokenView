"""Render only TokenView-owned controls. Never captures the desktop."""
import ctypes
import json
from pathlib import Path
import time
import os
from System.Drawing import Bitmap, Rectangle
from System.Drawing.Imaging import ImageFormat
from System.Windows.Forms import Application
from tokenview import native


def capture(form, path):
    Application.DoEvents()
    image = Bitmap(form.ClientSize.Width, form.ClientSize.Height)
    form.DrawToBitmap(image, Rectangle(0,0,image.Width,image.Height))
    image.Save(str(path), ImageFormat.Png)
    image.Dispose()


def region_check(form):
    gdi = ctypes.WinDLL('gdi32')
    gdi.CreateRectRgn.argtypes = [ctypes.c_int]*4
    gdi.CreateRectRgn.restype = ctypes.c_void_p
    gdi.PtInRegion.argtypes = [ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    native.user32.GetWindowRgn.argtypes = [ctypes.c_void_p,ctypes.c_void_p]
    region = gdi.CreateRectRgn(0,0,0,0)
    result = native.user32.GetWindowRgn(int(form.Handle.ToInt64()),region)
    assert result in (2,3), f'no native clipping region: {result}'
    assert not gdi.PtInRegion(region,0,0), 'square corner remains in native region'
    assert gdi.PtInRegion(region,form.Width//2,form.Height//2), 'center was clipped'
    gdi.DeleteObject(region)


def smoke(ui):
    ui.timer.Stop()  # This test drives ticks/paint explicitly; avoid DoEvents starvation.
    output = ui.store.root.parent / 'renders'
    output.mkdir(parents=True, exist_ok=True)
    for name, first, week in [('测试账号 A',62,41),('测试账号 B',76,31)]:
        a = ui.store.add_account('codex',name)
        ui.store.update_snapshot(a.id,a.generation,{'at':time.time(),'source':'TEST FIXTURE', 'metrics':[
            {'label':'5H','period':'5h','unit':'percent','value':first,'reset':time.time()+8640},
            {'label':'周','period':'weekly','unit':'percent','value':week,'reset':time.time()+360000}]})
    ui.store.select('codex',next(iter(ui.store.accounts)))
    ui.store.feed={'text':'TEST FIXTURE — latest post preview without translation.','kind':'NOTE','url':'https://codex-reset.com/','at':time.time()}
    ui.resize_and_position()
    ui.capsule.Show()
    capture(ui.capsule,output/'capsule.png')
    from tokenview.visual import host_palette
    original_colors = ui.host_colors
    for label, rgb in [('warm', (249, 246, 242)), ('dark', (28, 32, 40))]:
        ui.host_colors = host_palette([rgb] * 5)
        ui.capsule.Invalidate()
        ui.capsule.Update()
        target = output / f'capsule-{label}.png'
        capture(ui.capsule, target)
        rendered = Bitmap(str(target))
        pixel = rendered.GetPixel(round(6*ui.capsule_scale), round(20*ui.capsule_scale))
        assert (pixel.R, pixel.G, pixel.B) == rgb, 'capsule ignored sampled host background'
        rendered.Dispose()
    ui.host_colors = original_colors
    ui.capsule.Invalidate()
    collapsed=ui.capsule.Width
    region_check(ui.capsule)
    ui.expand()
    ui.panel.Opacity=1.0
    capture(ui.capsule,output/'expanded-capsule.png')
    capture(ui.panel,output/'accounts.png')
    first=Bitmap(str(output/'accounts.png'))
    time.sleep(0.2)
    ui.panel.Invalidate()
    ui.panel.Update()
    capture(ui.panel,output/'energy-frame2.png')
    second=Bitmap(str(output/'energy-frame2.png'))
    changed=0
    for y in range(round(250*ui.dpi),round(256*ui.dpi)):
        for x in range(round(46*ui.dpi),round(227*ui.dpi)):
            changed+=first.GetPixel(x,y).ToArgb()!=second.GetPixel(x,y).ToArgb()
    first.Dispose()
    second.Dispose()
    assert changed>0, 'energy pulse did not animate between rendered frames'
    region_check(ui.panel)
    assert ui.panel.ClientSize.Width==round(486*ui.dpi)
    assert ui.capsule.Width>collapsed, 'expanded capsule did not widen'
    ui.select_product('antigravity')
    capture(ui.panel,output/'antigravity-empty.png')
    ui.select_product('codex')
    ui.select_account(list(ui.store.accounts.values())[1])
    assert ui.store.selected_product=='codex'
    ui.open_settings()
    capture(ui.panel,output/'settings.png')
    back = next(rect for rect, action, _ in ui.hits['panel'] if action == ui.close_settings)
    apply = next(rect for rect, action, _ in ui.hits['panel'] if action == ui.apply_settings)
    assert back[1] == apply[1] and back[0] + back[2] < apply[0], 'settings back/apply are not one footer row'
    old_set_startup=native.set_startup
    native.set_startup=lambda *args: None
    try:
        ui.controls['size'].Value=120
        ui.apply_settings()
    finally:
        native.set_startup=old_set_startup
    assert ui.settings_mode and ui.controls, 'applying size closed settings'
    assert ui.store.settings['capsule_scale']==1.2
    ui.close_settings()
    ui.panel.Opacity=1.0
    gapx=ui.capsule.Left+40
    gapy=ui.capsule.Bottom+2
    ui.update_popup_pointer(gapx,gapy,100)
    assert ui.expanded, 'connecting gap incorrectly closed popup'
    outside_x=ui.panel.Right+10
    outside_y=ui.panel.Bottom+10
    ui.update_popup_pointer(outside_x,outside_y,101)
    ui.update_popup_pointer(outside_x,outside_y,101.16)
    ui.update_popup_pointer(outside_x,outside_y,101.34)
    assert not ui.expanded and not ui.panel.Visible, 'pointer departure failed to hide popup'
    ui.collapse()
    region_check(ui.capsule)
    from System.Windows.Forms import MouseEventArgs, MouseButtons
    event=MouseEventArgs(MouseButtons.Left,1,10,10,0)
    before=ui.capsule.Location
    ui.drag_start(ui.capsule,event)
    ox,oy,_=ui.dock.origin
    ui.dock.move(ox+30,oy+20,ui.dpi)
    ui.resize_and_position()
    ui.drag_end(ui.capsule,event)
    assert ui.capsule.Left>before.X and ui.capsule.Top>before.Y, 'timer positioning lost drag offset'
    ui.click('capsule',event)
    assert not ui.expanded, 'drag release incorrectly triggered a click'
    assert ui.panel.Left==ui.capsule.Left, 'popup detached after dragging'
    if os.environ.get('TOKENVIEW_STRESS') == '1':
        # Explicit refreshes drive this bounded test; leave no periodic paint
        # producer running while DoEvents drains the queue on a slow machine.
        ui.timer.Stop()
        native.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        native.user32.GetGuiResources.argtypes = [ctypes.c_void_p,ctypes.c_uint]
        handle = native.kernel32.GetCurrentProcess()
        before_gdi = native.user32.GetGuiResources(handle,0)
        for iteration in range(50):
            ui.expand()
            ui.capsule.Refresh()
            ui.panel.Refresh()
            bitmap = Bitmap(ui.panel.ClientSize.Width,ui.panel.ClientSize.Height)
            try:
                ui.panel.DrawToBitmap(bitmap,Rectangle(0,0,bitmap.Width,bitmap.Height))
            finally:
                bitmap.Dispose()
            if iteration % 10 == 0:
                ui.open_settings()
                ui.panel.Refresh()
                ui.close_settings()
            Application.DoEvents()
            ui.collapse()
        after_gdi = native.user32.GetGuiResources(handle,0)
        assert after_gdi-before_gdi <= 15, f'GDI handles grew: {before_gdi} -> {after_gdi}'
        print(json.dumps({'stress_cycles':50,'gdi_before':before_gdi,'gdi_after':after_gdi}),flush=True)
    result={'status':'passed','collapsed_width':collapsed,'panel_width':round(486*ui.dpi),'corner_clipping':True,'size_apply_keeps_settings':True,'drag_moves_both_windows':True,'drag_suppresses_click':True,'leave_hides_popup':True,'energy_changed_pixels':changed,'renders':str(output)}
    (output/'smoke-result.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps(result))
