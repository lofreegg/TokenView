import math


def capsule_metric_positions(name_width, width, expanded):
    start = 60 + name_width
    gap = 70
    if expanded:
        # Reserve a readable brand and chevron even for long provider names.
        room = max(0, width - 144 - (start + 132))
        start += min(8, room)
        gap += min(8, max(0, room - 8))
    return start, start + gap


def contrast_ratio(first, second):
    def luminance(hex_color):
        values = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def host_palette(samples):
    # Dominant color, not an average of background plus foreground glyphs.
    bins = {}
    for rgb in samples:
        key = tuple(v // 16 for v in rgb)
        bins.setdefault(key, []).append(rgb)
    group = max(bins.values(), key=len) if bins else [(248, 250, 252)]
    rgb = tuple(round(sum(p[i] for p in group) / len(group)) for i in range(3))
    background = '#' + ''.join(f'{v:02X}' for v in rgb)
    def readable(candidates):
        best = max(candidates, key=lambda c: contrast_ratio(background, c))
        return best if contrast_ratio(background, best) >= 4.5 else max(
            ('#000000', '#FFFFFF'), key=lambda c: contrast_ratio(background, c))
    ink = readable(('#18263E', '#F3F6FC'))
    return {'background': background, 'ink': ink,
            'muted': readable(('#52627A', '#C4CFDF')),
            'border': '#65748B' if ink in ('#F3F6FC', '#FFFFFF') else '#CDD7E2'}


def blend_color(first, second, amount):
    return '#' + ''.join(f'{round(int(first[i:i+2],16)*(1-amount) + int(second[i:i+2],16)*amount):02X}'
                         for i in (1, 3, 5))


def capsule_accent(background, accent):
    if contrast_ratio(background, accent) >= 3:
        return accent
    target = max(('#000000', '#FFFFFF'), key=lambda c: contrast_ratio(background, c))
    for step in range(1, 21):
        candidate = blend_color(accent, target, step / 20)
        if contrast_ratio(background, candidate) >= 3:
            return candidate
    return target


def ring_sweep(value):
    return 0 if value is None else 3.6 * max(0,min(100,float(value)))


def pulse_position(phase, width):
    return (phase % 1) * (width + 50) - 25


def pulse_strength(now):
    return 0.5 + 0.5 * math.sin(now * math.tau / 2.4)
