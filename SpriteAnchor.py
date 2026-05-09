"""
SpriteAnchor  —  UI 確認専用モック (rembg_batch_ui_test.py)

目的:
  - 添付完成イメージのレイアウト/配色だけを再現する見た目専用ファイル。
  - 画像処理・保存・ALIGN処理などのロジックは一切実装しない。
  - クリックしても何も起きないボタンが大半 (押下時は「(未接続) ボタン名」を print)。

バグ修正(前版からの差分):
  - すべての widget は親フレームを正しく指定し、生成 → 即時に grid/pack するよう統一。
  - Canvas.create_window の引数を (x, y) タプルから x, y の位置引数に修正。
  - 初期描画は __init__ 内の after(0, ...) ではなく <Map> イベントで実行。
  - ThumbCard 内の余計な Canvas ネストを削除し、Frame 単独構造へ簡略化。
  - ttk.Scale のスタイル指定で 'troughrelief' など clam で未対応の属性を回避。
"""

import os
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog


def _spriteanchor_user_path(filename: str) -> str:
    try:
        return os.path.join(os.path.expanduser("~"), filename)
    except Exception:
        return filename


def _spriteanchor_runtime_setup():
    """Set cache/model paths early so rembg works in both source and frozen app."""
    try:
        numba_cache = os.environ.get("NUMBA_CACHE_DIR") or _spriteanchor_user_path(".spriteanchor_numba_cache")
        try:
            os.makedirs(numba_cache, exist_ok=True)
        except Exception:
            numba_cache = os.path.join(tempfile.gettempdir(), "SpriteAnchor_numba_cache")
            os.makedirs(numba_cache, exist_ok=True)
        os.environ["NUMBA_CACHE_DIR"] = numba_cache
    except Exception:
        pass

    try:
        if getattr(sys, "frozen", False) and not os.environ.get("U2NET_HOME"):
            candidates = []
            base = getattr(sys, "_MEIPASS", "")
            if base:
                candidates.append(os.path.join(base, "u2net"))
                candidates.append(os.path.join(os.path.dirname(base), "Resources", "u2net"))
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(exe_dir, "..", "Resources", "u2net"))
            candidates.append(os.path.join(exe_dir, "u2net"))
            for path in candidates:
                path = os.path.abspath(path)
                if os.path.exists(os.path.join(path, "u2net.onnx")):
                    os.environ["U2NET_HOME"] = path
                    break
    except Exception:
        pass


def _spriteanchor_log(message: str):
    """Write diagnostics to a user-visible log file; print still helps CLI runs."""
    try:
        print(message)
    except Exception:
        pass
    try:
        path = _spriteanchor_user_path("SpriteAnchor_rembg.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except Exception:
        pass


_spriteanchor_runtime_setup()

# Pillow は画像読み込み・リサイズに必須
try:
    from PIL import Image, ImageTk, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# RESAMPLE: v35 と同じ
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    try:
        RESAMPLE = Image.LANCZOS
    except Exception:
        RESAMPLE = 1  # PIL.Image.ANTIALIAS 互換

# ═══════════════════════════════════════════════════════════════
#  v35 から移植した定数 (rembg_batch_v35_fixed_output_size.py 由来)
# ═══════════════════════════════════════════════════════════════

CANVAS_SIZE   = 1024
PREVIEW_SIZE  = 384
SCALE         = PREVIEW_SIZE / CANVAS_SIZE

MODE_NORMAL   = "normal"
MODE_LARGE    = "large"
MODE_MANUAL   = "manual"

SLIDER_MIN    = -1024
SLIDER_MAX    =  1024

# v70: 足元基準ライン色 (シアン)
BASE_LINE_COLOR     = "#00e5ff"
BASE_LINE_COLOR_RGB = (0, 229, 255)

# プレビュー無地背景色 (v35)
PREVIEW_BG_PLAIN = "#0e1a24"

# Ghost初期X (表示px、UIから操作)
OVERLAY_INIT_X = 200


# ═══════════════════════════════════════════════════════════════
#  v35 から移植した座標計算 (calc_y, place_on_canvas, render_canvas)
#  すべて 1024 論理座標系で計算する。
# ═══════════════════════════════════════════════════════════════

def calc_y(img_h: int, mode: str, y_offset: int,
           size: int = CANVAS_SIZE) -> int:
    """v35 calc_y を拡張: クランプ範囲を画像見切れまで完全許容。
    - min_y = -size       (画像が完全に上に消えてさらに上へ)
    - max_y = size * 2    (画像が完全に下に消える位置まで)
    Y Offset スライダーが ±1024 の範囲を持つので、それを完全に消化できる
    クランプ幅にする。これより狭いと、スライダーを動かしても途中で
    画像位置が止まってしまう違和感が出る。
    """
    if mode == MODE_NORMAL:
        y = size - img_h
    elif mode == MODE_LARGE:
        y = (size - img_h) // 2
    else:
        y = (size - img_h) // 2 + y_offset
    # 画像高さに依存せず canvas を基準にした余裕のあるクランプ幅
    min_y = -size
    max_y = size * 2
    return max(min_y, min(y, max_y))


def place_on_canvas(img_raw, mode: str,
                    y_offset: int = 0, scale_pct: int = 100,
                    size: int = CANVAS_SIZE):
    """v35 place_on_canvas をベースに、scale/Y Offset の動作を改善。

    旧版の問題:
    1. scale > 100 で「下端を残して上端をクロップ」 → ジャンプ
    2. foot_y を size でクリップしていたため、Y Offset を大きく振っても
       画像が canvas 外に出ない (= 下方向にスライドできない)

    新版の方針:
    - paste_y は y_offset に直接連動 (clamp は calc_y の min_y/max_y のみ)
      → 画像が canvas 外まで完全に出ていく動きが得られる
    - foot_y_1024 (返り値) は ALIGN 用なので、旧互換の値を返す
      (clamped_h = min(h, size) を使った計算)
    """
    img = img_raw.copy().convert("RGBA")
    if scale_pct != 100:
        sw = max(1, int(img.width  * scale_pct / 100))
        sh = max(1, int(img.height * scale_pct / 100))
        img = img.resize((sw, sh), RESAMPLE)

    w, h = img.size
    x = (size - w) // 2

    # ── paste_y: 実際の貼付位置 (y_offset 連動、size でクリップしない) ──
    # calc_y は min_y=-img_h, max_y=size までクランプを許すので、
    # ここでは img の実サイズ h でそのまま呼ぶ。canvas 外にはみ出る分は
    # PIL の paste が自動的にカットする。
    paste_y = calc_y(h, mode, y_offset, size)

    # ── foot_y_1024: ALIGN 用 (旧互換: clamped_h で計算 + size でクリップ) ──
    # ALIGN ロジックは「画像下端が canvas 内のどこか」を前提にしているので、
    # ここで値が大きく変わると ALIGN が壊れる。旧計算式を維持。
    clamped_h = min(h, size)
    y_for_foot = calc_y(clamped_h, mode, y_offset, size)
    foot_y = max(0, min(y_for_foot + clamped_h, size))

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, (x, paste_y), img)
    return canvas, foot_y


def compute_foot_y_alpha(img_raw, mode: str,
                         y_offset: int = 0, scale_pct: int = 100,
                         size: int = CANVAS_SIZE) -> int:
    """ALIGN 用の「実足元」検出。
    place_on_canvas で 1024 RGBA キャンバスに画像を配置した後、
    alpha チャンネルの bounding box を取得し、その bottom を足元として返す。
    透明部分・背景キャンバス下端を足元として扱わない。"""
    canvas_img, _ = place_on_canvas(img_raw, mode, y_offset, scale_pct, size)
    try:
        # alpha チャンネルの非透明領域 bbox
        a = canvas_img.split()[3]
        bbox = a.getbbox()  # (l, t, r, b) or None
    except Exception:
        bbox = None
    if bbox is None:
        # 全透明: 念のため画像全体下端を返す
        return size
    # bbox の bottom が「キャラの実際の足元 Y」
    return max(0, min(bbox[3], size))


def make_plain_bg(size: int) -> "Image.Image":
    """背景なし(透明RGBA)。SpriteAnchor は黒canvas透過表示が仕様。"""
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def render_canvas(img_raw, mode: str, y_offset: int,
                  display_size: int, scale_pct: int = 100,
                  line_color: tuple = (220, 40, 40),
                  show_line: bool = True,
                  ref_line_y_disp: int = None,
                  ref_line_subtle: bool = False):
    """v35 render_canvas を SpriteAnchor 仕様(背景なし)に調整。
    1024座標系で配置 → display_size に縮小 → 基準ライン描画。
    返り値: (PIL.Image[RGBA], foot_y_disp)。背景は透明、画像本体は alpha 維持。"""
    canvas_img, foot_y_1024 = place_on_canvas(
        img_raw, mode, y_offset, scale_pct)
    thumb = canvas_img.copy()
    thumb.thumbnail((display_size, display_size), RESAMPLE)
    tw, th = thumb.size
    # 透明RGBAキャンバスに画像本体だけ alpha 合成(青背景は使わない)
    bg = Image.new("RGBA", (display_size, display_size), (0, 0, 0, 0))
    ox = (display_size - tw) // 2
    oy = (display_size - th) // 2
    bg.paste(thumb, (ox, oy), thumb)
    foot_y_disp = int(foot_y_1024 * display_size / CANVAS_SIZE)
    foot_y_disp = max(1, min(foot_y_disp, display_size - 1))
    if show_line:
        draw = ImageDraw.Draw(bg)
        draw.line([(0, foot_y_disp), (display_size - 1, foot_y_disp)],
                  fill=line_color + (255,) if len(line_color) == 3
                       else line_color,
                  width=2)
    if ref_line_y_disp is not None:
        rl = max(1, min(ref_line_y_disp, display_size - 1))
        if ref_line_subtle:
            od = ImageDraw.Draw(bg)
            od.line([(0, rl), (display_size - 1, rl)],
                    fill=(0, 229, 255, 130), width=2)
            od.line([(0, rl), (6, rl)],
                    fill=(0, 229, 255, 200), width=2)
            od.line([(display_size - 7, rl), (display_size - 1, rl)],
                    fill=(0, 229, 255, 200), width=2)
        else:
            draw = ImageDraw.Draw(bg)
            draw.line([(0, rl), (display_size - 1, rl)],
                      fill=BASE_LINE_COLOR_RGB + (255,), width=3)
            draw.polygon([(0, rl-5), (7, rl), (0, rl+5)],
                         fill=BASE_LINE_COLOR_RGB + (255,))
            draw.polygon([(display_size-1, rl-5), (display_size-8, rl),
                          (display_size-1, rl+5)],
                         fill=BASE_LINE_COLOR_RGB + (255,))
    return bg, foot_y_disp


# ═══════════════════════════════════════════════════════════════
#  v35 ImageItem (簡略版)
# ═══════════════════════════════════════════════════════════════

class ImageItem:
    """v35 ImageItem 相当の最小構成。"""
    def __init__(self, path: str):
        self.path = path
        self.rgba = None
        self.y_offset = 0
        self.scale_pct = 100
        self.loaded = False
        # 処理状態フラグ (UI表示用、ロジックには影響しない)
        self.is_aligned = False   # 足元ALIGN済みか
        self.is_scaled  = False   # サイズ一括適用済みか
        self.bg_removed = False   # 背景透過済みフラグ (キャッシュ用)
        self.original_rgba = None # 透過前の元画像 (Restore BG 用)

    @property
    def label(self) -> str:
        n = os.path.basename(self.path)
        n_no_ext = os.path.splitext(n)[0]
        return n_no_ext if len(n_no_ext) <= 14 else n_no_ext[:11] + "…"

    def ensure_loaded(self):
        if self.loaded and self.rgba is not None:
            return
        try:
            im = Image.open(self.path).convert("RGBA")
            # v35 と同じく CANVAS_SIZE を超える素材は thumbnail で縮小
            if im.width > CANVAS_SIZE or im.height > CANVAS_SIZE:
                im.thumbnail((CANVAS_SIZE, CANVAS_SIZE), RESAMPLE)
            self.rgba = im
            self.loaded = True
        except Exception as e:
            print(f"(load error) {self.path}: {e}")
            self.loaded = False

# ═══════════════════════════════════════════════════════════════
#  カラーパレット (完成イメージ準拠: 漆黒 + 緑ネオン)
# ═══════════════════════════════════════════════════════════════
BG_BASE     = "#0a0d12"
BG_PANEL    = "#0f0f13"
BG_CARD     = "#16191f"
BG_CARD2    = "#1d2128"
BG_THUMB    = "#13161c"
BORDER      = "#262b35"
BORDER_SOFT = "#1a1e26"

ACCENT      = "#00ff9f"
ACCENT_DIM  = "#00b870"
ACCENT_GLOW = "#5cffbc"
TOGGLE_OFF  = "#2a2f3a"

TEXT_HI     = "#eaf7f1"
TEXT_MID    = "#c8d0db"
TEXT_LO     = "#7a8395"
TEXT_DIM    = "#4a5160"


# ═══════════════════════════════════════════════════════════════
#  汎用ヘルパー
# ═══════════════════════════════════════════════════════════════
def _on_unconnected(name: str):
    """未接続ボタン押下時の placeholder。任意引数を受け取る。"""
    def _h(*_a, **_kw):
        print(f"(未接続) {name}")
    return _h


def _round_rect_polygon_pts(x1, y1, x2, y2, r):
    """Canvas で smooth=True ポリゴン描画用の角丸矩形点列を返す。"""
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2,     y1,
        x2,     y1 + r,
        x2,     y2 - r,
        x2,     y2,
        x2 - r, y2,
        x1 + r, y2,
        x1,     y2,
        x1,     y2 - r,
        x1,     y1 + r,
        x1,     y1,
    ]


