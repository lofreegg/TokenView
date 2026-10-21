import ctypes
import os
from pathlib import Path
import time
import webbrowser
import clr
clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Drawing')
from System import IntPtr, Decimal
from System.Drawing import Color, Size, Point, Bitmap, Graphics, Icon, Region, Rectangle
from System.Drawing.Drawing2D import SmoothingMode
from System.Windows.Forms import (Application, ApplicationContext, Form, FormBorderStyle, FormStartPosition,
    AutoScaleMode, Timer, MouseButtons, Cursors, ContextMenuStrip, ToolStripMenuItem, NotifyIcon,
    ToolTip, MessageBox, MessageBoxButtons, MessageBoxIcon, DialogResult, CheckBox, NumericUpDown, TrackBar, Label, Keys)
from . import native
from .model import PRODUCTS, metric_text, reset_text
from .painting import Painter, color, tint, round_path, INK, MUTED, BORDER
from .layout import capsule_width, panel_height, visible_rows, PANEL_WIDTH, ROW_HEIGHT
from .dialogs import add_account
from .interaction import DockInteraction, LeaveGate, pointer_inside
from .visual import capsule_metric_positions, host_palette, capsule_accent, blend_color


class Desktop:
    def __init__(self, store, controller, smoke=False):
        self.store = store
        self.controller = controller
        self.smoke = smoke
        self.host = native.Host()
        self.painter = Painter()
        self.expanded = False
        self.settings_mode = False
        self.pinned = False
        self.manual_settings = False
        self.modal = False
        self.offset = 0
        self.closed = False
        self.dpi = 1.0
        self.capsule_scale = 1.0
        self.hits = {'capsule': [], 'panel': []}
        self.hover = None
        self.controls = {}
        self.last_repaint = 0
        self.host_colors = host_palette([])
        self.next_color_sample = 0
        self.last_outside = None
        self.fade_start = None
        self.open_until=0
        self.dock = DockInteraction(self.store.settings.get('dock_offset', (0, 0)))
        self.suppress_click = False
        self.leave_gate = LeaveGate()
        self.closing_at = None
        self.position_signature = None
        self.capsule = self.create_form('TokenView Python • capsule')
        native.no_activate(int(self.capsule.Handle.ToInt64()))
        self.panel = self.create_form('TokenView Python • panel')
        self.capsule.Paint += self.paint_capsule
        self.panel.Paint += self.paint_panel
        self.capsule.MouseClick += lambda s,e: self.click('capsule',e)
        self.panel.MouseClick += lambda s,e: self.click('panel',e)
        self.capsule.MouseMove += lambda s,e: self.mouse_move('capsule',e)
        self.capsule.MouseDown += self.drag_start
        self.capsule.MouseUp += self.drag_end
        self.panel.MouseMove += lambda s,e: self.mouse_move('panel',e)
        self.panel.MouseWheel += self.wheel
        self.panel.KeyPreview = True
        self.panel.KeyDown += self.key_down
        self.tip = ToolTip()
        self.tip.InitialDelay = 450
        self.tip.ReshowDelay = 200
        self.context = ContextMenuStrip()
        for title, callback in [('展开', self.expand), ('刷新额度', self.refresh), ('当前账号详情 / 重新登录', self.current_details), ('设置', self.open_settings), ('退出', self.exit)]:
            item = ToolStripMenuItem(title)
            item.Click += lambda s,e,action=callback: action()
            self.context.Items.Add(item)
        self.tray = NotifyIcon()
        self.icon_bitmap = Bitmap(32, 32)
        graphics = Graphics.FromImage(self.icon_bitmap)
        graphics.SmoothingMode = SmoothingMode.AntiAlias
        self.painter.box(graphics, 2, 2, 28, 28, 9, '#09A783', None)
        self.painter.text(graphics, 'T', 2, 3, 28, 24, 21, True, '#FFFFFF', True)
        graphics.Dispose()
        icon_handle = self.icon_bitmap.GetHicon()
        borrowed_icon = Icon.FromHandle(icon_handle)
        self.icon = borrowed_icon.Clone()
        borrowed_icon.Dispose()
        native.user32.DestroyIcon.argtypes = [ctypes.c_void_p]
        native.user32.DestroyIcon(int(icon_handle.ToInt64()))
        self.tray.Icon = self.icon
        self.tray.Text = 'TokenView · 额度查询'
        self.tray.ContextMenuStrip = self.context
        self.tray.DoubleClick += lambda s,e: self.expand()
        self.tray.BalloonTipClicked += lambda s,e: self.show_alert_account()
        self.tray.Visible = not smoke
        self.timer = Timer()
        self.timer.Interval = 40
        self.timer.Tick += self.tick
        self.timer.Start()
        self.resize_and_position()

    def create_form(self, title):
        form = Form()
        form.Text = title
        form.FormBorderStyle = getattr(FormBorderStyle, 'None')
        form.StartPosition = FormStartPosition.Manual
        form.AutoScaleMode = getattr(AutoScaleMode, 'None')
        form.ShowInTaskbar = False
        form.TopMost = True
        form.BackColor = Color.White
        from System.Reflection import BindingFlags
        clr.GetClrType(Form).GetProperty('DoubleBuffered', BindingFlags.NonPublic | BindingFlags.Instance).SetValue(form, True, None)
        _ = form.Handle
        native.no_shadow(int(form.Handle.ToInt64()))
        return form

    @property
    def theme(self):
        return PRODUCTS[self.store.selected_product]['color']

    def accounts(self):
        return [a for a in self.store.accounts.values() if a.product == self.store.selected_product]

    def current(self):
        return self.store.accounts.get(self.store.selected_account)

    def metrics(self, account):
        return account.snapshot.get('metrics', []) if account and account.snapshot else []

    def selected_metrics(self, account):
        values = self.metrics(account)
        if self.store.selected_product == 'deepseek':
            return values[:2]
        if self.store.selected_product == 'antigravity':
            values = [m for m in values if m.get('group') == 'Gemini']
        by_period = {m.get('period'): m for m in values}
        return [by_period.get('5h'), by_period.get('weekly')]

    def capsule_name(self):
        if not getattr(self,'expanded',True):
            return ''
        name=PRODUCTS[self.store.selected_product]['name']
        account=self.current()
        if account and len(self.accounts())>1 and self.store.selected_product != 'antigravity':
            name+=' · '+account.name
        return name

    def set_form_size(self, form, w, h, scale, radius):
        wanted = Size(round(w * scale), round(h * scale))
        if form.ClientSize != wanted:
            form.ClientSize = wanted
            old = form.Region
            path = round_path(0, 0, wanted.Width, wanted.Height, radius * scale)
            form.Region = Region(path)
            path.Dispose()
            if old:
                old.Dispose()
            native.no_shadow(int(form.Handle.ToInt64()))

    def resize_and_position(self):
        account = self.current()
        name = self.capsule_name()
        bitmap = Bitmap(1, 1)
        g = Graphics.FromImage(bitmap)
        name_width = min(162,g.MeasureString(name, self.painter.font(14, True)).Width)
        metrics = self.selected_metrics(account)
        widths = [70 if m and m.get('unit')=='percent' or self.store.selected_product!='deepseek' else g.MeasureString(metric_text(m), self.painter.font(12, True)).Width+40 for m in metrics or [None,None]]
        g.Dispose()
        bitmap.Dispose()
        host = self.host.hwnd
        if host:
            self.dpi = max(1.0, native.user32.GetDpiForWindow(host) / 96) * 0.82
            area = native.work_area(host)
            rect = native.window_rect(host)
            x, y = (rect[0] + round(24 * self.dpi), rect[1] + round(12 * self.dpi)) if rect else (40,40)
        else:
            self.dpi = 0.82
            area = native.work_area(int(self.panel.Handle.ToInt64()))
            x, y = area[0] + 40, area[1] + 40
        self.capsule_scale = self.dpi * (1.0 if self.expanded else float(self.store.settings['capsule_scale']))
        self.cw = capsule_width(name_width, widths, self.expanded)
        self.panel_height = 470 if self.settings_mode else panel_height(len(self.accounts()), False, int((area[3] - area[1] - 90 * self.dpi) / self.dpi))
        self.set_form_size(self.capsule, self.cw, 40, self.capsule_scale, 20)
        self.set_form_size(self.panel, PANEL_WIDTH, self.panel_height, self.dpi, 22)
        total_width = max(self.capsule.Width, self.panel.Width if self.expanded else 0)
        x += round(self.dock.offset[0] * self.dpi)
        y += round(self.dock.offset[1] * self.dpi)
        x = max(area[0], min(x, area[2] - total_width - 8))
        bottom = self.panel.Height + self.capsule.Height + round(8 * self.dpi) if self.expanded else self.capsule.Height
        y = max(area[1], min(y, area[3] - bottom - 8))
        self.capsule.Location = Point(x, y)
        self.panel.Location = Point(x, y + self.capsule.Height + round(8 * self.dpi))
        self.tip.SetToolTip(self.capsule, account.name if account else '悬停展开 · 左键拖动位置')
        self.layout_settings()
        self.position_signature = self.layout_signature()

    def layout_signature(self):
        host=self.host.hwnd
        return (host,native.window_rect(host) if host else None,
            native.user32.GetDpiForWindow(host) if host else 96,self.expanded,self.settings_mode,
            self.store.selected_product,self.store.selected_account,len(self.accounts()),
            self.store.settings['capsule_scale'],self.dock.offset,
            tuple(metric_text(m) for m in self.selected_metrics(self.current())))

    def add_hit(self, target, rect, action, tooltip=''):
        self.hits[target].append((rect, action, tooltip))

    def paint_capsule(self, sender, event):
        g = event.Graphics
        g.SmoothingMode = SmoothingMode.AntiAlias
        g.ScaleTransform(float(self.capsule_scale), float(self.capsule_scale))
        p = self.painter
        self.hits['capsule'] = []
        colors = self.host_colors
        p.box(g, 0.7, 0.7, self.cw - 1.4, 38.6, 20, colors['background'], colors['border'])
        account = self.current()
        values = self.selected_metrics(account)
        theme = capsule_accent(colors['background'], self.theme)
        dot_color = theme if account and account.snapshot and not account.error else colors['muted']
        p.dot(g, 14, 16, 8, dot_color)
        p.box(g, 28, 10, 22, 22, 7, blend_color(colors['background'],theme,.08), None)
        p.brand_icon(g,self.store.selected_product,28,10,22)
        name = self.capsule_name()
        namew = min(162,g.MeasureString(name, p.font(14, True)).Width) + 6 if name else 0
        if name:
            p.text(g, name, 59, 8, namew, 24, 14, True, colors['ink'])
        x = 60 + namew
        positions = capsule_metric_positions(namew, self.cw, self.expanded)
        for i, label in enumerate(['余额','赠送'] if self.store.selected_product == 'deepseek' else ['5H','周']):
            m = values[i] if i < len(values) else None
            money=self.store.selected_product=='deepseek'
            if not money:
                x = positions[i]
            width = g.MeasureString(metric_text(m),p.font(12,True)).Width+40 if money else 70
            if x + width < self.cw - 22:
                if money:
                    p.box(g,x,7,width-4,26,8,tint(theme,0.95),None)
                    p.text(g,f'{label} {metric_text(m)}',x+4,7,width-12,26,11,True,INK,True)
                else:
                    p.ring(g,x,4,32,m['value'] if m else None,theme,time.monotonic())
                    p.text(g,metric_text(m),x,4,32,32,9,True,colors['ink'],True)
                    # Both labels share the ring's center line and a centered cell.
                    p.capsule_label(g,label,x+34,4,28,32,colors['muted'])
                    if i == 0:
                        separator = (x + 62 + positions[1]) / 2
                        p.line(g,separator,12,separator,28,colors['border'],0.8)
                x += width
        if self.expanded:
            brand_x=x+8
            room=self.cw-26-brand_x
            if room>=62:
                if room>=118:
                    p.text(g,'TOKENVIEW · PERSONAL',brand_x,8,room,24,9,True,colors['muted'])
                else:
                    p.text(g,'TOKENVIEW',brand_x,8,room,12,8,True,theme,True)
                    p.text(g,'PERSONAL',brand_x,20,room,12,8,False,colors['muted'],True)
        p.text(g, '⌃' if self.expanded else '⌄', self.cw - 24, 8, 18, 24, 14, False, colors['muted'], True)
        self.add_hit('capsule', (0,0,self.cw,40), self.collapse if self.expanded else self.expand)

    def button(self, g, title, x, y, width, action, active=False):
        self.painter.box(g, x, y, width, 36, 9, tint(self.theme, 0.94) if active else '#F7FAFD', tint(self.theme, 0.55) if active else BORDER)
        self.painter.text(g, title, x, y, width, 36, 13, False, self.theme if active else MUTED, True)
        self.add_hit('panel', (x,y,width,36), action)

    def paint_panel(self, sender, event):
        g = event.Graphics
        g.SmoothingMode = SmoothingMode.AntiAlias
        g.ScaleTransform(float(self.dpi), float(self.dpi))
        self.hits['panel'] = []
        p = self.painter
        p.box(g, 0.7, 0.7, 484.6, self.panel_height - 1.4, 22, '#FFFFFF', BORDER, '#F7FAFE')
        if self.settings_mode:
            self.paint_settings(g)
            return
        theme = self.theme
        title = PRODUCTS[self.store.selected_product]['name']
        p.text(g, title, 24, 16, 240, 36, 24, True)
        current = self.current()
        if current and current.id in self.controller.running:
            status = '登录中' if self.controller.running[current.id][0] == 'login' else '刷新中'
        elif current and current.error:
            status = '待重连'
        elif current and current.snapshot:
            status = '已同步'
        else:
            status = '未连接'
        titlew = min(240, g.MeasureString(title, p.font(24, True)).Width + 12)
        p.box(g, 24 + titlew, 22, 67, 24, 12, tint(theme,0.93), tint(theme,0.65))
        p.dot(g, 32 + titlew, 30, 7, theme)
        p.text(g, status, 42 + titlew, 22, 45, 24, 11, False, theme)
        p.box(g, 426, 14, 36, 36, 10, '#F8FBFE', BORDER)
        p.pin(g, 444, 32, theme, self.pinned)
        self.add_hit('panel',(426,14,36,36), self.toggle_pin, '取消固定' if self.pinned else '固定窗口')
        for i,(product,meta) in enumerate(PRODUCTS.items()):
            self.model_tab(g, product, 24 + i * 148, 68)
        p.line(g, 24, 116, 462, 116)
        p.text(g, '账号', 24, 128, 120, 24, 12, True, MUTED)
        accounts = self.accounts()
        if not accounts:
            p.text(g,'+',421,124,34,33,22,False,self.theme,True)
            self.add_hit('panel',(421,124,34,33),self.add_account,'添加账号 / Key')
        rows, self.offset = visible_rows(len(accounts), self.panel_height, False, self.offset)
        y = 164
        if not accounts:
            p.box(g, 24, y, 438, 68, 14, '#F7FAFD', BORDER)
            p.text(g, '添加 Key 查询余额' if self.store.selected_product == 'deepseek' else '添加账号并完成登录授权', 44, y + 14, 388, 24, 14, True)
            p.text(g, '成功连接后显示真实额度和重置时间',44,y+38,388,20,11,False,MUTED)
        else:
            for account in accounts[self.offset:self.offset+rows]:
                self.paint_account(g, account, y)
                y += ROW_HEIGHT
        content_bottom = self.panel_height - 72
        if len(accounts) > rows:
            p.text(g, f'{self.offset+1}–{min(len(accounts),self.offset+rows)} / {len(accounts)} · 滚轮查看更多', 24, content_bottom-20, 340, 20, 10, False, MUTED)
        footer = self.panel_height - 65
        p.line(g,24,footer-4,462,footer-4)
        caption = '数据仅保存在本机'
        if current and current.snapshot:
            age = max(0,int(time.time()-current.snapshot['at']))
            caption = f'{age//60}分钟前同步' if age>=60 else '刚刚同步'
            if current.error or age>self.store.settings['refresh_seconds']*2:
                caption = '旧数据 · ' + caption
        p.text(g,caption,24,footer+12,230,28,11,False,MUTED)
        self.add_hit('panel',(24,footer+12,230,28), self.privacy, '本机数据说明')
        self.button(g,'↻ 刷新',296,footer+9,76,self.refresh)
        self.button(g,'⚙ 设置',382,footer+9,80,self.open_settings,True)

    def model_tab(self, g, product, x, y):
        p = self.painter
        meta = PRODUCTS[product]
        active = product == self.store.selected_product
        accent = meta['color'] if 'color' in meta else self.theme
        fill = tint(accent, .86) if active else '#F0F4F8'
        border = tint(accent, .38) if active else '#D2DCE7'
        p.box(g,x,y,140,36,10,fill,border)
        p.brand_icon(g,product,x+10,y+8,20)
        p.text(g,meta['name'],x+37,y,96,36,14,True,INK,True)
        self.add_hit('panel',(x,y,140,36),lambda product=product:self.select_product(product))

    def paint_account(self, g, account, y):
        p = self.painter
        selected = account.id == self.store.selected_account
        p.box(g,24,y,438,130,14,'#FFFFFF',tint(self.theme,0.72) if selected else BORDER,'#F8FBFE')
        p.box(g,36,y+12,22,22,7,tint(self.theme,0.87),None)
        p.brand_icon(g,account.product,36,y+12,22)
        p.text(g,account.name,67,y+8,318,24,13,True)
        active = self.controller.running.get(account.id)
        error = account.error or ('登录授权中…' if active and active[0]=='login' else '刷新中…' if active else '尚未同步' if not account.snapshot else '')
        p.text(g,error or ('MYAGENTS · 当前账号' if account.connection=='myagents' else '胶囊显示中' if selected else '点选在胶囊显示'),67,y+29,318,16,10,False,MUTED)
        metrics = self.selected_metrics(account)
        for i,label in enumerate(['账户余额','赠送余额'] if account.product=='deepseek' else ['5 小时额度','周额度']):
            x = 36 + i*213
            m = metrics[i] if i<len(metrics) else None
            p.box(g,x,y+48,201,70,11,'#FFFFFF',BORDER,'#F4F8FC')
            p.text(g,label,x+10,y+55,100,24,12,False,INK)
            p.text(g,metric_text(m),x+111,y+55,80,24,15,True,self.theme,True)
            if m and m.get('unit')=='percent':
                p.energy_meter(g,x+10,y+86,181,6,m['value'],self.theme,time.monotonic())
            reset = reset_text(m.get('reset')) if m and m.get('unit')=='percent' else '官方账户余额' if m else '未返回'
            p.text(g,reset,x+10,y+96,181,20,12,False,INK)
        p.trash(g,438,y+23)
        p.text(g,'+',387,y+5,32,33,21,False,self.theme,True)
        self.add_hit('panel',(387,y+5,32,33),self.add_account,'添加 Key' if account.product=='deepseek' else '添加账号')
        self.add_hit('panel',(421,y+5,34,33),lambda a=account:self.remove_account(a),'移除账号')
        self.add_hit('panel',(32,y+5,350,120),lambda a=account:self.select_account(a),account.error or account.name)

    def paint_settings(self, g):
        p = self.painter
        p.text(g,'TOKENVIEW · SETTINGS',24,22,330,24,11,True,self.theme)
        p.text(g,'设置',24,51,340,40,28,True)
        for y,h in [(114,64),(192,94),(300,82)]:
            p.box(g,24,y,438,h,14,'#F8FBFD',BORDER)
        p.text(g,'刷新间隔',40,205,130,30,13,True)
        p.text(g,'分钟',336,207,80,28,12,False,MUTED)
        money=self.store.selected_product=='deepseek'
        p.text(g,'余额提醒阈值' if money else '额度提醒阈值',40,246,165,28,12,False,MUTED)
        p.text(g,'按账户币种' if money else '%',336,246,112,28,11,False,MUTED)
        p.text(g,'胶囊尺寸',40,310,130,28,13,True)
        p.text(g,'应用后保持设置页打开',40,344,180,24,11,False,MUTED)
        p.text(g,'账号与 Key 在额度页添加；数据只存本机',24,394,350,26,11,False,MUTED)
        self.button(g,'应用',382,418,80,self.apply_settings,True)
        self.button(g,'← 返回',286,418,86,self.close_settings)

    def build_settings(self):
        if self.controls:
            return
        startup = CheckBox()
        startup.Text = '开机启动'
        startup.Checked = bool(self.store.settings['startup'])
        alerts = CheckBox()
        alerts.Text = '额度提醒'
        alerts.Checked = bool(self.store.settings['alerts'])
        interval = NumericUpDown()
        interval.Minimum = Decimal(1)
        interval.Maximum = Decimal(1440)
        interval.Value = Decimal(max(1, int(self.store.settings['refresh_seconds']/60)))
        threshold = NumericUpDown()
        money=self.store.selected_product=='deepseek'
        threshold.Minimum = Decimal(0 if money else 1)
        threshold.Maximum = Decimal(10000 if money else 90)
        threshold.DecimalPlaces = 2 if money else 0
        threshold.Value = Decimal(float(self.store.settings['money_threshold'])) if money else Decimal(int(self.store.settings['threshold']))
        size = TrackBar()
        size.Minimum = 80
        size.Maximum = 150
        size.Value = round(self.store.settings['capsule_scale']*100)
        size.TickFrequency = 10
        self.controls = {'startup':startup,'alerts':alerts,'interval':interval,'threshold':threshold,'size':size}
        for control in self.controls.values():
            control.Font = self.painter.font(13)
            control.BackColor = Color.FromArgb(248,251,253)
            self.panel.Controls.Add(control)
        self.layout_settings()

    def layout_settings(self):
        if not self.controls:
            return
        positions = {'startup':(40,132,165,30),'alerts':(244,132,170,30),'interval':(240,209,85,28),'threshold':(240,250,85,28),'size':(228,319,213,48)}
        for key,rect in positions.items():
            self.controls[key].SetBounds(*(round(v*self.dpi) for v in rect))

    def destroy_settings(self):
        for control in self.controls.values():
            self.panel.Controls.Remove(control)
            control.Dispose()
        self.controls = {}

    def apply_settings(self):
        try:
            startup = bool(self.controls['startup'].Checked)
            import sys
            launcher = Path(sys.executable) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'启动TokenView.vbs'
            native.set_startup(startup, launcher)
            threshold=float(str(self.controls['threshold'].Value))
            self.store.set_settings(startup=startup,alerts=bool(self.controls['alerts'].Checked),refresh_seconds=int(str(self.controls['interval'].Value))*60,
                threshold=int(threshold) if self.store.selected_product!='deepseek' else self.store.settings['threshold'],
                money_threshold=threshold if self.store.selected_product=='deepseek' else self.store.settings['money_threshold'],capsule_scale=int(self.controls['size'].Value)/100)
            self.controller.next_refresh = time.monotonic()+self.store.settings['refresh_seconds']
            self.resize_and_position()
            self.capsule.Invalidate()
            self.panel.Invalidate()
            from System.Windows.Forms import ToolTipIcon
            if not self.smoke:
                self.tray.ShowBalloonTip(1500,'TokenView','设置已应用',ToolTipIcon.Info)
        except Exception:
            MessageBox.Show(self.panel,'设置未保存，请检查启动项权限并重试','TokenView')

    def mouse_move(self, target, event):
        if target=='capsule' and self.dock.origin is not None:
            from System.Windows.Forms import Cursor
            pos=Cursor.Position
            if self.dock.move(pos.X,pos.Y,self.dpi):
                self.resize_and_position()
            return
        scale = self.capsule_scale if target=='capsule' else self.dpi
        x,y = event.X/scale,event.Y/scale
        hit = next((h for h in self.hits[target] if h[0][0]<=x<=h[0][0]+h[0][2] and h[0][1]<=y<=h[0][1]+h[0][3]),None)
        form = self.capsule if target=='capsule' else self.panel
        form.Cursor = Cursors.Hand if hit else Cursors.Default
        tooltip = hit[2] if hit else ''
        state = (target,tooltip)
        if self.hover!=state:
            self.tip.SetToolTip(form,tooltip)
            self.hover=state

    def drag_start(self, sender, event):
        if event.Button == MouseButtons.Left:
            from System.Windows.Forms import Cursor
            pos=Cursor.Position
            self.dock.press(pos.X,pos.Y)
            self.suppress_click=False
            self.capsule.Capture=True

    def drag_end(self, sender, event):
        if event.Button == MouseButtons.Left:
            self.suppress_click=self.dock.release()
            self.capsule.Capture=False
            if self.suppress_click:
                self.store.settings['dock_offset']=list(self.dock.offset)
                self.store.save()

    def click(self, target, event):
        if target=='capsule' and self.suppress_click:
            self.suppress_click=False
            return
        if event.Button == MouseButtons.Right:
            self.context.Show(self.capsule if target=='capsule' else self.panel,event.Location)
            return
        if event.Button != MouseButtons.Left:
            return
        scale = self.capsule_scale if target=='capsule' else self.dpi
        x,y = event.X/scale,event.Y/scale
        for rect,action,_ in self.hits[target]:
            if rect[0]<=x<=rect[0]+rect[2] and rect[1]<=y<=rect[1]+rect[3]:
                action()
                return

    def wheel(self,sender,event):
        self.offset=max(0,self.offset+(1 if event.Delta<0 else -1))
        self.panel.Invalidate()

    def key_down(self,sender,event):
        if event.KeyCode == Keys.Escape:
            self.close_settings() if self.settings_mode else self.collapse()

    def select_product(self,product):
        self.store.select(product)
        self.offset=0
        self.resize_and_position()
        self.capsule.Invalidate()
        self.panel.Invalidate()

    def select_account(self,account):
        self.store.select(account.product,account.id)
        self.capsule.Invalidate()
        self.panel.Invalidate()

    def expand(self):
        self.expanded=True
        self.closing_at=None
        self.leave_gate.outside_since=None
        self.fade_start=time.monotonic()
        self.last_outside=None
        self.panel.Opacity=0.35
        self.resize_and_position()
        self.panel.Show()
        self.panel.Invalidate()
        self.capsule.Invalidate()

    def collapse(self):
        self.expanded=False
        self.closing_at=None
        self.fade_start=None
        self.leave_gate.outside_since=None
        self.settings_mode=False
        self.manual_settings=False
        self.destroy_settings()
        self.panel.Hide()
        self.resize_and_position()
        self.capsule.Invalidate()

    def toggle_pin(self):
        self.pinned=not self.pinned
        self.panel.Invalidate()

    def open_settings(self):
        self.settings_mode=True
        self.manual_settings=not self.host.inspect()[0]
        self.build_settings()
        self.expand()

    def close_settings(self):
        self.settings_mode=False
        self.manual_settings=False
        self.destroy_settings()
        self.resize_and_position()
        self.fade_start=time.monotonic()
        self.panel.Opacity=0.85
        self.panel.Invalidate()

    def refresh(self):
        for account in self.accounts():
            self.controller.refresh(account.id)
        self.panel.Invalidate()

    def add_account(self):
        self.modal=True
        try:
            product=self.store.selected_product
            result=add_account(self.panel,product,len(self.accounts()))
            if result:
                account=self.store.add_account(product,result[0],key=result[1])
                self.offset=max(0,len(self.accounts())-1)
                if product in ('codex','antigravity'):
                    self.controller.authorize(account,webbrowser.open)
                else:
                    self.controller.refresh(account.id)
                self.resize_and_position()
                self.panel.Invalidate()
                self.capsule.Invalidate()
        finally:
            self.modal=False

    def remove_account(self,account):
        self.modal=True
        try:
            if MessageBox.Show(self.panel,f'移除“{account.name}”？本机 Key 和额度缓存会被删除。','移除账号',MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes:
                self.controller.remove(account)
                self.resize_and_position()
                self.panel.Invalidate()
                self.capsule.Invalidate()
        finally:
            self.modal=False

    def show_account(self,account):
        if (not account.snapshot or account.error) and account.product in ('codex','antigravity') and account.connection!='myagents':
            self.modal=True
            try:
                if MessageBox.Show(self.panel,'该账号尚未成功同步。现在重新登录授权？',PRODUCTS[account.product]['name'],MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes:
                    self.controller.authorize(account,webbrowser.open)
            finally:
                self.modal=False
            return
        lines=[account.name]
        for metric in self.metrics(account):
            lines.append(f"{metric.get('group','')} {metric['label']}：{metric_text(metric)}".strip())
            if metric.get('unit')=='percent':
                lines.append(reset_text(metric.get('reset')))
        if account.snapshot:
            lines.append('来源：'+account.snapshot.get('source',''))
            lines.append('同步时间：'+time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(account.snapshot['at'])))
        if account.error:
            lines.append(account.error)
        self.modal=True
        try:
            MessageBox.Show(self.panel,'\n'.join(lines),'账号详情')
        finally:
            self.modal=False

    def current_details(self):
        account=self.current()
        if account:
            self.show_account(account)

    def show_alert_account(self):
        account=self.store.accounts.get(self.controller.last_alert_account)
        if account:
            self.select_account(account)
        self.expand()

    def privacy(self):
        self.modal=True
        try:
            MessageBox.Show(self.panel,'已连接 MyAgents 的账号直接复用本机登录和 Key，只向对应服务查询额度，不复制登录 Token。移除此类账号不会退出 MyAgents 登录。\n\n额外添加的 DeepSeek Key 使用 Windows 当前用户加密；额外 Codex 账号由官方 CLI 授权。Antigravity 额度会核对 CLI 与 MyAgents 账号一致。\n\n不读取浏览器 Cookie。','本机数据说明')
        finally:
            self.modal=False

    def tick(self,sender,event):
        if self.closed:
            return
        if not self.smoke:
            self.controller.tick()
        changed,notices=self.controller.collect()
        for kind,message in notices:
            if kind=='open_url':
                webbrowser.open(message)
            else:
                from System.Windows.Forms import ToolTipIcon
                self.tray.ShowBalloonTip(5000,'TokenView',message,ToolTipIcon.Warning if kind=='alert' else ToolTipIcon.Info)
        valid,front,own=self.host.inspect()
        if valid and front and not self.smoke and time.monotonic() >= self.next_color_sample:
            self.next_color_sample = time.monotonic() + 2
            exclude = [(form.Left, form.Top, form.Width, form.Height)
                       for form in (self.capsule, self.panel) if form.Visible]
            samples = native.sample_host_background(self.host.hwnd, exclude)
            if samples:
                self.host_colors = host_palette(samples)
        if self.capsule.Visible and not self.expanded and not self.modal and not self.smoke:
            from System.Windows.Forms import Cursor
            pos=Cursor.Position
            if self.dock.hover(self.capsule.Bounds.Contains(pos),time.monotonic()):
                self.expand()
        else:
            self.dock.hover(False,time.monotonic())
        wake=self.store.root/'wake.flag'
        if wake.exists():
            wake.unlink(missing_ok=True)
            if valid:
                native.user32.SetForegroundWindow.argtypes=[ctypes.c_void_p]
                native.user32.SetForegroundWindow(self.host.hwnd)
                self.expand()
            elif not self.smoke:
                from System.Windows.Forms import ToolTipIcon
                self.tray.ShowBalloonTip(3000,'TokenView','请打开 MyAgents；也可右键托盘图标进入设置。',ToolTipIcon.Info)
        if not self.smoke:
            visible = valid and (front or own or self.modal)
            if visible:
                if changed or self.layout_signature()!=self.position_signature:
                    self.resize_and_position()
                if not self.capsule.Visible:
                    self.capsule.Show()
                if self.expanded and not self.panel.Visible:
                    self.panel.Show()
            elif not self.manual_settings and not self.modal:
                self.capsule.Hide()
                self.panel.Hide()
            if self.manual_settings and not self.panel.Visible:
                self.panel.Show()
        if self.fade_start is not None:
            elapsed=time.monotonic()-self.fade_start
            progress=min(1,elapsed/0.18)
            self.panel.Opacity=0.35+0.65*(1-(1-progress)**3)
            if progress>=1:
                self.fade_start=None
        if self.expanded and not self.smoke:
            from System.Windows.Forms import Cursor
            position=Cursor.Position
            self.update_popup_pointer(position.X,position.Y,time.monotonic())
        animated=self.capsule.Visible or self.panel.Visible
        cadence=0.04 if self.panel.Visible and not self.settings_mode else 0.10 if self.capsule.Visible else 1.0
        if changed or animated and time.monotonic()-self.last_repaint>=cadence:
            self.capsule.Invalidate()
            self.panel.Invalidate()
            self.last_repaint=time.monotonic()

    def update_popup_pointer(self, x, y, now):
        def rect(form):
            return form.Left,form.Top,form.Width,form.Height
        inside=pointer_inside(x,y,rect(self.capsule),rect(self.panel))
        held=self.pinned or self.settings_mode or self.modal or self.context.Visible or self.dock.origin is not None
        if not self.leave_gate.close_due(inside,now,held):
            if self.closing_at is not None:
                self.closing_at=None
                self.panel.Opacity=1.0
        elif self.closing_at is None:
            self.fade_start=None
            self.closing_at=now
        if self.closing_at is not None:
            progress=min(1,(now-self.closing_at)/0.16)
            self.panel.Opacity=max(0.01,1-progress*progress)
            if progress>=1:
                self.collapse()

    def exit(self):
        import logging
        logging.info('UI exit requested closed=%s',self.closed)
        if self.closed:
            return
        self.closed=True
        self.timer.Stop()
        self.controller.close()
        self.tray.Visible=False
        self.tray.Dispose()
        self.context.Dispose()
        self.tip.Dispose()
        self.destroy_settings()
        self.panel.Close()
        self.capsule.Close()
        self.panel.Dispose()
        self.capsule.Dispose()
        self.icon.Dispose()
        self.icon_bitmap.Dispose()
        self.painter.dispose()
        Application.ExitThread()

    def run(self):
        Application.Run(ApplicationContext())
