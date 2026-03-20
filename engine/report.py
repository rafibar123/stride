"""
Stride — World-class personal player performance report card.

Layout
------
Page 1  Cover: branding, four hero stat cards, zone distribution bar
Page 2  Movement heatmap (full-width pitch), session detail table, footer
"""

import io
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np


# ── palette (RGB 0-1) ─────────────────────────────────────────────────────────
_BG       = (0.027, 0.035, 0.059)   # #07090f
_SURF     = (0.051, 0.090, 0.051)   # #0d170d
_CARD     = (0.071, 0.118, 0.071)   # #121e12
_GREEN    = (0.000, 0.902, 0.463)   # #00e676
_GDIM     = (0.082, 0.314, 0.161)   # #155029
_TEXT     = (0.910, 0.961, 0.910)   # #e8f5e9
_TMID     = (0.604, 0.722, 0.604)   # #9ab89a
_TDIM     = (0.267, 0.341, 0.267)   # #445744
_WHITE    = (1.0,   1.0,   1.0)


def _c(*rgb):
    """Return a reportlab Color from 0-1 RGB tuple."""
    from reportlab.lib.colors import Color
    return Color(*rgb)


# ── Gaussian blur (pure numpy, no scipy) ─────────────────────────────────────

def _gauss_kernel(sigma: float, size: int) -> np.ndarray:
    ax = np.arange(-(size // 2), size // 2 + 1)
    k = np.exp(-0.5 * (ax / sigma) ** 2)
    k /= k.sum()
    return k


def _gaussian_blur_2d(arr: np.ndarray, sigma: float = 3.0) -> np.ndarray:
    size = max(3, int(sigma * 4) | 1)
    k = _gauss_kernel(sigma, size)
    out = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 0, arr)
    out = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, out)
    return out


# ── heatmap PNG via matplotlib ────────────────────────────────────────────────

def _render_heatmap_png(
    heatmap_points: List,
    pitch_length: float = 105.0,
    pitch_width: float = 68.0,
    dpi: int = 160,
) -> bytes:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.colors import LinearSegmentedColormap

        FW = 14.0
        FH = FW * (pitch_width / pitch_length)
        fig, ax = plt.subplots(figsize=(FW, FH))
        BG_C = "#07090f"
        ax.set_facecolor("#0d1a0d")
        fig.patch.set_facecolor(BG_C)

        # Subtle pitch stripes
        stripe = pitch_length / 10
        for i in range(10):
            if i % 2 == 0:
                ax.add_patch(patches.Rectangle(
                    (i * stripe, 0), stripe, pitch_width,
                    facecolor=(1, 1, 1, 0.022), edgecolor="none", zorder=1))

        lkw = dict(color="white", linewidth=0.9, alpha=0.5, zorder=3)
        # Boundary
        ax.add_patch(patches.Rectangle(
            (0, 0), pitch_length, pitch_width,
            linewidth=1.6, edgecolor=(1, 1, 1, 0.65), facecolor="none", zorder=3))
        # Halfway
        ax.plot([pitch_length / 2] * 2, [0, pitch_width], **lkw)
        # Centre circle + spot
        ax.add_patch(patches.Circle(
            (pitch_length / 2, pitch_width / 2), 9.15,
            fill=False, edgecolor=(1, 1, 1, 0.5), linewidth=0.9, zorder=3))
        ax.plot(pitch_length / 2, pitch_width / 2, "o",
                color="white", markersize=2.5, alpha=0.65, zorder=3)
        # Penalty arcs / areas
        paH, paW, gaH, gaW = 40.32, 16.5, 18.32, 5.5
        for gx, sign in [(0, 1), (pitch_length, -1)]:
            ax.add_patch(patches.Rectangle(
                (gx if sign > 0 else gx - paW, (pitch_width - paH) / 2),
                paW, paH, fill=False,
                edgecolor=(1, 1, 1, 0.45), linewidth=0.85, zorder=3))
            ax.add_patch(patches.Rectangle(
                (gx if sign > 0 else gx - gaW, (pitch_width - gaH) / 2),
                gaW, gaH, fill=False,
                edgecolor=(1, 1, 1, 0.35), linewidth=0.7, zorder=3))
            sx = 11.0 if sign > 0 else pitch_length - 11.0
            ax.plot(sx, pitch_width / 2, "o", color="white",
                    markersize=2, alpha=0.55, zorder=3)
        # Zone dashes
        for x in [35.0, 70.0]:
            ax.plot([x, x], [0, pitch_width],
                    color="#00e676", lw=0.9, alpha=0.28, ls="--", zorder=3)

        # ── density heatmap ───────────────────────────────────────────────
        if heatmap_points and len(heatmap_points) >= 2:
            xs = np.array([p[0] for p in heatmap_points], dtype=np.float64)
            ys = np.array([p[1] for p in heatmap_points], dtype=np.float64)

            cols, rows = 105, 68
            H, _, _ = np.histogram2d(
                xs, ys, bins=[cols, rows],
                range=[[0, pitch_length], [0, pitch_width]])
            H = _gaussian_blur_2d(H.T, sigma=2.8)
            mx = H.max()
            if mx > 0:
                H /= mx

            cmap = LinearSegmentedColormap.from_list("stride", [
                (0.00, (0.00, 0.00, 0.00, 0.00)),
                (0.12, (0.00, 0.55, 0.27, 0.35)),
                (0.35, (0.00, 0.90, 0.46, 0.62)),
                (0.60, (1.00, 0.93, 0.10, 0.80)),
                (0.80, (1.00, 0.48, 0.00, 0.90)),
                (1.00, (1.00, 0.10, 0.10, 1.00)),
            ], N=256)

            ax.imshow(H, extent=[0, pitch_length, 0, pitch_width],
                      origin="lower", aspect="auto",
                      cmap=cmap, interpolation="bicubic", zorder=2)

        ax.set_xlim(-1.5, pitch_length + 1.5)
        ax.set_ylim(-1.5, pitch_width + 1.5)
        ax.axis("off")
        plt.tight_layout(pad=0)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                    facecolor=BG_C, edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception:
        return b""