# ═══════════════════════════════════════════════════════════════
#  カスタムウィジェット
# ═══════════════════════════════════════════════════════════════
class NeonButton(tk.Canvas):
    """角丸の緑ネオン主役ボタン。"""
    def __init__(self, parent, *, text="", command=None,
                 width=220, height=56, radius=12,
                 fill=ACCENT, hover_fill=ACCENT_GLOW,
                 text_color="#04241a",
                 font=("Helvetica", 14, "bold"),
                 bg_parent=BG_PANEL):
        super().__init__(parent,
                         width=width, height=height,
                         bg=bg_parent,
                         highlightthickness=0, bd=0,
                         cursor="hand2")
        self._text = text
        self._command = command
        self._w_hint = width
        self._h_hint = height
        self._radius = radius
        self._fill = fill
        self._hover_fill = hover_fill
        self._current_fill = fill
        self._text_color = text_color
        self._font = font

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Map>",       lambda e: self._redraw())
        self.bind("<Enter>",     self._on_enter)
        self.bind("<Leave>",     self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: w = self._w_hint
        if h <= 1: h = self._h_hint
        pts = _round_rect_polygon_pts(2, 2, w - 2, h - 2, self._radius)
        self.create_polygon(pts, smooth=True,
                            fill=self._current_fill, outline="")
        self.create_text(w // 2, h // 2,
                         text=self._text,
                         fill=self._text_color,
                         font=self._font)

    def _on_enter(self, _e=None):
        self._current_fill = self._hover_fill
        self._redraw()

    def _on_leave(self, _e=None):
        self._current_fill = self._fill
        self._redraw()

    def _on_click(self, _e=None):
        if self._command:
            self._command()


class OutlineButton(tk.Canvas):
    """角丸 outline ボタン (個別ALIGN / START 用)。
    対応状態:
      - hover    : 枠/文字を hover_border / hover_text に
      - pressed  : クリック中だけ内側塗りを暗くして「沈む」表現
      - disabled : クリック不可。枠と文字を薄くする
      - busy     : 一時テキスト表示 (set_busy / set_done / restore で切替)
    """
    def __init__(self, parent, *, text="", command=None,
                 width=220, height=44, radius=10,
                 border=BORDER, hover_border=ACCENT_DIM,
                 text_color=TEXT_HI, hover_text=ACCENT,
                 font=("Helvetica", 12, "bold"),
                 bg_parent=BG_PANEL):
        super().__init__(parent,
                         width=width, height=height,
                         bg=bg_parent,
                         highlightthickness=0, bd=0,
                         cursor="hand2")
        self._text = text
        # set_busy / set_done で表示を一時上書きするため、元のテキストを別途保持
        self._original_text = text
        self._command = command
        self._w_hint = width
        self._h_hint = height
        self._radius = radius
        self._border = border
        self._hover_border = hover_border
        self._current_border = border
        self._text_color = text_color
        self._hover_text = hover_text
        self._current_text = text_color
        self._font = font

        # 内側塗り色 (pressed 時に暗化、disabled 時に薄化)
        self._fill_normal  = BG_CARD       # 通常 #16191f
        self._fill_hover   = "#1d2128"     # hover 時にわずかに明るく
        self._fill_pressed = "#0c0e12"     # 押下時に暗く沈む
        self._fill_disabled = "#101216"    # disabled は更に暗く沈黙
        self._current_fill = self._fill_normal

        # 状態フラグ
        self._is_pressed = False
        self._is_hover = False
        self._is_disabled = False

        self.bind("<Configure>",       lambda e: self._redraw())
        self.bind("<Map>",             lambda e: self._redraw())
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: w = self._w_hint
        if h <= 1: h = self._h_hint
        r = self._radius
        # ── 内側塗り (状態に応じて色決定) ──
        if self._is_disabled:
            fill = self._fill_disabled
        elif self._is_pressed:
            fill = self._fill_pressed
        elif self._is_hover:
            fill = self._fill_hover
        else:
            fill = self._fill_normal
        self._current_fill = fill
        pts = _round_rect_polygon_pts(2, 2, w - 2, h - 2, r)
        self.create_polygon(pts, smooth=True,
                            fill=fill, outline="")
        # 上下辺
        self.create_line(r + 2, 2, w - r - 2, 2,
                         fill=self._current_border, width=2)
        self.create_line(r + 2, h - 2, w - r - 2, h - 2,
                         fill=self._current_border, width=2)
        # 左右辺
        self.create_line(2, r + 2, 2, h - r - 2,
                         fill=self._current_border, width=2)
        self.create_line(w - 2, r + 2, w - 2, h - r - 2,
                         fill=self._current_border, width=2)
        # 4 隅の弧
        self.create_arc(2, 2, 2 + 2 * r, 2 + 2 * r,
                        start=90, extent=90, style="arc",
                        outline=self._current_border, width=2)
        self.create_arc(w - 2 - 2 * r, 2, w - 2, 2 + 2 * r,
                        start=0, extent=90, style="arc",
                        outline=self._current_border, width=2)
        self.create_arc(2, h - 2 - 2 * r, 2 + 2 * r, h - 2,
                        start=180, extent=90, style="arc",
                        outline=self._current_border, width=2)
        self.create_arc(w - 2 - 2 * r, h - 2 - 2 * r, w - 2, h - 2,
                        start=270, extent=90, style="arc",
                        outline=self._current_border, width=2)
        # ── テキスト (押下時にわずかに下にずれる = 沈む表現) ──
        text_y = h // 2 + (1 if self._is_pressed else 0)
        self.create_text(w // 2, text_y,
                         text=self._text,
                         fill=self._current_text,
                         font=self._font)

    def _on_enter(self, _e=None):
        if self._is_disabled:
            return
        self._is_hover = True
        self._current_border = self._hover_border
        self._current_text = self._hover_text
        self._redraw()

    def _on_leave(self, _e=None):
        if self._is_disabled:
            return
        self._is_hover = False
        self._is_pressed = False
        self._current_border = self._border
        self._current_text = self._text_color
        self._redraw()

    def _on_press(self, _e=None):
        if self._is_disabled:
            return "break"
        self._is_pressed = True
        self._redraw()

    def _on_click(self, _e=None):
        if self._is_disabled:
            return "break"
        self._is_pressed = False
        self._redraw()
        if self._command:
            self._command()

    # ── 公開メソッド: disable / enable / busy / done / restore ──
    def set_disabled(self, disabled: bool):
        """ボタンを無効化。disabled 中はクリック不可、見た目も明確に変更。"""
        self._is_disabled = bool(disabled)
        try:
            self.config(cursor="" if self._is_disabled else "hand2")
        except Exception:
            pass
        if self._is_disabled:
            self._is_hover = False
            self._is_pressed = False
        self._redraw()

    def set_busy(self, busy_text: str = "Processing..."):
        """処理中表示に切替。テキストを差し替えて disabled にする。"""
        self._text = busy_text
        self.set_disabled(True)

    def set_done(self, done_text: str = "Done!"):
        """完了表示に切替。disabled は維持して数秒後に restore() で戻す想定。"""
        self._text = done_text
        # disabled のままだが、見た目はアクセント色寄りに
        self._redraw()

    def restore_text(self):
        """元のテキストに戻し、disabled も解除。"""
        self._text = self._original_text
        self.set_disabled(False)


class ToggleSwitch(tk.Canvas):
    """ピル型トグル。状態は self._on(bool)。"""
    def __init__(self, parent, *,
                 width=44, height=22,
                 initial=False,
                 on_color=ACCENT, off_color=TOGGLE_OFF,
                 knob_color="#ffffff",
                 bg_parent=BG_PANEL,
                 command=None):
        super().__init__(parent,
                         width=width, height=height,
                         bg=bg_parent,
                         highlightthickness=0, bd=0,
                         cursor="hand2")
        self._w_hint = width
        self._h_hint = height
        self._on = bool(initial)
        self._on_color = on_color
        self._off_color = off_color
        self._knob = knob_color
        self._command = command
        self.bind("<ButtonRelease-1>", self._toggle)
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Map>",       lambda e: self._redraw())

    def get(self):
        return self._on

    def _toggle(self, _e=None):
        self._on = not self._on
        self._redraw()
        if self._command:
            try:
                self._command(self._on)
            except TypeError:
                # 引数を受けないハンドラ向けフォールバック
                self._command()

    def _redraw(self):
        self.delete("all")
        w = self._w_hint
        h = self._h_hint
        r = h // 2
        track = self._on_color if self._on else self._off_color
        # ピル形のトラック
        self.create_oval(0, 0, h, h, fill=track, outline="")
        self.create_oval(w - h, 0, w, h, fill=track, outline="")
        self.create_rectangle(r, 0, w - r, h, fill=track, outline="")
        # ノブ
        pad = 3
        kr = r - pad
        kx1 = (w - h + pad) if self._on else pad
        self.create_oval(kx1, pad, kx1 + kr * 2, pad + kr * 2,
                         fill=self._knob, outline="")


class ThumbCard(tk.Frame):
    """サムネカード(下部一覧用)。
    item (ImageItem) が渡されればプレビューと同じ render_canvas で
    処理後(scale/y_offset適用後)の見た目を描画する。
    item が無く image_path だけのときは画像をそのまま縮小表示。"""
    def __init__(self, parent, *, label="", on_click=None, selected=False,
                 image_path=None, is_aligned=False, is_scaled=False,
                 on_right_click=None, on_close=None,
                 on_double_click=None,   # 廃止: 互換のためのみ受け取る
                 item=None):
        super().__init__(parent, bg=BG_BASE)
        self._on_click = on_click
        self._on_right_click = on_right_click
        self._on_close = on_close
        # ダブルクリック機能は廃止 (Shift/Ctrl 操作に統一)。
        # 引数 on_double_click は後方互換のため受け取るが使用しない。
        self._on_double_click = None
        self._label = label
        self._selected = selected
        # 複数選択状態 (Shift/Ctrl/Cmd-click でのマルチ選択)。
        # _selected (黄色枠 = アクティブ) とは独立。両方 true のときは _selected が優先。
        self._multi_selected = False
        # ★ 自前ダブルクリック検出用: 直前の release 時刻 (ms)
        self._last_release_ms = 0
        # クリック保留用 after id
        self._click_after_id = None
        self._image_path = image_path
        self._item = item        # 描画は item を優先 (処理後の見た目)
        self._photo = None       # PhotoImage 参照保持
        # 処理状態フラグ
        self._is_aligned = bool(is_aligned)
        self._is_scaled  = bool(is_scaled)
        # ツールチップ
        self._tip_win = None

        # 外枠: 選択中は黄色 3px、未選択は処理状態色 2px
        border_col = self._status_border_color()
        init_thick = 3 if selected else 2
        outer = tk.Frame(self,
                         bg=BG_THUMB,
                         highlightthickness=init_thick,
                         highlightbackground=border_col,
                         highlightcolor=border_col,
                         width=120, height=120,
                         cursor="hand2")
        outer.pack(padx=2, pady=(2, 2))
        outer.pack_propagate(False)

        # 内側に Canvas
        cv = tk.Canvas(outer, bg=BG_THUMB,
                       highlightthickness=0, bd=0,
                       cursor="hand2")
        cv.pack(expand=True, fill="both")
        self._cv = cv
        cv.bind("<Configure>", lambda e: self._redraw())
        cv.bind("<Map>",       lambda e: self._redraw())

        # ラベル
        self._lbl = tk.Label(self, text=label,
                             bg=BG_BASE,
                             fg=("#ffd64a" if selected else TEXT_LO),
                             font=("Helvetica", 11, "bold"))
        self._lbl.pack(pady=(4, 4))

        # ── クリック / ダブルクリック / 右クリック バインド ──
        # NOTE: Tk の <Double-Button-1> は環境/bindtag 順で発火しないことがある
        #       ため、<ButtonRelease-1> 1 本に統合し、自前で時刻差を見て
        #       ダブルクリックを検出する (350ms 以内の連続クリック = double)。
        # outer Frame に保存しておかないと self._outer が後の処理で参照できない
        self._outer = outer

        # ★ サムネカード全構成ウィジェットに ButtonRelease-1 を bind ★
        # self (= ThumbCard 自体), outer, cv, self._lbl すべてに同じハンドラを
        # 付与し、子ウィジェットがクリックを吸わないようにする。
        all_widgets = (self, outer, cv, self._lbl)
        for w in all_widgets:
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<Button-3>",         self._right_click)
            w.bind("<Button-2>",         self._right_click)

        # ツールチップ (ホバー)
        for w in (outer, cv):
            w.bind("<Enter>", self._on_hover_enter)
            w.bind("<Leave>", self._on_hover_leave)

        # ── 右上の × 削除ボタン (初期非表示。ホバー時に place で表示) ──
        self._btn_close = tk.Label(
            outer, text="×",
            bg="#1a1d22", fg="#ffffff",
            font=("Helvetica", 11, "bold"),
            padx=4, pady=0,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground="#2a2f3a")
        self._btn_close.bind("<Enter>",
            lambda _e: self._btn_close.config(fg="#ff5555"))
        self._btn_close.bind("<Leave>",
            lambda _e: self._btn_close.config(fg="#ffffff"))
        self._btn_close.bind("<ButtonRelease-1>", self._on_close_click)

        # ×表示制御: カード全体の Enter/Leave
        for w in (outer, cv, self._lbl):
            w.bind("<Enter>", self._on_card_enter, add="+")
            w.bind("<Leave>", self._on_card_leave, add="+")

    # ── ツールチップ ──────────────────────
    def _tooltip_text(self):
        parts = []
        if self._is_aligned:
            parts.append("Aligned")
        if self._is_scaled:
            parts.append("Scaled")
        return " / ".join(parts) if parts else ""

    def _on_hover_enter(self, _e=None):
        text = self._tooltip_text()
        if not text:
            return
        try:
            if self._tip_win is not None:
                return
            x = self.winfo_rootx() + 10
            y = self.winfo_rooty() - 22
            tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tip.configure(bg=BG_CARD2)
            lbl = tk.Label(tip, text=text,
                           bg=BG_CARD2, fg=ACCENT,
                           font=("Helvetica", 9, "bold"),
                           padx=6, pady=2,
                           highlightthickness=1,
                           highlightbackground=ACCENT_DIM)
            lbl.pack()
            self._tip_win = tip
        except Exception:
            self._tip_win = None

    def _on_hover_leave(self, _e=None):
        try:
            if self._tip_win is not None:
                self._tip_win.destroy()
        except Exception:
            pass
        self._tip_win = None

    def _redraw(self):
        """item があればプレビューと同じ render_canvas で処理後の見た目を描画。
        無ければ画像をそのまま縮小表示(後方互換)。"""
        cv = self._cv
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 8 or h < 8:
            return

        rendered = False

        # ── 優先: item からプレビュー同等のロジックで描画 ──
        item = self._item
        if (item is not None and _PIL_AVAILABLE
                and getattr(item, "rgba", None) is not None):
            try:
                pad = 4
                disp = max(16, min(w, h) - pad * 2)
                # キャッシュキー: 処理状態を含める(scale/y_offset 変更で再生成)
                key = ("item", id(item), disp,
                       int(item.y_offset), int(item.scale_pct))
                if self._photo is None or getattr(self, "_photo_key", None) != key:
                    bg, _foot = render_canvas(
                        item.rgba, MODE_MANUAL,
                        int(item.y_offset), disp,
                        scale_pct=int(item.scale_pct),
                        show_line=False,           # サムネには BASE LINE を描かない
                        ref_line_y_disp=None)
                    self._photo = ImageTk.PhotoImage(bg)
                    self._photo_key = key
                cv.create_image(w // 2, h // 2,
                                image=self._photo, anchor="center")
                rendered = True
            except Exception as e:
                print(f"(thumb render error) {e}")

        # ── フォールバック: image_path をそのまま縮小表示 ──
        if not rendered and self._image_path and _PIL_AVAILABLE \
                and os.path.exists(self._image_path):
            try:
                key = ("path", self._image_path, w, h)
                if self._photo is None or getattr(self, "_photo_key", None) != key:
                    im = Image.open(self._image_path).convert("RGBA")
                    pad = 6
                    tw = max(8, w - pad * 2)
                    th = max(8, h - pad * 2)
                    im.thumbnail((tw, th), Image.LANCZOS)
                    self._photo = ImageTk.PhotoImage(im)
                    self._photo_key = key
                cv.create_image(w // 2, h // 2,
                                image=self._photo, anchor="center")
                rendered = True
            except Exception as e:
                print(f"(thumb load error) {self._image_path}: {e}")

        if not rendered:
            self._draw_demo_char()

        # 選択ハイライト + 処理状態オーバーレイ + 状態テキスト
        try:
            self._draw_status_overlay(cv, w, h)
            self._draw_status_text(cv, w, h)
        except Exception:
            pass

    def _draw_status_text(self, cv, w, h):
        """サムネ右上に「A 80% +10」のような小さな状態テキストを描画。
        - A : ALIGN済み
        - 80%: scale_pct (100% のときも表示)
        - +10: y_offset (0 のときは省略)
        """
        item = self._item
        if item is None:
            return
        parts = []
        if getattr(self, "_is_aligned", False):
            parts.append("A")
        try:
            sp = int(item.scale_pct)
            parts.append(f"{sp}%")
        except Exception:
            pass
        try:
            yo = int(item.y_offset)
            if yo != 0:
                parts.append(f"{yo:+d}")
        except Exception:
            pass
        if not parts:
            return
        text = " ".join(parts)
        # 視認しやすいように影付き
        try:
            cv.create_text(w - 5, 4, text=text, anchor="ne",
                           fill="#000000",
                           font=("Helvetica", 8, "bold"))
            cv.create_text(w - 6, 3, text=text, anchor="ne",
                           fill=ACCENT if self._is_aligned else TEXT_HI,
                           font=("Helvetica", 8, "bold"))
        except Exception:
            pass

    # ── 処理状態 → 枠色 ─────────────────────
    def _status_border_color(self):
        """枠色:
        - 選択中(アクティブ)   : 黄色 (#FFD64A) — 単一選択 / プレビュー対象
        - マルチ選択 (緑枠)    : #22d680 — 複数選択中、Restore/Remove Selected 対象
        - 両方処理済み          : ACCENT_GLOW
        - ALIGN済み            : ACCENT
        - Scale済み            : シアン青 (#3aa8ff)
        - 未処理                : BORDER
        """
        if self._selected:
            return "#ffd64a"
        if self._multi_selected:
            return "#22d680"
        a, s = self._is_aligned, self._is_scaled
        if a and s:
            return ACCENT_GLOW
        if a:
            return ACCENT
        if s:
            return "#3aa8ff"
        return BORDER

    def _draw_status_overlay(self, cv, w, h):
        """選択中は外枠色(黄色)で区別するため、内側ラインは描かない。
        テキスト/アイコン/下ラインは描画しない。"""
        return

    def _draw_demo_char(self):
        """画像が無いときのピクセル風プレースホルダ。"""
        cv = self._cv
        w = cv.winfo_width()
        h = cv.winfo_height()
        cx = w // 2
        base_y = int(h * 0.92)
        total_h = int(h * 0.78)

        if self._selected:
            body, body_light, body_shadow = ACCENT, "#7dffc8", ACCENT_DIM
            outline = "#04241a"; eye = "#04241a"
        else:
            body, body_light, body_shadow = "#3a4150", "#4a5260", "#2a3038"
            outline = "#1a1e26"; eye = "#1a1e26"

        pmap = [
            "00011110",
            "00111111",
            "01122112",
            "11222221",
            "11252521",
            "11222221",
            "11122211",
            "01111110",
            "01133110",
            "01100110",
        ]
        rows = len(pmap); cols = len(pmap[0])
        px = max(2, total_h // rows)
        char_w = cols * px; char_h = rows * px
        x0 = cx - char_w // 2; y0 = base_y - char_h
        color_map = {"1": body, "2": body_light, "3": body_shadow,
                     "4": outline, "5": eye}
        for r, row in enumerate(pmap):
            for c, ch in enumerate(row):
                if ch == "0":
                    continue
                col = color_map.get(ch, body)
                xa = x0 + c * px; ya = y0 + r * px
                cv.create_rectangle(xa, ya, xa + px, ya + px,
                                    fill=col, outline="")

    def _on_release(self, e=None):
        """ButtonRelease-1 ハンドラ。
        ダブルクリック判定は廃止し、シングルクリックのみで動作する。
        Shift / Ctrl(Cmd) 修飾キーは _click → _on_click コールバック側で
        判定する。
        """
        self._click(e)
        return "break"

    def _click(self, e=None):
        if self._on_click:
            # Shift / Ctrl / Cmd 押下情報を呼び出し側へ渡せるよう event 同梱で呼ぶ。
            # 後方互換: 旧コールバックが (label) のみ受ける場合に備えて、
            # 引数2個で受けられるか確認してから呼び分ける。
            try:
                import inspect
                params = len(inspect.signature(self._on_click).parameters)
            except Exception:
                params = 1
            try:
                if params >= 2:
                    self._on_click(self._label, e)
                else:
                    self._on_click(self._label)
            except TypeError:
                # 呼び出し失敗時は label のみで再試行
                self._on_click(self._label)

    def _right_click(self, e=None):
        if self._on_right_click:
            try:
                self._on_right_click(e)
            except Exception:
                pass

    # ── × 削除ボタン制御 ─────────────────────
    def _on_card_enter(self, _e=None):
        try:
            self._btn_close.place(relx=1.0, x=-4, y=4, anchor="ne")
            self._btn_close.lift()
        except Exception:
            pass

    def _on_card_leave(self, _e=None):
        # ポインタがカードの矩形内にまだあれば消さない (子ウィジェット間移動対策)
        try:
            x = self.winfo_pointerx() - self.winfo_rootx()
            y = self.winfo_pointery() - self.winfo_rooty()
            if 0 <= x < self.winfo_width() and 0 <= y < self.winfo_height():
                return
        except Exception:
            pass
        try:
            self._btn_close.place_forget()
        except Exception:
            pass

    def _on_close_click(self, _e=None):
        # 軽い縮小アニメ (約120ms) → 削除コールバック
        try:
            steps = [(0, 110), (40, 90), (80, 60)]
            for ms, sz in steps:
                self.after(ms, lambda s=sz: self._shrink(s))
            self.after(120, self._fire_close)
        except Exception:
            self._fire_close()
        return "break"  # 親への伝播を止める (誤って _click が走らないように)

    def _shrink(self, size):
        try:
            self._outer.config(width=size, height=size)
        except Exception:
            pass

    def _fire_close(self):
        if callable(getattr(self, "_on_close", None)):
            try:
                self._on_close()
            except Exception:
                pass

    def _apply_border_state(self):
        """現在の _selected / _multi_selected / 処理状態に基づいて
        外枠の色と太さを再計算して適用する。常に呼び出し OK (冪等)。"""
        try:
            outer = self._outer
            col = self._status_border_color()
            # 黄色 (active) または 緑 (multi) のときは 3px、それ以外 2px
            thick = 3 if (self._selected or self._multi_selected) else 2
            outer.config(highlightbackground=col,
                         highlightcolor=col,
                         highlightthickness=thick)
        except Exception:
            pass
        try:
            # ラベル色: アクティブ=黄、multi=緑、通常=低彩度
            if self._selected:
                self._lbl.config(fg="#ffd64a")
            elif self._multi_selected:
                self._lbl.config(fg="#22d680")
            else:
                self._lbl.config(fg=TEXT_LO)
        except Exception:
            pass

    def set_selected(self, sel: bool):
        """選択状態(アクティブ=黄色枠)を更新。
        ★ 早期 return しない: _multi_selected との組み合わせで枠色が
           変わる可能性があるため、毎回 _apply_border_state を呼ぶ。
        """
        self._selected = bool(sel)
        self._apply_border_state()
        try:
            self._redraw()
        except Exception:
            pass

    def set_multi_selected(self, multi: bool):
        """複数選択(緑枠)状態を更新。
        ★ 早期 return しない: _selected 変更後に呼ばれた場合に
           枠色を更新できなくなるのを防ぐ。
        """
        self._multi_selected = bool(multi)
        self._apply_border_state()

    def pulse(self, *, strong: bool = False, delay_ms: int = 0):
        """一瞬だけ枠を太く・明るく光らせて元に戻す。
        strong=True で持続時間を長め(現在選択中の強調用)。
        delay_ms で発光開始を遅延できる(全カードを順に光らせる演出用)。"""
        try:
            outer = self.winfo_children()[0]
        except Exception:
            return

        # 元の状態を保存
        try:
            orig_thick = int(outer.cget("highlightthickness"))
        except Exception:
            orig_thick = 2
        # 戻し色 = 現時点の処理状態色 (選択は内側ラインで表現するので無関係)
        orig_color = self._status_border_color()

        # 段階: (時間ms, 太さ, 色) のリスト
        if strong:
            steps = [
                (0,   4, ACCENT_GLOW),
                (180, 3, ACCENT),
                (360, 2, ACCENT_GLOW),
                (500, orig_thick, None),   # None = 最新の処理状態色を使う
            ]
        else:
            steps = [
                (0,   4, ACCENT_GLOW),
                (160, 3, ACCENT),
                (300, orig_thick, None),
            ]

        def _apply(thick, col):
            try:
                # col が None なら現時点の処理状態色に戻す
                final_col = col if col is not None else self._status_border_color()
                outer.config(highlightthickness=thick,
                             highlightbackground=final_col,
                             highlightcolor=final_col)
            except Exception:
                pass

        for ms, th, col in steps:
            try:
                self.after(delay_ms + ms, lambda t=th, c=col: _apply(t, c))
            except Exception:
                pass

    def set_status(self, *, is_aligned=None, is_scaled=None):
        """処理状態フラグを更新して再描画(再生成は不要)。"""
        changed = False
        if is_aligned is not None and bool(is_aligned) != self._is_aligned:
            self._is_aligned = bool(is_aligned)
            changed = True
        if is_scaled is not None and bool(is_scaled) != self._is_scaled:
            self._is_scaled = bool(is_scaled)
            changed = True
        if changed:
            try:
                outer = self.winfo_children()[0]
                col = self._status_border_color()
                outer.config(highlightbackground=col, highlightcolor=col)
            except Exception:
                pass
            # フラグ変更時はテキスト/画像も最新化するため photo キャッシュ破棄
            self._photo = None
            self._photo_key = None
            try:
                self._redraw()
            except Exception:
                pass

    def refresh_view(self):
        """item の y_offset / scale_pct が外で変わったあと、サムネを最新の
        処理後の見た目で再描画する(プレビューと同期)。"""
        # photo キャッシュを破棄してから再描画
        self._photo = None
        self._photo_key = None
        try:
            self._redraw()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  メイン UI
# ═══════════════════════════════════════════════════════════════
class App:
    def __init__(self, root):
        self.root = root
        root.title("SpriteAnchor")
        root.configure(bg=BG_BASE)
        root.geometry("1240x880")
        root.minsize(1180, 820)

        # ── 画像状態管理 ───────────────────────────────────
        # _images        : 読み込んだ画像のパス順序リスト
        # _current_idx   : 現在プレビューしている index (-1 = 未選択)
        # _preview_photo : PhotoImage 参照保持(GC防止)
        # _thumb_inner   : サムネ列を入れる Frame
        # _thumb_canvas  : サムネ列の親 Canvas (横スクロール用)
        # _thumb_cards   : 生成済み ThumbCard 参照(クリック切替の高速化用)
        # _preview_cache : path → PIL.Image (リサイズ前の RGBA)。読込時に1回だけ確保。
        # _preview_size  : 直前にレンダしたプレビュー領域(w,h)。サイズ変化時のみ再リサイズ。
        # _preview_photo_for_path : 直前のプレビューPhotoImageが対応する path
        # ═══════════════════════════════════════════════════════
        #  状態管理 (v35 準拠)
        # ═══════════════════════════════════════════════════════
        # self.item_list      : list[ImageItem] - v35 と同じ。各 item に
        #                       y_offset / scale_pct / rgba を保持。
        # self.current_idx    : 現在表示中の index (-1 = 未選択)
        # self.ref_line_y     : BASE LINE の Y(1024座標系 int)。v35 と同じ。
        #                       初期値は CANVAS_SIZE(=最下端)。
        # self._ghost_prev    : 直前選択画像のスナップショット dict
        #                       {rgba, y, scale, label}。Ghost表示に使用。
        # self._prev_item_idx : 直前選択 index (互換)
        self.item_list = []
        self.current_idx = -1
        # 複数選択 (Shift/Ctrl/Cmd-click): set[int]
        # current_idx は「アクティブなプレビュー対象」、selected_idxs は
        # Restore Selected / Remove BG Selected の対象集合。
        self.selected_idxs = set()
        self.ref_line_y = CANVAS_SIZE
        # ── ヘッドライン (上ライン) 状態 ──
        # 1024 座標系での上ライン Y。BASE LINE と独立、ドラッグで上下移動。
        # 初期位置は canvas の上から 10% 程度の場所 (= y=102 付近)。
        self.head_y = int(CANVAS_SIZE * 0.10)
        self._headline_dragging = False
        self._ghost_prev = None
        self._prev_item_idx = -1

        # 描画キャッシュ(参照保持・GC防止用)
        self._preview_photo = None       # メインプレビュー (1枚)
        self._thumb_inner = None
        self._thumb_canvas = None
        self._thumb_cards = []

        # BASE LINE のドラッグ操作状態
        self._baseline_dragging = False

        # ── BASE LINE 表示 ON/OFF (描画のみ制御、ALIGN/Y計算ロジックには無関係) ──
        # CHECK モード中は False に強制、通常モードでは True に戻す。
        self.show_baseline = True

        # CHECK MODE 状態
        self.check_mode = False
        self._check_frame = None        # 確認モード用フレーム (preview と重ね配置)
        self._check_inner = None        # スクロール内側 frame
        self._check_canvas = None       # スクロール用 canvas
        self._check_photos = []         # PhotoImage の参照保持(GC防止)
        self._check_cell_widgets = []   # クリック切替用のセル outer 参照

        # Manual Erase インラインモード状態 (None = 通常モード)
        self._inline_erase = None

        # 出力設定 (左ペイン常時表示 + START 用)
        # 出力サイズは複数選択 (チェックボックス方式)
        self.var_save_dir   = tk.StringVar(value="")
        self.var_prefix     = tk.StringVar(value="transparent")
        self.var_size_1024  = tk.BooleanVar(value=True)
        self.var_size_2048  = tk.BooleanVar(value=False)
        self.var_size_3072  = tk.BooleanVar(value=False)
        self.var_size_custom = tk.BooleanVar(value=False)
        self.var_custom_size = tk.StringVar(value="1024")

        self._init_styles()

        # 全体grid: row 0=タイトル, row 1=メイン3カラム, row 2=下部一覧
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=1)
        root.rowconfigure(2, weight=0)

        self._build_titlebar(root)
        self._build_main(root)
        self._build_thumbs(root)

        # ── キーボード / 右クリック / D&D の登録 ──
        self._install_keybindings()
        self._install_context_menus()
        self._install_drag_and_drop()

        # ── 前回の出力設定を復元 (UI 構築後に実行) ──
        try:
            self._load_export_settings()
        except Exception as e:
            print(f"(load export settings error) {e}")

    # ───────────────────────────────────────────────────────
    def _init_styles(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Neon.Horizontal.TScale",
                    background=BG_PANEL,
                    troughcolor=TOGGLE_OFF,
                    bordercolor=BG_PANEL,
                    lightcolor=ACCENT,
                    darkcolor=ACCENT_DIM)

    # ───────────────────────────────────────────────────────
    def _build_titlebar(self, root):
        bar = tk.Frame(root, bg=BG_BASE, height=56)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(0, weight=0)
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(2, weight=0)

        # 左: アイコンプレースホルダ (空のままにする)
        # 旧 GLS の "G" マークは製品名 SpriteAnchor と一致しないため削除。
        # 同一サイズ(36×36)の空 Canvas を維持してレイアウト寸法を変えない。
        ico = tk.Canvas(bar, width=36, height=36,
                        bg=BG_BASE, highlightthickness=0, bd=0)
        ico.grid(row=0, column=0, padx=(14, 8), pady=10)

        # 中央: タイトル + サブテキスト
        title_box = tk.Frame(bar, bg=BG_BASE)
        title_box.grid(row=0, column=1, sticky="")
        title = tk.Label(title_box, text="SpriteAnchor",
                         bg=BG_BASE, fg=TEXT_HI,
                         font=("Helvetica", 14, "bold"))
        title.pack()
        subtitle = tk.Label(title_box, text="Align sprites to a base line",
                            bg=BG_BASE, fg=TEXT_LO,
                            font=("Helvetica", 9))
        subtitle.pack()

        # 右: ウィンドウ操作 (ダミー)
        win_btns = tk.Frame(bar, bg=BG_BASE)
        win_btns.grid(row=0, column=2, padx=14)
        for sym in ("—", "◻", "✕"):
            tk.Label(win_btns, text=sym,
                     bg=BG_BASE, fg=TEXT_LO,
                     font=("Helvetica", 13, "bold"),
                     padx=8, cursor="hand2"
                     ).pack(side="left")

        # 下端のうっすら境界
        sep = tk.Frame(bar, bg=BORDER_SOFT, height=1)
        sep.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")

        # ── ヘッドライン (フローティング、ドラッグ移動可能、位置永続化) ──
        # root 全体に place で重ねる。タイトルバーやペインの上を自由に動かせる。
        self._build_headline(root)

    # ── アプリ設定の永続化 (ヘッドライン位置 / 出力設定) ──────────────
    def _settings_path(self):
        """アプリ設定 JSON のパスを返す (~/.spriteanchor_settings.json)。"""
        try:
            home = os.path.expanduser("~")
            return os.path.join(home, ".spriteanchor_settings.json")
        except Exception:
            return None

    def _settings_load(self) -> dict:
        """アプリ設定全体を dict で返す。失敗時は {}。"""
        path = self._settings_path()
        if not path or not os.path.exists(path):
            return {}
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _settings_save(self, updates: dict):
        """アプリ設定を merge して保存。既存キーは保持して updates だけ上書き。"""
        path = self._settings_path()
        if not path:
            return
        try:
            import json
            data = self._settings_load()
            data.update(updates)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"(settings save error) {e}")

    # ── 互換ラッパー: 旧ヘッドライン用関数 ──
    def _headline_settings_path(self):
        return self._settings_path()

    def _load_headline_pos(self):
        data = self._settings_load()
        try:
            x = int(data.get("headline_x", -1))
            y = int(data.get("headline_y", -1))
            if x < 0 or y < 0:
                return None
            return (x, y)
        except Exception:
            return None

    def _save_headline_pos(self, x: int, y: int):
        self._settings_save({"headline_x": int(x), "headline_y": int(y)})

    # ── 出力設定の保存 / 復元 ──
    def _save_export_settings(self):
        """現在の出力設定を JSON に保存する。
        保存項目: 保存先フォルダ / prefix / 出力サイズ on/off / Custom 値。
        START 実行直前および出力設定ダイアログの確定時に呼ぶ。"""
        try:
            updates = {
                "export_save_dir":     self.var_save_dir.get().strip(),
                "export_prefix":       self.var_prefix.get().strip() or "transparent",
                "export_size_1024":    bool(self.var_size_1024.get()),
                "export_size_2048":    bool(self.var_size_2048.get()),
                "export_size_3072":    bool(self.var_size_3072.get()),
                "export_size_custom":  bool(self.var_size_custom.get()),
                "export_custom_size":  str(self.var_custom_size.get()).strip(),
            }
            self._settings_save(updates)
            print(f"(export settings saved) {updates}")
        except Exception as e:
            print(f"(export settings save error) {e}")

    def _load_export_settings(self):
        """起動時に出力設定を復元する。
        - 保存先フォルダが存在しない場合は空にして警告ログを出す
        - prefix が空なら 'transparent' に
        - サイズが1つも True でなければ 1024 を強制 ON
        """
        data = self._settings_load()
        if not data:
            return

        # 保存先フォルダ (存在しない場合はクリア)
        save_dir = str(data.get("export_save_dir", "")).strip()
        if save_dir:
            try:
                if os.path.isdir(save_dir):
                    self.var_save_dir.set(save_dir)
                else:
                    print(f"(export settings) saved folder not found: {save_dir!r}")
                    self.var_save_dir.set("")
            except Exception:
                self.var_save_dir.set("")

        # prefix (空なら transparent)
        prefix = str(data.get("export_prefix", "")).strip() or "transparent"
        try:
            self.var_prefix.set(prefix)
        except Exception:
            pass

        # サイズチェック
        try:
            self.var_size_1024.set(bool(data.get("export_size_1024", True)))
            self.var_size_2048.set(bool(data.get("export_size_2048", False)))
            self.var_size_3072.set(bool(data.get("export_size_3072", False)))
            self.var_size_custom.set(bool(data.get("export_size_custom", False)))
        except Exception:
            pass

        # Custom サイズ値
        try:
            cs = str(data.get("export_custom_size", "1024")).strip() or "1024"
            self.var_custom_size.set(cs)
        except Exception:
            pass

        # 安全弁: 1つも選ばれていない場合は 1024 を強制 ON
        try:
            if not any([self.var_size_1024.get(),
                        self.var_size_2048.get(),
                        self.var_size_3072.get(),
                        self.var_size_custom.get()]):
                self.var_size_1024.set(True)
                print("(export settings) no sizes checked, forced 1024 ON")
        except Exception:
            pass

        # 出力パネルの表示も更新
        try:
            self._refresh_export_panel()
        except Exception:
            pass
        print(f"(export settings loaded) folder={self.var_save_dir.get()!r} "
              f"prefix={self.var_prefix.get()!r}")

    def _build_headline(self, root):
        """ヘッドラインラベルを root に place で配置。
        - 左ドラッグで移動可能 (タイトル文字列領域のみ反応)
        - ウィンドウ外に出ないようクランプ
        - 位置は ~/.spriteanchor_settings.json に永続化
        - ホバー時にカーソルを fleur に変更
        """
        # ヘッドライン文言: 製品価値を一文で
        text = "Align sprites instantly. Fix baselines. Export clean assets."
        lbl = tk.Label(root, text=text,
                       bg=BG_BASE, fg=ACCENT,
                       font=("Helvetica", 11, "bold"),
                       padx=14, pady=4,
                       cursor="fleur")
        # 初期位置: 保存値があればそれ、なければ画面上部中央
        saved = self._load_headline_pos()
        if saved is not None:
            init_x, init_y = saved
            lbl.place(x=init_x, y=init_y)
        else:
            # タイトルバー直下に水平中央配置 (relx=0.5 で center)
            lbl.place(relx=0.5, y=58, anchor="n")
        self._headline_lbl = lbl

        # ── ドラッグ移動 ──
        drag_state = {"sx": 0, "sy": 0, "lx": 0, "ly": 0, "dragging": False}

        def _on_press(e):
            try:
                # 現在の絶対位置を取得 (place 情報から)
                lx = lbl.winfo_x()
                ly = lbl.winfo_y()
            except Exception:
                lx = ly = 0
            drag_state["sx"] = e.x_root
            drag_state["sy"] = e.y_root
            drag_state["lx"] = lx
            drag_state["ly"] = ly
            drag_state["dragging"] = True
            return "break"

        def _on_drag(e):
            if not drag_state["dragging"]:
                return
            dx = e.x_root - drag_state["sx"]
            dy = e.y_root - drag_state["sy"]
            new_x = drag_state["lx"] + dx
            new_y = drag_state["ly"] + dy
            # ウィンドウ内に制限
            try:
                rw = root.winfo_width()
                rh = root.winfo_height()
                lw = lbl.winfo_width()
                lh = lbl.winfo_height()
                new_x = max(0, min(new_x, max(0, rw - lw)))
                new_y = max(0, min(new_y, max(0, rh - lh)))
            except Exception:
                pass
            # anchor=nw で配置 (relx は使わない)
            lbl.place(x=new_x, y=new_y, anchor="nw")
            return "break"

        def _on_release(e):
            if not drag_state["dragging"]:
                return
            drag_state["dragging"] = False
            try:
                x = lbl.winfo_x()
                y = lbl.winfo_y()
                self._save_headline_pos(x, y)
            except Exception:
                pass
            return "break"

        lbl.bind("<ButtonPress-1>",   _on_press)
        lbl.bind("<B1-Motion>",       _on_drag)
        lbl.bind("<ButtonRelease-1>", _on_release)

        # ヘッドラインが他の UI より前面に出るように
        try:
            lbl.lift()
        except Exception:
            pass

    # ───────────────────────────────────────────────────────
    def _build_main(self, root):
        main = tk.Frame(root, bg=BG_BASE)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0, minsize=200)   # 左 (素材読み込みのみ)
        main.columnconfigure(1, weight=1)                # 中央 (プレビュー)
        main.columnconfigure(2, weight=0, minsize=260)   # 右 (操作集約)
        main.rowconfigure(0, weight=1)
        # Manual Erase の固定レイアウトで使用 (左右に新パネルを差し込む親)
        self._main_grid_frame = main

        self._build_workflow(main)
        self._build_preview(main)
        self._build_controls(main)

    # ───────────────────────────────────────────────────────
    def _build_workflow(self, parent):
        # 左ペイン (最小): 「素材読み込みのみ」
        #   - ＋画像を選ぶ ボタン
        #   - 読み込み枚数表示
        # Workflow手順 / 保存先 / ファイル名 / 出力サイズ は全削除。
        # 保存系の設定は START 押下時の Toplevel ダイアログでのみ表示する。
        wf_outer = tk.Frame(parent, bg=BG_PANEL, padx=18, pady=22)
        wf_outer.grid(row=0, column=0, sticky="nsw")
        wf_outer.columnconfigure(0, weight=1)
        self._wf_outer = wf_outer

        # 上部の小さいラベル(完成イメージの "#0f0f13" 表記は維持)
        tk.Label(wf_outer, text="#0f0f13",
                 bg=BG_PANEL, fg=ACCENT,
                 font=("Menlo", 10, "bold")
                 ).pack(anchor="w")
        tk.Frame(wf_outer, bg=BORDER, height=1, width=80
                 ).pack(anchor="w", pady=(3, 22))

        # セクション見出し
        tk.Label(wf_outer, text="Sprites",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 12, "bold")
                 ).pack(anchor="w", pady=(0, 6))

        # + Add Sprites
        btn = OutlineButton(wf_outer, text="+ Add Sprites",
                            command=self._pick_images,
                            width=200, height=40, radius=8,
                            border=ACCENT_DIM, hover_border=ACCENT,
                            text_color=ACCENT, hover_text=ACCENT_GLOW,
                            font=("Helvetica", 11, "bold"),
                            bg_parent=BG_PANEL)
        btn.pack(anchor="w", fill="x")

        # 読み込み枚数表示
        self.lbl_load_count = tk.Label(wf_outer,
                                       text="Loaded: 0",
                                       bg=BG_PANEL, fg=TEXT_LO,
                                       font=("Helvetica", 10))
        self.lbl_load_count.pack(anchor="w", pady=(8, 14))

        # Clear All
        self.btn_del_all = OutlineButton(
            wf_outer, text="Clear All",
            command=self._delete_all,
            width=200, height=32, radius=8,
            border=BORDER, hover_border="#d05a5a",
            text_color=TEXT_MID, hover_text="#ff8a8a",
            font=("Helvetica", 10, "bold"),
            bg_parent=BG_PANEL)
        self.btn_del_all.pack(anchor="w", fill="x")

        # ── ドロップ案内 (D&Dが効くなら有効化されるヒント) ──
        self.lbl_dnd_hint = tk.Label(
            wf_outer,
            text="Drag & Drop files or folders",
            bg=BG_PANEL, fg=TEXT_DIM,
            font=("Helvetica", 9))
        self.lbl_dnd_hint.pack(anchor="w", pady=(14, 0))

        # ── Output Settings (常時表示) ──
        # 区切り線
        tk.Frame(wf_outer, bg=BORDER_SOFT, height=1
                 ).pack(anchor="w", fill="x", pady=(22, 12))
        tk.Label(wf_outer, text="Output Settings",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 11, "bold")
                 ).pack(anchor="w")

        ex_box = tk.Frame(wf_outer, bg=BG_PANEL)
        ex_box.pack(anchor="w", fill="x", pady=(6, 0))
        ex_box.columnconfigure(1, weight=1)

        def _row(r, label_text, value_var_name, default="—"):
            tk.Label(ex_box, text=label_text,
                     bg=BG_PANEL, fg=TEXT_LO,
                     font=("Helvetica", 9)
                     ).grid(row=r, column=0, sticky="w", pady=(2, 0))
            lbl = tk.Label(ex_box, text=default,
                           bg=BG_PANEL, fg=TEXT_HI,
                           font=("Helvetica", 9, "bold"),
                           anchor="w", justify="left",
                           wraplength=160)
            lbl.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=(2, 0))
            setattr(self, value_var_name, lbl)

        _row(0, "Folder",  "lbl_ex_folder", "Not set")
        _row(1, "Prefix",  "lbl_ex_prefix", self.var_prefix.get() or "—")
        _init_sizes = ", ".join(self._get_selected_sizes_disp()) or "(none)"
        _row(2, "Size",    "lbl_ex_size",   _init_sizes)

        # Change ボタン
        self.btn_export_change = OutlineButton(
            wf_outer, text="Change",
            command=self._open_export_dialog,
            width=200, height=28, radius=8,
            border=BORDER, hover_border=ACCENT_DIM,
            text_color=TEXT_MID, hover_text=ACCENT,
            font=("Helvetica", 10, "bold"),
            bg_parent=BG_PANEL)
        self.btn_export_change.pack(anchor="w", fill="x", pady=(10, 0))

        # 初期表示
        self._refresh_export_panel()

        # ── Grid Settings (左ペイン補助設定) ──
        tk.Frame(wf_outer, bg=BORDER_SOFT, height=1
                 ).pack(anchor="w", fill="x", pady=(22, 12))
        tk.Label(wf_outer, text="Grid Settings",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 11, "bold")
                 ).pack(anchor="w")

        gs_box = tk.Frame(wf_outer, bg=BG_PANEL)
        gs_box.pack(anchor="w", fill="x", pady=(8, 0))
        gs_box.columnconfigure(0, weight=1)
        gs_box.columnconfigure(1, weight=0)

        # Grid ON/OFF
        tk.Label(gs_box, text="Grid",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 10)
                 ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        def _on_grid_toggle(state):
            try:
                self._draw_preview_demo()
            except Exception:
                pass

        self.tg_grid = ToggleSwitch(
            gs_box, initial=True,
            command=_on_grid_toggle,
            bg_parent=BG_PANEL)
        self.tg_grid.grid(row=0, column=1, sticky="e", pady=(0, 6))

        # Grid Size (16 / 32 / 64)
        tk.Label(gs_box, text="Size",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 10)
                 ).grid(row=1, column=0, sticky="w")
        gs_pills_wrap = tk.Frame(gs_box, bg=BG_PANEL)
        gs_pills_wrap.grid(row=1, column=1, sticky="e")

        self.var_grid_size = tk.StringVar(value="32")
        self._grid_size_pills = {}

        def _on_grid_size(val: str):
            self.var_grid_size.set(val)
            self._refresh_grid_size_pills()
            try:
                self._draw_preview_demo()
            except Exception:
                pass

        for val in ("16", "32", "64"):
            pill = tk.Label(gs_pills_wrap, text=val,
                            bg=BG_CARD, fg=TEXT_MID,
                            font=("Helvetica", 9, "bold"),
                            padx=8, pady=3,
                            cursor="hand2",
                            highlightthickness=1,
                            highlightbackground=BORDER)
            pill.pack(side="left", padx=(0, 4))
            pill.bind("<ButtonRelease-1>",
                      lambda _e, v=val: _on_grid_size(v))
            self._grid_size_pills[val] = pill
        self._refresh_grid_size_pills()

    # ── パス短縮 (左ペイン表示用) ──────────────────
    @staticmethod
    def _shorten_path(p: str, max_len: int = 28) -> str:
        if not p:
            return "Not set"
        if len(p) <= max_len:
            return p
        # 末尾優先で省略 (.../parent/name)
        try:
            head, tail = os.path.split(p)
            if len(tail) >= max_len - 3:
                return "…" + tail[-(max_len - 1):]
            head_room = max_len - len(tail) - 4
            if head_room <= 0:
                return "…/" + tail
            return "…" + head[-head_room:] + "/" + tail
        except Exception:
            return "…" + p[-(max_len - 1):]

    def _refresh_export_panel(self):
        """左ペイン下部の Output Settings 表示を最新値に同期。"""
        try:
            self.lbl_ex_folder.config(
                text=self._shorten_path(self.var_save_dir.get()))
        except Exception:
            pass
        try:
            self.lbl_ex_prefix.config(
                text=self.var_prefix.get() or "—")
        except Exception:
            pass
        try:
            sizes = self._get_selected_sizes_disp()
            if not sizes:
                self.lbl_ex_size.config(text="(none)", fg="#ff8a8a")
            else:
                self.lbl_ex_size.config(text=", ".join(sizes), fg=TEXT_HI)
        except Exception:
            pass

    def _get_selected_sizes(self):
        """選択中のサイズを int リストで返す(出力処理用)。
        Custom が選ばれていれば数値化して追加。重複は排除。"""
        out = []
        if self.var_size_1024.get():
            out.append(1024)
        if self.var_size_2048.get():
            out.append(2048)
        if self.var_size_3072.get():
            out.append(3072)
        if self.var_size_custom.get():
            try:
                cs = int(str(self.var_custom_size.get()).strip())
                if cs > 0:
                    out.append(cs)
            except Exception:
                pass
        # 重複排除 + ソート
        seen = set()
        uniq = []
        for v in out:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        return sorted(uniq)

    def _get_selected_sizes_disp(self):
        """表示用の文字列リスト(例: ['1024', '2048', '3072(C)'])。"""
        out = []
        if self.var_size_1024.get():
            out.append("1024")
        if self.var_size_2048.get():
            out.append("2048")
        if self.var_size_3072.get():
            out.append("3072")
        if self.var_size_custom.get():
            cs = str(self.var_custom_size.get()).strip() or "?"
            out.append(f"{cs}(C)")
        return out

    # ═══════════════════════════════════════════════════════
    #  出力設定ダイアログ (START 押下時のみ表示)
    # ═══════════════════════════════════════════════════════
    def _on_start_clicked(self):
        """START 押下時の挙動。
        - 出力フォルダ未選択 → 即座にフォルダ選択ダイアログを開く
          (キャンセルされた場合は出力設定モーダルを開いて編集機会を提供)
        - 出力フォルダ選択済み → 即処理開始
        """
        print("[START] clicked")
        cur_dir = self.var_save_dir.get().strip()
        if not cur_dir:
            try:
                d = filedialog.askdirectory(
                    title="Select Output Folder",
                    parent=self.root)
            except Exception:
                d = ""
            if d:
                self.var_save_dir.set(d)
                self._refresh_export_panel()
                self._run_export()
            else:
                # キャンセル時は設定モーダルを開いて編集してもらう
                self._open_export_dialog()
            return
        # 設定済み → 即処理開始
        self._run_export()

    def _run_export(self):
        """START 押下時の入口。UI を busy 状態 (Exporting...) にしてから
        50ms 後に実保存処理 _run_export_actual を呼ぶ。
        50ms 遅延は Tkinter に Exporting... 表示を反映する時間を与えるため。
        処理完了後は Done! を 0.8 秒表示してから START に戻す。
        """
        # 出力設定を永続化 (次回起動時に自動復元される)
        try:
            self._save_export_settings()
        except Exception as e:
            print(f"(save export settings error) {e}")

        # ボタン busy 表示 + 連打防止
        try:
            self.btn_start.set_busy("Exporting...")
        except Exception:
            pass
        # UI を即時更新してから重い処理を実行
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        def _do():
            try:
                self._run_export_actual()
            except Exception as e:
                print(f"[EXPORT] uncaught error: {e}")
            # 完了表示 → 元に戻す
            try:
                self.btn_start.set_done("✓ Done!")
            except Exception:
                pass
            try:
                self.root.after(800, self._restore_start_button)
            except Exception:
                # after が動かない場合は即時リストア
                self._restore_start_button()

        try:
            self.root.after(50, _do)
        except Exception:
            _do()

    def _restore_start_button(self):
        try:
            self.btn_start.restore_text()
        except Exception:
            pass

    def _run_export_actual(self):
        """選択されたすべてのサイズで PNG を書き出す (実処理)。
        ファイル名: {prefix}_{連番3桁}_{size}.png

        実装方針:
        - 各 item を MODE_MANUAL + 現在の y_offset / scale_pct で
          place_on_canvas() に渡し、1024×1024 RGBA キャンバスを生成
        - 出力サイズが 1024 ならそのまま保存、それ以外なら resize して保存
        - 透過 PNG として保存 (背景は透明のまま)
        - 保存先フォルダが存在しない場合は自動作成
        - 各保存後にファイル存在確認を行い、結果をログ出力
        """
        from pathlib import Path
        print("=" * 60)
        print("[EXPORT] START clicked")

        sizes = self._get_selected_sizes()
        if not sizes:
            self.var_size_1024.set(True)
            sizes = [1024]
            try:
                self._refresh_export_panel()
            except Exception:
                pass

        folder = self.var_save_dir.get().strip()
        prefix = self.var_prefix.get().strip() or "transparent"
        n = len(self.item_list)
        print(f"[EXPORT] folder={folder!r} prefix={prefix!r} "
              f"sizes={sizes} items={n}")

        if not folder:
            print("[EXPORT] ABORT: folder is empty")
            return
        if n == 0:
            print("[EXPORT] ABORT: no items loaded")
            return

        # ── 保存先フォルダ確認 / 自動作成 ──
        try:
            out_dir = Path(folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"[EXPORT] output dir ready: {out_dir.resolve()}")
        except Exception as e:
            print(f"[EXPORT] ERROR cannot create folder: {e}")
            return

        ok_count = 0
        fail_count = 0

        # ── 各 item × 各 size で保存 ──
        for i, it in enumerate(self.item_list):
            # 未読込なら遅延ロード
            if not it.loaded:
                try:
                    it.ensure_loaded()
                except Exception as e:
                    print(f"[EXPORT] item#{i+1} ensure_loaded error: {e}")
                    fail_count += len(sizes)
                    continue
            if not it.loaded or it.rgba is None:
                print(f"[EXPORT] item#{i+1} not loaded, skip")
                fail_count += len(sizes)
                continue

            # 1024 RGBA キャンバスをプレビューと同じロジックで生成
            try:
                canvas_1024, _foot = place_on_canvas(
                    it.rgba,
                    MODE_MANUAL,
                    int(it.y_offset),
                    int(it.scale_pct),
                    CANVAS_SIZE,
                )
            except Exception as e:
                print(f"[EXPORT] item#{i+1} place_on_canvas error: {e}")
                fail_count += len(sizes)
                continue

            for sz in sizes:
                # サイズに合わせて resize (透過維持のため LANCZOS)
                try:
                    if sz == CANVAS_SIZE:
                        out_img = canvas_1024
                    else:
                        out_img = canvas_1024.resize((sz, sz), RESAMPLE)
                except Exception as e:
                    print(f"[EXPORT] item#{i+1} resize({sz}) error: {e}")
                    fail_count += 1
                    continue

                fname = f"{prefix}_{i+1:03d}_{sz}.png"
                save_path = out_dir / fname
                # 絶対パスでログ出力 (デバッグ用)
                print(f"[EXPORT] SAVE PATH: {save_path}")
                try:
                    # PNG として保存 (透過チャンネル維持)
                    out_img.save(str(save_path), "PNG")
                except Exception as e:
                    print(f"[EXPORT] SAVE FAILED ({fname}): {e}")
                    fail_count += 1
                    continue

                # 保存後の存在確認
                if save_path.exists():
                    size_kb = save_path.stat().st_size // 1024
                    print(f"[EXPORT] SAVED OK: {save_path}  ({size_kb} KB)")
                    ok_count += 1
                else:
                    print(f"[EXPORT] SAVE FAILED (file not found): {save_path}")
                    fail_count += 1

        total = n * len(sizes)
        print(f"[EXPORT] DONE  ok={ok_count}/{total}  fail={fail_count}")
        print("=" * 60)

    def _open_export_dialog(self):
        """START ボタンから呼ばれる Toplevel ダイアログ。
        保存先 / ファイル名 / 出力サイズ / 実行ボタンを内包する。"""
        # 既に開いていたら再フォーカスのみ
        existing = getattr(self, "_export_win", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_set()
                    return
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        win.title("Export Settings")
        win.configure(bg=BG_BASE)
        win.transient(self.root)
        win.geometry("480x440")
        win.minsize(460, 420)
        try:
            win.grab_set()
        except Exception:
            pass
        self._export_win = win

        def _close(_e=None):
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            self._export_win = None

        win.bind("<Escape>", _close)
        win.protocol("WM_DELETE_WINDOW", _close)

        # 状態変数は __init__ で生成済み (左ペインと共有)
        body = tk.Frame(win, bg=BG_BASE, padx=22, pady=22)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        # 見出し
        tk.Label(body, text="Export Settings",
                 bg=BG_BASE, fg=TEXT_HI,
                 font=("Helvetica", 14, "bold")
                 ).grid(row=0, column=0, sticky="w")
        tk.Label(body, text="Configure output folder, filename, and sizes",
                 bg=BG_BASE, fg=TEXT_LO,
                 font=("Helvetica", 9)
                 ).grid(row=1, column=0, sticky="w", pady=(2, 16))

        # ── 保存先 ──
        tk.Label(body, text="Output Folder",
                 bg=BG_BASE, fg=TEXT_HI,
                 font=("Helvetica", 11, "bold")
                 ).grid(row=2, column=0, sticky="w", pady=(0, 4))

        def _pick_save_dir():
            try:
                d = filedialog.askdirectory(
                    title="Select Output Folder",
                    initialdir=self.var_save_dir.get() or None,
                    parent=win)
            except Exception:
                d = ""
            if d:
                self.var_save_dir.set(d)
                try:
                    self.lbl_save_dir.config(text=self._shorten_path(d))
                except Exception:
                    pass

        save_btn = OutlineButton(body, text="Select Folder",
                                 command=_pick_save_dir,
                                 width=200, height=36, radius=8,
                                 border=BORDER, hover_border=ACCENT_DIM,
                                 text_color=TEXT_HI, hover_text=ACCENT,
                                 font=("Helvetica", 11, "bold"),
                                 bg_parent=BG_BASE)
        save_btn.grid(row=3, column=0, sticky="ew")
        cur_dir = self.var_save_dir.get()
        self.lbl_save_dir = tk.Label(body,
                                     text=(self._shorten_path(cur_dir)
                                           if cur_dir else "—"),
                                     bg=BG_BASE, fg=TEXT_LO,
                                     font=("Helvetica", 9),
                                     anchor="w", justify="left",
                                     wraplength=420)
        self.lbl_save_dir.grid(row=4, column=0, sticky="w", pady=(4, 14))

        # ── ファイル名(prefix) ──
        tk.Label(body, text="Filename Prefix",
                 bg=BG_BASE, fg=TEXT_HI,
                 font=("Helvetica", 11, "bold")
                 ).grid(row=5, column=0, sticky="w", pady=(0, 4))

        entry_wrap = tk.Frame(body, bg=BG_CARD,
                              highlightthickness=1,
                              highlightbackground=BORDER,
                              highlightcolor=ACCENT_DIM)
        entry_wrap.grid(row=6, column=0, sticky="ew")
        entry_wrap.columnconfigure(0, weight=1)
        tk.Entry(entry_wrap,
                 textvariable=self.var_prefix,
                 bg=BG_CARD, fg=TEXT_HI,
                 insertbackground=ACCENT,
                 relief="flat", bd=0,
                 font=("Menlo", 11),
                 highlightthickness=0
                 ).grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        tk.Label(body, text="Example: transparent_001.png — saved with sequential numbering",
                 bg=BG_BASE, fg=TEXT_DIM,
                 font=("Helvetica", 9)
                 ).grid(row=7, column=0, sticky="w", pady=(4, 14))

        # ── 出力サイズ (複数選択可) ──
        tk.Label(body, text="Output Size (px) — multiple allowed",
                 bg=BG_BASE, fg=TEXT_HI,
                 font=("Helvetica", 11, "bold")
                 ).grid(row=8, column=0, sticky="w", pady=(0, 6))

        chk_wrap = tk.Frame(body, bg=BG_BASE)
        chk_wrap.grid(row=9, column=0, sticky="ew")
        for c in range(4):
            chk_wrap.columnconfigure(c, weight=1, uniform="size")

        def _on_size_changed():
            # Custom チェック状態に応じて Entry の有効/無効を切替
            try:
                if self.var_size_custom.get():
                    self.entry_custom.config(state="normal")
                else:
                    self.entry_custom.config(state="disabled")
            except Exception:
                pass
            # 全て未選択になりそうなら 1024 を強制ON (最低1つは選択保証)
            if not (self.var_size_1024.get() or self.var_size_2048.get()
                    or self.var_size_3072.get() or self.var_size_custom.get()):
                self.var_size_1024.set(True)
            # チェックマーク表示を更新
            self._refresh_size_check_marks()

        # 独自チェックボックス: ✅ / □ をテキストとして描画
        # (ttk.Checkbutton の indicator は OS によって × に見えるケースがあるため)
        self._size_check_widgets = []  # [(label_widget, var), ...]
        opts = [("1024",   self.var_size_1024),
                ("2048",   self.var_size_2048),
                ("3072",   self.var_size_3072),
                ("Custom", self.var_size_custom)]
        for col, (label_text, var) in enumerate(opts):
            cell = tk.Frame(chk_wrap, bg=BG_BASE, cursor="hand2")
            cell.grid(row=0, column=col, sticky="w",
                      padx=(0 if col == 0 else 8, 0), pady=4)
            mark = tk.Label(cell, text="✅" if var.get() else "□",
                            bg=BG_BASE, fg=ACCENT,
                            font=("Helvetica", 12, "bold"),
                            cursor="hand2", width=2)
            mark.pack(side="left")
            txt = tk.Label(cell, text=label_text,
                           bg=BG_BASE, fg=TEXT_HI,
                           font=("Helvetica", 11), cursor="hand2")
            txt.pack(side="left", padx=(2, 0))

            def _toggle(_e=None, v=var):
                v.set(not v.get())
                _on_size_changed()
            for w in (cell, mark, txt):
                w.bind("<ButtonRelease-1>", _toggle)
            self._size_check_widgets.append((mark, var))

        # Custom 入力
        custom_wrap = tk.Frame(body, bg=BG_CARD,
                               highlightthickness=1,
                               highlightbackground=BORDER,
                               highlightcolor=ACCENT_DIM)
        custom_wrap.grid(row=10, column=0, sticky="ew", pady=(8, 16))
        custom_wrap.columnconfigure(0, weight=1)
        custom_wrap.columnconfigure(1, weight=0)
        self.entry_custom = tk.Entry(custom_wrap,
                                     textvariable=self.var_custom_size,
                                     bg=BG_CARD, fg=TEXT_HI,
                                     insertbackground=ACCENT,
                                     relief="flat", bd=0,
                                     font=("Menlo", 11),
                                     highlightthickness=0,
                                     state=("normal" if self.var_size_custom.get() else "disabled"),
                                     disabledbackground=BG_CARD,
                                     disabledforeground=TEXT_DIM)
        self.entry_custom.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        tk.Label(custom_wrap, text="px",
                 bg=BG_CARD, fg=TEXT_LO,
                 font=("Helvetica", 10)
                 ).grid(row=0, column=1, sticky="e", padx=(0, 8))

        # ── 操作行(キャンセル / 実行) ──
        btn_row = tk.Frame(body, bg=BG_BASE)
        btn_row.grid(row=11, column=0, sticky="ew", pady=(8, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=0)
        btn_row.columnconfigure(2, weight=0)

        cancel_btn = OutlineButton(btn_row, text="Cancel",
                                   command=_close,
                                   width=120, height=40, radius=8,
                                   border=BORDER, hover_border=TEXT_MID,
                                   text_color=TEXT_MID, hover_text=TEXT_HI,
                                   font=("Helvetica", 11, "bold"),
                                   bg_parent=BG_BASE)
        cancel_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))

        def _save_and_close():
            # 最低1つ選択保証 (全部 OFF の状態で閉じられたら 1024 を ON に戻す)
            if not (self.var_size_1024.get() or self.var_size_2048.get()
                    or self.var_size_3072.get() or self.var_size_custom.get()):
                self.var_size_1024.set(True)
            # prefix が空なら transparent をデフォルトに
            try:
                if not self.var_prefix.get().strip():
                    self.var_prefix.set("transparent")
            except Exception:
                pass
            # 出力設定を永続化 (次回起動時に自動復元される)
            try:
                self._save_export_settings()
            except Exception as e:
                print(f"(save export settings error) {e}")
            # 左ペインの常時表示パネルを最新値で更新してから閉じる
            try:
                self._refresh_export_panel()
            except Exception:
                pass
            _close()

        run_btn = NeonButton(btn_row, text="Export",
                             command=_save_and_close,
                             width=160, height=40, radius=8,
                             fill=ACCENT, hover_fill=ACCENT_GLOW,
                             text_color="#04241a",
                             font=("Helvetica", 12, "bold"),
                             bg_parent=BG_BASE)
        run_btn.grid(row=0, column=2, sticky="e")
        self._export_run_btn = run_btn

    def _update_run_btn_state(self):
        """モーダル内の「保存」ボタン活性状態を更新(現状はサイズ最低1つ保証のみ)。
        将来 disable 制御を追加する余地として残す。"""
        # 実装上は _on_size_changed 内で常に最低1つ ON が保証されるため特段の処理不要。
        return

    def _refresh_size_check_marks(self):
        """出力サイズの独自チェックボックス表示を更新 (✅ / □)。"""
        widgets = getattr(self, "_size_check_widgets", None) or []
        for mark_lbl, var in widgets:
            try:
                mark_lbl.config(text="✅" if var.get() else "□",
                                fg=ACCENT if var.get() else TEXT_LO)
            except Exception:
                pass

    # ───────────────────────────────────────────────────────
    def _build_preview(self, parent):
        wrap = tk.Frame(parent, bg=BG_BASE, padx=14, pady=18)
        wrap.grid(row=0, column=1, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self._preview_wrap = wrap

        cv = tk.Canvas(wrap, bg="#1a1d22",
                       highlightthickness=1,
                       highlightbackground=BORDER_SOFT, bd=0)
        cv.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas = cv
        cv.bind("<Configure>", self._draw_preview_demo)

        # ── 確認モード用 Frame (同じ row=0, column=0 に重ね配置) ──
        # 通常時は grid_remove() で隠し、CHECK ON 時に grid() で表示。
        self._build_check_frame(wrap)

        # BASE LINE ドラッグ判定用しきい値
        self._baseline_hit_tol = 18

        # 通常モード用バインドを設定
        self._install_preview_default_bindings()

    # ── BASE LINE ドラッグ用ハンドラ (メソッド化して再バインド可能に) ──
    def _hit_baseline(self, y_px: int) -> bool:
        try:
            ly = getattr(self, "_line_y_canvas", -1)
            return abs(y_px - ly) <= getattr(self, "_baseline_hit_tol", 18)
        except Exception:
            return False

    def _hit_headline(self, y_px: int) -> bool:
        try:
            ly = getattr(self, "_head_line_y_canvas", -1)
            return abs(y_px - ly) <= getattr(self, "_baseline_hit_tol", 18)
        except Exception:
            return False

    def _baseline_apply_y(self, y_canvas: int):
        disp = getattr(self, "_disp_size", 0)
        oy = getattr(self, "_disp_oy", 0)
        if disp <= 0:
            return
        y_disp = y_canvas - oy
        y_disp = max(0, min(disp, y_disp))
        y_1024 = int(y_disp * CANVAS_SIZE / disp)
        self._set_ref_line(y_1024)

    def _headline_apply_y(self, y_canvas: int):
        """ヘッドラインの Y を canvas px から 1024 座標に変換して保存。"""
        disp = getattr(self, "_disp_size", 0)
        oy = getattr(self, "_disp_oy", 0)
        if disp <= 0:
            return
        y_disp = y_canvas - oy
        y_disp = max(0, min(disp, y_disp))
        y_1024 = int(y_disp * CANVAS_SIZE / disp)
        # 1024 範囲内にクランプ
        self.head_y = max(0, min(y_1024, CANVAS_SIZE))
        try:
            self._draw_preview_demo()
        except Exception:
            pass

    def _baseline_on_press(self, e):
        # ヘッドラインを優先判定 (BASE LINE と重なった場合は両方判定で BASE LINE が勝つように下に配置)
        # → ベース、ヘッドの順で hit 判定し、近い方を採用
        hit_base = self._hit_baseline(e.y)
        hit_head = self._hit_headline(e.y)
        if hit_base and hit_head:
            # 両方ヒット範囲: ピクセル距離で近い方
            d_base = abs(e.y - getattr(self, "_line_y_canvas", -999))
            d_head = abs(e.y - getattr(self, "_head_line_y_canvas", -999))
            if d_head < d_base:
                hit_base = False
            else:
                hit_head = False
        if hit_base:
            self._baseline_dragging = True
            try:
                self.preview_canvas.config(cursor="sb_v_double_arrow")
            except Exception:
                pass
            self._baseline_apply_y(e.y)
        elif hit_head:
            self._headline_dragging = True
            try:
                self.preview_canvas.config(cursor="sb_v_double_arrow")
            except Exception:
                pass
            self._headline_apply_y(e.y)

    def _baseline_on_motion_hover(self, e):
        if self._baseline_dragging or self._headline_dragging:
            return
        try:
            if self._hit_baseline(e.y) or self._hit_headline(e.y):
                self.preview_canvas.config(cursor="sb_v_double_arrow")
            else:
                self.preview_canvas.config(cursor="")
        except Exception:
            pass

    def _baseline_on_drag(self, e):
        if self._baseline_dragging:
            self._baseline_apply_y(e.y)
        elif self._headline_dragging:
            self._headline_apply_y(e.y)

    def _baseline_on_release(self, _e):
        if self._baseline_dragging:
            self._baseline_dragging = False
            try:
                self.preview_canvas.config(cursor="")
            except Exception:
                pass
            try:
                self._draw_preview_demo()
            except Exception:
                pass
        elif self._headline_dragging:
            self._headline_dragging = False
            try:
                self.preview_canvas.config(cursor="")
            except Exception:
                pass
            try:
                self._draw_preview_demo()
            except Exception:
                pass

    def _install_preview_default_bindings(self):
        """preview_canvas に通常モード用のバインドを設定 (Manual Erase 終了時に復元)。"""
        cv = self.preview_canvas
        try:
            cv.bind("<Configure>",       self._draw_preview_demo)
            cv.bind("<Button-1>",        self._baseline_on_press)
            cv.bind("<B1-Motion>",       self._baseline_on_drag)
            cv.bind("<ButtonRelease-1>", self._baseline_on_release)
            cv.bind("<Motion>",          self._baseline_on_motion_hover)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    #  v35 準拠の操作メソッド (BASE LINE / Y Offset / Scale / ALIGN)
    # ═══════════════════════════════════════════════════════════
    @property
    def current_item(self):
        if 0 <= self.current_idx < len(self.item_list):
            return self.item_list[self.current_idx]
        return None

    def _current_y_offset(self) -> int:
        """v35 _current_y_offset 同等。"""
        try:
            return int(self.var_y.get())
        except Exception:
            return 0

    # ── BASE LINE 操作 (v35 _on_ref_line_slider / _set_ref_line) ──
    def _set_ref_line(self, y_1024: int):
        """v35 _set_ref_line そのまま。1024座標値で BASE LINE を設定。"""
        y_1024 = max(0, min(int(y_1024), CANVAS_SIZE))
        self.ref_line_y = y_1024
        # スライダー / ラベル同期(再帰防止フラグ)
        try:
            self._refline_sync = True
            self.var_baseline_y.set(y_1024)
            if hasattr(self, "lbl_baseline_y"):
                self.lbl_baseline_y.config(text=f"Y={y_1024}")
        except Exception:
            pass
        finally:
            self._refline_sync = False
        self._draw_preview_demo()

    def _on_ref_line_slider(self, _=None):
        """v35 _on_ref_line_slider 同等。"""
        if getattr(self, "_refline_sync", False):
            return
        try:
            v = int(float(self.var_baseline_y.get()))
        except Exception:
            return
        v = max(0, min(v, CANVAS_SIZE))
        self.ref_line_y = v
        try:
            if hasattr(self, "lbl_baseline_y"):
                self.lbl_baseline_y.config(text=f"Y={v}")
        except Exception:
            pass
        self._draw_preview_demo()

    # ── Y Offset (v35 _on_slider / _set_y) ──
    def _on_slider(self, _=None):
        """Y Offset スライダーの値が変化したときに呼ばれる。
        ttk.Scale の command はドラッグ中ピクセル単位で連続発火するため、
        毎回フル再描画 (place_on_canvas + 1024 RGBA 生成 + サムネ再生成) を
        走らせると重い。

        軽量化方針:
          - 値の反映 (item.y_offset = ...) だけは即座に行う
          - プレビュー再描画は after() でスロットリング (約 30ms に1回)
          - サムネは確定時 (ButtonRelease) まで更新しない
            → ドラッグ中の重い再生成を完全に省略
          - スライダー操作終了時 (_remember_prev_y 呼出時) にフル更新で帳尻を合わせる
        """
        item = self.current_item
        if item:
            try:
                item.y_offset = int(self.var_y.get())
            except Exception:
                pass
        # ── スロットリング: 既に予約があればスキップ ──
        if getattr(self, "_slider_redraw_pending", False):
            return
        self._slider_redraw_pending = True

        def _do_redraw():
            self._slider_redraw_pending = False
            try:
                self._draw_preview_demo()
            except Exception:
                pass
            # サムネ更新はドラッグ中はしない (確定時に _on_slider_release で実施)

        try:
            self.root.after(30, _do_redraw)
        except Exception:
            _do_redraw()

    def _on_slider_release(self, _e=None):
        """Y Offset スライダーのドラッグ終了時に呼ばれる。
        ドラッグ中スキップしていたサムネ更新と prev_y 記憶を行う。"""
        # 保留中のプレビュー再描画があれば即実行
        try:
            if getattr(self, "_slider_redraw_pending", False):
                self._slider_redraw_pending = False
                self._draw_preview_demo()
        except Exception:
            pass
        # 確定したのでサムネを最終状態に更新
        try:
            self._refresh_thumb_view()
        except Exception:
            pass
        # 既存の prev_y 記憶も呼ぶ
        try:
            self._remember_prev_y()
        except Exception:
            pass

    def _set_y(self, val: int):
        """v35 _set_y 同等。"""
        try:
            self.var_y.set(int(val))
        except Exception:
            pass
        # 値表示は var_y trace で自動同期されるので明示更新不要
        item = self.current_item
        if item:
            item.y_offset = int(val)
        self._draw_preview_demo()
        self._refresh_thumb_view()

    # ── Prev Y (前回値の自動記憶 + 表示 + クリックで再適用) ─────────────
    def _remember_prev_y(self, val=None):
        """直前に確定した Y 値を保存。FIT TO LINE 完了時 / スライダー操作
        終了時など、ユーザーが「この位置で確定した」タイミングで呼び出す。
        val を省略すると現在の var_y 値を使う。
        """
        if val is None:
            try:
                val = int(self.var_y.get())
            except Exception:
                return
        try:
            self._prev_y = int(val)
            # ラベル更新 (補助情報サイズ)
            self.lbl_prev_y.config(
                text=f"{self._prev_y:+d}",
                fg=TEXT_MID)
        except Exception:
            pass

    def _apply_prev_y(self):
        """Prev Y ラベルクリックで現在画像にその値を適用。"""
        if getattr(self, "_prev_y", None) is None:
            return
        v = max(SLIDER_MIN, min(int(self._prev_y), SLIDER_MAX))
        self._set_y(v)
        print(f"(Apply Prev Y) {v} -> current item")

    # ── Scale % (v35 _on_scale_slider / _set_scale / _update_scale_label) ──
    def _on_scale_slider(self, _=None):
        """v35 _on_scale_slider 同等。"""
        item = self.current_item
        if item:
            try:
                item.scale_pct = int(float(self.var_scale.get()))
            except Exception:
                pass
        self._draw_preview_demo()
        self._refresh_thumb_view()

    def _set_scale(self, val: int):
        """v35 _set_scale 同等。"""
        try:
            self.var_scale.set(int(val))
        except Exception:
            pass
        item = self.current_item
        if item:
            item.scale_pct = int(val)
        self._draw_preview_demo()
        self._refresh_thumb_view()

    # ── ALIGN (v35 _align_to_ref_line / _align_all_to_ref_line) ──
    def _align_to_ref_line(self):
        """v35 _align_to_ref_line を alpha bbox ベース足元検出で実行。
        現在 item の「キャラ実足元(非透明ピクセル最下端)」を ref_line_y に揃える
        Y Offset を計算して設定。"""
        item = self.current_item
        if item is None or not item.loaded or item.rgba is None:
            return
        y_offset = self._current_y_offset()
        scale = item.scale_pct
        try:
            # 画像全体下端ではなく、alpha 非透明領域の bottom を足元として使う
            foot_y_1024 = compute_foot_y_alpha(
                item.rgba, MODE_MANUAL, y_offset, scale)
        except Exception as e:
            print(f"(align error) {e}")
            return
        new_y = self.ref_line_y - foot_y_1024 + y_offset
        new_y = max(SLIDER_MIN, min(new_y, SLIDER_MAX))
        self._set_y(new_y)
        item.y_offset = new_y
        # FIT TO LINE で確定したので prev_y に記憶
        try:
            self._remember_prev_y(new_y)
        except Exception:
            pass
        # 状態フラグ + サムネ更新
        item.is_aligned = True
        try:
            idx = self.current_idx
            if 0 <= idx < len(self._thumb_cards):
                self._thumb_cards[idx].set_status(is_aligned=True)
        except Exception:
            pass
        # サムネを最新の処理後表示で同期
        self._refresh_thumb_view()

    def _align_all_to_ref_line(self):
        """全画像の足元を BASE LINE (ref_line_y) に一括で揃える。
        - BASE LINE は固定 (self.ref_line_y を変更しない)
        - 各 item.scale_pct は変更しない
        - 各 item.y_offset のみ更新 (画像ごとに永続化)
        - 現在表示中の画像は再描画される
        - サムネ選択 (current_idx) は維持される
        """
        if not self.item_list:
            return
        applied = 0
        applied_idxs = []
        for i, it in enumerate(self.item_list):
            if not it.loaded:
                it.ensure_loaded()
            if not it.loaded or it.rgba is None:
                continue
            try:
                # alpha 非透明領域の bottom = キャラの実足元 (1024座標)
                foot_y_1024 = compute_foot_y_alpha(
                    it.rgba, MODE_MANUAL, it.y_offset, it.scale_pct)
                # 足元を ref_line_y に合わせる y_offset を計算
                new_y = self.ref_line_y - foot_y_1024 + it.y_offset
                new_y = max(SLIDER_MIN, min(new_y, SLIDER_MAX))
                it.y_offset = new_y
                it.is_aligned = True
                applied += 1
                applied_idxs.append(i)
            except Exception as e:
                print(f"(fit-to-line all error) {e}")
        # 現在 item の Y Offset スライダー UI 同期
        cur = self.current_item
        if cur is not None:
            try:
                self.var_y.set(cur.y_offset)
            except Exception:
                pass
        # サムネ状態バッジ更新
        try:
            for i in applied_idxs:
                if 0 <= i < len(self._thumb_cards):
                    self._thumb_cards[i].set_status(is_aligned=True)
        except Exception:
            pass
        # 全サムネを最新の処理後表示で同期 (y_offset 変更を反映)
        self._refresh_all_thumb_views()
        # 現在表示中の画像を再描画 (BASE LINE と current_idx は不変)
        # _draw_preview_demo は check_mode なら自動的に CHECK 側を再描画する
        self._draw_preview_demo()
        print(f"(FIT TO LINE / all) applied={applied}/{len(self.item_list)}")

        # ── UI フィードバック (処理ロジックには影響しない) ──
        try:
            self._fire_align_feedback(label="ALIGN COMPLETE")
        except Exception as e:
            print(f"(feedback error) {e}")

    # ── 背景透過 (Remove BG / Restore BG) ─────────────────────
    def _remove_bg_one(self, item):
        """1 item の背景を透過。可能なら rembg を使い、なければ簡易フォールバック。
        既に透過済み(item.bg_removed=True)ならスキップ(キャッシュ)。
        透過前の rgba を item.original_rgba に保存して Restore 可能にする。"""
        if item is None:
            return False
        if not item.loaded or item.rgba is None:
            try:
                item.ensure_loaded()
            except Exception:
                pass
        if not item.loaded or item.rgba is None:
            return False
        if getattr(item, "bg_removed", False):
            return False  # 既に透過済み
        try:
            # 元画像をバックアップ (Restore 用)
            if item.original_rgba is None:
                item.original_rgba = item.rgba.copy()
            new_rgba = self._do_remove_bg(item.rgba)
            if new_rgba is not None:
                item.rgba = new_rgba
                item.bg_removed = True
                return True
        except Exception as e:
            print(f"(remove bg error) {e}")
        return False

    def _restore_bg_one(self, item):
        """1 item の rgba を元画像に戻す。元画像が無ければ何もしない。"""
        if item is None:
            return False
        if not getattr(item, "bg_removed", False):
            return False
        if item.original_rgba is None:
            return False
        try:
            item.rgba = item.original_rgba.copy()
            item.bg_removed = False
            return True
        except Exception as e:
            print(f"(restore bg error) {e}")
        return False

    def _get_rembg_session(self):
        """rembg のセッションを使い回す (毎回モデルロードを避けて高速化)。
        rembg が無ければ None を返す → フォールバック処理が動く。
        精度最優先のため、デフォルトの u2net (高精度) を使用する。"""
        sess = getattr(self, "_rembg_session", None)
        if sess is not None:
            return sess
        if getattr(self, "_rembg_unavailable", False):
            return None
        try:
            from rembg import new_session  # type: ignore
            _spriteanchor_log(
                f"(rembg) creating u2net session; U2NET_HOME={os.environ.get('U2NET_HOME', '')!r} "
                f"NUMBA_CACHE_DIR={os.environ.get('NUMBA_CACHE_DIR', '')!r}"
            )
            self._rembg_session = new_session("u2net")
            _spriteanchor_log("(rembg) u2net session ready")
            return self._rembg_session
        except Exception as e:
            _spriteanchor_log(f"(rembg unavailable, using fallback) {e}")
            self._rembg_unavailable = True
            try:
                if not getattr(self, "_rembg_warning_shown", False):
                    self._rembg_warning_shown = True
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "SpriteAnchor rembg fallback",
                        "High-quality rembg background removal is unavailable.\n"
                        "SpriteAnchor will use simple fallback removal.\n\n"
                        "Details were written to ~/SpriteAnchor_rembg.log",
                        parent=self.root,
                    )
            except Exception:
                pass
            return None

    def _do_remove_bg(self, img_rgba):
        """背景透過の実装。
        - rembg があればセッションを使い回し (毎回モデルロードしない)
        - 元画像サイズのまま処理 (品質最優先・縮小しない)
        - rembg が使えなければ簡易処理 (4隅平均色) でフォールバック
        """
        # ── rembg を試す (セッション再利用、元サイズで処理) ──
        try:
            from rembg import remove as _rembg_remove  # type: ignore
            session = self._get_rembg_session()
            if session is not None:
                # 縮小処理は廃止: 精度を最優先するため元画像サイズで rembg 実行
                return _rembg_remove(img_rgba.convert("RGBA"),
                                     session=session)
        except Exception as e:
            _spriteanchor_log(f"(rembg session error, fallback) {e}")
            self._rembg_unavailable = True
        # ── フォールバック: 4隅平均色を背景とみなして透過 ──
        try:
            im = img_rgba.convert("RGBA").copy()
            w, h = im.size
            px = im.load()
            corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
            br = sum(c[0] for c in corners) // 4
            bg = sum(c[1] for c in corners) // 4
            bb = sum(c[2] for c in corners) // 4
            tol = 28
            for y in range(h):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if (abs(r - br) <= tol and abs(g - bg) <= tol
                            and abs(b - bb) <= tol):
                        px[x, y] = (r, g, b, 0)
            return im
        except Exception as e:
            print(f"(fallback bg removal error) {e}")
            return None

    # ── Remove BG セクション 進行表示ヘルパー ──
    def _bg_button_widgets(self):
        """Remove BG セクションのボタン参照を集めて返す (存在チェック付き)。"""
        return [
            getattr(self, name, None)
            for name in (
                "btn_rmbg_this", "btn_rmbg_all",
                "btn_rmbg_selected", "btn_restorebg_selected",
                "btn_restorebg_this", "btn_restorebg_all",
                "btn_manual_erase",
            )
        ]

    def _set_bg_buttons_busy(self, active_btn, busy_text="Removing..."):
        """Remove BG 系ボタンを一括 disabled に。アクティブな1つだけ
        busy_text を表示、他はそのままテキストで disabled。"""
        for b in self._bg_button_widgets():
            if b is None:
                continue
            try:
                if b is active_btn:
                    b.set_busy(busy_text)
                else:
                    b.set_disabled(True)
            except Exception:
                pass

    def _restore_bg_buttons(self, active_btn, *, done_text="✓ Done!", delay_ms=800):
        """active_btn に Done! 表示 → delay_ms 後に元のテキストに戻し、
        他ボタンの disabled も解除する。"""
        try:
            if active_btn is not None:
                active_btn.set_done(done_text)
        except Exception:
            pass

        def _restore_all():
            for b in self._bg_button_widgets():
                if b is None:
                    continue
                try:
                    b.restore_text()
                except Exception:
                    pass

        try:
            self.root.after(delay_ms, _restore_all)
        except Exception:
            _restore_all()

    def _remove_bg_current(self):
        """現在選択中の item の背景を透過し、即プレビュー/サムネ/CHECK 反映。"""
        item = self.current_item
        if item is None:
            return
        # 進行表示開始
        self._set_bg_buttons_busy(self.btn_rmbg_this, "Removing...")
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        def _do():
            changed = False
            try:
                changed = self._remove_bg_one(item)
            except Exception as e:
                print(f"(Remove BG This error) {e}")
            if changed:
                self._refresh_thumb_view()
                self._draw_preview_demo()
                print("(Remove BG This) done")
            else:
                print("(Remove BG This) no change (already removed or failed)")
            self._restore_bg_buttons(self.btn_rmbg_this)

        try:
            self.root.after(50, _do)
        except Exception:
            _do()

    def _remove_bg_all(self):
        """全 item の背景を透過 (キャッシュ済みはスキップ)。
        並列処理 (ThreadPoolExecutor, max_workers=4) で高速化。
        重い rembg 処理はワーカースレッドで実行し、UI スレッドはブロックしない。
        進捗中は Remove BG セクションのボタン群を一時無効化、完了後 self.root.after() で
        サムネ更新 / プレビュー再描画 を UI スレッドで行う。"""
        if not self.item_list:
            return
        if getattr(self, "_bg_running", False):
            print("(Remove BG All) already running")
            return

        # 透過対象 (まだ透過されていない & 読み込み済みのもの)
        targets = []
        for it in self.item_list:
            if not it.loaded or it.rgba is None:
                try:
                    it.ensure_loaded()
                except Exception:
                    pass
            if it.loaded and it.rgba is not None and not getattr(it, "bg_removed", False):
                targets.append(it)
        if not targets:
            print("(Remove BG All) nothing to do")
            return

        # rembg セッションは UI スレッドで先に1回だけ作成 (ワーカーから共有)
        try:
            self._get_rembg_session()
        except Exception:
            pass

        self._bg_running = True
        # 進行中は誤操作を防ぐためカーソルを変更 + ボタン群 busy
        try:
            self.root.config(cursor="watch")
        except Exception:
            pass
        self._set_bg_buttons_busy(self.btn_rmbg_all, "Removing...")

        def _work(item):
            """ワーカースレッドで実行する純粋処理 (UI 操作禁止)。"""
            try:
                if item.rgba is None:
                    return (item, None)
                # original のバックアップは UI スレッド側で行う (item を共有するため)
                new_rgba = self._do_remove_bg(item.rgba)
                return (item, new_rgba)
            except Exception as e:
                print(f"(parallel bg error) {e}")
                return (item, None)

        from concurrent.futures import ThreadPoolExecutor
        # NOTE: GIL があっても rembg / PIL は内部で I/O・C 拡張を多用するため
        #       スレッド並列でもそれなりに高速化する。CPUバウンド純Pythonなら
        #       ProcessPoolExecutor の方が速いが、PIL Image をプロセス間で
        #       やり取りするコストが大きいので Thread を採用。
        executor = ThreadPoolExecutor(max_workers=4)
        futures = [executor.submit(_work, it) for it in targets]
        total = len(targets)
        applied = [0]

        def _poll():
            """UI スレッドで定期的に未完了 future を回収 → 反映。"""
            try:
                pending = []
                for fut in futures:
                    if not fut.done():
                        pending.append(fut)
                        continue
                    try:
                        item, new_rgba = fut.result()
                    except Exception as e:
                        print(f"(future error) {e}")
                        continue
                    if new_rgba is not None and not getattr(item, "bg_removed", False):
                        if item.original_rgba is None:
                            try:
                                item.original_rgba = item.rgba.copy()
                            except Exception:
                                pass
                        item.rgba = new_rgba
                        item.bg_removed = True
                        applied[0] += 1
                # 残りがあれば次のループへ
                if pending:
                    futures[:] = pending
                    self.root.after(60, _poll)
                    return
                # ── 完了処理 ──
                executor.shutdown(wait=False)
                self._bg_running = False
                try:
                    self.root.config(cursor="")
                except Exception:
                    pass
                self._refresh_all_thumb_views()
                self._draw_preview_demo()
                print(f"(Remove BG All) applied={applied[0]}/{total} (parallel)")
                # ボタン群 Done! 表示 → 800ms 後に元に戻す
                self._restore_bg_buttons(self.btn_rmbg_all)
            except Exception as e:
                print(f"(poll error) {e}")
                self._bg_running = False
                try:
                    self.root.config(cursor="")
                except Exception:
                    pass
                # エラー時もボタンを必ず元に戻す
                self._restore_bg_buttons(self.btn_rmbg_all, done_text="Error", delay_ms=600)

        # 100ms 後にポーリング開始 (submit直後はまだ何も終わってないので少し待つ)
        self.root.after(100, _poll)

    def _restore_bg_current(self):
        """現在選択中の item を背景透過前の元画像に戻す。"""
        item = self.current_item
        if item is None:
            return
        changed = self._restore_bg_one(item)
        if changed:
            self._refresh_thumb_view()
            self._draw_preview_demo()
            print("(Restore BG This) done")
        else:
            print("(Restore BG This) no change (not removed yet)")

    def _restore_bg_all(self):
        """全 item を背景透過前の元画像に戻す。"""
        if not self.item_list:
            return
        applied = 0
        for it in self.item_list:
            if self._restore_bg_one(it):
                applied += 1
        if applied > 0:
            self._refresh_all_thumb_views()
            self._draw_preview_demo()
        print(f"(Restore BG All) applied={applied}/{len(self.item_list)}")

    # ── 複数選択 → Restore / Remove ─────────────────────
    def _restore_bg_selected(self):
        """selected_idxs に含まれる item のみ元画像に戻す。
        他の item には影響しない。current_idx も変更しない。"""
        if not self.item_list:
            return
        idxs = sorted(i for i in self.selected_idxs
                      if 0 <= i < len(self.item_list))
        if not idxs:
            print("(Restore BG Selected) no items selected")
            return
        applied = 0
        for i in idxs:
            if self._restore_bg_one(self.item_list[i]):
                applied += 1
        if applied > 0:
            # 該当サムネのみ更新 (他は触らない)
            for i in idxs:
                try:
                    self._refresh_thumb_view(i)
                except Exception:
                    pass
            self._draw_preview_demo()
        print(f"(Restore BG Selected) applied={applied}/{len(idxs)}")

    def _remove_bg_selected(self):
        """selected_idxs に含まれる item のみ並列で透過処理。
        他の item には影響しない。"""
        if not self.item_list:
            return
        idxs = sorted(i for i in self.selected_idxs
                      if 0 <= i < len(self.item_list))
        if not idxs:
            print("(Remove BG Selected) no items selected")
            return
        if getattr(self, "_bg_running", False):
            print("(Remove BG Selected) already running")
            return

        # 透過対象 (選択中 & 未透過 & 読み込み済み)
        targets = []
        for i in idxs:
            it = self.item_list[i]
            if not it.loaded or it.rgba is None:
                try:
                    it.ensure_loaded()
                except Exception:
                    pass
            if (it.loaded and it.rgba is not None
                    and not getattr(it, "bg_removed", False)):
                targets.append((i, it))
        if not targets:
            print("(Remove BG Selected) nothing to do")
            return

        try:
            self._get_rembg_session()
        except Exception:
            pass
        self._bg_running = True
        try:
            self.root.config(cursor="watch")
        except Exception:
            pass
        # ボタン群 busy 表示
        self._set_bg_buttons_busy(self.btn_rmbg_selected, "Removing...")

        def _work(item):
            try:
                if item.rgba is None:
                    return (item, None)
                return (item, self._do_remove_bg(item.rgba))
            except Exception as e:
                print(f"(parallel bg error) {e}")
                return (item, None)

        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=4)
        # i (index) と future の対応を保持しておくと、完了時に該当サムネだけ更新できる
        idx_by_item = {id(it): i for i, it in targets}
        futures = [executor.submit(_work, it) for _i, it in targets]
        total = len(targets)
        applied_count = [0]
        affected_idxs = []

        def _poll():
            try:
                pending = []
                for fut in futures:
                    if not fut.done():
                        pending.append(fut)
                        continue
                    try:
                        item, new_rgba = fut.result()
                    except Exception as e:
                        print(f"(future error) {e}")
                        continue
                    if (new_rgba is not None
                            and not getattr(item, "bg_removed", False)):
                        if item.original_rgba is None:
                            try:
                                item.original_rgba = item.rgba.copy()
                            except Exception:
                                pass
                        item.rgba = new_rgba
                        item.bg_removed = True
                        applied_count[0] += 1
                        idx_for_this = idx_by_item.get(id(item))
                        if idx_for_this is not None:
                            affected_idxs.append(idx_for_this)
                if pending:
                    futures[:] = pending
                    self.root.after(60, _poll)
                    return
                executor.shutdown(wait=False)
                self._bg_running = False
                try:
                    self.root.config(cursor="")
                except Exception:
                    pass
                # 影響を受けたサムネだけ更新
                for i in affected_idxs:
                    try:
                        self._refresh_thumb_view(i)
                    except Exception:
                        pass
                self._draw_preview_demo()
                print(f"(Remove BG Selected) applied={applied_count[0]}/{total}")
                # ボタン群 Done! 表示 → 800ms 後に元に戻す
                self._restore_bg_buttons(self.btn_rmbg_selected)
            except Exception as e:
                print(f"(poll error) {e}")
                self._bg_running = False
                try:
                    self.root.config(cursor="")
                except Exception:
                    pass
                self._restore_bg_buttons(self.btn_rmbg_selected, done_text="Error", delay_ms=600)

        self.root.after(100, _poll)

    # ── 手動透過編集 ─────────────────────
    def _open_manual_erase(self):
        """現在選択中の item を Manual Erase インラインモードで開く。
        別ウィンドウは開かず、メインプレビュー上で直接編集する。"""
        item = self.current_item
        if item is None or not item.loaded or item.rgba is None:
            print("(Manual Erase) no item selected")
            return
        if getattr(self, "_inline_erase", None) is not None:
            # 既にモード中なら何もしない
            return
        self._enter_inline_manual_erase(item)

    # ── Manual Erase インラインモード ─────────────────────
    def _enter_inline_manual_erase(self, item):
        """インライン編集モードに入る。
        - 編集対象 rgba をコピーして編集中状態に保存
        - 右ペインにツールパネルを重ね表示
        - preview_canvas に直接描画 (BASE LINE / Grid / Ghost は非表示)
        - マウスイベントを編集用にバインドし直す
        """
        try:
            edit_img = item.rgba.copy().convert("RGBA")
        except Exception as e:
            print(f"(manual erase enter error) {e}")
            return
        # 編集中の状態を保持する辞書 (ManualEraseEditor の self._xxx 相当を平坦化)
        self._inline_erase = {
            "item": item,
            "img": edit_img,
            "undo": [],
            "mode": "erase",          # "erase" | "flood"
            "brush": 24,
            "user_zoom": None,        # None=Fit
            "is_drawing": False,
            "last_xy": None,
            "disp_scale": 1.0,
            "disp_ox": 0,
            "disp_oy": 0,
            "disp_w": 0,
            "disp_h": 0,
            "photo": None,
            # ── パン軽量化用キャッシュ ──
            # bg_photo: チェッカー柄 PhotoImage (ズーム変更時のみ再生成)
            # bg_zoom_key: そのキャッシュが対応する (dw, dh)
            # bg_item_id / img_item_id: canvas item ID (パン時 coords で動かす対象)
            "bg_photo": None,
            "bg_zoom_key": None,
            "bg_item_id": None,
            "img_item_id": None,
            # 画像パン (ズーム時に表示位置をずらすためのオフセット, canvas px)
            "pan_x": 0,
            "pan_y": 0,
            "_pan_drag_start": None,
            # canvas の元イベントバインドを保存して、終了時に戻す
            "saved_bindings": {},
            "panel": None,
        }
        # 既存の preview_canvas のバインドを退避 + 編集用に差し替え
        cv = self.preview_canvas
        try:
            saved = {
                "<Configure>":         cv.bind("<Configure>"),
                "<ButtonPress-1>":     cv.bind("<ButtonPress-1>"),
                "<B1-Motion>":         cv.bind("<B1-Motion>"),
                "<ButtonRelease-1>":   cv.bind("<ButtonRelease-1>"),
                "<Motion>":            cv.bind("<Motion>"),
                "<Button-3>":          cv.bind("<Button-3>"),
                "<Button-2>":          cv.bind("<Button-2>"),
                "<Control-Button-1>":  cv.bind("<Control-Button-1>"),
            }
            self._inline_erase["saved_bindings"] = saved
        except Exception:
            pass

        # 編集用バインド (canvas は1つしかないので bind で上書き=既存ハンドラ無効)
        cv.bind("<Configure>",       lambda _e: self._erase_inline_render())
        cv.bind("<ButtonPress-1>",   self._erase_inline_press)
        cv.bind("<B1-Motion>",       self._erase_inline_drag)
        cv.bind("<ButtonRelease-1>", self._erase_inline_release)
        cv.bind("<Motion>",          self._erase_inline_hover)
        # 中ボタン / 右ボタン / Space+左 ドラッグで画像をパン移動
        cv.bind("<ButtonPress-2>",   self._erase_inline_pan_start)
        cv.bind("<B2-Motion>",       self._erase_inline_pan_drag)
        cv.bind("<ButtonRelease-2>", self._erase_inline_pan_end)
        cv.bind("<ButtonPress-3>",   self._erase_inline_pan_start)
        cv.bind("<B3-Motion>",       self._erase_inline_pan_drag)
        cv.bind("<ButtonRelease-3>", self._erase_inline_pan_end)
        cv.bind("<Control-Button-1>", lambda _e: "break")

        # マウスホイール: Ctrl/Cmd でズーム / Shift で左右パン / 通常で上下パン
        def _on_wheel(e):
            d = getattr(e, "delta", 0)
            if d == 0:
                return
            state = int(getattr(e, "state", 0) or 0)
            ctrl_or_cmd = bool(state & 0x0004) or bool(state & 0x0008)
            shift = bool(state & 0x0001)
            if ctrl_or_cmd:
                # Ctrl/Cmd + ホイール: ズーム
                self._erase_inline_zoom_step(1 if d > 0 else -1)
                return
            # ホイール量 → ピクセル換算 (1ノッチ = 60px 程度のスクロール)
            # Tk の delta は Win=±120/notch、macOS は小さい値が連続。共通化:
            step = 60 if abs(d) >= 60 else max(20, abs(d))
            sign = 1 if d > 0 else -1
            st = self._inline_erase
            if st is None:
                return
            if shift:
                # Shift + ホイール: 横方向パン (右回しで右へ移動 = pan_x 増)
                st["pan_x"] = int(st.get("pan_x", 0)) + sign * step
            else:
                # 通常ホイール: 縦方向パン (上回しで下へ移動 = pan_y 増)
                st["pan_y"] = int(st.get("pan_y", 0)) + sign * step
            self._erase_inline_render()
        cv.bind("<Enter>", lambda _e: cv.bind_all("<MouseWheel>", _on_wheel))
        cv.bind("<Leave>", lambda _e: cv.unbind_all("<MouseWheel>"))

        # ── Space + 左ドラッグでもパン (Photoshop 等の慣習) ──
        # Space キー押下中フラグを用意し、左ボタン Press/Drag をパン処理に
        # 振り分ける。Erase 中の左ドラッグと衝突しないようガードする。
        st_init = self._inline_erase
        st_init["_space_held"] = False
        def _on_space_down(_e=None):
            s = self._inline_erase
            if s is None:
                return
            if not s.get("_space_held", False):
                s["_space_held"] = True
                try:
                    self.preview_canvas.config(cursor="fleur")
                except Exception:
                    pass
            return "break"
        def _on_space_up(_e=None):
            s = self._inline_erase
            if s is None:
                return
            s["_space_held"] = False
            try:
                # Erase/Flood モードに応じてカーソルを戻す
                self.preview_canvas.config(
                    cursor="tcross" if s["mode"] == "erase" else "crosshair")
            except Exception:
                pass
            return "break"
        try:
            self.root.bind_all("<KeyPress-space>", _on_space_down)
            self.root.bind_all("<KeyRelease-space>", _on_space_up)
        except Exception:
            pass

        try:
            cv.config(cursor="tcross")
        except Exception:
            pass

        # 右ペインに編集ツールパネルを構築
        self._build_inline_erase_panel()

        # 既存の右ペインボタン群を一時的に無効化 (誤操作防止)
        self._disable_main_controls(True)

        # ── キーボードショートカット (Manual Erase 中のみ有効) ──
        #   Ctrl+Z / Cmd+Z : Undo
        #   Enter / Return : Apply & Return
        #   Escape         : Cancel
        try:
            root = self.root
            def _ks_undo(_e=None):
                try:
                    self._erase_inline_undo()
                except Exception:
                    pass
                return "break"
            def _ks_apply(_e=None):
                try:
                    self._exit_inline_manual_erase(applied=True)
                except Exception:
                    pass
                return "break"
            def _ks_cancel(_e=None):
                try:
                    self._exit_inline_manual_erase(applied=False)
                except Exception:
                    pass
                return "break"
            # bind_all で root 全体に効かせる (preview_canvas にフォーカスが無くても動く)
            root.bind_all("<Control-z>", _ks_undo)
            root.bind_all("<Control-Z>", _ks_undo)
            root.bind_all("<Command-z>", _ks_undo)
            root.bind_all("<Command-Z>", _ks_undo)
            root.bind_all("<Return>", _ks_apply)
            root.bind_all("<KP_Enter>", _ks_apply)
            root.bind_all("<Escape>", _ks_cancel)
            # 解除時に必要なバインド名を保存
            self._inline_erase["_kbd_bound"] = (
                "<Control-z>", "<Control-Z>",
                "<Command-z>", "<Command-Z>",
                "<Return>", "<KP_Enter>", "<Escape>"
            )
        except Exception as e:
            print(f"(manual erase shortcut bind error) {e}")

        # 初回描画
        self._erase_inline_render()
        print("(Manual Erase) inline mode ON")

    def _exit_inline_manual_erase(self, *, applied=False):
        """インライン編集モードを抜ける。"""
        st = getattr(self, "_inline_erase", None)
        if st is None:
            return
        item = st["item"]
        new_img = st["img"]

        # キーボードショートカットを解除 (Ctrl+Z / Enter / Esc / Space)
        try:
            for ev in st.get("_kbd_bound", ()):
                try:
                    self.root.unbind_all(ev)
                except Exception:
                    pass
        except Exception:
            pass
        # Space pan 用バインドも解除
        try:
            self.root.unbind_all("<KeyPress-space>")
            self.root.unbind_all("<KeyRelease-space>")
        except Exception:
            pass

        # canvas のバインドを元に戻す
        cv = self.preview_canvas
        try:
            for ev in ("<Configure>", "<ButtonPress-1>", "<B1-Motion>",
                       "<ButtonRelease-1>", "<Motion>",
                       "<ButtonPress-2>", "<B2-Motion>", "<ButtonRelease-2>",
                       "<ButtonPress-3>", "<B3-Motion>", "<ButtonRelease-3>",
                       "<Button-3>", "<Button-2>", "<Control-Button-1>",
                       "<Enter>", "<Leave>"):
                cv.unbind(ev)
        except Exception:
            pass
        # 通常時の bind を再構築
        try:
            self._install_preview_default_bindings()
        except Exception:
            pass
        # 右クリックメニュー類を再適用
        try:
            self._install_context_menus()
        except Exception:
            pass
        try:
            cv.unbind_all("<MouseWheel>")
        except Exception:
            pass
        try:
            cv.config(cursor="")
        except Exception:
            pass

        # ツールパネルを片付ける (新レイアウトの side / hint と互換用 panel)
        for key in ("side_panel", "hint_panel", "panel"):
            try:
                p = st.get(key)
                if p is not None:
                    p.destroy()
            except Exception:
                pass

        # 通常コントロール復帰
        self._disable_main_controls(False)

        # 状態破棄 → Apply 反映
        self._inline_erase = None
        if applied:
            try:
                if item.original_rgba is None:
                    item.original_rgba = item.rgba.copy()
                item.rgba = new_img
                item.bg_removed = True
            except Exception as e:
                print(f"(manual erase apply error) {e}")

        # サムネ + プレビュー再描画
        try:
            self._refresh_thumb_view()
        except Exception:
            pass
        try:
            self._draw_preview_demo()
        except Exception:
            pass
        print("(Manual Erase) inline mode OFF" + (" (applied)" if applied else " (cancelled)"))

    def _disable_main_controls(self, disable: bool):
        """Manual Erase 中: 右ペイン(全操作)と左ペインの設定群を完全に隠す。
        通常モード復帰時: 元通り表示する。
        - これにより FIT TO LINE / ALIGN / CHECK / sliders / Ghost / Remove BG /
          Output Settings / Grid Settings / START すべてが Manual Erase 中は
          画面から消える。Manual Erase 専用パネルだけが見える状態になる。
        """
        # 右ペイン全体
        ctrl = getattr(self, "_ctrl_panel", None)
        if ctrl is not None:
            try:
                if disable:
                    ctrl.grid_remove()
                else:
                    ctrl.grid()
            except Exception:
                pass
        # 左ペイン全体 (Output Settings / Grid Settings 含む)
        wf = getattr(self, "_wf_outer", None)
        if wf is not None:
            try:
                if disable:
                    wf.grid_remove()
                else:
                    wf.grid()
            except Exception:
                pass
        # サムネ一覧も触らせない (誤って別 item に切り替えると編集対象が消える)
        thumbs_outer = getattr(self, "_thumb_outer", None)
        if thumbs_outer is not None:
            try:
                if disable:
                    thumbs_outer.grid_remove()
                else:
                    thumbs_outer.grid()
            except Exception:
                pass

    def _build_inline_erase_panel(self):
        """Manual Erase 用の固定レイアウトを構築。
        - 左サイドバー (column=0): ツールパネル (Erase / Flood / Brush / Zoom / Undo / Cancel / Apply & Return)
        - 中央 (column=1): 既存の preview_canvas を編集キャンバスとして流用
        - 右サイドバー (column=2): 操作説明
        通常時の左ペイン/右ペイン/サムネは _disable_main_controls(True) で grid_remove 済み。
        """
        st = self._inline_erase
        if st is None:
            return

        main = self._main_grid_frame  # main = 左/中央/右の親 grid

        # ── 右サイドバー: Manual Erase ツールパネル (column=2) ──
        # 通常画面と同じ「操作系は右」というレイアウト方針に統一
        side = tk.Frame(main, bg=BG_PANEL,
                        highlightthickness=1,
                        highlightbackground=ACCENT_DIM,
                        padx=14, pady=14, width=260)
        side.grid(row=0, column=2, sticky="nse")
        side.grid_propagate(False)
        st["side_panel"] = side

        # タイトル
        tk.Label(side, text="✎ Manual Erase",
                 bg=BG_PANEL, fg=ACCENT,
                 font=("Helvetica", 12, "bold")
                 ).pack(anchor="w", pady=(0, 12))

        # モード切替
        st["mode_widgets"] = {}
        for m, label in [("erase", "✎ Erase"),
                         ("flood", "💧 Flood Erase")]:
            b = tk.Label(side, text=label,
                         bg=BG_CARD, fg=TEXT_HI,
                         font=("Helvetica", 10, "bold"),
                         padx=10, pady=6, cursor="hand2",
                         highlightthickness=1, highlightbackground=BORDER)
            b.pack(anchor="w", fill="x", pady=(0, 6))
            b.bind("<ButtonRelease-1>",
                   lambda _e, mm=m: self._erase_inline_set_mode(mm))
            st["mode_widgets"][m] = b

        # モード説明
        st["help_lbl"] = tk.Label(side, text="",
                                  bg=BG_PANEL, fg=TEXT_LO,
                                  font=("Helvetica", 9),
                                  wraplength=210, justify="left", anchor="w")
        st["help_lbl"].pack(anchor="w", fill="x", pady=(0, 12))

        # Brush Size
        tk.Label(side, text="Brush Size",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 9, "bold")).pack(anchor="w")
        brush_row = tk.Frame(side, bg=BG_PANEL)
        brush_row.pack(anchor="w", fill="x", pady=(2, 12))
        st["var_brush"] = tk.IntVar(value=st["brush"])
        ttk.Scale(brush_row, from_=5, to=80,
                  orient="horizontal",
                  variable=st["var_brush"],
                  command=lambda _v: self._erase_inline_brush_changed(),
                  length=150,
                  style="Neon.Horizontal.TScale"
                  ).pack(side="left")
        st["brush_lbl"] = tk.Label(brush_row, text=f"{st['brush']}px",
                                   bg=BG_PANEL, fg=TEXT_HI,
                                   font=("Menlo", 10, "bold"),
                                   width=5, anchor="w")
        st["brush_lbl"].pack(side="left", padx=(8, 0))

        # ── Zoom (スライダー方式: 50%〜400%, 1%刻み) ──
        zoom_hdr = tk.Frame(side, bg=BG_PANEL)
        zoom_hdr.pack(anchor="w", fill="x")
        zoom_hdr.columnconfigure(0, weight=1)
        zoom_hdr.columnconfigure(1, weight=0)
        tk.Label(zoom_hdr, text="Zoom",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 9, "bold")
                 ).grid(row=0, column=0, sticky="w")
        st["zoom_lbl"] = tk.Label(zoom_hdr, text="100%",
                                  bg=BG_PANEL, fg=ACCENT,
                                  font=("Menlo", 10, "bold"),
                                  width=6, anchor="e")
        st["zoom_lbl"].grid(row=0, column=1, sticky="e")

        # スライダー本体 (50..400, 1%刻み)
        st["var_zoom"] = tk.DoubleVar(value=100.0)
        st["_zoom_slider_sync"] = False  # スライダー操作とプリセット適用の循環防止

        def _on_zoom_slider(_v=None):
            if st.get("_zoom_slider_sync", False):
                return
            try:
                v = float(st["var_zoom"].get())
            except Exception:
                return
            self._erase_inline_set_zoom(v / 100.0, _from_slider=True)

        ttk.Scale(side, from_=50, to=400,
                  orient="horizontal",
                  variable=st["var_zoom"],
                  command=_on_zoom_slider,
                  style="Neon.Horizontal.TScale"
                  ).pack(anchor="w", fill="x", pady=(2, 6))

        # 補助ボタン: −/+/Fit (プリセット50/100/200/400は廃止)
        zoom_btns = tk.Frame(side, bg=BG_PANEL)
        zoom_btns.pack(anchor="w", fill="x", pady=(0, 12))

        def _mk_btn(parent_w, text, cmd, w=4):
            b = tk.Label(parent_w, text=text,
                         bg=BG_CARD, fg=TEXT_HI,
                         font=("Helvetica", 10, "bold"),
                         padx=8, pady=3, cursor="hand2",
                         highlightthickness=1, highlightbackground=BORDER,
                         width=w)
            b.bind("<ButtonRelease-1>", lambda _e: cmd())
            return b

        _mk_btn(zoom_btns, "−",
                lambda: self._erase_inline_zoom_step(-1), w=3
                ).pack(side="left", padx=(0, 4))
        _mk_btn(zoom_btns, "+",
                lambda: self._erase_inline_zoom_step(+1), w=3
                ).pack(side="left", padx=(0, 8))
        _mk_btn(zoom_btns, "Fit",
                lambda: self._erase_inline_set_zoom(None), w=4
                ).pack(side="left")

        # プリセットは廃止 (互換用ダミー dict)
        st["zoom_presets"] = {}

        # Undo
        undo_btn = tk.Label(side, text="↶ Undo",
                            bg=BG_CARD, fg=TEXT_HI,
                            font=("Helvetica", 10, "bold"),
                            padx=10, pady=6, cursor="hand2",
                            highlightthickness=1, highlightbackground=BORDER)
        undo_btn.pack(anchor="w", fill="x", pady=(0, 14))
        undo_btn.bind("<ButtonRelease-1>", lambda _e: self._erase_inline_undo())

        # スペーサ + 下部固定の Cancel / Apply
        # (右パネル下部に固定 = pack(fill="both", expand=True) の空 frame で押し下げる)
        tk.Frame(side, bg=BG_PANEL).pack(fill="both", expand=True)

        # Cancel: 控えめに (テキストのみ・薄色)
        cancel_btn = tk.Label(side, text="Cancel",
                              bg=BG_PANEL, fg=TEXT_LO,
                              font=("Helvetica", 10),
                              padx=12, pady=6, cursor="hand2",
                              highlightthickness=1, highlightbackground=BORDER_SOFT)
        cancel_btn.pack(anchor="w", fill="x", pady=(0, 10))
        cancel_btn.bind("<ButtonRelease-1>",
                        lambda _e: self._exit_inline_manual_erase(applied=False))

        # Apply & Return: 一番目立たせる (大きめ・グロー枠)
        apply_btn = tk.Label(side, text="✔  Apply & Return",
                             bg=ACCENT, fg="#04241a",
                             font=("Helvetica", 12, "bold"),
                             padx=14, pady=14, cursor="hand2",
                             highlightthickness=2, highlightbackground=ACCENT_GLOW)
        apply_btn.pack(anchor="w", fill="x")
        apply_btn.bind("<ButtonRelease-1>",
                       lambda _e: self._exit_inline_manual_erase(applied=True))

        # ── 左サイドバー: 操作説明 (column=0) ──
        hint = tk.Frame(main, bg=BG_PANEL,
                        highlightthickness=1,
                        highlightbackground=BORDER_SOFT,
                        padx=18, pady=18, width=240)
        hint.grid(row=0, column=0, sticky="nsw")
        hint.grid_propagate(False)
        st["hint_panel"] = hint

        tk.Label(hint, text="How to use",
                 bg=BG_PANEL, fg=ACCENT,
                 font=("Helvetica", 11, "bold")
                 ).pack(anchor="w", pady=(0, 12))

        hints = [
            ("Drag",
             "Drag on the canvas with Erase to make pixels transparent."),
            ("Flood Erase",
             "Click with Flood Erase to remove a connected similar-color region."),
            ("Brush Size",
             "Adjust the brush from 5–80 px for fine or broad work."),
            ("Zoom",
             "Use Zoom +/− or presets to inspect fine details."),
            ("Pan",
             "Middle-drag or right-drag the canvas to pan when zoomed in."),
            ("Undo",
             "Step back through your most recent edits."),
            ("Apply & Return",
             "Save the edited image and return to the main view."),
            ("Cancel",
             "Discard all edits and return without changes."),
        ]
        for title, desc in hints:
            tk.Label(hint, text=title,
                     bg=BG_PANEL, fg=TEXT_HI,
                     font=("Helvetica", 9, "bold"),
                     anchor="w", justify="left"
                     ).pack(anchor="w", pady=(6, 0))
            tk.Label(hint, text=desc,
                     bg=BG_PANEL, fg=TEXT_LO,
                     font=("Helvetica", 9),
                     anchor="w", justify="left",
                     wraplength=210
                     ).pack(anchor="w")

        # 互換用エイリアス (旧 panel キーへのアクセスがあっても落ちないように)
        st["panel"] = side
        st["panel_parent"] = main

        self._erase_inline_set_mode("erase")
        self._erase_inline_brush_changed()
        self._erase_inline_refresh_zoom_presets()

    # ── 旧ヘッダドラッグ用ハンドラ (固定レイアウト化に伴い no-op 化) ──
    def _erase_panel_drag_start(self, _e):
        return "break"

    def _erase_panel_drag_move(self, _e):
        return "break"

    def _erase_panel_drag_end(self, _e):
        return "break"

    # ── インライン編集 描画 ─────────────────────
    def _erase_inline_render(self):
        st = self._inline_erase
        if st is None:
            return
        cv = self.preview_canvas
        cv.delete("all")
        cw = max(1, cv.winfo_width())
        ch = max(1, cv.winfo_height())
        img = st["img"]
        iw, ih = img.size
        if st["user_zoom"] is None:
            scale = min(cw / iw, ch / ih, 1.0)
            if scale <= 0:
                scale = 1.0
        else:
            scale = float(st["user_zoom"])
        scale = max(0.1, min(scale, 12.0))
        st["disp_scale"] = scale
        dw = max(1, int(iw * scale))
        dh = max(1, int(ih * scale))
        # 中央配置 + ユーザー指定のパンオフセット
        ox = (cw - dw) // 2 + int(st.get("pan_x", 0))
        oy = (ch - dh) // 2 + int(st.get("pan_y", 0))
        st["disp_ox"] = ox
        st["disp_oy"] = oy
        st["disp_w"] = dw
        st["disp_h"] = dh

        # ── チェッカー背景: 画像サイズが前回と同じならキャッシュを流用 ──
        # (透過部分が見えるよう、画像と同じ寸法のチェッカー画像を1枚作って
        #  create_image で1命令で描画する。従来の create_rectangle 多重ループ
        #  (1024x1024 表示で約7400回) を 1 命令に削減。)
        bg_zoom_key = (dw, dh)
        if (st.get("bg_photo") is None
                or st.get("bg_zoom_key") != bg_zoom_key):
            try:
                st["bg_photo"] = self._erase_inline_build_checker(dw, dh)
                st["bg_zoom_key"] = bg_zoom_key
            except Exception as e:
                print(f"(checker cache build error) {e}")
                st["bg_photo"] = None

        if st.get("bg_photo") is not None:
            try:
                bg_id = cv.create_image(ox, oy,
                                        image=st["bg_photo"], anchor="nw")
                st["bg_item_id"] = bg_id
            except Exception:
                st["bg_item_id"] = None
        else:
            # フォールバック: 旧来の create_rectangle 描画
            c1, c2 = "#26292f", "#1a1d22"
            cell = 12
            for y in range(0, dh, cell):
                for x in range(0, dw, cell):
                    col = c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2
                    x1 = ox + x
                    y1 = oy + y
                    x2 = min(x1 + cell, ox + dw)
                    y2 = min(y1 + cell, oy + dh)
                    cv.create_rectangle(x1, y1, x2, y2, fill=col, outline="")
            st["bg_item_id"] = None

        try:
            disp = img.resize((dw, dh), RESAMPLE)
            st["photo"] = ImageTk.PhotoImage(disp)
            img_id = cv.create_image(ox, oy, image=st["photo"], anchor="nw")
            st["img_item_id"] = img_id
        except Exception as e:
            print(f"(inline erase render error) {e}")
            st["img_item_id"] = None

        # ズームラベル更新
        try:
            st["zoom_lbl"].config(text=f"{int(round(scale * 100))}%")
        except Exception:
            pass
        self._erase_inline_refresh_zoom_presets()

    def _erase_inline_build_checker(self, dw: int, dh: int):
        """指定サイズのチェッカー柄 PhotoImage を生成して返す。
        編集モード中、画像表示サイズが変わったとき (= ズーム変更時) のみ呼ばれる。
        ドラッグ中・パン中には呼ばれない。"""
        from PIL import Image as _Image
        c1 = (0x26, 0x29, 0x2f)
        c2 = (0x1a, 0x1d, 0x22)
        cell = 12
        # 2x2 セル (=24x24) のタイル画像をまず作り、resize で全面に展開する
        tile = _Image.new("RGB", (cell * 2, cell * 2), c1)
        for ty in range(2):
            for tx in range(2):
                if (tx + ty) % 2 == 1:
                    for py in range(cell):
                        for px in range(cell):
                            tile.putpixel((tx * cell + px,
                                           ty * cell + py), c2)
        # 全面に並べる
        bg = _Image.new("RGB", (dw, dh), c1)
        # cell 単位で貼り付け
        for y in range(0, dh, cell * 2):
            for x in range(0, dw, cell * 2):
                bg.paste(tile, (x, y))
        return ImageTk.PhotoImage(bg)

    def _erase_inline_refresh_zoom_presets(self):
        st = self._inline_erase
        if st is None:
            return
        widgets = st.get("zoom_presets", {})
        cur_pct = int(round(st["disp_scale"] * 100))
        is_fit = (st["user_zoom"] is None)
        for pct, w in widgets.items():
            try:
                if (not is_fit) and pct == cur_pct:
                    w.config(bg=ACCENT_DIM, fg="#04241a",
                             highlightbackground=ACCENT)
                else:
                    w.config(bg=BG_CARD, fg=TEXT_MID,
                             highlightbackground=BORDER)
            except Exception:
                pass

    # ── インライン編集 入力 ─────────────────────
    def _erase_inline_canvas_to_image(self, ev_x, ev_y):
        st = self._inline_erase
        if st is None:
            return None
        ox, oy = st["disp_ox"], st["disp_oy"]
        dw, dh = st["disp_w"], st["disp_h"]
        if not (ox <= ev_x < ox + dw and oy <= ev_y < oy + dh):
            return None
        scale = st["disp_scale"]
        if scale <= 0:
            return None
        ix = int((ev_x - ox) / scale)
        iy = int((ev_y - oy) / scale)
        iw, ih = st["img"].size
        ix = max(0, min(ix, iw - 1))
        iy = max(0, min(iy, ih - 1))
        return ix, iy

    def _erase_inline_press(self, e):
        st = self._inline_erase
        if st is None:
            return
        # Space 押下中なら左ドラッグもパン扱い (Erase/Flood は実行しない)
        if st.get("_space_held", False):
            self._erase_inline_pan_start(e)
            return "break"
        pt = self._erase_inline_canvas_to_image(e.x, e.y)
        if pt is None:
            return
        if st["mode"] == "erase":
            self._erase_inline_push_undo()
            st["is_drawing"] = True
            st["last_xy"] = pt
            self._erase_inline_erase_at(*pt)
            self._erase_inline_render()
        else:  # flood
            self._erase_inline_push_undo()
            self._erase_inline_flood_at(*pt)
            self._erase_inline_render()

    def _erase_inline_drag(self, e):
        st = self._inline_erase
        if st is None:
            return
        # Space 押下中なら左ドラッグはパン
        if st.get("_space_held", False):
            self._erase_inline_pan_drag(e)
            return "break"
        if st["mode"] != "erase" or not st["is_drawing"]:
            self._erase_inline_hover(e)
            return
        pt = self._erase_inline_canvas_to_image(e.x, e.y)
        if pt is None:
            return
        if st["last_xy"] is not None:
            self._erase_inline_erase_line(st["last_xy"], pt)
        else:
            self._erase_inline_erase_at(*pt)
        st["last_xy"] = pt
        self._erase_inline_render()

    def _erase_inline_release(self, _e=None):
        st = self._inline_erase
        if st is None:
            return
        # Space + 左ドラッグでのパン終了処理
        if st.get("_space_held", False) or st.get("_pan_drag_start") is not None:
            self._erase_inline_pan_end(_e)
            return "break"
        st["is_drawing"] = False
        st["last_xy"] = None

    # ── 画像パン (中ボタン / 右ボタンドラッグ) ─────────────────────
    def _erase_inline_pan_start(self, e):
        st = self._inline_erase
        if st is None:
            return "break"
        st["_pan_drag_start"] = (e.x, e.y,
                                 int(st.get("pan_x", 0)),
                                 int(st.get("pan_y", 0)))
        try:
            self.preview_canvas.config(cursor="fleur")
        except Exception:
            pass
        return "break"

    def _erase_inline_pan_drag(self, e):
        st = self._inline_erase
        if st is None:
            return "break"
        start = st.get("_pan_drag_start")
        if start is None:
            return "break"
        sx, sy, px0, py0 = start
        new_pan_x = px0 + (e.x - sx)
        new_pan_y = py0 + (e.y - sy)
        st["pan_x"] = new_pan_x
        st["pan_y"] = new_pan_y
        # ── パン中はフル再描画せず、cv.coords() で位置だけ更新する ──
        # PIL.resize や PhotoImage 再生成・チェッカー再描画は走らない。
        # 表示サイズ (dw, dh) は不変なので、ox/oy だけ計算して動かす。
        try:
            cv = self.preview_canvas
            cw = max(1, cv.winfo_width())
            ch = max(1, cv.winfo_height())
            dw = int(st.get("disp_w", 0))
            dh = int(st.get("disp_h", 0))
            ox = (cw - dw) // 2 + new_pan_x
            oy = (ch - dh) // 2 + new_pan_y
            st["disp_ox"] = ox
            st["disp_oy"] = oy
            bg_id  = st.get("bg_item_id")
            img_id = st.get("img_item_id")
            moved = False
            if bg_id is not None:
                cv.coords(bg_id, ox, oy)
                moved = True
            if img_id is not None:
                cv.coords(img_id, ox, oy)
                moved = True
            # 万一 item ID が無効ならフォールバックでフル再描画
            if not moved:
                self._erase_inline_render()
        except Exception:
            # 例外時もフォールバックでフル再描画
            try:
                self._erase_inline_render()
            except Exception:
                pass
        return "break"

    def _erase_inline_pan_end(self, _e=None):
        st = self._inline_erase
        if st is None:
            return "break"
        st["_pan_drag_start"] = None
        try:
            self.preview_canvas.config(
                cursor="tcross" if st["mode"] == "erase" else "crosshair")
        except Exception:
            pass
        return "break"

    def _erase_inline_hover(self, e):
        st = self._inline_erase
        if st is None:
            return
        cv = self.preview_canvas
        try:
            cv.delete("brush_cursor")
        except Exception:
            pass
        if st["mode"] != "erase":
            return
        r = max(2, int(st["brush"] * st["disp_scale"] * 0.5))
        try:
            cv.create_oval(e.x - r, e.y - r, e.x + r, e.y + r,
                           outline=ACCENT, width=1, tags="brush_cursor")
        except Exception:
            pass

    # ── 編集処理 ─────────────────────
    def _erase_inline_push_undo(self):
        st = self._inline_erase
        if st is None:
            return
        try:
            st["undo"].append(st["img"].copy())
            if len(st["undo"]) > 30:
                st["undo"].pop(0)
        except Exception:
            pass

    def _erase_inline_undo(self):
        st = self._inline_erase
        if st is None or not st["undo"]:
            return
        try:
            st["img"] = st["undo"].pop()
            self._erase_inline_render()
        except Exception:
            pass

    def _erase_inline_erase_at(self, ix, iy):
        st = self._inline_erase
        if st is None:
            return
        r = max(1, st["brush"] // 2)
        from PIL import ImageDraw as _ID
        try:
            img = st["img"]
            a = img.split()[3]
            d = _ID.Draw(a)
            d.ellipse((ix - r, iy - r, ix + r, iy + r), fill=0)
            img.putalpha(a)
        except Exception as e:
            print(f"(inline erase error) {e}")

    def _erase_inline_erase_line(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        steps = max(abs(x2 - x1), abs(y2 - y1)) + 1
        if steps <= 1:
            self._erase_inline_erase_at(x2, y2)
            return
        for i in range(steps + 1):
            t = i / steps
            xi = int(x1 + (x2 - x1) * t)
            yi = int(y1 + (y2 - y1) * t)
            self._erase_inline_erase_at(xi, yi)

    def _erase_inline_flood_at(self, ix, iy):
        st = self._inline_erase
        if st is None:
            return
        try:
            img = st["img"]
            w, h = img.size
            px = img.load()
            r0, g0, b0, a0 = px[ix, iy]
            if a0 == 0:
                return
            tol = 32
            from collections import deque
            q = deque([(ix, iy)])
            seen = {(ix, iy)}
            while q:
                x, y = q.popleft()
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if (abs(r - r0) > tol or abs(g - g0) > tol
                        or abs(b - b0) > tol):
                    continue
                px[x, y] = (r, g, b, 0)
                for nx, ny in ((x + 1, y), (x - 1, y),
                               (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        q.append((nx, ny))
        except Exception as e:
            print(f"(inline flood error) {e}")

    # ── モード/ブラシ/ズーム 設定 ─────────────────────
    def _erase_inline_set_mode(self, mode):
        st = self._inline_erase
        if st is None:
            return
        st["mode"] = mode
        for m, w in st.get("mode_widgets", {}).items():
            try:
                if m == mode:
                    w.config(bg=ACCENT_DIM, fg="#04241a",
                             highlightbackground=ACCENT)
                else:
                    w.config(bg=BG_CARD, fg=TEXT_HI,
                             highlightbackground=BORDER)
            except Exception:
                pass
        try:
            self.preview_canvas.config(
                cursor="tcross" if mode == "erase" else "crosshair")
        except Exception:
            pass
        try:
            if mode == "erase":
                st["help_lbl"].config(
                    text="Drag to erase areas to transparent.\nBrush size controls stroke width.")
            else:
                st["help_lbl"].config(
                    text="Click to erase connected pixels of similar color.")
        except Exception:
            pass

    def _erase_inline_brush_changed(self):
        st = self._inline_erase
        if st is None:
            return
        try:
            v = max(5, min(80, int(st["var_brush"].get())))
            st["brush"] = v
            st["brush_lbl"].config(text=f"{v}px")
        except Exception:
            pass

    def _erase_inline_set_zoom(self, scale, _from_slider=False):
        """ズーム倍率を設定。
        - scale=None で Fit (画像が画面に収まる倍率を自動計算)
        - _from_slider=True のときはスライダーからの呼び出し → スライダー側を更新しない
          (循環防止)
        """
        st = self._inline_erase
        if st is None:
            return
        if scale is None:
            st["user_zoom"] = None
        else:
            # スライダー範囲 50%〜400% (= 0.5..4.0) でクランプ
            st["user_zoom"] = max(0.5, min(float(scale), 4.0))
        # ズーム変更時はパンをリセット (中央表示に戻す)
        st["pan_x"] = 0
        st["pan_y"] = 0
        self._erase_inline_render()
        # スライダーの値を同期 (Fit / +/- / ホイール経由の場合のみ)
        if not _from_slider:
            try:
                var = st.get("var_zoom")
                if var is not None:
                    st["_zoom_slider_sync"] = True
                    pct = int(round(st["disp_scale"] * 100))
                    pct = max(50, min(pct, 400))
                    var.set(pct)
                    st["_zoom_slider_sync"] = False
            except Exception:
                st["_zoom_slider_sync"] = False

    def _erase_inline_zoom_step(self, direction):
        """+/− ボタン or Ctrl+ホイールで 5% 刻みズーム (50..400 範囲)。"""
        st = self._inline_erase
        if st is None:
            return
        cur = st["user_zoom"] if st["user_zoom"] is not None else st["disp_scale"]
        cur_pct = int(round(cur * 100))
        step = 5  # 5% 刻み
        new_pct = cur_pct + (step if direction > 0 else -step)
        new_pct = max(50, min(new_pct, 400))
        self._erase_inline_set_zoom(new_pct / 100.0)

    def _apply_scale_to_all(self):
        """現在 item の scale_pct を全 item に一括適用。
        - ref_line_y / y_offset は変更しない
        - 各 item の is_scaled = True
        - 現在 item が無いときは現在のスライダー値を採用
        """
        if not self.item_list:
            return
        # 適用元 scale を決定
        try:
            cur = self.current_item
            if cur is not None:
                src_scale = int(cur.scale_pct)
            else:
                src_scale = int(float(self.var_scale.get()))
        except Exception:
            src_scale = 100
        applied_idxs = []
        for i, it in enumerate(self.item_list):
            try:
                it.scale_pct = src_scale
                it.is_scaled = True
                applied_idxs.append(i)
            except Exception:
                pass
        # サムネ状態バッジ更新
        try:
            for i in applied_idxs:
                if 0 <= i < len(self._thumb_cards):
                    self._thumb_cards[i].set_status(is_scaled=True)
        except Exception:
            pass
        # 全サムネを最新の処理後表示で同期 (scale_pct 変更を反映)
        self._refresh_all_thumb_views()
        # 再描画
        self._draw_preview_demo()
        print(f"(Apply to All / scale={src_scale}%) applied={len(applied_idxs)}")
        # フィードバック
        try:
            self._fire_align_feedback(label="SCALE APPLIED")
        except Exception as e:
            print(f"(feedback error) {e}")

    # ── 一括ALIGN 完了時の視覚フィードバック ──────────────────
    def _fire_align_feedback(self, label: str = "ALIGN COMPLETE"):
        """全サムネを一瞬光らせ + 中央に完了テキストを短時間表示。
        処理ロジック (y_offset / scale / ref_line_y) には一切触れない。"""
        # サムネを順に軽くパルス。現在選択中のカードは強めに光らせる。
        try:
            for i, card in enumerate(self._thumb_cards):
                strong = (i == self.current_idx)
                # 端から端へ波及するように 18ms ずつ遅延
                delay = i * 18
                card.pulse(strong=strong, delay_ms=delay)
        except Exception:
            pass
        # 中央に完了フラッシュ
        try:
            self._show_align_flash(label)
        except Exception:
            pass

    def _show_align_flash(self, text: str):
        """preview_canvas 中央に短時間だけテキストを表示してフェードアウト。"""
        cv = getattr(self, "preview_canvas", None)
        if cv is None:
            return
        try:
            w = cv.winfo_width()
            h = cv.winfo_height()
        except Exception:
            return
        if w < 10 or h < 10:
            return

        cx, cy = w // 2, int(h * 0.18)

        # フェード段階: (時間ms, 文字色)
        # tkinter は alpha を持たないので、明度を段階的に落として近似
        steps = [
            (0,   ACCENT_GLOW),
            (120, ACCENT),
            (260, ACCENT_DIM),
            (420, "#0a3a26"),
        ]
        # 既存のフラッシュが残っていたら消す
        try:
            old = getattr(self, "_align_flash_ids", [])
            for tid in old:
                cv.delete(tid)
        except Exception:
            pass
        self._align_flash_ids = []

        # 影 (微かに後ろに置いて発光感)
        try:
            shadow = cv.create_text(cx + 1, cy + 1, text=text,
                                    fill="#04241a",
                                    font=("Helvetica", 22, "bold"))
            main = cv.create_text(cx, cy, text=text,
                                  fill=ACCENT_GLOW,
                                  font=("Helvetica", 22, "bold"))
            self._align_flash_ids = [shadow, main]
        except Exception:
            return

        def _set_color(col):
            try:
                cv.itemconfig(main, fill=col)
            except Exception:
                pass

        def _remove():
            try:
                for tid in self._align_flash_ids:
                    cv.delete(tid)
                self._align_flash_ids = []
            except Exception:
                pass

        for ms, col in steps:
            try:
                self.root.after(ms, lambda c=col: _set_color(c))
            except Exception:
                pass
        try:
            self.root.after(500, _remove)
        except Exception:
            pass

    # ── サムネクリック (v35 _on_thumb_click) ──
    # NOTE: ダブルクリック機能は廃止 (Shift/Ctrl 操作に統一)。
    #       このメソッドは現在の構成では呼ばれない (ThumbCard 側で
    #       on_double_click が None のため)。後方互換のため残置。
    def _on_thumb_double_click(self, idx: int, ev=None):
        """[deprecated] ダブルクリック機能は廃止。"""
        if not (0 <= idx < len(self.item_list)):
            return
        # 修飾キー判定 (Tk の event.state ビット)
        # 0x0001 = Shift, 0x0008 = Alt (Linux/Win), 0x0010 = Mod3 (Alt変形),
        # macOS の Option(Alt) は 0x0010 か 0x0080 のことがある → 広めに見る
        state = 0
        try:
            if ev is not None:
                state = int(getattr(ev, "state", 0) or 0)
        except Exception:
            state = 0
        shift = bool(state & 0x0001)
        alt   = bool(state & 0x0008) or bool(state & 0x0010) or bool(state & 0x0080)
        # macOS の Cmd は 0x0008 (= Alt と被るプラットフォームあり) のため
        # 厳密に Cmd と Alt を分けたい場合は keysym で見るが、ここでは
        # 「修飾キー付きダブルクリック」を Alt 系/Shift 系で大別する。

        if alt and not shift:
            # Alt + ダブルクリック → 即 Remove BG (該当 item のみ)
            it = self.item_list[idx]
            if not it.loaded:
                try:
                    it.ensure_loaded()
                except Exception:
                    pass
            try:
                changed = self._remove_bg_one(it)
            except Exception as e:
                print(f"(double-click remove error) {e}")
                changed = False
            if changed:
                try:
                    self._refresh_thumb_view(idx)
                except Exception:
                    pass
                if idx == self.current_idx:
                    self._draw_preview_demo()
            return
        if shift and not alt:
            # Shift + ダブルクリック → 即 Restore (該当 item のみ)
            it = self.item_list[idx]
            try:
                changed = self._restore_bg_one(it)
            except Exception as e:
                print(f"(double-click restore error) {e}")
                changed = False
            if changed:
                try:
                    self._refresh_thumb_view(idx)
                except Exception:
                    pass
                if idx == self.current_idx:
                    self._draw_preview_demo()
            return

        # [deprecated] 単独選択 + プレビュー切替 (現在は呼ばれない)
        self.selected_idxs = {idx}
        self._activate_thumb_force(idx)
        self._refresh_thumb_selected_visuals()

    def _activate_thumb_force(self, idx: int):
        """idx を current にして、UI(右ペイン値・ハイライト・プレビュー)を
        強制的に再同期する。同 idx でも処理する点が _on_thumb_click と異なる。

        ★ サムネ枠の更新は _refresh_thumb_selected_visuals に一任する
          (selected_idxs と current_idx の整合性を保つため)。
        """
        if not (0 <= idx < len(self.item_list)):
            return
        prev = None
        if 0 <= self.current_idx < len(self.item_list):
            prev = self.item_list[self.current_idx]
        # Ghost 用に直前 item を保存 (current が変わる場合のみ)
        if (prev is not None and prev is not self.item_list[idx]
                and prev.loaded and prev.rgba is not None):
            try:
                self._ghost_prev = {
                    "rgba":  prev.rgba,
                    "y":     int(prev.y_offset),
                    "scale": int(prev.scale_pct),
                    "label": prev.label,
                }
            except Exception:
                self._ghost_prev = None
        self._prev_item_idx = self.current_idx
        self.current_idx = idx
        item = self.item_list[idx]
        if not item.loaded:
            try:
                item.ensure_loaded()
            except Exception:
                pass
        if item.loaded:
            try:
                self.var_y.set(item.y_offset)
                self.var_scale.set(item.scale_pct)
            except Exception:
                pass
        # サムネ枠は _refresh_thumb_selected_visuals 側で一括更新する
        # プレビュー再描画
        self._draw_preview_demo()

    def _on_thumb_click_with_modifier(self, idx: int, ev=None):
        """サムネクリック (修飾キー対応)。
        - 通常クリック       : 単一選択 (selected_idxs = {idx}) + プレビュー切替
        - Shift+クリック     : current_idx〜idx の範囲を選択に追加
        - Ctrl/Cmd+クリック  : idx を選択集合にトグル
        既存の単一クリック挙動 (_on_thumb_click) は維持し、修飾キー時のみ
        複数選択処理を上書き実行する。
        """
        # 修飾キー判定 (Tk の event.state ビット)
        # 0x0001 = Shift, 0x0004 = Control, 0x0008 = Cmd (macOS)
        state = 0
        try:
            if ev is not None:
                state = int(getattr(ev, "state", 0) or 0)
        except Exception:
            state = 0
        shift = bool(state & 0x0001)
        ctrl  = bool(state & 0x0004)
        cmd   = bool(state & 0x0008)

        if shift and 0 <= self.current_idx < len(self.item_list):
            # 範囲選択
            lo, hi = sorted((self.current_idx, idx))
            self.selected_idxs |= set(range(lo, hi + 1))
            self._refresh_thumb_selected_visuals()
            return
        if ctrl or cmd:
            # トグル選択
            if idx in self.selected_idxs:
                self.selected_idxs.discard(idx)
            else:
                self.selected_idxs.add(idx)
            # current_idx は変えない (プレビューは維持)
            self._refresh_thumb_selected_visuals()
            return

        # 通常クリック: 単一選択 + プレビュー切替
        self.selected_idxs = {idx}
        self._on_thumb_click(idx)
        self._refresh_thumb_selected_visuals()

    def _refresh_thumb_selected_visuals(self):
        """selected_idxs / current_idx に基づいてサムネのハイライトを更新。
        - current_idx (アクティブ): 黄色枠 (set_selected(True))
        - selected_idxs に含まれる (multi): 緑枠 (set_multi_selected(True))
        - それ以外: 通常 (処理状態色)
        """
        try:
            for i, card in enumerate(self._thumb_cards):
                is_active = (i == self.current_idx)
                is_multi  = (i in self.selected_idxs and not is_active)
                # アクティブ枠 (黄色) を更新
                card.set_selected(is_active)
                # マルチ選択枠 (緑) を更新
                card.set_multi_selected(is_multi)
        except Exception:
            pass

    def _on_thumb_click(self, idx: int):
        """v35 _on_thumb_click 同等。直前 item を _ghost_prev に保存し
        画像切替後 y_var/scale_var を item の値に同期。"""
        if not (0 <= idx < len(self.item_list)):
            return
        if idx == self.current_idx:
            return
        prev = self.current_item
        if prev is not None and prev.loaded and prev.rgba is not None:
            try:
                self._ghost_prev = {
                    "rgba":  prev.rgba,
                    "y":     int(prev.y_offset),
                    "scale": int(prev.scale_pct),
                    "label": prev.label,
                }
            except Exception:
                self._ghost_prev = None
        self._prev_item_idx = self.current_idx
        self.current_idx = idx
        item = self.current_item
        if item and not item.loaded:
            item.ensure_loaded()
        if item and item.loaded:
            try:
                self.var_y.set(item.y_offset)
                self.var_scale.set(item.scale_pct)
            except Exception:
                pass
        # サムネハイライト同期 (selected_idxs / current_idx ベースの統一 API 経由)
        try:
            self._refresh_thumb_selected_visuals()
        except Exception:
            pass
        self._draw_preview_demo()

    # ═══════════════════════════════════════════════════════
    #  CHECK MODE (確認モード)
    # ═══════════════════════════════════════════════════════
    def _build_check_frame(self, parent_wrap):
        """確認モード用のスクロール可能な Frame を構築。
        通常時は grid_remove() で隠れている。"""
        outer = tk.Frame(parent_wrap, bg="#1a1d22",
                         highlightthickness=1,
                         highlightbackground=BORDER_SOFT, bd=0)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        self._check_frame = outer
        # スクロール用 Canvas + 内部 Frame
        cv = tk.Canvas(outer, bg="#1a1d22",
                       highlightthickness=0, bd=0)
        cv.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        sb.grid(row=0, column=1, sticky="ns")
        cv.configure(yscrollcommand=sb.set)
        inner = tk.Frame(cv, bg="#1a1d22")
        cv.create_window(0, 0, window=inner, anchor="nw")
        self._check_canvas = cv
        self._check_inner = inner

        def _on_inner_resize(_e=None):
            try:
                cv.configure(scrollregion=cv.bbox("all"))
            except Exception:
                pass
        inner.bind("<Configure>", _on_inner_resize)

        def _on_canvas_resize(e):
            # 横スクロールは出さず、内部の幅を canvas 幅に合わせる
            try:
                cv.itemconfigure("all", width=e.width)
            except Exception:
                pass
            # CHECK中ならグリッドを再構築 (列数が変わるため)
            if self.check_mode:
                self._draw_check_mode()
        cv.bind("<Configure>", _on_canvas_resize)

        # ホイールスクロール
        def _on_wheel(e):
            d = getattr(e, "delta", 0)
            if d == 0:
                return
            cv.yview_scroll(int(-d / 30) if abs(d) > 60 else (-1 if d > 0 else 1),
                            "units")
        cv.bind("<Enter>", lambda _e: cv.bind_all("<MouseWheel>", _on_wheel))
        cv.bind("<Leave>", lambda _e: cv.unbind_all("<MouseWheel>"))

        outer.grid_remove()  # 初期は隠す

    def _toggle_check_mode(self):
        """CHECK ボタン押下時。通常 ⇄ 確認モードを切り替える。
        CHECK モード中はベースライン非表示でズレを強調、
        通常モードでは表示に戻す (描画のみの制御、Y 計算には無関係)。"""
        self.check_mode = not self.check_mode
        # ── BASE LINE 表示の連動 (描画のみ) ──
        try:
            self.show_baseline = (not self.check_mode)
            # UI チェックボックスの見た目も同期
            if hasattr(self, "var_show_baseline"):
                self.var_show_baseline.set(self.show_baseline)
        except Exception:
            pass
        if self.check_mode:
            try:
                self.preview_canvas.master.grid()  # wrap は元々表示中
                self._check_frame.grid()
                self._check_frame.lift()
            except Exception:
                pass
            self._draw_check_mode()
        else:
            try:
                self._check_frame.grid_remove()
            except Exception:
                pass
            self._draw_preview_demo()
        # ボタン見た目更新
        try:
            label = "EXIT CHECK" if self.check_mode else "CHECK"
            self.btn_check._text = label
            self.btn_check._redraw()
        except Exception:
            pass

    def _draw_check_mode(self):
        """確認モードの再描画。
        - render_canvas を流用 (新ロジック禁止)
        - 全画像に共通の ref_line_y を適用 (= ベースライン共通)
        - foot_y_alpha の中央値からの差分が ±3px を超えるセルは枠を赤に
        - クリックで通常モードへ戻り、その画像を選択
        - グリッドは inner 内で中央寄せ (左右の余白が等分されるよう
          中央列に grid_holder を置く)
        """
        inner = self._check_inner
        if inner is None:
            return
        for w in inner.winfo_children():
            w.destroy()
        self._check_photos = []
        self._check_cell_widgets = []

        if not self.item_list or not _PIL_AVAILABLE:
            tk.Label(inner,
                     text="No images loaded",
                     bg="#1a1d22", fg=TEXT_LO,
                     font=("Helvetica", 11)
                     ).pack(padx=20, pady=40)
            return

        # セルサイズ
        cell_disp = 180        # render_canvas の display_size
        cell_pad = 10
        cell_total = cell_disp + cell_pad * 2 + 10  # 枠+ラベル余裕

        # canvas 幅から列数を決める
        try:
            cw = self._check_canvas.winfo_width()
        except Exception:
            cw = 800
        cw = max(cell_total, cw)
        cols = max(1, cw // cell_total)

        # ── 中央寄せ用ホルダ ──
        # inner の幅は canvas 幅に追従 (itemconfigure(width=...))。
        # その中央列 (column=1) に実際のグリッドを置き、左右 (column=0/2) に
        # weight=1 のスペーサ列を配置することで中央配置になる。
        for col in range(3):
            inner.columnconfigure(col, weight=0)
        inner.columnconfigure(0, weight=1)   # 左スペーサ
        inner.columnconfigure(2, weight=1)   # 右スペーサ
        # column=1 は weight=0 (中身分の幅で固定)

        grid_holder = tk.Frame(inner, bg="#1a1d22")
        grid_holder.grid(row=0, column=1, sticky="n", pady=10)

        # 各 item の foot_y_1024 を計算
        foot_list = []
        for it in self.item_list:
            if not it.loaded:
                it.ensure_loaded()
            try:
                if it.loaded and it.rgba is not None:
                    fy = compute_foot_y_alpha(
                        it.rgba, MODE_MANUAL, it.y_offset, it.scale_pct)
                else:
                    fy = None
            except Exception:
                fy = None
            foot_list.append(fy)

        drift_base = self.ref_line_y
        DRIFT_PX = 3

        # ref_line_y → display 上の Y px (全セル共通)
        ref_line_y_disp = int(self.ref_line_y * cell_disp / CANVAS_SIZE)

        # グリッド配置 (grid_holder の中)
        for c in range(cols):
            grid_holder.columnconfigure(c, weight=0, uniform="check_col")

        for i, it in enumerate(self.item_list):
            r = i // cols
            c = i % cols
            cell = self._make_check_cell(
                grid_holder, it, i,
                cell_disp=cell_disp,
                ref_line_y_disp=ref_line_y_disp,
                foot_y_1024=foot_list[i],
                drift_ref=drift_base,
                drift_px=DRIFT_PX)
            cell.grid(row=r, column=c, padx=cell_pad, pady=cell_pad,
                      sticky="n")

        # スクロール領域更新
        try:
            self._check_canvas.update_idletasks()
            self._check_canvas.configure(
                scrollregion=self._check_canvas.bbox("all"))
        except Exception:
            pass

    def _make_check_cell(self, parent, item, idx, *,
                         cell_disp, ref_line_y_disp,
                         foot_y_1024, drift_ref, drift_px):
        """確認モードの1セル(Frame)を作成。クリックで通常モードへ戻る。"""
        # 枠色: ズレが基準±drift_px を超えていれば赤
        is_drift = (foot_y_1024 is not None
                    and abs(foot_y_1024 - drift_ref) > drift_px)
        border_col = "#ff4d4d" if is_drift else BORDER

        outer = tk.Frame(parent, bg=BG_THUMB,
                         highlightthickness=2,
                         highlightbackground=border_col,
                         highlightcolor=border_col,
                         cursor="hand2")
        outer.pack_propagate(False)
        outer.config(width=cell_disp + 4, height=cell_disp + 4 + 18)

        # 画像描画 Canvas
        cv = tk.Canvas(outer, bg=BG_THUMB,
                       highlightthickness=0, bd=0,
                       width=cell_disp, height=cell_disp,
                       cursor="hand2")
        cv.pack(side="top", padx=2, pady=2)

        # render_canvas 流用 (新ロジック禁止)
        try:
            if item.loaded and item.rgba is not None:
                bg, _foot_disp = render_canvas(
                    item.rgba, MODE_MANUAL,
                    item.y_offset, cell_disp,
                    scale_pct=item.scale_pct,
                    show_line=False,
                    ref_line_y_disp=None)
                photo = ImageTk.PhotoImage(bg)
                self._check_photos.append(photo)
                cv.create_image(0, 0, image=photo, anchor="nw")
        except Exception as e:
            print(f"(check render error) {e}")

        # 共通 BASE LINE (緑) を全セル同じ Y に描画 (細線 1px)
        # show_baseline が False のときは描画自体をスキップ
        # (CHECK モード入時に self.show_baseline = False になる仕様により、
        #  CHECK モードではデフォルトでベースラインが消える = ズレが強調される)
        if self.show_baseline:
            try:
                ly = max(1, min(ref_line_y_disp, cell_disp - 1))
                cv.create_line(0, ly, cell_disp, ly,
                               fill=ACCENT, width=1)
            except Exception:
                pass

        # ズレ量バッジ (左上)
        if foot_y_1024 is not None:
            diff = foot_y_1024 - drift_ref
            txt = f"{diff:+d}"
            col = "#ff8a8a" if is_drift else TEXT_LO
            cv.create_text(6, 6, text=txt, anchor="nw",
                           fill=col, font=("Menlo", 9, "bold"))

        # ラベル
        lbl = tk.Label(outer, text=item.label,
                       bg=BG_THUMB, fg=TEXT_LO,
                       font=("Helvetica", 9))
        lbl.pack(side="bottom")

        # クリックでそのitemを選択 → CHECK MODE 終了 → 通常編集画面へ
        def _on_click(_e=None, ix=idx):
            try:
                # 1. CHECK MODE を確実に終了 (描画を通常側へ戻す)
                if self.check_mode:
                    self._toggle_check_mode()
                # 2. その item を選択 (同じ idx でも UI 値を再同期する)
                if 0 <= ix < len(self.item_list):
                    if ix != self.current_idx:
                        self._on_thumb_click(ix)
                    else:
                        # 同 idx クリック: _on_thumb_click は早期 return するので
                        # 明示的に Y/Scale UI 値とサムネ選択ハイライトを同期
                        cur = self.item_list[ix]
                        if not cur.loaded:
                            cur.ensure_loaded()
                        try:
                            self.var_y.set(cur.y_offset)
                            self.var_scale.set(cur.scale_pct)
                        except Exception:
                            pass
                        try:
                            for i, card in enumerate(self._thumb_cards):
                                card.set_selected(i == ix)
                        except Exception:
                            pass
                        self._draw_preview_demo()
            except Exception as e:
                print(f"(check click error) {e}")
        for w in (outer, cv, lbl):
            w.bind("<ButtonRelease-1>", _on_click)

        # 軽いホバー演出 (枠色を ACCENT 寄りに)
        def _on_enter(_e=None):
            try:
                outer.config(highlightbackground=ACCENT_GLOW
                             if not is_drift else "#ff8a8a")
            except Exception:
                pass
        def _on_leave(_e=None):
            try:
                outer.config(highlightbackground=border_col)
            except Exception:
                pass
        outer.bind("<Enter>", _on_enter)
        outer.bind("<Leave>", _on_leave)

        self._check_cell_widgets.append(outer)
        return outer

    def _draw_preview_demo(self, _e=None):
        """v35 準拠のプレビュー描画。
        - 1024 論理座標系で計算 → display_size に縮小して表示。
        - display_size = canvas の短辺(可変)。
        - MAIN は v35 render_canvas で生成。
        - Ghost は別レイヤとして PIL で合成。
        - BASE LINE は v35 ref_line_y(1024座標) を render_canvas に渡して描画。"""
        # Manual Erase インラインモード中は通常描画を完全にスキップ。
        # 描画は _erase_inline_render が担当する。
        if getattr(self, "_inline_erase", None) is not None:
            try:
                self._erase_inline_render()
            except Exception as e:
                print(f"(inline render error) {e}")
            return
        # CHECK MODE 中は preview_canvas は隠れている。
        # ただし y_offset / scale 等の状態が変わったら CHECK 側も即更新する。
        if self.check_mode:
            try:
                self._draw_check_mode()
            except Exception as e:
                print(f"(check sync redraw error) {e}")
            return
        cv = self.preview_canvas
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 10 or h < 10:
            return

        # ── Grid 表示 (Grid トグル ON 時のみ) ──
        try:
            grid_on = self.tg_grid.get() if hasattr(self, "tg_grid") else False
        except Exception:
            grid_on = False
        if grid_on:
            try:
                step = int(self.var_grid_size.get())
            except Exception:
                step = 32
            step = max(8, step)
            grid_color = "#0f2a1f"
            for x in range(0, w, step):
                cv.create_line(x, 0, x, h, fill=grid_color, width=1)
            for y in range(0, h, step):
                cv.create_line(0, y, w, y, fill=grid_color, width=1)

        # ── 画像未読込時: デモキャラ描画 (BASE LINE は ref_line_y から) ──
        if not (self.item_list
                and 0 <= self.current_idx < len(self.item_list)
                and _PIL_AVAILABLE):
            self._draw_demo_chars(cv, w, h)
            return

        # ── 画像表示モード (v35 ロジック) ──
        item = self.item_list[self.current_idx]
        if not item.loaded:
            item.ensure_loaded()
        if not item.loaded or item.rgba is None:
            self._draw_demo_chars(cv, w, h)
            return

        # display_size: canvas 短辺(余白を少し残す) — MAIN画像本体のサイズ基準は不変
        display_size = max(64, min(w, h) - 8)
        # canvas 内の中央配置オフセット (MAIN は中央正方形に配置)
        ox = (w - display_size) // 2
        oy = (h - display_size) // 2

        # v35 と同じ: ref_line_y(1024座標) → display_size 上の Y px
        ref_line_y_disp = int(self.ref_line_y * display_size / CANVAS_SIZE)

        # MAIN レンダリング (v35 render_canvas: BASE LINEは描かない=透明背景のみ)
        mode = MODE_MANUAL
        y_offset = item.y_offset
        scale_pct = item.scale_pct
        try:
            main_bg, _foot_disp = render_canvas(
                item.rgba, mode, y_offset, display_size,
                scale_pct=scale_pct,
                show_line=False,
                ref_line_y_disp=None)
        except Exception as e:
            print(f"(render_canvas error) {e}")
            return

        # 合成キャンバスは canvas 全体の幅・高さで作る(正方形ではない)。
        # MAIN はその中央(横方向)に display_size 正方形として配置。
        # これにより Ghost は左右の余白部分まで自由に動ける。
        composed = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        main_rgba = main_bg if main_bg.mode == "RGBA" else main_bg.convert("RGBA")
        composed.paste(main_rgba, (ox, oy), main_rgba)

        # ── Ghost レイヤ合成 (canvas 全幅レイヤに貼る) ──
        try:
            ghost_on = bool(self.tg_overlay.get())
        except Exception:
            ghost_on = False
        try:
            alpha_pct = max(0, min(100, int(self.var_ghost_op.get())))
        except Exception:
            alpha_pct = 40

        if (ghost_on and alpha_pct > 0
                and self._ghost_prev is not None
                and self._ghost_prev.get("rgba") is not None):
            try:
                cmp_rgba = self._ghost_prev["rgba"]
                cmp_y = int(self._ghost_prev.get("y", 0))
                cmp_scale = int(self._ghost_prev.get("scale", 100))
                # v35 と同じく 1024 座標系で配置 → display_size 正方形に resize
                # (Ghost の Y/Scale は MAIN と同じ display_size 系で計算する)
                canvas_1024, _ = place_on_canvas(
                    cmp_rgba, MODE_MANUAL, cmp_y, cmp_scale)
                ghost_rgba = canvas_1024.convert("RGBA").resize(
                    (display_size, display_size), RESAMPLE)
                # アルファ減衰 (v35 と同じ式)
                eff_k = alpha_pct / 100.0
                a = ghost_rgba.split()[3]
                a = a.point(lambda v, k=eff_k: int(v * k))
                ghost_rgba.putalpha(a)
                # Ghost X Offset (表示px) — MAIN の中央位置を基準に dx ずらす
                try:
                    dx = int(self.var_ghost_xoff.get())
                except Exception:
                    dx = OVERLAY_INIT_X
                # canvas 全幅レイヤに貼る。貼付け基準は MAIN と同じ (ox, oy) + dx。
                # PIL の paste は貼付け先の範囲外を自動でクリップするので、
                # canvas 端を超えた部分だけが自然に消える(正方形端での不自然な切れは無くなる)。
                ghost_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                ghost_layer.paste(ghost_rgba, (ox + dx, oy), ghost_rgba)
                composed = Image.alpha_composite(composed, ghost_layer)
            except Exception as e:
                print(f"(ghost composite error) {e}")

        # PhotoImage を 1 枚作って canvas (0,0) に貼る(背景透明)
        self._preview_photo = ImageTk.PhotoImage(composed)
        cv.create_image(0, 0, image=self._preview_photo, anchor="nw")

        # ドラッグ判定 / canvas Tk 側 BASE LINE 描画用座標
        # display_size / oy は MAIN 正方形基準のまま維持(BASE LINE の Y換算は不変)
        self._disp_size = display_size
        self._disp_ox = ox
        self._disp_oy = oy
        line_y = oy + ref_line_y_disp
        self._line_y_canvas = line_y

        # ── BASE LINE 描画 (canvas Tk 側、緑ネオン) ──
        # プレビュー全幅 (左端 0 → 右端 w) を 1px の細線で描画。
        # ドラッグ中だけ若干強調 (width=2 + グロー1本)。
        # show_baseline が False のときは描画自体をスキップ (描画のみ制御)。
        if self.show_baseline:
            if self._baseline_dragging:
                cv.create_line(0, line_y, w, line_y,
                               fill=ACCENT_GLOW, width=2)
            else:
                cv.create_line(0, line_y, w, line_y,
                               fill=ACCENT, width=1)

        # ── HEADLINE 描画 (canvas Tk 側、紫) ──
        # ベースラインと明確に区別する色 (#a855f7 紫) で全幅描画。
        # head_y_disp = display_size 上の Y px に変換 (1024 → display_size)
        head_y_disp = int(self.head_y * display_size / CANVAS_SIZE)
        head_line_y = oy + head_y_disp
        self._head_line_y_canvas = head_line_y
        if self._headline_dragging:
            cv.create_line(0, head_line_y, w, head_line_y,
                           fill="#c084fc", width=2)  # 明るい紫
        else:
            cv.create_line(0, head_line_y, w, head_line_y,
                           fill="#a855f7", width=1)  # 通常紫

    def _draw_demo_chars(self, cv, w, h):
        """画像未読込時のデモキャラ描画。
        BASE LINE は ref_line_y(1024座標) を canvas px に変換して使う。"""
        display_size = max(64, min(w, h) - 8)
        ox = (w - display_size) // 2
        oy = (h - display_size) // 2
        # canvas 上の BASE LINE Y(描画にも当たり判定にも使う)
        ref_line_y_disp = int(self.ref_line_y * display_size / CANVAS_SIZE)
        line_y = oy + ref_line_y_disp
        self._disp_size = display_size
        self._disp_ox = ox
        self._disp_oy = oy
        self._line_y_canvas = line_y

        main_cx = int(w * 0.42)
        ghost_cx = main_cx + 180
        char_h = 200

        self._draw_pixel_char(cv, main_cx, line_y, char_h,
                              body=ACCENT,
                              body_light="#7dffc8",
                              body_shadow=ACCENT_DIM,
                              outline="#04241a",
                              ghost=False)
        self._draw_pixel_char(cv, ghost_cx, line_y, char_h,
                              body="#1a8556",
                              body_light="#2bb574",
                              body_shadow="#0e5538",
                              outline="#062a1c",
                              ghost=True)

        # 基準ライン: プレビュー全幅 + 細線 (1px、ドラッグ中は 2px)
        # show_baseline が False のときは描画自体をスキップ。
        if self.show_baseline:
            if self._baseline_dragging:
                cv.create_line(0, line_y, w, line_y,
                               fill=ACCENT_GLOW, width=2)
            else:
                cv.create_line(0, line_y, w, line_y,
                               fill=ACCENT, width=1)

        # ヘッドライン (上ライン、紫): demo モードでも描画
        head_y_disp = int(self.head_y * display_size / CANVAS_SIZE)
        head_line_y = oy + head_y_disp
        self._head_line_y_canvas = head_line_y
        if self._headline_dragging:
            cv.create_line(0, head_line_y, w, head_line_y,
                           fill="#c084fc", width=2)
        else:
            cv.create_line(0, head_line_y, w, head_line_y,
                           fill="#a855f7", width=1)

    def _draw_pixel_char(self, cv, cx, base_y, total_h,
                         *, body, body_light, body_shadow, outline,
                         ghost=False):
        """完成イメージのカバ風キャラに寄せたピクセル風シルエット。
        cx       : 中心 X
        base_y   : キャラの足元の Y (この位置に基準ラインが来る)
        total_h  : キャラの全高
        body / body_light / body_shadow / outline : 配色
        ghost    : True で半透明風 (色をくすませる)
        """
        # 8x10 グリッドの簡易ピクセルマップで描画
        # 0=透明 / 1=本体 / 2=ハイライト / 3=シャドウ / 4=輪郭 / 5=目
        pmap = [
            "00011110",
            "00111111",
            "01122112",
            "11222221",
            "11252521",
            "11222221",
            "11122211",
            "01111110",
            "01133110",
            "01100110",
        ]
        rows = len(pmap)
        cols = len(pmap[0])
        px = max(2, total_h // rows)   # 1ピクセルあたりの実サイズ
        char_w = cols * px
        char_h = rows * px
        x0 = cx - char_w // 2
        y0 = base_y - char_h          # 足元 = base_y

        if ghost:
            # 半透明風: 色を背景に寄せる(tkinterで真の半透明は困難)
            body        = "#155c3f"
            body_light  = "#1d8159"
            body_shadow = "#0a3a26"
            outline     = "#082619"
            eye_color   = "#0a3a26"
        else:
            eye_color   = "#04241a"

        color_map = {
            "1": body,
            "2": body_light,
            "3": body_shadow,
            "4": outline,
            "5": eye_color,
        }
        for r, row in enumerate(pmap):
            for c, ch in enumerate(row):
                if ch == "0":
                    continue
                col = color_map.get(ch, body)
                xa = x0 + c * px
                ya = y0 + r * px
                cv.create_rectangle(xa, ya, xa + px, ya + px,
                                    fill=col, outline="")

    # ───────────────────────────────────────────────────────
    def _build_controls(self, parent):
        # 右ペインを「flex column 風」3ブロック構成に変更:
        #   1. top_block : メイン操作 (FIT TO LINE / Individual / CHECK)
        #   2. mid_block : スライダー・設定群 (Y Offset / BASE LINE / Scale / Ghost / Remove BG)
        #      → flex:1 相当 (rowconfigure weight=1) で余白を吸収
        #   3. footer    : STARTボタン (margin-top:auto 相当 = 一番下に固定)
        # スクロールは完全に廃止 (Canvas/Scrollbar 不使用、overflow:hidden 相当)
        wrapper = tk.Frame(parent, bg=BG_PANEL)
        wrapper.grid(row=0, column=2, sticky="nse")
        wrapper.columnconfigure(0, weight=1)
        # row 0=top, 1=mid (伸縮), 2=footer (固定)
        wrapper.rowconfigure(0, weight=0)
        wrapper.rowconfigure(1, weight=1)
        wrapper.rowconfigure(2, weight=0)

        # ── ① top_block: メイン操作 ──
        # NOTE: tk.Frame コンストラクタの padx/pady は単一の数値のみ受け付ける。
        #       タプル指定 (左,右)/(上,下) は pack()/grid() のジオメトリ側でしか使えない。
        top_block = tk.Frame(wrapper, bg=BG_PANEL, padx=14, pady=8)
        # top の grid に下方向 pady を入れて、Main Actions と Adjust の間に余白
        top_block.grid(row=0, column=0, sticky="ew", pady=(8, 12))
        top_block.columnconfigure(0, weight=1)

        # ── ② mid_block: スライダー・設定群 (flex:1 で余白吸収) ──
        mid_block = tk.Frame(wrapper, bg=BG_PANEL, padx=14, pady=4)
        mid_block.grid(row=1, column=0, sticky="nsew")
        mid_block.columnconfigure(0, weight=1)

        # ── ③ footer: STARTボタン (常時下部固定) ──
        footer_frame = tk.Frame(wrapper, bg=BG_PANEL, padx=14, pady=10)
        # footer の grid に上方向 pady を入れて、Remove BG と START の間にも余白
        footer_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer_frame.columnconfigure(0, weight=1)
        tk.Frame(footer_frame, bg=BORDER_SOFT, height=1
                 ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._footer_frame = footer_frame

        # 互換: 既存コードが ctrl 変数を参照していた箇所のため、mid_block を ctrl とみなす
        # ※下のスライダー類は ctrl(=mid_block) の子になる
        ctrl = mid_block

        # Manual Erase 中に grid_remove で隠す対象は wrapper 全体
        self._ctrl_panel = wrapper

        # ── top_block: FIT TO LINE + Baseline + Individual + CHECK ──
        self.btn_fit = NeonButton(
            top_block, text="FIT TO LINE",
            command=lambda: self._align_all_to_ref_line(),
            width=210, height=44, radius=12,
            fill=ACCENT, hover_fill=ACCENT_GLOW,
            text_color="#04241a",
            font=("Helvetica", 13, "bold"),
            bg_parent=BG_PANEL)
        self.btn_fit.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # ── BASE LINE 表示 ON/OFF トグル (FIT TO LINE 直下に配置) ──
        # 描画のみを制御 (Y 計算ロジックには影響しない)。
        baseline_row = tk.Frame(top_block, bg=BG_PANEL)
        baseline_row.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        # 互換のため var_show_baseline / baseline_var の両名で同一 BooleanVar を参照可能に
        self.var_show_baseline = tk.BooleanVar(value=self.show_baseline)
        self.baseline_var = self.var_show_baseline   # alias

        def _on_baseline_toggle():
            try:
                self.show_baseline = bool(self.var_show_baseline.get())
            except Exception:
                self.show_baseline = True
            # 通常モード/CHECK モードに応じて再描画
            try:
                if getattr(self, "check_mode", False):
                    self._draw_check_mode()
                else:
                    self._draw_preview_demo()
            except Exception:
                pass

        # 視認性のため tk.Checkbutton を明示色指定で構築
        # (ダークテーマ上で indicator が背景に溶けないよう、
        #  selectcolor は明るい色、テキスト色も TEXT_HI で確実に表示する。)
        chk = tk.Checkbutton(
            baseline_row, text="Baseline",
            variable=self.var_show_baseline,
            command=_on_baseline_toggle,
            bg=BG_PANEL, fg=TEXT_HI,
            activebackground=BG_PANEL,
            activeforeground=ACCENT,
            selectcolor="#1d2128",       # チェック ON 時の indicator 内部色
            font=("Helvetica", 10, "bold"),
            bd=0, highlightthickness=0,
            padx=4, pady=2,
            cursor="hand2",
            anchor="w")
        chk.pack(side="left", anchor="w")
        self._baseline_toggle_chk = chk

        align_box = tk.Frame(top_block, bg=BG_PANEL)
        align_box.grid(row=2, column=0, sticky="ew")
        align_box.columnconfigure(0, weight=1, uniform="ab")
        align_box.columnconfigure(1, weight=1, uniform="ab")

        self.btn_individual = OutlineButton(
            align_box, text="Individual",
            command=lambda: self._align_to_ref_line(),
            width=100, height=30, radius=8,
            border=BORDER, hover_border=ACCENT_DIM,
            text_color=TEXT_HI, hover_text=ACCENT,
            font=("Helvetica", 10, "bold"),
            bg_parent=BG_PANEL)
        self.btn_individual.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_check = OutlineButton(
            align_box, text="CHECK",
            command=lambda: self._toggle_check_mode(),
            width=100, height=30, radius=8,
            border=ACCENT_DIM, hover_border=ACCENT,
            text_color=ACCENT, hover_text=ACCENT_GLOW,
            font=("Helvetica", 10, "bold"),
            bg_parent=BG_PANEL)
        self.btn_check.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # 区切り線 (top と mid の間)
        tk.Frame(top_block, bg=BORDER_SOFT, height=1
                 ).grid(row=3, column=0, sticky="ew", pady=(10, 0))

        # ── mid_block 内: 論理ブロックを縦に分散配置 ──
        # ブロック構成 (mid_block の row):
        #   row=0  : 上スペーサ           (weight=1) ← Adjust ブロックの上に余白
        #   row=1  : Adjust  (Y / BASE / Scale / Apply to All)
        #   row=2  : 中スペーサ1          (weight=1)
        #   row=3  : Ghost   (Toggle / Opacity / X Offset)
        #   row=4  : 中スペーサ2          (weight=1)
        #   row=5  : Remove BG (Remove/Restore × This/All + Manual Erase)
        #   row=6  : 下スペーサ           (weight=1)
        # mid_block 自体が wrapper.rowconfigure(1, weight=1) で flex:1 として伸びるので、
        # 余った縦スペースは 4 つのスペーサ行に均等に分配される
        # → ブロック間に自然な余白ができ、操作群が縦方向に分散して見える。
        for sp_row in (0, 2, 4, 6):
            ctrl.rowconfigure(sp_row, weight=1)
            tk.Frame(ctrl, bg=BG_PANEL, height=1
                     ).grid(row=sp_row, column=0, sticky="nsew")

        # ════════════════════════════════════════════════
        # Adjust ブロック (row=1)
        # ════════════════════════════════════════════════
        adj_block = tk.Frame(ctrl, bg=BG_PANEL)
        adj_block.grid(row=1, column=0, sticky="ew")
        adj_block.columnconfigure(0, weight=1)

        # Y Offset (ラベル + 値表示 + スライダー)
        yo_row = tk.Frame(adj_block, bg=BG_PANEL)
        yo_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        yo_row.columnconfigure(2, weight=1)
        tk.Label(yo_row, text="Y Offset",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 10, "bold"), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        # 現在値表示 (常時)
        self.lbl_y_value = tk.Label(yo_row, text="+0",
                                    bg=BG_PANEL, fg=ACCENT,
                                    font=("Menlo", 9, "bold"),
                                    width=6, anchor="e")
        self.lbl_y_value.grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.var_y = tk.DoubleVar(value=0)
        # var_y の変更を監視してラベルを自動同期 (どこから set されても OK)
        def _on_var_y_change(*_args):
            try:
                v = int(self.var_y.get())
            except Exception:
                v = 0
            try:
                self.lbl_y_value.config(text=f"{'+' if v >= 0 else ''}{v}")
            except Exception:
                pass
        try:
            self.var_y.trace_add("write", _on_var_y_change)
        except Exception:
            try:
                self.var_y.trace("w", _on_var_y_change)  # 古い tkinter 互換
            except Exception:
                pass
        # スライダー値変更時の処理 (画像更新)
        y_scale = ttk.Scale(yo_row, from_=SLIDER_MIN, to=SLIDER_MAX,
                            orient="horizontal",
                            variable=self.var_y,
                            command=lambda _v: self._on_slider(),
                            style="Neon.Horizontal.TScale")
        y_scale.grid(row=0, column=2, sticky="ew")
        # スライダー操作終了時: ドラッグ中省略していたサムネ更新 + prev_y 記憶 を実行
        y_scale.bind("<ButtonRelease-1>",
                     lambda _e: self._on_slider_release(_e))

        # ── Y Offset 手入力 + 記憶機能 (1行) ──
        # 入力欄 + Remember + Apply + Apply All の小さいサブ行
        # ── Prev Y 表示 (補助情報、クリックで適用) ──
        # Set Y 入力欄 / Remember ボタンは廃止し、最後に確定された Y を
        # 自動的に prev_y に保存して表示するだけのシンプル UI にする。
        yo_sub = tk.Frame(adj_block, bg=BG_PANEL)
        yo_sub.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        yo_sub.columnconfigure(0, weight=0)
        yo_sub.columnconfigure(1, weight=1)

        tk.Label(yo_sub, text="Prev Y",
                 bg=BG_PANEL, fg=TEXT_LO,
                 font=("Helvetica", 8), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        # 値表示ラベル (クリックでその Y へジャンプ可能)
        self.lbl_prev_y = tk.Label(yo_sub, text="—",
                                   bg=BG_PANEL, fg=TEXT_MID,
                                   font=("Menlo", 9),
                                   anchor="w", cursor="hand2")
        self.lbl_prev_y.grid(row=0, column=1, sticky="ew")
        # クリックで現在画像にその Y を適用
        self.lbl_prev_y.bind("<ButtonRelease-1>",
                             lambda _e: self._apply_prev_y())
        # ホバー時にアクセント色
        self.lbl_prev_y.bind("<Enter>",
                             lambda _e: self.lbl_prev_y.config(fg=ACCENT))
        self.lbl_prev_y.bind("<Leave>",
                             lambda _e: self.lbl_prev_y.config(
                                 fg=TEXT_MID if self._prev_y is not None else TEXT_LO))

        # 自動記憶される直前の Y 値 (None = 未確定)
        self._prev_y = None

        # BASE LINE Y (1行: ラベル + 数値 + スライダー)
        bl_row = tk.Frame(adj_block, bg=BG_PANEL)
        bl_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        bl_row.columnconfigure(2, weight=1)
        tk.Label(bl_row, text="BASE LINE",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 10, "bold"), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        self.lbl_baseline_y = tk.Label(bl_row, text=f"{CANVAS_SIZE}",
                                       bg=BG_PANEL, fg=ACCENT,
                                       font=("Menlo", 9, "bold"),
                                       width=5, anchor="e")
        self.lbl_baseline_y.grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.var_baseline_y = tk.DoubleVar(value=CANVAS_SIZE)
        self._refline_sync = False
        ttk.Scale(bl_row, from_=0, to=CANVAS_SIZE,
                  orient="horizontal",
                  variable=self.var_baseline_y,
                  command=lambda _v: self._on_ref_line_slider(),
                  style="Neon.Horizontal.TScale"
                  ).grid(row=0, column=2, sticky="ew")

        # Scale % (1行: ラベル + スライダー)
        sc_row = tk.Frame(adj_block, bg=BG_PANEL)
        sc_row.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        sc_row.columnconfigure(1, weight=1)
        tk.Label(sc_row, text="Scale %",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 10, "bold"), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        self.var_scale = tk.DoubleVar(value=100)
        ttk.Scale(sc_row, from_=10, to=250,
                  orient="horizontal",
                  variable=self.var_scale,
                  command=lambda _v: self._on_scale_slider(),
                  style="Neon.Horizontal.TScale"
                  ).grid(row=0, column=1, sticky="ew")

        # Apply to All
        self.btn_apply_all = OutlineButton(
            adj_block, text="Apply to All",
            command=lambda: self._apply_scale_to_all(),
            width=210, height=26, radius=8,
            border=ACCENT_DIM, hover_border=ACCENT,
            text_color=ACCENT, hover_text=ACCENT_GLOW,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_apply_all.grid(row=4, column=0, sticky="ew")

        # ════════════════════════════════════════════════
        # Ghost ブロック (row=3)
        # ════════════════════════════════════════════════
        ghost_block = tk.Frame(ctrl, bg=BG_PANEL)
        ghost_block.grid(row=3, column=0, sticky="ew")
        ghost_block.columnconfigure(0, weight=1)

        # Ghost トグル
        ov_row = tk.Frame(ghost_block, bg=BG_PANEL)
        ov_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ov_row.columnconfigure(0, weight=1)
        tk.Label(ov_row, text="Ghost",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 10, "bold")
                 ).grid(row=0, column=0, sticky="w")

        def _on_ghost_toggle(state):
            try:
                self._draw_preview_demo()
            except Exception:
                pass

        self.tg_overlay = ToggleSwitch(
            ov_row, initial=True,
            command=_on_ghost_toggle,
            bg_parent=BG_PANEL)
        self.tg_overlay.grid(row=0, column=1, sticky="e")

        # Ghost Opacity (1行: ラベル + 値 + スライダー)
        gop_row = tk.Frame(ghost_block, bg=BG_PANEL)
        gop_row.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        gop_row.columnconfigure(2, weight=1)
        tk.Label(gop_row, text="Opacity",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 9), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        self.lbl_ghost_op = tk.Label(gop_row, text="40%",
                                     bg=BG_PANEL, fg=ACCENT,
                                     font=("Menlo", 9, "bold"),
                                     width=5, anchor="e")
        self.lbl_ghost_op.grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.var_ghost_op = tk.DoubleVar(value=40)
        self._ghost_op_pending = False

        def _do_redraw_ghost():
            self._ghost_op_pending = False
            try:
                self._draw_preview_demo()
            except Exception:
                pass

        def _on_ghost_op(_v=None):
            try:
                self.lbl_ghost_op.config(
                    text=f"{int(self.var_ghost_op.get())}%")
            except Exception:
                pass
            if not self._ghost_op_pending:
                self._ghost_op_pending = True
                try:
                    self.root.after(40, _do_redraw_ghost)
                except Exception:
                    pass

        ttk.Scale(gop_row, from_=0, to=100,
                  orient="horizontal",
                  variable=self.var_ghost_op,
                  command=lambda _v: _on_ghost_op(),
                  style="Neon.Horizontal.TScale"
                  ).grid(row=0, column=2, sticky="ew")

        # Ghost X Offset (1行)
        gxo_row = tk.Frame(ghost_block, bg=BG_PANEL)
        gxo_row.grid(row=2, column=0, sticky="ew")
        gxo_row.columnconfigure(2, weight=1)
        tk.Label(gxo_row, text="X Offset",
                 bg=BG_PANEL, fg=TEXT_MID,
                 font=("Helvetica", 9), width=11, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        self.lbl_ghost_xoff = tk.Label(gxo_row, text="+200",
                                       bg=BG_PANEL, fg=ACCENT,
                                       font=("Menlo", 9, "bold"),
                                       width=5, anchor="e")
        self.lbl_ghost_xoff.grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.var_ghost_xoff = tk.DoubleVar(value=200)
        self._ghost_xoff_pending = False

        def _do_redraw_xoff():
            self._ghost_xoff_pending = False
            try:
                self._draw_preview_demo()
            except Exception:
                pass

        def _on_ghost_xoff(_v=None):
            try:
                v = int(self.var_ghost_xoff.get())
                self.lbl_ghost_xoff.config(
                    text=f"{'+' if v >= 0 else ''}{v}")
            except Exception:
                pass
            if not self._ghost_xoff_pending:
                self._ghost_xoff_pending = True
                try:
                    self.root.after(40, _do_redraw_xoff)
                except Exception:
                    pass

        ttk.Scale(gxo_row, from_=-600, to=600,
                  orient="horizontal",
                  variable=self.var_ghost_xoff,
                  command=lambda _v: _on_ghost_xoff(),
                  style="Neon.Horizontal.TScale"
                  ).grid(row=0, column=2, sticky="ew")

        # ════════════════════════════════════════════════
        # Remove BG ブロック (row=5)
        # ════════════════════════════════════════════════
        rb_box = tk.Frame(ctrl, bg=BG_PANEL)
        rb_box.grid(row=5, column=0, sticky="ew")
        rb_box.columnconfigure(0, weight=1, uniform="rb")
        rb_box.columnconfigure(1, weight=1, uniform="rb")

        tk.Label(rb_box, text="Remove BG",
                 bg=BG_PANEL, fg=TEXT_HI,
                 font=("Helvetica", 10, "bold")
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.btn_rmbg_this = OutlineButton(
            rb_box, text="Remove This",
            command=self._remove_bg_current,
            width=100, height=26, radius=7,
            border=BORDER, hover_border=ACCENT_DIM,
            text_color=TEXT_MID, hover_text=ACCENT,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_rmbg_this.grid(row=1, column=0, sticky="ew",
                                padx=(0, 3), pady=(0, 4))

        self.btn_rmbg_all = OutlineButton(
            rb_box, text="Remove All",
            command=self._remove_bg_all,
            width=100, height=26, radius=7,
            border=BORDER, hover_border=ACCENT_DIM,
            text_color=TEXT_MID, hover_text=ACCENT,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_rmbg_all.grid(row=1, column=1, sticky="ew",
                               padx=(3, 0), pady=(0, 4))

        self.btn_restorebg_this = OutlineButton(
            rb_box, text="Restore This",
            command=self._restore_bg_current,
            width=100, height=26, radius=7,
            border=BORDER, hover_border=TEXT_MID,
            text_color=TEXT_LO, hover_text=TEXT_HI,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_restorebg_this.grid(row=2, column=0, sticky="ew",
                                     padx=(0, 3))

        self.btn_restorebg_all = OutlineButton(
            rb_box, text="Restore All",
            command=self._restore_bg_all,
            width=100, height=26, radius=7,
            border=BORDER, hover_border=TEXT_MID,
            text_color=TEXT_LO, hover_text=TEXT_HI,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_restorebg_all.grid(row=2, column=1, sticky="ew",
                                    padx=(3, 0))

        # ── Selected 系 (複数選択された画像のみ操作) ──
        # ヒント: Shift / Ctrl / Cmd + クリックでサムネを複数選択
        self.btn_rmbg_selected = OutlineButton(
            rb_box, text="Remove Selected",
            command=self._remove_bg_selected,
            width=100, height=26, radius=7,
            border=ACCENT_DIM, hover_border=ACCENT,
            text_color=ACCENT, hover_text=ACCENT_GLOW,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_rmbg_selected.grid(row=3, column=0, sticky="ew",
                                    padx=(0, 3), pady=(6, 0))

        self.btn_restorebg_selected = OutlineButton(
            rb_box, text="Restore Selected",
            command=self._restore_bg_selected,
            width=100, height=26, radius=7,
            border=ACCENT_DIM, hover_border=ACCENT,
            text_color=ACCENT, hover_text=ACCENT_GLOW,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_restorebg_selected.grid(row=3, column=1, sticky="ew",
                                         padx=(3, 0), pady=(6, 0))

        # Manual Erase (フル幅)
        self.btn_manual_erase = OutlineButton(
            rb_box, text="✎ Manual Erase",
            command=self._open_manual_erase,
            width=210, height=26, radius=7,
            border=ACCENT_DIM, hover_border=ACCENT,
            text_color=ACCENT, hover_text=ACCENT_GLOW,
            font=("Helvetica", 9, "bold"),
            bg_parent=BG_PANEL)
        self.btn_manual_erase.grid(row=4, column=0, columnspan=2,
                                   sticky="ew", pady=(8, 0))

        # ── START (固定 footer に配置 = 常時表示) ──
        # フォルダ未選択 → 出力設定モーダルを開く / 設定済み → 即処理開始
        self.btn_start = OutlineButton(
            self._footer_frame, text="START",
            command=self._on_start_clicked,
            width=210, height=38, radius=10,
            border=BORDER, hover_border=ACCENT_DIM,
            text_color=TEXT_HI, hover_text=ACCENT,
            font=("Helvetica", 11, "bold"),
            bg_parent=BG_PANEL)
        self.btn_start.grid(row=1, column=0, sticky="ew")

    def _refresh_grid_size_pills(self):
        cur = self.var_grid_size.get()
        for val, pill in self._grid_size_pills.items():
            if val == cur:
                pill.config(bg=ACCENT_DIM, fg="#04241a",
                            highlightbackground=ACCENT)
            else:
                pill.config(bg=BG_CARD, fg=TEXT_MID,
                            highlightbackground=BORDER)

    # ───────────────────────────────────────────────────────
    def _build_thumbs(self, root):
        # 下部キャラ一覧
        bottom = tk.Frame(root, bg=BG_BASE, height=178)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_propagate(False)
        self._thumb_outer = bottom
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=0)   # sep
        bottom.rowconfigure(1, weight=0)   # ★ 操作説明
        bottom.rowconfigure(2, weight=1)   # サムネ列

        # 上部の細い区切り
        sep = tk.Frame(bottom, bg=BORDER_SOFT, height=1)
        sep.grid(row=0, column=0, sticky="ew")

        # ── サムネイル操作説明 (Shift / Ctrl 操作を案内) ──
        hint_bar = tk.Frame(bottom, bg=BG_BASE)
        hint_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(6, 0))
        tk.Label(hint_bar,
                 text="Click: select  /  Shift+Click: range  /  Ctrl/Cmd+Click: toggle multi",
                 bg=BG_BASE, fg=TEXT_LO,
                 font=("Helvetica", 9)
                 ).pack(side="left")

        scroll_wrap = tk.Frame(bottom, bg=BG_BASE)
        scroll_wrap.grid(row=2, column=0, sticky="nsew", padx=18, pady=(4, 12))
        scroll_wrap.columnconfigure(0, weight=1)
        scroll_wrap.rowconfigure(0, weight=1)

        cv = tk.Canvas(scroll_wrap, bg=BG_BASE,
                       highlightthickness=0, bd=0,
                       height=144)
        cv.grid(row=0, column=0, sticky="nsew")
        self._thumb_canvas = cv

        # Canvas 内に乗せる Frame
        inner = tk.Frame(cv, bg=BG_BASE)
        cv.create_window(0, 0, window=inner, anchor="nw")
        self._thumb_inner = inner

        # スクロール領域更新
        def _resize(_e=None):
            try:
                cv.configure(scrollregion=cv.bbox("all"))
            except Exception:
                pass
        inner.bind("<Configure>", _resize)
        cv.bind("<Configure>", _resize)

        # ── 横スクロール: トラックパッド/ホイール対応(全プラットフォーム) ──
        # macOS/Windows: <MouseWheel>(delta±120/3〜10)
        # macOS の横スクロール: <Shift-MouseWheel>
        # Linux: Button-4/5(縦) Button-6/7(横)
        def _scroll_units(delta_px: int):
            try:
                # delta_px は「動かしたいピクセル数」のヒント。
                # xview_scroll は units 単位。1 unit ≒ 数px〜十px程度。
                # 細かい刻みのトラックパッド向けに units を増減。
                units = max(1, abs(delta_px) // 30)
                if delta_px < 0:
                    cv.xview_scroll(-units, "units")
                else:
                    cv.xview_scroll(units, "units")
            except Exception:
                pass

        def _on_mousewheel(e):
            # 縦ホイールでも横スクロール(macOS主)
            d = getattr(e, "delta", 0)
            if d == 0:
                return
            # macOS は delta が小さい(±1〜±数十)、Win/Linux は ±120 系
            # 符号反転してスクロール方向を一般感覚に合わせる
            _scroll_units(-d * 4)

        def _on_shift_mousewheel(e):
            d = getattr(e, "delta", 0)
            if d == 0:
                return
            _scroll_units(-d * 4)

        def _on_button4(_e):  # Linux: 上方向 → 左へ
            _scroll_units(-30)

        def _on_button5(_e):  # Linux: 下方向 → 右へ
            _scroll_units(30)

        def _on_button6(_e):  # Linux: 横左
            _scroll_units(-30)

        def _on_button7(_e):  # Linux: 横右
            _scroll_units(30)

        # canvas / inner 双方にバインド(マウスがどこに乗っても効くように)
        def _safe_bind(w, ev, fn):
            try:
                w.bind(ev, fn)
            except Exception:
                pass

        for w in (cv, inner):
            _safe_bind(w, "<MouseWheel>",         _on_mousewheel)
            _safe_bind(w, "<Shift-MouseWheel>",   _on_shift_mousewheel)
            _safe_bind(w, "<Button-4>",           _on_button4)
            _safe_bind(w, "<Button-5>",           _on_button5)
            _safe_bind(w, "<Button-6>",           _on_button6)
            _safe_bind(w, "<Button-7>",           _on_button7)

        # Enter/Leave で bind_all による全体捕捉(サムネカードに乗ってる間も効く)
        def _safe_bind_all(ev, fn):
            try:
                cv.bind_all(ev, fn)
            except Exception:
                pass

        def _enter(_e=None):
            _safe_bind_all("<MouseWheel>",       _on_mousewheel)
            _safe_bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)
            _safe_bind_all("<Button-4>",         _on_button4)
            _safe_bind_all("<Button-5>",         _on_button5)
            _safe_bind_all("<Button-6>",         _on_button6)
            _safe_bind_all("<Button-7>",         _on_button7)

        def _leave(_e=None):
            for ev in ("<MouseWheel>", "<Shift-MouseWheel>",
                       "<Button-4>", "<Button-5>",
                       "<Button-6>", "<Button-7>"):
                try:
                    cv.unbind_all(ev)
                except Exception:
                    pass

        cv.bind("<Enter>", _enter)
        cv.bind("<Leave>", _leave)

        # 初期表示
        self._refresh_thumbs()


    # ═══════════════════════════════════════════════════════
    #  画像読み込み / サムネ / プレビュー切替
    # ═══════════════════════════════════════════════════════
    def _pick_images(self):
        """『＋画像を選ぶ』押下時。複数画像を ImageItem として読み込む。"""
        if not _PIL_AVAILABLE:
            print("(error) Pillow が未インストールです: pip install pillow")
            return

        paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("PNG",    "*.png"),
                ("JPEG",   "*.jpg *.jpeg"),
                ("All",    "*.*"),
            ])
        if not paths:
            return
        self._add_paths(paths)

    # ── 画像追加の共通処理 (ファイル選択 / D&D 共通) ──────────
    def _add_paths(self, paths):
        """与えられたパス列(ファイル/フォルダ混在可)を読み込み item_list に追加。
        - 重複パスは除外
        - フォルダはトップレベルの png/jpg/jpeg を再帰的でなく1階層だけ取り込む
        - 追加後にサムネ再構築 + 必要なら1枚目を自動選択
        """
        if not _PIL_AVAILABLE:
            print("(error) Pillow が未インストールです: pip install pillow")
            return
        valid_ext = (".png", ".jpg", ".jpeg")

        def _collect(p):
            try:
                if os.path.isdir(p):
                    out = []
                    for name in sorted(os.listdir(p)):
                        full = os.path.join(p, name)
                        if (os.path.isfile(full)
                                and name.lower().endswith(valid_ext)):
                            out.append(full)
                    return out
                if os.path.isfile(p) and p.lower().endswith(valid_ext):
                    return [p]
            except Exception as e:
                print(f"(collect error) {p}: {e}")
            return []

        flat = []
        for p in paths:
            flat.extend(_collect(p))
        if not flat:
            return

        existing_paths = {it.path for it in self.item_list}
        added = 0
        for p in flat:
            if p in existing_paths:
                continue
            self.item_list.append(ImageItem(p))
            existing_paths.add(p)
            added += 1
        if added == 0:
            print("(add) 追加対象なし (重複/非対応)")
            return

        try:
            self.lbl_load_count.config(text=f"Loaded: {len(self.item_list)}")
        except Exception:
            pass

        if self.current_idx < 0 and self.item_list:
            self.current_idx = 0
            first = self.item_list[0]
            first.ensure_loaded()
            try:
                self.var_y.set(first.y_offset)
                self.var_scale.set(first.scale_pct)
            except Exception:
                pass
        self._refresh_thumbs()
        self._draw_preview_demo()
        print(f"(loaded) +{added} files / total={len(self.item_list)}")

    # ── 削除系 ─────────────────────────────────────────
    def _delete_at(self, idx: int):
        """指定 index の画像を削除(サムネ右上の × から呼ばれる)。
        現在表示中なら _delete_current と同じ選択追従を行う。"""
        if not (0 <= idx < len(self.item_list)):
            return
        if idx == self.current_idx:
            self._delete_current()
            return
        # Ghost 参照クリア
        try:
            removed = self.item_list[idx]
            if (self._ghost_prev is not None
                    and self._ghost_prev.get("rgba") is removed.rgba):
                self._ghost_prev = None
        except Exception:
            pass
        del self.item_list[idx]
        # current_idx 補正 (削除位置より後ろなら 1 詰める)
        if self.current_idx > idx:
            self.current_idx -= 1
        try:
            self.lbl_load_count.config(text=f"Loaded: {len(self.item_list)}")
        except Exception:
            pass
        self._refresh_thumbs()
        self._draw_preview_demo()

    def _delete_current(self):
        """現在選択中の画像を1枚削除。次の画像を自動選択。
        最後の1枚なら未選択状態へ戻す。"""
        if not self.item_list:
            return
        idx = self.current_idx
        if not (0 <= idx < len(self.item_list)):
            return
        # Ghost が消えた item を参照していたらクリア
        try:
            removed = self.item_list[idx]
            if (self._ghost_prev is not None
                    and self._ghost_prev.get("rgba") is removed.rgba):
                self._ghost_prev = None
        except Exception:
            pass
        del self.item_list[idx]

        if not self.item_list:
            self.current_idx = -1
            self._ghost_prev = None
            try:
                self.var_y.set(0)
                self.var_scale.set(100)
            except Exception:
                pass
        else:
            # 同じ idx を維持(末尾削除なら一つ前へ)
            new_idx = min(idx, len(self.item_list) - 1)
            self.current_idx = new_idx
            cur = self.item_list[new_idx]
            if not cur.loaded:
                cur.ensure_loaded()
            try:
                self.var_y.set(cur.y_offset)
                self.var_scale.set(cur.scale_pct)
            except Exception:
                pass

        try:
            self.lbl_load_count.config(text=f"Loaded: {len(self.item_list)}")
        except Exception:
            pass
        self._refresh_thumbs()
        self._draw_preview_demo()

    def _delete_all(self):
        """全画像削除(確認ダイアログあり)。"""
        if not self.item_list:
            return
        try:
            from tkinter import messagebox
            ok = messagebox.askokcancel(
                "Clear All",
                f"Remove all {len(self.item_list)} images?",
                parent=self.root)
        except Exception:
            ok = True
        if not ok:
            return
        self.item_list.clear()
        self.current_idx = -1
        self._ghost_prev = None
        self._prev_item_idx = -1
        try:
            self.var_y.set(0)
            self.var_scale.set(100)
        except Exception:
            pass
        try:
            self.lbl_load_count.config(text=f"Loaded: 0")
        except Exception:
            pass
        self._refresh_thumbs()
        self._draw_preview_demo()
        print("(delete all) cleared")

    # ── 右クリックメニュー ─────────────────────────────
    def _show_context_menu(self, event, target_idx=None):
        """サムネまたはプレビュー上で右クリック時に呼ばれる。
        target_idx を渡せばそのサムネを対象にする(現在選択中以外でも削除可)。"""
        if target_idx is not None:
            if 0 <= target_idx < len(self.item_list) and target_idx != self.current_idx:
                self._on_thumb_click(target_idx)
        try:
            menu = tk.Menu(self.root, tearoff=0,
                           bg=BG_CARD, fg=TEXT_HI,
                           activebackground=ACCENT_DIM,
                           activeforeground="#04241a",
                           bd=0)
            has_item = self.current_idx >= 0 and bool(self.item_list)
            menu.add_command(label="Delete Selected  (Delete)",
                             command=self._delete_current,
                             state=("normal" if has_item else "disabled"))
            menu.add_separator()
            menu.add_command(label="Clear All",
                             command=self._delete_all,
                             state=("normal" if self.item_list else "disabled"))
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"(context menu error) {e}")
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    # ── キーバインド ───────────────────────────────────
    def _install_keybindings(self):
        """Delete / BackSpace で現在画像を削除。
        Entry / Text / Spinbox にフォーカスがあるときは無効化(誤爆防止)。"""
        def _on_delete(_e=None):
            # 入力ウィジェットにフォーカスがあれば無視
            try:
                w = self.root.focus_get()
                cls = w.winfo_class() if w is not None else ""
                if cls in ("Entry", "TEntry", "Text", "Spinbox", "TSpinbox",
                           "TCombobox"):
                    return
            except Exception:
                pass
            self._delete_current()

        try:
            self.root.bind_all("<Delete>",     _on_delete)
            self.root.bind_all("<BackSpace>",  _on_delete)
        except Exception:
            pass

    # ── 右クリックメニュー登録 ─────────────────────────
    def _install_context_menus(self):
        """preview canvas 上で右クリック → 全体メニュー。
        サムネ上の右クリックは _refresh_thumbs 内で個別カードに登録。"""
        cv = getattr(self, "preview_canvas", None)
        if cv is None:
            return
        try:
            # macOS: Button-2 (旧トラックパッド), 一般: Button-3
            cv.bind("<Button-3>",
                    lambda e: self._show_context_menu(e, target_idx=None))
            cv.bind("<Button-2>",
                    lambda e: self._show_context_menu(e, target_idx=None))
            cv.bind("<Control-Button-1>",
                    lambda e: self._show_context_menu(e, target_idx=None))
        except Exception:
            pass

    # ── ドラッグ&ドロップ ──────────────────────────────
    def _install_drag_and_drop(self):
        """tkinterDnD2 が利用可能なら preview / 左ペイン両方を D&D 受付に。
        利用不可なら案内ラベルを薄くしてヒントを切り替える。"""
        # root が TkinterDnD.Tk であれば drop_target_register が生える
        widgets = []
        cv = getattr(self, "preview_canvas", None)
        if cv is not None:
            widgets.append(cv)
        wf = getattr(self, "_wf_outer", None)
        if wf is not None:
            widgets.append(wf)

        # tkinterDnD2 経由 (root が DnD 対応のとき)
        try:
            DND_FILES = "DND_Files"
            ok = False
            for w in widgets:
                if hasattr(w, "drop_target_register"):
                    try:
                        w.drop_target_register(DND_FILES)
                        w.dnd_bind("<<Drop>>", self._on_dnd_drop)
                        ok = True
                    except Exception:
                        pass
            if ok:
                try:
                    self.lbl_dnd_hint.config(
                        text="Drag & Drop files or folders",
                        fg=TEXT_LO)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # フォールバック: D&D 不可
        try:
            self.lbl_dnd_hint.config(
                text="(Install tkinterdnd2 to enable D&D)",
                fg=TEXT_DIM)
        except Exception:
            pass

    def _on_dnd_drop(self, event):
        """tkinterDnD2 のドロップイベント。event.data はスペース区切りの
        パス文字列(空白を含むパスは {} で囲まれる)。"""
        raw = getattr(event, "data", "") or ""
        paths = self._parse_dnd_data(raw)
        if not paths:
            return
        self._add_paths(paths)

    @staticmethod
    def _parse_dnd_data(s: str):
        """tkinterDnD2 の event.data 文字列をパス配列に分解。
        '{C:/Path with space/file.png} D:/other.png' のような形式に対応。"""
        out = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch == "{":
                j = s.find("}", i + 1)
                if j == -1:
                    out.append(s[i + 1:])
                    break
                out.append(s[i + 1:j])
                i = j + 1
            elif ch.isspace():
                i += 1
            else:
                j = i
                while j < n and not s[j].isspace():
                    j += 1
                out.append(s[i:j])
                i = j
        return [p for p in out if p]

    def _refresh_thumb_view(self, idx=None):
        """指定 index (または現在 item) のサムネだけを処理後の見た目で再描画。
        idx=None なら current_idx。プレビューと同期させる軽量版更新。"""
        try:
            if idx is None:
                idx = self.current_idx
            if 0 <= idx < len(self._thumb_cards):
                self._thumb_cards[idx].refresh_view()
        except Exception:
            pass

    def _refresh_all_thumb_views(self):
        """全サムネを処理後の見た目で再描画(再生成しない)。"""
        try:
            for card in self._thumb_cards:
                card.refresh_view()
        except Exception:
            pass

    def _refresh_thumbs(self):
        """サムネ再構築。item_list 基準。"""
        inner = self._thumb_inner
        if inner is None:
            return
        for w in inner.winfo_children():
            w.destroy()
        self._thumb_cards = []

        if not self.item_list:
            tk.Label(inner,
                     text="← Add images to display thumbnails here",
                     bg=BG_BASE, fg=TEXT_LO,
                     font=("Helvetica", 10)
                     ).pack(side="left", padx=14, pady=40)
            try:
                self._thumb_canvas.configure(scrollregion=(0, 0, 0, 0))
            except Exception:
                pass
            return

        for i, it in enumerate(self.item_list):
            # サムネ描画には rgba が必要 (プレビュー同様の render_canvas を使うため)
            if not it.loaded:
                try:
                    it.ensure_loaded()
                except Exception:
                    pass
            card = ThumbCard(inner,
                             label=it.label,
                             on_click=lambda _lbl, ev=None, idx=i: self._on_thumb_click_with_modifier(idx, ev),
                             on_right_click=lambda e, idx=i: self._show_context_menu(e, target_idx=idx),
                             on_close=lambda idx=i: self._delete_at(idx),
                             selected=(i == self.current_idx),
                             image_path=it.path,
                             item=it,
                             is_aligned=getattr(it, "is_aligned", False),
                             is_scaled=getattr(it, "is_scaled", False))
            card.pack(side="left", padx=10)
            self._thumb_cards.append(card)

        try:
            self._thumb_canvas.update_idletasks()
            self._thumb_canvas.configure(
                scrollregion=self._thumb_canvas.bbox("all"))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--rembg-self-test" in sys.argv:
        try:
            _spriteanchor_log("(rembg self-test) starting")
            from PIL import Image as _SelfTestImage
            from rembg import new_session, remove as _selftest_remove  # type: ignore
            session = new_session("u2net")
            img = _SelfTestImage.new("RGBA", (64, 64), (255, 255, 255, 255))
            out = _selftest_remove(img, session=session)
            _spriteanchor_log(
                f"(rembg self-test) ok session={type(session).__name__} "
                f"out_mode={getattr(out, 'mode', '')} "
                f"U2NET_HOME={os.environ.get('U2NET_HOME', '')!r} "
                f"NUMBA_CACHE_DIR={os.environ.get('NUMBA_CACHE_DIR', '')!r}"
            )
            raise SystemExit(0)
        except Exception as e:
            _spriteanchor_log(f"(rembg self-test) failed: {e}")
            raise

    # tkinterdnd2 が入っていれば D&D 対応の Tk ルートを使う。
    # 入っていなくても通常の tk.Tk() で起動する(D&D は無効化される)。
    root = None
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore
        root = TkinterDnD.Tk()
    except Exception:
        root = tk.Tk()
    App(root)
    root.mainloop()
