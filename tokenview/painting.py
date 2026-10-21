import clr
import math
from pathlib import Path
clr.AddReference('System.Drawing')
clr.AddReference('System.Windows.Forms')
from System.Drawing import Color, Font, FontStyle, GraphicsUnit, SolidBrush, Pen, RectangleF, StringFormat, StringTrimming, StringAlignment
from System.Drawing.Drawing2D import GraphicsPath, LinearGradientBrush, SmoothingMode, PixelOffsetMode, LineCap, ColorBlend
from System.Drawing.Text import TextRenderingHint
from .visual import ring_sweep, pulse_position, pulse_strength

INK = '#18263E'
MUTED = '#3F5068'
BORDER = '#DAE5F0'


def color(value):
    return Color.FromArgb(int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def tint(value, amount=0.9):
    c = color(value)
    return Color.FromArgb(int(c.R + (255 - c.R) * amount), int(c.G + (255 - c.G) * amount), int(c.B + (255 - c.B) * amount))


def round_path(x, y, width, height, radius):
    path = GraphicsPath()
    r = min(radius, width / 2, height / 2)
    d = max(0.1, r * 2)
    path.AddArc(float(x), float(y), float(d), float(d), 180.0, 90.0)
    path.AddArc(float(x + width - d), float(y), float(d), float(d), 270.0, 90.0)
    path.AddArc(float(x + width - d), float(y + height - d), float(d), float(d), 0.0, 90.0)
    path.AddArc(float(x), float(y + height - d), float(d), float(d), 90.0, 90.0)
    path.CloseFigure()
    return path


class Painter:
    def __init__(self):
        self.fonts = {}
        self.brand_images = {}

    def brand_icon(self, g, product, x, y, size):
        from System.Drawing import Image, Icon
        if product not in self.brand_images:
            assets = Path(__file__).resolve().parents[1] / 'assets'
            if product == 'deepseek':
                icon = Icon(str(assets/'deepseek.ico'))
                try:
                    self.brand_images[product] = icon.ToBitmap()
                finally:
                    icon.Dispose()
            else:
                from System.Drawing import Bitmap, Graphics
                source = Image.FromFile(str(assets/(product+'.png')))
                raster = Bitmap(96,96)
                target = Graphics.FromImage(raster)
                try:
                    from System.Drawing.Drawing2D import InterpolationMode
                    target.InterpolationMode = InterpolationMode.HighQualityBicubic
                    target.DrawImage(source,RectangleF(0.0,0.0,96.0,96.0))
                    self.brand_images[product] = raster
                finally:
                    target.Dispose()
                    source.Dispose()
        bitmap = self.brand_images[product]
        ratio = min(size/bitmap.Width,size/bitmap.Height)
        width,height = bitmap.Width*ratio,bitmap.Height*ratio
        g.DrawImage(bitmap,RectangleF(float(x+(size-width)/2),float(y+(size-height)/2),float(width),float(height)))

    def font(self, size=14, bold=False, family='Segoe UI'):
        key = size, bold, family
        if key not in self.fonts:
            self.fonts[key] = Font(family, float(size), FontStyle.Bold if bold else FontStyle.Regular, GraphicsUnit.Pixel)
        return self.fonts[key]

    def text(self, g, text, x, y, width, height=24, size=14, bold=False, ink=INK, center=False, wrap=False):
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit
        brush = SolidBrush(color(ink) if isinstance(ink, str) else ink)
        fmt = StringFormat()
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.Alignment = StringAlignment.Center if center else StringAlignment.Near
        fmt.LineAlignment = StringAlignment.Center
        if not wrap:
            from System.Drawing import StringFormatFlags
            fmt.FormatFlags = StringFormatFlags.NoWrap
        try:
            family = 'Microsoft YaHei' if not bold and any(ord(c)>127 for c in str(text)) else 'Segoe UI'
            g.DrawString(str(text), self.font(size, bold, family), brush, RectangleF(float(x), float(y), float(width), float(height)), fmt)
        finally:
            brush.Dispose()
            fmt.Dispose()

    def capsule_label(self, g, label, x, y, width, height, ink):
        # Measure the actual glyph ink, not font line height: CJK and Latin
        # fallback fonts otherwise appear vertically offset in identical cells.
        from System.Drawing import PointF
        path = GraphicsPath()
        fmt = StringFormat.GenericTypographic
        font = self.font(12, True)
        brush = SolidBrush(color(ink))
        try:
            path.AddString(label, font.FontFamily, int(font.Style), 12.0, PointF(0.0, 0.0), fmt)
            bounds = path.GetBounds()
            from System.Drawing.Drawing2D import Matrix
            transform = Matrix()
            try:
                transform.Translate(float(x+(width-bounds.Width)/2-bounds.X),
                                    float(y+(height-bounds.Height)/2-bounds.Y))
                path.Transform(transform)
            finally:
                transform.Dispose()
            g.FillPath(brush, path)
        finally:
            path.Dispose()
            fmt.Dispose()
            brush.Dispose()

    def box(self, g, x, y, width, height, radius=12, fill='#F7FAFD', border=BORDER, gradient=None):
        path = round_path(x, y, width, height, radius)
        brush = LinearGradientBrush(RectangleF(float(x), float(y), float(width), float(height)), color(fill) if isinstance(fill, str) else fill, color(gradient), 90.0) if gradient else SolidBrush(color(fill) if isinstance(fill, str) else fill)
        pen = Pen(color(border) if isinstance(border, str) else border, 1.0) if border else None
        try:
            g.FillPath(brush, path)
            if pen:
                g.DrawPath(pen, path)
        finally:
            path.Dispose()
            brush.Dispose()
            if pen:
                pen.Dispose()

    def line(self, g, x1, y1, x2, y2, ink=BORDER, width=1.0):
        pen = Pen(color(ink), float(width))
        try:
            g.DrawLine(pen, float(x1), float(y1), float(x2), float(y2))
        finally:
            pen.Dispose()

    def dot(self, g, x, y, size, ink):
        brush = SolidBrush(color(ink))
        try:
            g.FillEllipse(brush, float(x), float(y), float(size), float(size))
        finally:
            brush.Dispose()

    def ring(self, g, x, y, diameter, value, ink, now):
        rect=RectangleF(float(x+3),float(y+3),float(diameter-6),float(diameter-6))
        base=Pen(tint(ink,0.88),2.4)
        g.DrawEllipse(base,rect)
        base.Dispose()
        sweep=ring_sweep(value)
        if sweep<=0:
            return
        glow=Pen(Color.FromArgb(int(22+20*pulse_strength(now)),color(ink)),5.0)
        pen=Pen(color(ink),2.4)
        pen.StartCap=pen.EndCap=LineCap.Round
        g.DrawArc(glow,rect,-90.0,float(sweep))
        g.DrawArc(pen,rect,-90.0,float(sweep))
        glow.Dispose()
        pen.Dispose()
        angle=math.radians(-90+sweep*((now/2.4)%1))
        radius=(diameter-6)/2
        cx,cy=x+diameter/2,y+diameter/2
        self.dot(g,cx+radius*math.cos(angle)-1.5,cy+radius*math.sin(angle)-1.5,3,'#FFFFFF')

    def energy_meter(self, g, x, y, width, height, value, ink, now):
        self.box(g,x,y,width,height,height/2,'#E5EBF2',None)
        fill=width*max(0,min(100,float(value)))/100
        if fill<0.2:
            return
        path=round_path(x,y,fill,height,height/2)
        base=LinearGradientBrush(RectangleF(float(x),float(y),float(max(1,fill)),float(height)),tint(ink,0.2),color(ink),0.0)
        g.FillPath(base,path)
        base.Dispose()
        state=g.Save()
        g.SetClip(path)
        position=pulse_position(now/2.4,fill)
        beam=LinearGradientBrush(RectangleF(float(x+position-25),float(y),50.0,float(height)),Color.Transparent,Color.Transparent,0.0)
        from System import Array, Single
        blend=ColorBlend(3)
        blend.Colors=Array[Color]([Color.FromArgb(0,255,255,255),Color.FromArgb(180,255,255,255),Color.FromArgb(0,255,255,255)])
        blend.Positions=Array[Single]([0,0.5,1])
        beam.InterpolationColors=blend
        g.FillRectangle(beam,float(x+position-25),float(y),50.0,float(height))
        beam.Dispose()
        g.Restore(state)
        path.Dispose()

    def pin(self, g, x, y, ink, active):
        state = g.Save()
        try:
            g.TranslateTransform(float(x), float(y))
            g.RotateTransform(32.0)
            pen = Pen(color(ink), 1.8)
            path = GraphicsPath()
            from System.Drawing import PointF
            from System import Array
            points = Array[PointF]([PointF(-5,-8),PointF(5,-8),PointF(5,-5),PointF(3,-4),PointF(3,1),PointF(6,4),PointF(-6,4),PointF(-3,1),PointF(-3,-4),PointF(-5,-5)])
            path.AddPolygon(points)
            if active:
                brush = SolidBrush(tint(ink, 0.5))
                g.FillPath(brush, path)
                brush.Dispose()
            g.DrawPath(pen, path)
            g.DrawLine(pen, 0.0, 4.0, 0.0, 11.0)
            path.Dispose()
            pen.Dispose()
        finally:
            g.Restore(state)

    def trash(self, g, x, y):
        self.line(g, x - 5, y - 5, x + 5, y - 5, MUTED)
        self.line(g, x - 3, y - 8, x + 3, y - 8, MUTED)
        self.line(g, x - 4, y - 4, x - 3, y + 6, MUTED)
        self.line(g, x + 4, y - 4, x + 3, y + 6, MUTED)
        self.line(g, x - 3, y + 6, x + 3, y + 6, MUTED)

    def dispose(self):
        for font in self.fonts.values():
            font.Dispose()
        for bitmap in self.brand_images.values():
            bitmap.Dispose()
