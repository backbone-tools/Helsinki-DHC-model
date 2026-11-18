"""Inline SVG panels for the validation report: a trend panel and a stacked-bar panel.

Every panel is one small chart over the same years. Colours come from CSS variables (--s1 ..
--s7 for series, --ink, --muted, --grid, --band), so the page's light and dark themes restyle
every panel. Each mark carries an SVG <title>: hovering shows its series, year and value.
`shaded` is a (first year, last year) pair drawn as a quiet band behind the plot.
"""
from html import escape
from math import floor, log10

H = 176
PAD_L, PAD_R, PAD_T, PAD_B = 46, 8, 8, 22
STAT, MODEL = "var(--s1)", "var(--s2)"


def nice_ticks(lo, hi, n=5):
    """Round tick values from lo to at least hi, in steps of 1, 2 or 5 times a power of ten."""
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    step = 10 ** floor(log10(span / n))
    for m in (1, 2, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    ticks, t = [], floor(lo / step) * step
    while not ticks or ticks[-1] < hi:
        ticks.append(round(t, 10))
        t += step
    return ticks


def _frame(years, lo, hi, unit, width, shaded):
    pw, ph = width - PAD_L - PAD_R, H - PAD_T - PAD_B
    step = pw / len(years)
    ticks = nice_ticks(lo, hi)
    y0, y1 = ticks[0], ticks[-1]

    def X(year):
        return PAD_L + (years.index(year) + 0.5) * step

    def Y(val):
        return PAD_T + ph - (val - y0) / (y1 - y0) * ph

    parts = [f'<svg class="chart" viewBox="0 0 {width} {H}" role="img" aria-label="{escape(unit)} a year">']
    if shaded and shaded[0] in years and shaded[1] in years:
        x0 = PAD_L + years.index(shaded[0]) * step
        parts.append(f'<rect x="{x0:.1f}" y="{PAD_T}" width="{step * (years.index(shaded[1]) - years.index(shaded[0]) + 1):.1f}" '
                     f'height="{ph}" class="band"/>')
    thousands = max(abs(y0), abs(y1)) >= 10000
    for t in ticks:
        parts.append(f'<line x1="{PAD_L}" x2="{width - PAD_R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" '
                     f'class="{"axis0" if t == 0 else "gl"}"/>')
        label = "0" if t == 0 else (f"{t / 1000:g}k" if thousands else f"{t:,.0f}")
        parts.append(f'<text x="{PAD_L - 6}" y="{Y(t) + 4:.1f}" class="tick" text-anchor="end">{label}</text>')
    for year in years[::3]:
        parts.append(f'<text x="{X(year):.1f}" y="{H - 6}" class="tick" text-anchor="middle">{year}</text>')
    return parts, X, Y, step


def _tip(name, year, val, unit, signed=False):
    num = f"{val:+,.0f}".replace("-", "−") if signed else f"{val:,.0f}"
    return f"<title>{escape(name)}, {year}: {num} {escape(unit)}</title>"


def trend(years, stat, model, unit, width, ymax=None, shaded=None):
    """Statistics (solid, round marks) and model (dashed, square marks) over the years.

    stat, model: {year: value or None}. ymax: the top of the scale when a row of panels shares one.
    """
    vals = [v for d in (stat, model) for v in d.values() if v is not None]
    hi = ymax if ymax is not None else (max(vals) if vals else 1)
    parts, X, Y, _ = _frame(years, 0, max(hi, 1) * 1.03, unit, width, shaded)
    for name, data, color, dashed in (("statistics", stat, STAT, False), ("model", model, MODEL, True)):
        runs, cur = [], []
        for year in years:  # a missing year breaks the line
            if data.get(year) is None:
                if cur:
                    runs.append(cur)
                cur = []
            else:
                cur.append(year)
        if cur:
            runs.append(cur)
        dash = ' stroke-dasharray="5 3"' if dashed else ""
        for run in runs:
            d = " ".join(f"{'M' if i == 0 else 'L'}{X(y):.1f},{Y(data[y]):.1f}" for i, y in enumerate(run))
            parts.append(f'<path d="{d}" style="fill:none;stroke:{color};stroke-width:2"{dash}/>')
        for year in years:
            val = data.get(year)
            if val is None:
                continue
            x, y = X(year), Y(val)
            mark = (f'<rect x="{x - 3:.1f}" y="{y - 3:.1f}" width="6" height="6" style="fill:{color}" class="mark"/>'
                    if dashed else f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" style="fill:{color}" class="mark"/>')
            parts.append(f'<g class="pt"><circle cx="{x:.1f}" cy="{y:.1f}" r="8" class="hit"/>{mark}'
                         f'{_tip(name, year, val, unit)}</g>')
    parts.append("</svg>")
    return "".join(parts)


def bars(years, parts_, unit, width, shaded=None, net=None):
    """Stacked bars a year: positive parts above zero, negative below.

    parts_: [(name, colour, {year: value})]. net: a name, to mark each year's sum with a dot.
    """
    up = {y: sum(max(d.get(y) or 0, 0) for _, _, d in parts_) for y in years}
    down = {y: sum(min(d.get(y) or 0, 0) for _, _, d in parts_) for y in years}
    parts, X, Y, step = _frame(years, min(down.values()) * 1.03, max(max(up.values()), 1) * 1.03, unit, width, shaded)
    bw = step * 0.66
    for year in years:
        top = bottom = 0.0
        for name, color, d in parts_:
            val = d.get(year) or 0
            if abs(val) < 0.5:
                continue
            if val > 0:
                a, b, top = top, top + val, top + val
            else:
                a, b, bottom = bottom + val, bottom, bottom + val
            parts.append(f'<rect x="{X(year) - bw / 2:.1f}" y="{Y(b):.1f}" width="{bw:.1f}" '
                         f'height="{max(Y(a) - Y(b) - 1, 0.5):.1f}" style="fill:{color}" class="seg">'
                         f'{_tip(name, year, val, unit, signed=net is not None)}</rect>')
        if net:
            total = up[year] + down[year]
            parts.append(f'<g class="pt"><circle cx="{X(year):.1f}" cy="{Y(total):.1f}" r="8" class="hit"/>'
                         f'<circle cx="{X(year):.1f}" cy="{Y(total):.1f}" r="3.4" style="fill:var(--ink)" class="mark"/>'
                         f'{_tip(net, year, total, unit, signed=True)}</g>')
    parts.append("</svg>")
    return "".join(parts)


def legend(items, cls="", label=""):
    """items: [(name, colour, kind)], kind: 'line' | 'dash' | 'box' | 'dot' | 'band'."""
    out = [f'<div class="legend {cls}">' + (f"<span>{escape(label)}</span>" if label else "")]
    for name, color, kind in items:
        if kind == "band":
            sw = '<span class="sw box band-sw"></span>'
        elif kind in ("box", "dot"):
            sw = f'<span class="sw {kind}" style="background:{color}"></span>'
        else:
            sw = f'<span class="sw line" style="border-top:2px {"dashed" if kind == "dash" else "solid"} {color}"></span>'
        out.append(f'<span class="li">{sw}{escape(name)}</span>')
    out.append("</div>")
    return "".join(out)