# ── canvas drawing helpers ────────────────────────────────────────────────────

def _fill(c, rgb):
    c.setFillColorRGB(*rgb)

def _stroke(c, rgb):
    c.setStrokeColorRGB(*rgb)

def _rounded_rect(c, x, y, w, h, r=6,
                  fill_rgb=None, stroke_rgb=None, stroke_w=0.5):
    if fill_rgb:
        c.setFillColorRGB(*fill_rgb)
    if stroke_rgb:
        c.setStrokeColorRGB(*stroke_rgb)
        c.setLineWidth(stroke_w)
    c.roundRect(x, y, w, h, r,
                fill=1 if fill_rgb else 0,
                stroke=1 if stroke_rgb else 0)


def _draw_background(c, W, H):
    _fill(c, _BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def _draw_green_line(c, x, y, w, thickness=1.0):
    _stroke(c, _GREEN)
    c.setLineWidth(thickness)
    c.line(x, y, x + w, y)


# ── stat card ─────────────────────────────────────────────────────────────────

def _draw_stat_card(c, x, y, w, h,
                    value: str, unit: str, label: str,
                    accent_rgb=None):
    accent = accent_rgb or _GREEN
    _rounded_rect(c, x, y, w, h, r=8,
                  fill_rgb=_CARD,
                  stroke_rgb=_GDIM, stroke_w=0.8)

    # Top accent bar
    _fill(c, accent)
    c.roundRect(x, y + h - 4, w, 4, 2, fill=1, stroke=0)

    # Value
    c.setFont("Helvetica-Bold", 36)
    _fill(c, accent)
    c.drawCentredString(x + w / 2, y + h - 58, value)

    # Unit
    c.setFont("Helvetica-Bold", 13)
    _fill(c, _TMID)
    c.drawCentredString(x + w / 2, y + h - 74, unit)

    # Label
    c.setFont("Helvetica", 9)
    _fill(c, _TDIM)
    c.drawCentredString(x + w / 2, y + 12, label.upper())


# ── zone distribution bar ─────────────────────────────────────────────────────

def _draw_zone_bar(c, x, y, w, h, zone_frames: Dict):
    d = zone_frames.get("defensive_third", 0)
    m = zone_frames.get("middle_third", 0)
    a = zone_frames.get("attacking_third", 0)
    total = d + m + a or 1
    dp, mp, ap = d / total, m / total, a / total

    r = 5
    # Background track
    _rounded_rect(c, x, y, w, h, r=r, fill_rgb=_SURF)

    # Segments (clipped manually as three non-overlapping rects)
    dw, mw, aw = dp * w, mp * w, ap * w

    def _seg(sx, sw, rgb):
        if sw < 1:
            return
        _fill(c, rgb)
        if sw < r * 2:
            c.rect(sx, y, sw, h, fill=1, stroke=0)
        else:
            c.roundRect(sx, y, sw, h, r, fill=1, stroke=0)

    # Draw as overlapping rounded rects that get cut off — simpler: use plain rect for middle
    _fill(c, (0.18, 0.46, 0.85))   # blue — defensive
    if dw > 0:
        c.rect(x, y, dw, h, fill=1, stroke=0)
    _fill(c, _GREEN)               # green — middle
    if mw > 0:
        c.rect(x + dw, y, mw, h, fill=1, stroke=0)
    _fill(c, (0.98, 0.67, 0.07))   # amber — attacking
    if aw > 0:
        c.rect(x + dw + mw, y, aw, h, fill=1, stroke=0)

    # Round the whole bar with a border
    _rounded_rect(c, x, y, w, h, r=r,
                  stroke_rgb=_GDIM, stroke_w=0.6)

    # Labels below
    label_y = y - 14
    c.setFont("Helvetica-Bold", 8)
    positions = [
        (x + dw / 2,       (0.55, 0.72, 1.00), f"DEF  {dp*100:.0f}%"),
        (x + dw + mw / 2,  _GREEN,              f"MID  {mp*100:.0f}%"),
        (x + dw + mw + aw / 2, (1.0, 0.80, 0.25), f"ATT  {ap*100:.0f}%"),
    ]
    for cx, rgb, text in positions:
        _fill(c, rgb)
        c.drawCentredString(cx, label_y, text)


# ── page 1: cover ─────────────────────────────────────────────────────────────

def _draw_cover(c, W, H, data: Dict):
    from reportlab.lib.units import cm
    _draw_background(c, W, H)

    margin = 2.0 * cm
    inner_w = W - 2 * margin

    # ── top accent strip ──────────────────────────────────────────────────
    _fill(c, _GREEN)
    c.rect(0, H - 6, W, 6, fill=1, stroke=0)

    # ── branding ──────────────────────────────────────────────────────────
    top_y = H - 6 - 1.2 * cm
    c.setFont("Helvetica-Bold", 38)
    _fill(c, _GREEN)
    c.drawString(margin, top_y - 30, "STRIDE")

    c.setFont("Helvetica", 13)
    _fill(c, _TMID)
    c.drawString(margin, top_y - 48, "Personal Performance Report")

    # ── session meta (top-right) ──────────────────────────────────────────
    fps = data.get("fps", 25.0)
    frames = data.get("frames_processed", 0)
    dur_s = frames / max(fps, 1.0)
    dur_str = f"{int(dur_s // 60)}m {int(dur_s % 60)}s"
    vm = data.get("video", {})
    res = f"{vm.get('width','?')}×{vm.get('height','?')}"
    now = datetime.utcnow().strftime("%d %b %Y")

    c.setFont("Helvetica-Bold", 10)
    _fill(c, _TEXT)
    meta_x = W - margin
    c.drawRightString(meta_x, top_y - 28, now)
    c.setFont("Helvetica", 9)
    _fill(c, _TMID)
    c.drawRightString(meta_x, top_y - 41, f"{dur_str}  ·  {res}  ·  {fps:.0f} fps")

    # ── green divider ─────────────────────────────────────────────────────
    line_y = H - 6 - 3.6 * cm
    _draw_green_line(c, margin, line_y, inner_w, thickness=0.8)

    # ── player identity ───────────────────────────────────────────────────
    player_info  = data.get("player_info", {}) or {}
    p_name       = player_info.get("name", "")
    p_number     = player_info.get("number", "")
    p_color_hex  = player_info.get("jerseyColor", "")
    p_team       = player_info.get("teamName", "")

    # ── pull player stats ─────────────────────────────────────────────────
    per_player = data.get("per_player_metrics", [])
    player = per_player[0] if per_player else {}
    dist_m       = player.get("distance_m", 0.0)
    max_spd_mps  = player.get("max_speed_mps", 0.0)
    avg_spd_mps  = player.get("avg_speed_mps", 0.0)
    sprints      = player.get("sprint_count", 0)
    zone_frames  = player.get("zone_frames", {
        "defensive_third": 0, "middle_third": 0, "attacking_third": 0})

    dist_km = dist_m / 1000
    dist_val  = f"{dist_km:.2f}" if dist_km >= 1 else f"{dist_m:.0f}"
    dist_unit = "km" if dist_km >= 1 else "m"

    # ── player identity block (name / jersey / team) ──────────────────────
    id_y = line_y - 0.55 * cm
    if p_name or p_number:
        # Jersey color swatch
        if p_color_hex and len(p_color_hex) == 7:
            try:
                jr = int(p_color_hex[1:3], 16) / 255
                jg = int(p_color_hex[3:5], 16) / 255
                jb = int(p_color_hex[5:7], 16) / 255
                swatch_size = 1.1 * cm
                swatch_x = margin
                swatch_y = id_y - swatch_size
                _rounded_rect(c, swatch_x, swatch_y, swatch_size, swatch_size,
                               r=6, fill_rgb=(jr, jg, jb))
                # jersey number inside swatch
                lum = 0.299 * jr + 0.587 * jg + 0.114 * jb
                num_color = (0.027, 0.035, 0.059) if lum > 0.55 else _WHITE
                _fill(c, num_color)
                c.setFont("Helvetica-Bold", 16)
                c.drawCentredString(
                    swatch_x + swatch_size / 2,
                    swatch_y + swatch_size / 2 - 6,
                    p_number or "?")
                text_x = swatch_x + swatch_size + 0.35 * cm
            except Exception:
                text_x = margin
        else:
            text_x = margin

        if p_name:
            c.setFont("Helvetica-Bold", 22)
            _fill(c, _TEXT)
            c.drawString(text_x, id_y - 0.65 * cm, p_name)
        if p_team:
            c.setFont("Helvetica", 10)
            _fill(c, _TMID)
            c.drawString(text_x, id_y - 1.05 * cm, p_team)

        id_consumed = 1.25 * cm
    else:
        id_consumed = 0.0

    # ── section label ─────────────────────────────────────────────────────
    cards_top = line_y - 0.7 * cm - id_consumed
    c.setFont("Helvetica-Bold", 8)
    _fill(c, _TDIM)
    c.drawString(margin, cards_top, "PERFORMANCE SUMMARY")

    # ── 4 stat cards ──────────────────────────────────────────────────────
    card_gap = 0.35 * cm
    card_w = (inner_w - 3 * card_gap) / 4
    card_h = 3.2 * cm
    card_y = cards_top - card_h - 0.3 * cm

    # ── pull pass stats ───────────────────────────────────────────────────
    ps            = data.get("pass_stats", {}) or {}
    pass_total    = int(ps.get("total", 0))
    pass_accurate = int(ps.get("accurate", 0))
    pass_pct      = float(ps.get("accuracy_pct", 0.0))
    has_pass_data = pass_total >= 3

    if has_pass_data:
        if pass_pct >= 80: pass_acc_rgb = _GREEN
        elif pass_pct >= 60: pass_acc_rgb = (0.984, 0.749, 0.141)
        else: pass_acc_rgb = (0.973, 0.431, 0.431)
        pass_val  = f"{pass_accurate}/{pass_total}"
        pass_unit = f"{pass_pct:.0f}% accurate"
    else:
        pass_acc_rgb = (0.220, 0.741, 0.973)
        pass_val  = "N/A"
        pass_unit = "no ball data"

    stats = [
        (dist_val,                         dist_unit,         "Distance Run"),
        (f"{max_spd_mps * 3.6:.1f}",       "km/h",            "Top Speed"),
        (f"{avg_spd_mps * 3.6:.1f}",       "km/h",            "Avg Speed"),
        (str(sprints),                     "bursts",           "Sprint Count"),
        (pass_val,                         pass_unit,          "Passes"),
    ]
    accents = [_GREEN, _GREEN, _GREEN, _GREEN, pass_acc_rgb]

    # 5 cards — slightly narrower
    card_w = (inner_w - 4 * card_gap) / 5

    for i, ((val, unit, lbl), acc) in enumerate(zip(stats, accents)):
        cx = margin + i * (card_w + card_gap)
        _draw_stat_card(c, cx, card_y, card_w, card_h,
                        value=val, unit=unit, label=lbl, accent_rgb=acc)

    # ── sub-stat row (frames, duration) ───────────────────────────────────
    sub_y = card_y - 0.55 * cm
    sub_items = [
        ("Session duration", dur_str),
        ("Frames analysed", f"{frames:,}"),
        ("Video", res),
        ("Frame rate", f"{fps:.0f} fps"),
    ]
    sub_col_w = inner_w / len(sub_items)
    for i, (lbl, val) in enumerate(sub_items):
        sx = margin + i * sub_col_w + sub_col_w / 2
        c.setFont("Helvetica", 7.5)
        _fill(c, _TDIM)
        c.drawCentredString(sx, sub_y - 2, lbl.upper())
        c.setFont("Helvetica-Bold", 9.5)
        _fill(c, _TMID)
        c.drawCentredString(sx, sub_y - 13, val)

    # ── rating section ────────────────────────────────────────────────────
    rating = data.get("rating", {})
    if rating:
        overall     = rating.get("overall", 0.0)
        physical    = rating.get("physical", 0.0)
        attacking   = rating.get("attacking", 0.0)
        positioning = rating.get("positioning", 0.0)
        pressing    = rating.get("pressing", 0.0)

        def _rating_rgb(v):
            if v >= 8.5: return (0.984, 0.749, 0.141)  # gold
            if v >= 7.0: return _GREEN
            if v >= 5.5: return (0.220, 0.741, 0.973)  # blue
            return (0.973, 0.431, 0.431)                # red

        rat_y = sub_y - 1.8 * cm
        c.setFont("Helvetica-Bold", 8)
        _fill(c, _TDIM)
        c.drawString(margin, rat_y, "PERFORMANCE RATING")

        # Big overall number
        ov_rgb = _rating_rgb(overall)
        ov_size = 52
        c.setFont("Helvetica-Bold", ov_size)
        _fill(c, ov_rgb)
        ov_x = margin + 0.1 * cm
        ov_y = rat_y - ov_size * 0.8
        c.drawString(ov_x, ov_y, f"{overall:.1f}")

        # Rating label beside the number
        def _rat_label(v):
            if v >= 9.0: return "World Class"
            if v >= 8.0: return "Excellent"
            if v >= 7.0: return "Very Good"
            if v >= 6.0: return "Good"
            return "Average"

        c.setFont("Helvetica-Bold", 11)
        _fill(c, ov_rgb)
        c.drawString(ov_x + 68, ov_y + 18, _rat_label(overall))
        c.setFont("Helvetica", 9)
        _fill(c, _TDIM)
        c.drawString(ov_x + 68, ov_y + 4, "Overall Performance Score")

        # 5 sub-score attribute bars (including Passing)
        passing = rating.get("passing", 6.0)
        bar_items = [
            ("Physical",    physical),
            ("Attacking",   attacking),
            ("Positioning", positioning),
            ("Pressing",    pressing),
            ("Passing",     passing),
        ]
        bar_x      = ov_x + 72
        bar_w      = inner_w - 72 - 0.1 * cm
        bar_height = 0.26 * cm
        bar_gap    = 0.44 * cm
        bar_start  = ov_y - 0.1 * cm

        for i, (lbl, val) in enumerate(bar_items):
            by = bar_start - i * bar_gap
            rgb = _rating_rgb(val)

            # Track
            _rounded_rect(c, bar_x, by - bar_height, bar_w, bar_height,
                           r=2, fill_rgb=_SURF)
            # Fill (3-9.8 range → 0-100%)
            fill_pct = max(0.0, min(1.0, (val - 3.0) / 6.8))
            fill_w = fill_pct * bar_w
            if fill_w > 2:
                _rounded_rect(c, bar_x, by - bar_height, fill_w, bar_height,
                               r=2, fill_rgb=rgb)

            # Label left
            c.setFont("Helvetica-Bold", 8)
            _fill(c, _TMID)
            c.drawRightString(bar_x - 4, by - bar_height + 2, lbl[:3].upper())

            # Value right
            c.setFont("Helvetica-Bold", 8)
            _fill(c, rgb)
            c.drawString(bar_x + bar_w + 4, by - bar_height + 2, f"{val:.1f}")

        rat_consumed = ov_size * 0.8 + bar_gap * 5 + 0.6 * cm
    else:
        rat_consumed = 0.0

    # ── zone section ──────────────────────────────────────────────────────
    zone_label_y = sub_y - 2.0 * cm - rat_consumed
    c.setFont("Helvetica-Bold", 8)
    _fill(c, _TDIM)
    c.drawString(margin, zone_label_y, "PITCH ZONE COVERAGE")

    zone_bar_h = 0.55 * cm
    zone_bar_y = zone_label_y - zone_bar_h - 0.25 * cm
    _draw_zone_bar(c, margin, zone_bar_y, inner_w, zone_bar_h, zone_frames)

    # ── heatmap teaser / pitch icon ───────────────────────────────────────
    # Draw a mini pitch outline at the bottom with "→ See page 2" label
    pitch_label_y = zone_bar_y - 2.0 * cm
    c.setFont("Helvetica-Bold", 8)
    _fill(c, _TDIM)
    c.drawString(margin, pitch_label_y, "MOVEMENT HEATMAP")
    c.setFont("Helvetica", 8)
    _fill(c, _TDIM)
    c.drawRightString(W - margin, pitch_label_y, "continued on next page →")

    # A small decorative pitch outline
    mp_h = pitch_label_y - 1.0 * cm
    mp_w = inner_w
    mp_y = 2.2 * cm
    mp_x = margin
    available_h = mp_h - mp_y
    if available_h > 1.5 * cm:
        _draw_mini_pitch(c, mp_x, mp_y, mp_w, available_h, zone_frames)

    # ── footer ────────────────────────────────────────────────────────────
    _draw_green_line(c, margin, 1.35 * cm, inner_w, thickness=0.4)
    c.setFont("Helvetica", 7.5)
    _fill(c, _TDIM)
    run_id = data.get("run_id", "")
    c.drawString(margin, 0.9 * cm, f"Stride · run {run_id[:8]} · {now}")
    c.drawRightString(W - margin, 0.9 * cm,
                      "Personal reference only · stride.ai")


def _draw_mini_pitch(c, x, y, w, h, zone_frames: Dict):
    """Draw a small decorative pitch with zone shading."""
    ratio = 68 / 105
    ph = min(h, w * ratio)
    pw = ph / ratio
    px = x + (w - pw) / 2
    py = y + (h - ph) / 2

    d = zone_frames.get("defensive_third", 0)
    m = zone_frames.get("middle_third", 0)
    a = zone_frames.get("attacking_third", 0)
    total = d + m + a or 1

    # Zone fills
    def _zone_rect(frac_x, frac_w, alpha_rgb):
        r, g, b, a_val = alpha_rgb
        _fill(c, (r * a_val + 0.051 * (1 - a_val),
                  g * a_val + 0.090 * (1 - a_val),
                  b * a_val + 0.051 * (1 - a_val)))
        c.rect(px + frac_x * pw, py, frac_w * pw, ph, fill=1, stroke=0)

    _zone_rect(0,     1/3, (0.18, 0.46, 0.85, 0.18 * (d / total) * 3))
    _zone_rect(1/3,   1/3, (0.00, 0.90, 0.46, 0.18 * (m / total) * 3))
    _zone_rect(2/3,   1/3, (0.98, 0.67, 0.07, 0.18 * (a / total) * 3))

    # Pitch outline
    _stroke(c, _GDIM)
    c.setLineWidth(0.8)
    c.rect(px, py, pw, ph, fill=0, stroke=1)
    # Halfway
    c.setLineWidth(0.5)
    c.line(px + pw / 2, py, px + pw / 2, py + ph)
    # Zone dashes
    c.setDash([3, 3])
    _stroke(c, _GDIM)
    for frac in [1/3, 2/3]:
        c.line(px + frac * pw, py, px + frac * pw, py + ph)
    c.setDash([])


# ── page 2: heatmap + table ───────────────────────────────────────────────────

def _draw_details_page(c, W, H, data: Dict, heatmap_tmp: Optional[str]):
    from reportlab.lib.units import cm
    _draw_background(c, W, H)

    margin = 2.0 * cm
    inner_w = W - 2 * margin

    # ── top accent strip ──────────────────────────────────────────────────
    _fill(c, _GREEN)
    c.rect(0, H - 6, W, 6, fill=1, stroke=0)

    # ── page title ────────────────────────────────────────────────────────
    top_y = H - 6 - 1.1 * cm
    c.setFont("Helvetica-Bold", 14)
    _fill(c, _GREEN)
    c.drawString(margin, top_y - 18, "MOVEMENT HEATMAP")
    c.setFont("Helvetica", 9)
    _fill(c, _TDIM)
    c.drawRightString(W - margin, top_y - 20, "Density of positions tracked during session")

    line_y = top_y - 2.0 * cm
    _draw_green_line(c, margin, line_y, inner_w, thickness=0.5)

    # ── heatmap image ─────────────────────────────────────────────────────
    if heatmap_tmp and os.path.exists(heatmap_tmp):
        from reportlab.platypus import Image as RLImage
        img_ratio = 68 / 105
        img_w = inner_w
        img_h = img_w * img_ratio

        # Cap height so it doesn't eat the whole page
        max_img_h = H * 0.48
        if img_h > max_img_h:
            img_h = max_img_h
            img_w = img_h / img_ratio

        img_x = margin + (inner_w - img_w) / 2
        img_y = line_y - 0.4 * cm - img_h

        c.drawImage(heatmap_tmp, img_x, img_y, width=img_w, height=img_h,
                    preserveAspectRatio=True)

        # Zone labels under heatmap
        lbl_y = img_y - 0.45 * cm
        thirds = [("DEF. THIRD", 0), ("MID. THIRD", 1), ("ATT. THIRD", 2)]
        for name, idx in thirds:
            lx = img_x + img_w * (idx / 3 + 1 / 6)
            c.setFont("Helvetica-Bold", 7)
            _fill(c, _TDIM)
            c.drawCentredString(lx, lbl_y, name)

        table_top = lbl_y - 1.0 * cm
    else:
        # No heatmap — placeholder box
        box_h = H * 0.35
        box_y = line_y - 0.4 * cm - box_h
        _rounded_rect(c, margin, box_y, inner_w, box_h, r=6,
                      fill_rgb=_SURF, stroke_rgb=_GDIM)
        c.setFont("Helvetica", 10)
        _fill(c, _TDIM)
        c.drawCentredString(W / 2, box_y + box_h / 2,
                            "No heatmap data available for this session.")
        table_top = box_y - 1.0 * cm

    # ── session details table ─────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    _fill(c, _TDIM)
    c.drawString(margin, table_top, "SESSION DETAILS")
    _draw_green_line(c, margin, table_top - 0.3 * cm, inner_w, 0.4)

    fps    = data.get("fps", 25.0)
    frames = data.get("frames_processed", 0)
    dur_s  = frames / max(fps, 1.0)
    vm     = data.get("video", {})
    pi     = data.get("player_info", {}) or {}
    per_player = data.get("per_player_metrics", [])
    player = per_player[0] if per_player else {}

    dist_m      = player.get("distance_m", 0.0)
    max_spd_mps = player.get("max_speed_mps", 0.0)
    avg_spd_mps = player.get("avg_speed_mps", 0.0)
    sprints     = player.get("sprint_count", 0)
    zf          = player.get("zone_frames", {})
    zd = zf.get("defensive_third", 0)
    zm = zf.get("middle_third", 0)
    za = zf.get("attacking_third", 0)
    zt = zd + zm + za or 1

    dur_str = f"{int(dur_s // 60)}m {int(dur_s % 60)}s"
    rat    = data.get("rating", {})
    ps_d   = data.get("pass_stats", {}) or {}
    rows: list = []
    if rat:
        rows.append(("Overall Rating",
                     f"{rat.get('overall', 0):.1f} / 10  —  "
                     f"Phy {rat.get('physical',0):.1f} · "
                     f"Att {rat.get('attacking',0):.1f} · "
                     f"Pos {rat.get('positioning',0):.1f} · "
                     f"Prs {rat.get('pressing',0):.1f} · "
                     f"Pas {rat.get('passing',0):.1f}"))
    if pi.get("name"):
        rows.append(("Player", pi["name"]))
    if pi.get("number"):
        jersey_str = f"#{pi['number']}"
        if pi.get("jerseyColor"):
            jersey_str += f"  ·  {pi['jerseyColor'].upper()}"
        rows.append(("Jersey", jersey_str))
    if pi.get("teamName"):
        rows.append(("Team", pi["teamName"]))
    rows += [
        ("Duration analysed",        dur_str),
        ("Frames processed",         f"{frames:,}"),
        ("Video resolution",         f"{vm.get('width','?')}×{vm.get('height','?')} @ {fps:.0f} fps"),
        ("Distance run",             f"{dist_m:.1f} m  ({dist_m/1000:.3f} km)"),
        ("Top speed",                f"{max_spd_mps:.2f} m/s  ({max_spd_mps*3.6:.1f} km/h)"),
        ("Average speed",            f"{avg_spd_mps:.2f} m/s  ({avg_spd_mps*3.6:.1f} km/h)"),
        ("Sprint bursts (≥18 km/h)", str(sprints)),
        ("Defensive third",          f"{zd/zt*100:.0f}% of tracked time"),
        ("Middle third",             f"{zm/zt*100:.0f}% of tracked time"),
        ("Attacking third",          f"{za/zt*100:.0f}% of tracked time"),
    ]
    # Pass stats row
    pt = int(ps_d.get("total", 0))
    pa = int(ps_d.get("accurate", 0))
    pp = float(ps_d.get("accuracy_pct", 0.0))
    if pt >= 3:
        rows.append(("Passes (accurate / total)", f"{pa} / {pt}  ({pp:.0f}%)"))

    row_h = 0.52 * cm
    col_w = inner_w / 2
    row_y = table_top - 0.65 * cm

    for i, (label, value) in enumerate(rows):
        if row_y < 2.5 * cm:
            break
        bg = _SURF if i % 2 == 0 else _CARD
        _rounded_rect(c, margin, row_y - row_h + 2, inner_w, row_h, r=3,
                      fill_rgb=bg)
        c.setFont("Helvetica", 8.5)
        _fill(c, _TMID)
        c.drawString(margin + 8, row_y - row_h + 8, label)
        c.setFont("Helvetica-Bold", 8.5)
        _fill(c, _TEXT)
        c.drawRightString(margin + inner_w - 8, row_y - row_h + 8, value)
        row_y -= row_h + 1

    # ── coach note box ─────────────────────────────────────────────────────
    coach = ps_d.get("coach_note", "")
    if coach and row_y > 4.0 * cm:
        box_h = 1.15 * cm
        box_y = row_y - 0.4 * cm - box_h
        _rounded_rect(c, margin, box_y, inner_w, box_h, r=6,
                      fill_rgb=_GDIM, stroke_rgb=_GREEN, stroke_w=0.5)
        # ⚽ icon
        c.setFont("Helvetica-Bold", 10)
        _fill(c, _GREEN)
        c.drawString(margin + 10, box_y + box_h / 2 - 4, "\u26bd")
        # note text (truncate to fit single line)
        max_chars = int(inner_w / 4.8)
        display_note = coach if len(coach) <= max_chars else coach[:max_chars - 1] + "…"
        c.setFont("Helvetica", 8)
        _fill(c, _TEXT)
        c.drawString(margin + 26, box_y + box_h / 2 - 4, display_note)

    # ── footer ────────────────────────────────────────────────────────────
    _draw_green_line(c, margin, 1.35 * cm, inner_w, thickness=0.4)
    c.setFont("Helvetica", 7.5)
    _fill(c, _TDIM)
    run_id = data.get("run_id", "")
    now = datetime.utcnow().strftime("%d %b %Y")
    c.drawString(margin, 0.9 * cm,
                 f"Stride · run {run_id[:8]} · {now}")
    c.drawRightString(W - margin, 0.9 * cm,
                      "Personal reference only · stride.ai")


# ── main entry point ──────────────────────────────────────────────────────────

def generate_pdf(result_dict: Dict, output_path: str) -> str:
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is required for PDF generation. "
            "Install it with: pip install reportlab"
        ) from exc

    W, H = A4  # 595.27 × 841.89 pt

    # ── render heatmap PNG ────────────────────────────────────────────────
    heatmap_pts  = result_dict.get("heatmap_points", [])
    pitch        = result_dict.get("pitch", {})
    pitch_length = pitch.get("pitch_length_m", 105.0)
    pitch_width  = pitch.get("pitch_width_m", 68.0)

    heatmap_png = _render_heatmap_png(heatmap_pts, pitch_length, pitch_width)

    tmp_files: List[str] = []

    def _to_tmp(data: bytes) -> Optional[str]:
        if not data:
            return None
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except Exception:
            return None
        tmp_files.append(path)
        return path

    heatmap_tmp = _to_tmp(heatmap_png)

    # ── build PDF ─────────────────────────────────────────────────────────
    try:
        c = rl_canvas.Canvas(output_path, pagesize=A4)
        c.setTitle("Stride Performance Report")
        c.setAuthor("Stride")
        c.setSubject("Personal Football Performance Report Card")

        # Page 1 — cover
        _draw_cover(c, W, H, result_dict)
        c.showPage()

        # Page 2 — heatmap + details
        _draw_details_page(c, W, H, result_dict, heatmap_tmp)
        c.showPage()

        c.save()
    finally:
        for p in tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    return output_path
