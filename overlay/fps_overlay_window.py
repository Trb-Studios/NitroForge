"""
Always-on-top, transparent, draggable FPS overlay.

Plain Tk toplevel: overrideredirect (no title bar), -topmost, and a
-transparentcolor key so only the text is visible over the game.  Works over
windowed / borderless-windowed games; games in *exclusive* fullscreen bypass
the desktop compositor, so no desktop overlay (ours or others') can draw over
them -- that is a Windows fact, not a bug; use borderless mode.
"""
from __future__ import annotations

import tkinter as tk

_TRANSPARENT = "#010101"          # unlikely-to-clash color key
_SIZES = {"small": 16, "medium": 24, "large": 36}
_MARGIN = 24


class FpsOverlayWindow(tk.Toplevel):
    def __init__(self, master, fps_monitor, corner="top-left", size="medium"):
        super().__init__(master)
        self._fps = fps_monitor
        self._drag_off = (0, 0)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", _TRANSPARENT)
        self.configure(bg=_TRANSPARENT)

        px = _SIZES.get(size, 24)
        self._fps_lbl = tk.Label(self, text="-- FPS", fg="#39ff5f",
                                 bg=_TRANSPARENT,
                                 font=("Consolas", px, "bold"))
        self._fps_lbl.pack(anchor="w")
        self._ft_lbl = tk.Label(self, text="-- ms", fg="#c3c2b7",
                                bg=_TRANSPARENT,
                                font=("Consolas", max(px - 8, 10)))
        self._ft_lbl.pack(anchor="w")

        for w in (self, self._fps_lbl, self._ft_lbl):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        self._place(corner)
        self._alive = True
        self._tick()

    def _place(self, corner: str) -> None:
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = max(self.winfo_reqwidth(), 120), max(self.winfo_reqheight(), 50)
        x = _MARGIN if "left" in corner else sw - w - _MARGIN
        y = _MARGIN if "top" in corner else sh - h - _MARGIN
        self.geometry(f"+{x}+{y}")

    def _drag_start(self, e) -> None:
        self._drag_off = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e) -> None:
        self.geometry(f"+{e.x_root - self._drag_off[0]}"
                      f"+{e.y_root - self._drag_off[1]}")

    def _tick(self) -> None:
        if not self._alive:
            return
        stats = self._fps.current_stats()
        if stats["fps"]:
            self._fps_lbl.configure(text=f"{stats['fps']:.0f} FPS")
            self._ft_lbl.configure(
                text=f"{stats['frametime_ms']:.1f} ms  {stats['process'] or ''}")
        else:
            self._fps_lbl.configure(text="-- FPS")
            self._ft_lbl.configure(text="waiting for frames...")
        self.after(500, self._tick)

    def close(self) -> None:
        self._alive = False
        try:
            self.destroy()
        except tk.TclError:
            pass
