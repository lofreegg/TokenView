class DockInteraction:
    def __init__(self, offset=(0, 0)):
        self.offset = tuple(offset)
        self.origin = None
        self.dragged = False
        self.hover_since = None

    def press(self, x, y):
        self.origin = (x, y, self.offset)
        self.dragged = False
        self.hover_since = None

    def move(self, x, y, scale):
        if self.origin is None:
            return False
        ox, oy, offset = self.origin
        dx, dy = x - ox, y - oy
        if abs(dx) + abs(dy) >= 4:
            self.dragged = True
        if self.dragged:
            self.offset = (offset[0] + dx / scale, offset[1] + dy / scale)
        return self.dragged

    def release(self):
        dragged = self.dragged
        self.origin = None
        return dragged

    def hover(self, inside, now):
        if not inside or self.origin is not None:
            self.hover_since = None
            return False
        if self.hover_since is None:
            self.hover_since = now
        return now - self.hover_since >= 0.12


class LeaveGate:
    def __init__(self):
        self.outside_since = None

    def close_due(self, inside, now, held=False):
        if inside or held:
            self.outside_since = None
            return False
        if self.outside_since is None:
            self.outside_since = now
        return now - self.outside_since >= 0.14


def pointer_inside(x, y, capsule, panel):
    def contains(rect):
        rx, ry, w, h = rect
        return rx <= x <= rx+w and ry <= y <= ry+h
    if contains(capsule) or contains(panel):
        return True
    # Only the narrow connecting gap; not a large bounding box around both windows.
    left=max(capsule[0],panel[0])
    right=min(capsule[0]+capsule[2],panel[0]+panel[2])
    return left <= x <= right and capsule[1]+capsule[3] <= y <= panel[1]
