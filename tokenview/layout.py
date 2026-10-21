PANEL_WIDTH = 486
ROW_HEIGHT = 142


def capsule_width(name_width, metric_widths, expanded=False):
    return PANEL_WIDTH if expanded else max(220, min(440, 74 + name_width + sum(metric_widths) + 28))


def panel_height(accounts, feed, available):
    wanted = 234 + max(1, accounts) * ROW_HEIGHT
    return min(max(376, wanted), max(376, available))


def visible_rows(count, height, feed, offset):
    rows = max(1, int((height - 234) // ROW_HEIGHT))
    rows = min(max(1, count), rows)
    start = max(0, min(int(offset), max(0, count - rows)))
    return rows, start


def row_rects(width):
    return ((34, 0, 130, 64), (176, 0, 110, 64), (298, 0, 110, 64), (424, 0, 30, 64))
