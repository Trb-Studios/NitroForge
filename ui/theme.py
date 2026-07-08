"""
Shared look & feel: colors, fonts, spacing, small widget builders.

Color tuples are (light_mode, dark_mode) as CustomTkinter expects.
Chart + status colors are the validated reference data-viz palette
(categorical slots in fixed order; status colors reserved for severity).
"""
from __future__ import annotations

import customtkinter as ctk

# ------------------------------------------------------------------ colors
SURFACE = ("#f9f9f7", "#0d0d0d")        # page plane
CARD = ("#fcfcfb", "#1a1a19")           # chart/card surface
CARD_2 = ("#f0efec", "#242423")         # nested/inset surface
INK = ("#0b0b0b", "#ffffff")            # primary text
INK_2 = ("#52514e", "#c3c2b7")          # secondary text
MUTED = ("#898781", "#898781")          # axis/labels
BORDER = ("#e1e0d9", "#2c2c2a")
ACCENT = ("#2a78d6", "#3987e5")         # categorical slot 1 (blue)
ACCENT_HOVER = ("#256abf", "#5598e7")

# status palette -- reserved for severity, never used as series colors
SEV = {
    "ok":   ("#006300", "#0ca30c"),
    "warn": ("#8a6100", "#fab219"),
    "bad":  ("#d03b3b", "#d03b3b"),
}
SEV_LABEL = {"ok": "OK", "warn": "WARN", "bad": "ISSUE"}

# matplotlib chart chrome + series (categorical slots, fixed order:
# 1 blue=CPU, 2 aqua=RAM, 3 yellow=GPU, 4 green=FPS, 5 violet=frame time)
CHART = {
    "light": {"surface": "#fcfcfb", "grid": "#e1e0d9", "ink": "#0b0b0b",
              "muted": "#898781", "baseline": "#c3c2b7",
              "cpu": "#2a78d6", "ram": "#1baf7a", "gpu": "#eda100",
              "fps": "#008300", "frametime": "#4a3aa7"},
    "dark": {"surface": "#1a1a19", "grid": "#2c2c2a", "ink": "#ffffff",
             "muted": "#898781", "baseline": "#383835",
             "cpu": "#3987e5", "ram": "#199e70", "gpu": "#c98500",
             "fps": "#008300", "frametime": "#9085e9"},
}

# ------------------------------------------------------------------- fonts
FAMILY = "Segoe UI"
FONT_TITLE = (FAMILY, 20, "bold")
FONT_HEAD = (FAMILY, 15, "bold")
FONT_BODY = (FAMILY, 13)
FONT_SMALL = (FAMILY, 11)
FONT_HERO = (FAMILY, 30, "bold")
FONT_MONO = ("Consolas", 12)

# ----------------------------------------------------------------- spacing
PAD = 12
GAP = 8
RADIUS = 10


def mode() -> str:
    return "dark" if ctk.get_appearance_mode().lower() == "dark" else "light"


# --------------------------------------------------------- widget builders
def card(parent, **kw) -> ctk.CTkFrame:
    kw.setdefault("fg_color", CARD)
    kw.setdefault("corner_radius", RADIUS)
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", BORDER)
    return ctk.CTkFrame(parent, **kw)


def heading(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_HEAD, text_color=INK,
                        anchor="w")


def body_label(parent, text: str, secondary=False, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=FONT_BODY, anchor="w",
                        text_color=INK_2 if secondary else INK,
                        justify="left", **kw)


def stat_tile(parent, title: str) -> tuple[ctk.CTkFrame, ctk.CTkLabel]:
    """Card with a muted title + hero value label. Returns (frame, value_lbl)."""
    tile = card(parent)
    ctk.CTkLabel(tile, text=title.upper(), font=FONT_SMALL, text_color=MUTED,
                 anchor="w").pack(fill="x", padx=PAD, pady=(GAP, 0))
    val = ctk.CTkLabel(tile, text="--", font=FONT_HERO, text_color=INK,
                       anchor="w")
    val.pack(fill="x", padx=PAD, pady=(0, GAP))
    return tile, val


def severity_row(parent, severity: str, title: str, detail: str) -> ctk.CTkFrame:
    """Finding card with a colored severity bar + plain-English text."""
    row = card(parent)
    row.grid_columnconfigure(1, weight=1)
    bar = ctk.CTkFrame(row, width=6, corner_radius=3,
                       fg_color=SEV.get(severity, MUTED))
    bar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(GAP, 0), pady=GAP)
    ctk.CTkLabel(row, text=f"[{SEV_LABEL.get(severity, '?')}]  {title}",
                 font=(FAMILY, 13, "bold"),
                 text_color=SEV.get(severity, INK), anchor="w"
                 ).grid(row=0, column=1, sticky="ew", padx=PAD, pady=(GAP, 0))
    ctk.CTkLabel(row, text=detail, font=FONT_SMALL, text_color=INK_2,
                 anchor="w", justify="left", wraplength=760
                 ).grid(row=1, column=1, sticky="ew", padx=PAD, pady=(0, GAP))
    return row
