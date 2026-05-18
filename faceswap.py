"""
KKG FaceSwap - app nativo de face swap por marcadores manuais.

Fluxo:
  1) Escolher 2 fotos (Base = destino, Face = origem).
  2) Posicionar 3 marcadores em cada (olho esquerdo, olho direito, boca).
  3) Pintar com pincel (tamanho / borda dura ou suave / opacidade) para revelar
     a Face warpeada por affine 3-pontos sobre a Base.
  4) Salvar PNG.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageTk

APP_TITLE = "KKG FaceSwap"
MAX_DISPLAY_W = 900
MAX_DISPLAY_H = 640
MARKER_COLORS = ["#3DDC97", "#FF6B6B", "#4DB8FF"]
MARKER_LABELS = ["Olho Esquerdo", "Olho Direito", "Boca"]
BG = "#1e1e22"
PANEL = "#27272e"
ACCENT = "#7c5cff"
TEXT = "#f5f5f7"
MUTED = "#9aa0a6"


def pil_to_np_rgba(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGBA"), dtype=np.uint8)


def np_rgba_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr, mode="RGBA")


def fit_size(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int, float]:
    scale = min(max_w / w, max_h / h, 1.0)
    return max(1, int(round(w * scale))), max(1, int(round(h * scale))), scale


class FaceSwapApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("1180x780")
        self.root.minsize(1000, 700)

        self._setup_style()

        # estado global
        self.img_a_pil: Image.Image | None = None  # Base (destino)
        self.img_b_pil: Image.Image | None = None  # Face (origem)
        self.path_a: str | None = None
        self.path_b: str | None = None
        # marcadores em coordenadas ORIGINAIS da imagem
        self.markers_a: list[tuple[float, float]] = []
        self.markers_b: list[tuple[float, float]] = []

        # cache da composição (tela 3)
        self.warped_b_full: np.ndarray | None = None       # RGBA shape (Ah, Aw, 4) - foto B warpeada na resolução de A
        self.warped_b_color_full: np.ndarray | None = None # warp da versão com color transfer
        self.base_a_full: np.ndarray | None = None         # RGBA shape (Ah, Aw, 4)
        self.mask_full: np.ndarray | None = None           # uint8 (Ah, Aw)
        self.display_scale: float = 1.0                    # scale para o canvas de pintura
        self.display_base: np.ndarray | None = None        # RGBA (h_disp, w_disp, 4)
        self.display_warp: np.ndarray | None = None        # RGBA (h_disp, w_disp, 4)
        self.display_warp_color: np.ndarray | None = None  # versão com color transfer
        self.display_mask: np.ndarray | None = None        # float32 0..1 (h_disp, w_disp)
        self.display_composite_tk: ImageTk.PhotoImage | None = None

        # parâmetros do pincel
        self.brush_size = tk.IntVar(value=60)
        self.brush_softness = tk.StringVar(value="suave")   # "duro" | "suave"
        self.brush_opacity = tk.IntVar(value=100)
        self.brush_mode = tk.StringVar(value="revelar")     # "revelar" | "apagar"

        # filtro de cor (color transfer LAB)
        self.color_match_enabled = tk.BooleanVar(value=False)
        self.color_match_strength = tk.IntVar(value=80)

        # container das telas
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True)

        self.current_frame: tk.Frame | None = None
        self.show_step1()

    # ------------------------------------------------------------------ style

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Card.TFrame", background=PANEL, relief="flat")
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Step.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground=TEXT,
            font=("Segoe UI", 10, "bold"),
            padding=(18, 10),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#9277ff"), ("disabled", "#4a4760")],
            foreground=[("disabled", "#bdbdbd")],
        )
        style.configure(
            "Ghost.TButton",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 10),
            padding=(14, 8),
            borderwidth=0,
        )
        style.map("Ghost.TButton", background=[("active", "#33333c")])
        style.configure("Horizontal.TScale", background=PANEL, troughcolor="#3a3a44")
        style.configure(
            "TRadiobutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10), focuscolor=PANEL
        )
        style.map("TRadiobutton", background=[("active", PANEL)])
        style.configure(
            "TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10), focuscolor=PANEL
        )
        style.map("TCheckbutton", background=[("active", PANEL)])

    # ------------------------------------------------------------------ helpers

    def _swap_frame(self, builder):
        if self.current_frame is not None:
            self.current_frame.destroy()
        frame = tk.Frame(self.container, bg=BG)
        frame.pack(fill="both", expand=True)
        self.current_frame = frame
        builder(frame)

    def _header(self, parent: tk.Frame, step: str, title: str, subtitle: str):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", padx=28, pady=(20, 6))
        ttk.Label(wrap, text=step, style="Step.TLabel").pack(anchor="w")
        ttk.Label(wrap, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(wrap, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

    # ============================================================= STEP 1

    def show_step1(self):
        self._swap_frame(self._build_step1)

    def _build_step1(self, frame: tk.Frame):
        self._header(
            frame,
            "Etapa 1 de 3",
            "Escolha as duas fotos",
            "Foto Base é onde o rosto será aplicado. Foto Face é o rosto que entra.",
        )

        body = tk.Frame(frame, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=18)
        body.grid_columnconfigure(0, weight=1, uniform="col")
        body.grid_columnconfigure(1, weight=1, uniform="col")
        body.grid_rowconfigure(0, weight=1)

        (
            self._card_a_lbl,
            self._card_a_name,
            self._card_a_rot_left,
            self._card_a_rot_right,
        ) = self._build_image_card(body, "Foto Base (destino)", "a")
        (
            self._card_b_lbl,
            self._card_b_name,
            self._card_b_rot_left,
            self._card_b_rot_right,
        ) = self._build_image_card(body, "Foto Face (origem)", "b")
        self._card_a_lbl.master.master.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_b_lbl.master.master.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._refresh_card("a")
        self._refresh_card("b")

        footer = tk.Frame(frame, bg=BG)
        footer.pack(fill="x", padx=28, pady=(8, 20))
        self.btn_next1 = ttk.Button(
            footer, text="Continuar  →", style="Accent.TButton", command=self._go_to_step2
        )
        self.btn_next1.pack(side="right")
        self._update_next1()

    def _build_image_card(self, parent, title: str, which: str):
        card = ttk.Frame(parent, style="Card.TFrame")
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(inner, text=title, style="Panel.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        thumb = tk.Label(inner, bg="#1a1a1f", fg=MUTED, text="(nenhuma imagem)", width=44, height=14)
        thumb.pack(fill="both", expand=True, pady=12)
        name_lbl = ttk.Label(inner, text="—", style="Panel.TLabel")
        name_lbl.pack(anchor="w")

        actions = tk.Frame(inner, bg=PANEL)
        actions.pack(fill="x", pady=(10, 0))
        rot_left = ttk.Button(
            actions, text="↺ 90°", style="Ghost.TButton",
            command=lambda: self._rotate_image(which, -90),
        )
        rot_left.pack(side="left")
        rot_right = ttk.Button(
            actions, text="↻ 90°", style="Ghost.TButton",
            command=lambda: self._rotate_image(which, 90),
        )
        rot_right.pack(side="left", padx=(6, 0))
        ttk.Button(
            actions, text="Escolher imagem…", style="Ghost.TButton",
            command=lambda: self._pick_image(which),
        ).pack(side="right")
        return thumb, name_lbl, rot_left, rot_right

    def _pick_image(self, which: str):
        path = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)  # respeita orientação EXIF do celular
            img = img.convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao abrir imagem:\n{exc}")
            return
        if which == "a":
            self.img_a_pil = img
            self.path_a = path
            self.markers_a = []
        else:
            self.img_b_pil = img
            self.path_b = path
            self.markers_b = []
        self._refresh_card(which)
        self._update_next1()

    def _rotate_image(self, which: str, degrees: int):
        img = self.img_a_pil if which == "a" else self.img_b_pil
        if img is None:
            return
        # Image.rotate com expand=True ajusta o tamanho. Negativo = horário no PIL,
        # então invertemos para que ↻ (positivo) realmente gire no sentido horário.
        rotated = img.rotate(-degrees, expand=True, resample=Image.BICUBIC)
        if which == "a":
            self.img_a_pil = rotated
            self.markers_a = []
        else:
            self.img_b_pil = rotated
            self.markers_b = []
        self._refresh_card(which)
        self._update_next1()

    def _refresh_card(self, which: str):
        if which == "a":
            img, path = self.img_a_pil, self.path_a
            thumb, name_lbl = self._card_a_lbl, self._card_a_name
            rot_left, rot_right = self._card_a_rot_left, self._card_a_rot_right
        else:
            img, path = self.img_b_pil, self.path_b
            thumb, name_lbl = self._card_b_lbl, self._card_b_name
            rot_left, rot_right = self._card_b_rot_left, self._card_b_rot_right
        if img is None:
            thumb.config(image="", text="(nenhuma imagem)", width=44, height=14)
            thumb.image = None
            name_lbl.config(text="—")
            rot_left.state(["disabled"])
            rot_right.state(["disabled"])
            return
        w, h = img.size
        tw, th, _ = fit_size(w, h, 380, 280)
        preview = img.resize((tw, th), Image.LANCZOS)
        photo = ImageTk.PhotoImage(preview)
        thumb.config(image=photo, text="", width=tw, height=th)
        thumb.image = photo  # keep ref
        name_lbl.config(text=f"{os.path.basename(path)}   ·   {w}×{h}")
        rot_left.state(["!disabled"])
        rot_right.state(["!disabled"])

    def _update_next1(self):
        ready = self.img_a_pil is not None and self.img_b_pil is not None
        self.btn_next1.state(["!disabled"] if ready else ["disabled"])

    def _go_to_step2(self):
        if self.img_a_pil is None or self.img_b_pil is None:
            return
        self.show_step2()

    # ============================================================= STEP 2

    def show_step2(self):
        self._swap_frame(self._build_step2)

    def _build_step2(self, frame: tk.Frame):
        self._header(
            frame,
            "Etapa 2 de 3",
            "Posicione os 3 marcadores em cada foto",
            "Clique para colocar e arraste para ajustar. Ordem: olho esquerdo (verde), olho direito (vermelho), boca (azul).",
        )

        body = tk.Frame(frame, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=14)
        body.grid_columnconfigure(0, weight=1, uniform="col")
        body.grid_columnconfigure(1, weight=1, uniform="col")
        body.grid_rowconfigure(0, weight=1)

        self.marker_canvas_a = MarkerCanvas(
            body, "Foto Base", self.img_a_pil, self.markers_a, self._on_markers_a_change
        )
        self.marker_canvas_a.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.marker_canvas_b = MarkerCanvas(
            body, "Foto Face", self.img_b_pil, self.markers_b, self._on_markers_b_change
        )
        self.marker_canvas_b.frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        footer = tk.Frame(frame, bg=BG)
        footer.pack(fill="x", padx=28, pady=(4, 20))
        ttk.Button(footer, text="← Voltar", style="Ghost.TButton", command=self.show_step1).pack(side="left")
        ttk.Button(
            footer,
            text="Limpar marcadores",
            style="Ghost.TButton",
            command=self._clear_markers,
        ).pack(side="left", padx=(10, 0))
        self.btn_next2 = ttk.Button(
            footer, text="Continuar  →", style="Accent.TButton", command=self._go_to_step3
        )
        self.btn_next2.pack(side="right")
        self._update_next2()

    def _on_markers_a_change(self, markers):
        self.markers_a = markers
        self._update_next2()

    def _on_markers_b_change(self, markers):
        self.markers_b = markers
        self._update_next2()

    def _clear_markers(self):
        self.markers_a = []
        self.markers_b = []
        self.marker_canvas_a.set_markers([])
        self.marker_canvas_b.set_markers([])
        self._update_next2()

    def _update_next2(self):
        ok = len(self.markers_a) == 3 and len(self.markers_b) == 3
        self.btn_next2.state(["!disabled"] if ok else ["disabled"])

    def _go_to_step3(self):
        if len(self.markers_a) != 3 or len(self.markers_b) != 3:
            return
        try:
            self._prepare_warp()
        except Exception as exc:
            messagebox.showerror("Erro no warp", str(exc))
            return
        self.show_step3()

    # ----- warp -------------------------------------------------------------

    def _prepare_warp(self):
        assert self.img_a_pil is not None and self.img_b_pil is not None
        base = pil_to_np_rgba(self.img_a_pil)
        src = pil_to_np_rgba(self.img_b_pil)
        Ah, Aw = base.shape[:2]

        src_pts = np.float32(self.markers_b)   # B -> A
        dst_pts = np.float32(self.markers_a)
        M = cv2.getAffineTransform(src_pts, dst_pts)

        warped = cv2.warpAffine(
            src,
            M,
            (Aw, Ah),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        self.base_a_full = base
        self.warped_b_full = warped
        # cache de cor invalidado (marcadores ou imagens podem ter mudado)
        self.warped_b_color_full = None
        self.display_warp_color = None

        # preserva máscara se as dimensões da Base não mudaram (usuário voltou só pra ajustar marcadores)
        if (
            self.mask_full is None
            or self.mask_full.shape != (Ah, Aw)
        ):
            self.mask_full = np.zeros((Ah, Aw), dtype=np.uint8)
            reset_mask = True
        else:
            reset_mask = False

        # versão de display
        dw, dh, scale = fit_size(Aw, Ah, MAX_DISPLAY_W, MAX_DISPLAY_H)
        self.display_scale = scale
        self.display_base = cv2.resize(base, (dw, dh), interpolation=cv2.INTER_AREA)
        self.display_warp = cv2.resize(warped, (dw, dh), interpolation=cv2.INTER_AREA)
        if reset_mask or self.display_mask is None or self.display_mask.shape != (dh, dw):
            self.display_mask = np.zeros((dh, dw), dtype=np.float32)
        # se preservou, mantém self.display_mask como estava

    # ---- color transfer (Reinhard, LAB) ------------------------------------

    @staticmethod
    def _color_transfer_lab(source_rgb: np.ndarray, target_rgb: np.ndarray) -> np.ndarray:
        """Ajusta source para ter média/desvio por canal LAB iguais aos de target.
        Recebe arrays uint8 RGB; retorna uint8 RGB."""
        s_lab = cv2.cvtColor(source_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        t_lab = cv2.cvtColor(target_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        for c in range(3):
            s_mean = s_lab[..., c].mean()
            s_std = s_lab[..., c].std()
            t_mean = t_lab[..., c].mean()
            t_std = t_lab[..., c].std()
            if s_std < 1e-6:
                continue
            s_lab[..., c] = (s_lab[..., c] - s_mean) * (t_std / s_std) + t_mean
        s_lab = np.clip(s_lab, 0, 255).astype(np.uint8)
        return cv2.cvtColor(s_lab, cv2.COLOR_LAB2RGB)

    def _ensure_color_warp(self):
        """Calcula warp da versão color-matched (lazy)."""
        if self.warped_b_color_full is not None:
            return
        assert self.img_b_pil is not None and self.base_a_full is not None
        src_full = pil_to_np_rgba(self.img_b_pil)
        # color transfer usa apenas a base de A onde tem opacidade plena (toda a foto, no caso)
        target_rgb = self.base_a_full[..., :3]
        matched_rgb = self._color_transfer_lab(src_full[..., :3], target_rgb)
        matched_rgba = np.concatenate(
            [matched_rgb, src_full[..., 3:4]], axis=-1
        )
        src_pts = np.float32(self.markers_b)
        dst_pts = np.float32(self.markers_a)
        M = cv2.getAffineTransform(src_pts, dst_pts)
        Ah, Aw = self.base_a_full.shape[:2]
        warped = cv2.warpAffine(
            matched_rgba, M, (Aw, Ah),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        self.warped_b_color_full = warped
        dh, dw = self.display_base.shape[:2]
        self.display_warp_color = cv2.resize(warped, (dw, dh), interpolation=cv2.INTER_AREA)

    # ============================================================= STEP 3

    def show_step3(self):
        self._swap_frame(self._build_step3)

    def _build_step3(self, frame: tk.Frame):
        self._header(
            frame,
            "Etapa 3 de 3",
            "Pinte para revelar o rosto",
            "Use o pincel para revelar a face alinhada. Botão direito do mouse apaga. Veja a prévia ao vivo.",
        )

        body = tk.Frame(frame, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=14)

        # painel lateral
        side = tk.Frame(body, bg=PANEL, width=240)
        side.pack(side="left", fill="y", padx=(0, 16))
        side.pack_propagate(False)

        ttk.Label(side, text="Pincel", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=14, pady=(14, 8)
        )

        # tamanho
        ttk.Label(side, text="Tamanho", style="Panel.TLabel").pack(anchor="w", padx=14)
        size_row = tk.Frame(side, bg=PANEL)
        size_row.pack(fill="x", padx=14, pady=(2, 8))
        size_scale = ttk.Scale(
            size_row,
            from_=4,
            to=300,
            variable=self.brush_size,
            command=lambda _v: self._update_brush_label(),
        )
        size_scale.pack(side="left", fill="x", expand=True)
        self.size_value_lbl = ttk.Label(size_row, text="60 px", style="Panel.TLabel", width=6)
        self.size_value_lbl.pack(side="right")

        # tipo
        ttk.Label(side, text="Borda", style="Panel.TLabel").pack(anchor="w", padx=14, pady=(6, 2))
        ttk.Radiobutton(
            side, text="Suave (gradiente)", value="suave", variable=self.brush_softness
        ).pack(anchor="w", padx=14)
        ttk.Radiobutton(
            side, text="Dura (fixa)", value="duro", variable=self.brush_softness
        ).pack(anchor="w", padx=14)

        # opacidade
        ttk.Label(side, text="Opacidade", style="Panel.TLabel").pack(anchor="w", padx=14, pady=(10, 2))
        op_row = tk.Frame(side, bg=PANEL)
        op_row.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Scale(
            op_row, from_=10, to=100, variable=self.brush_opacity, command=lambda _v: self._update_brush_label()
        ).pack(side="left", fill="x", expand=True)
        self.opacity_value_lbl = ttk.Label(op_row, text="100%", style="Panel.TLabel", width=6)
        self.opacity_value_lbl.pack(side="right")

        # modo
        ttk.Label(side, text="Modo", style="Panel.TLabel").pack(anchor="w", padx=14, pady=(10, 2))
        ttk.Radiobutton(
            side, text="Revelar rosto", value="revelar", variable=self.brush_mode
        ).pack(anchor="w", padx=14)
        ttk.Radiobutton(
            side, text="Apagar pintura", value="apagar", variable=self.brush_mode
        ).pack(anchor="w", padx=14)

        # ---- filtro de cor (opcional) ----
        ttk.Label(
            side, text="Cor / Iluminação (opcional)",
            style="Panel.TLabel", font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 4))
        self.color_chk = ttk.Checkbutton(
            side,
            text="Casar cores com a Base",
            variable=self.color_match_enabled,
            command=self._on_color_match_toggle,
            style="TCheckbutton",
        )
        self.color_chk.pack(anchor="w", padx=14)
        cm_row = tk.Frame(side, bg=PANEL)
        cm_row.pack(fill="x", padx=14, pady=(4, 8))
        ttk.Label(cm_row, text="Intensidade", style="Panel.TLabel").pack(anchor="w")
        cm_slider_row = tk.Frame(cm_row, bg=PANEL)
        cm_slider_row.pack(fill="x")
        ttk.Scale(
            cm_slider_row,
            from_=0, to=100,
            variable=self.color_match_strength,
            command=lambda _v: self._on_color_match_change(),
        ).pack(side="left", fill="x", expand=True)
        self.cm_value_lbl = ttk.Label(cm_slider_row, text="80%", style="Panel.TLabel", width=6)
        self.cm_value_lbl.pack(side="right")

        ttk.Button(
            side, text="Limpar tudo", style="Ghost.TButton", command=self._clear_mask
        ).pack(fill="x", padx=14, pady=(18, 4))
        ttk.Button(
            side, text="Revelar tudo", style="Ghost.TButton", command=self._fill_mask
        ).pack(fill="x", padx=14, pady=(0, 4))
        ttk.Button(
            side, text="Pré-visualizar marcadores", style="Ghost.TButton",
            command=self._toggle_markers_preview
        ).pack(fill="x", padx=14, pady=(0, 4))

        ttk.Button(
            side, text="↓  Baixar PNG", style="Accent.TButton", command=self._save_result
        ).pack(fill="x", padx=14, pady=(18, 14))

        # canvas
        canvas_wrap = tk.Frame(body, bg="#16161a")
        canvas_wrap.pack(side="left", fill="both", expand=True)

        dh, dw = self.display_base.shape[:2]
        self.paint_canvas = tk.Canvas(
            canvas_wrap, width=dw, height=dh, bg="#16161a", highlightthickness=0, cursor="crosshair"
        )
        self.paint_canvas.pack(expand=True)

        self._paint_img_id = None
        self._cursor_id = None
        self._show_markers_preview = False
        self._last_paint_pos = None

        self.paint_canvas.bind("<Motion>", self._on_paint_move)
        self.paint_canvas.bind("<Leave>", lambda _e: self._hide_cursor())
        self.paint_canvas.bind("<ButtonPress-1>", self._on_paint_press_reveal)
        self.paint_canvas.bind("<B1-Motion>", self._on_paint_drag_reveal)
        self.paint_canvas.bind("<ButtonRelease-1>", self._on_paint_release)
        self.paint_canvas.bind("<ButtonPress-3>", self._on_paint_press_erase)
        self.paint_canvas.bind("<B3-Motion>", self._on_paint_drag_erase)
        self.paint_canvas.bind("<ButtonRelease-3>", self._on_paint_release)

        footer = tk.Frame(frame, bg=BG)
        footer.pack(fill="x", padx=28, pady=(4, 20))
        ttk.Button(
            footer, text="← Editar marcadores", style="Ghost.TButton", command=self.show_step2
        ).pack(side="left")
        ttk.Label(
            footer,
            text="Dica: clique esquerdo = revela, clique direito = apaga. A pintura é preservada se você voltar pra ajustar os marcadores.",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(14, 0))

        self._update_brush_label()
        self._update_color_match_label()
        self._render_composite()

    def _update_brush_label(self):
        self.size_value_lbl.config(text=f"{int(self.brush_size.get())} px")
        self.opacity_value_lbl.config(text=f"{int(self.brush_opacity.get())}%")

    def _update_color_match_label(self):
        self.cm_value_lbl.config(text=f"{int(self.color_match_strength.get())}%")

    def _on_color_match_toggle(self):
        if self.color_match_enabled.get():
            try:
                self._ensure_color_warp()
            except Exception as exc:
                messagebox.showerror("Erro no filtro", str(exc))
                self.color_match_enabled.set(False)
                return
        self._render_composite()

    def _on_color_match_change(self):
        self._update_color_match_label()
        if self.color_match_enabled.get():
            self._render_composite()

    def _effective_display_warp(self) -> np.ndarray:
        if self.color_match_enabled.get() and self.display_warp_color is not None:
            alpha = self.color_match_strength.get() / 100.0
            return (
                self.display_warp.astype(np.float32) * (1 - alpha)
                + self.display_warp_color.astype(np.float32) * alpha
            ).astype(np.uint8)
        return self.display_warp

    def _effective_full_warp(self) -> np.ndarray:
        if self.color_match_enabled.get():
            self._ensure_color_warp()
            if self.warped_b_color_full is not None:
                alpha = self.color_match_strength.get() / 100.0
                return (
                    self.warped_b_full.astype(np.float32) * (1 - alpha)
                    + self.warped_b_color_full.astype(np.float32) * alpha
                ).astype(np.uint8)
        return self.warped_b_full

    # ----- paint ------------------------------------------------------------

    def _clear_mask(self):
        if self.display_mask is None:
            return
        self.display_mask[:] = 0
        self.mask_full[:] = 0
        self._render_composite()

    def _fill_mask(self):
        if self.display_mask is None:
            return
        self.display_mask[:] = 1.0
        self.mask_full[:] = 255
        self._render_composite()

    def _toggle_markers_preview(self):
        self._show_markers_preview = not self._show_markers_preview
        self._render_composite()

    def _on_paint_move(self, event):
        self._draw_cursor(event.x, event.y)

    def _hide_cursor(self):
        if self._cursor_id is not None:
            self.paint_canvas.delete(self._cursor_id)
            self._cursor_id = None

    def _draw_cursor(self, x: int, y: int):
        r = max(2, int(self.brush_size.get()) / 2)
        self._hide_cursor()
        self._cursor_id = self.paint_canvas.create_oval(
            x - r, y - r, x + r, y + r, outline=ACCENT, width=2
        )

    def _on_paint_press_reveal(self, event):
        self._last_paint_pos = (event.x, event.y)
        self._apply_brush(event.x, event.y, erase=self.brush_mode.get() == "apagar")

    def _on_paint_drag_reveal(self, event):
        erase = self.brush_mode.get() == "apagar"
        self._apply_brush_segment(event.x, event.y, erase=erase)
        self._draw_cursor(event.x, event.y)

    def _on_paint_press_erase(self, event):
        self._last_paint_pos = (event.x, event.y)
        self._apply_brush(event.x, event.y, erase=True)

    def _on_paint_drag_erase(self, event):
        self._apply_brush_segment(event.x, event.y, erase=True)
        self._draw_cursor(event.x, event.y)

    def _on_paint_release(self, _event):
        self._last_paint_pos = None

    def _apply_brush_segment(self, x: int, y: int, erase: bool):
        """Interpola entre o último ponto e o atual para não deixar buracos."""
        if self._last_paint_pos is None:
            self._apply_brush(x, y, erase=erase)
            self._last_paint_pos = (x, y)
            return
        x0, y0 = self._last_paint_pos
        dx, dy = x - x0, y - y0
        dist = max(abs(dx), abs(dy))
        spacing = max(1, int(self.brush_size.get()) // 4)
        steps = max(1, dist // spacing)
        for i in range(1, steps + 1):
            xi = int(x0 + dx * i / steps)
            yi = int(y0 + dy * i / steps)
            self._apply_brush(xi, yi, erase=erase, defer_render=(i != steps))
        self._last_paint_pos = (x, y)

    def _apply_brush(self, x: int, y: int, erase: bool, defer_render: bool = False):
        if self.display_mask is None:
            return
        size = int(self.brush_size.get())
        if size < 2:
            size = 2
        radius = size / 2
        soft = self.brush_softness.get() == "suave"
        opacity = max(0.05, min(1.0, self.brush_opacity.get() / 100.0))

        dh, dw = self.display_mask.shape
        x0 = max(0, int(np.floor(x - radius)))
        y0 = max(0, int(np.floor(y - radius)))
        x1 = min(dw, int(np.ceil(x + radius)) + 1)
        y1 = min(dh, int(np.ceil(y + radius)) + 1)
        if x0 >= x1 or y0 >= y1:
            return

        ys = np.arange(y0, y1, dtype=np.float32) - y
        xs = np.arange(x0, x1, dtype=np.float32) - x
        dist2 = ys[:, None] ** 2 + xs[None, :] ** 2
        if soft:
            # 1 no centro, 0 na borda — perfil cossenoidal suave
            d = np.sqrt(dist2) / radius
            stamp = np.clip(1.0 - d, 0.0, 1.0)
            stamp = stamp * stamp * (3 - 2 * stamp)  # smoothstep
        else:
            stamp = (dist2 <= radius * radius).astype(np.float32)
        stamp *= opacity

        region = self.display_mask[y0:y1, x0:x1]
        if erase:
            self.display_mask[y0:y1, x0:x1] = np.clip(region - stamp, 0.0, 1.0)
        else:
            self.display_mask[y0:y1, x0:x1] = np.clip(region + stamp, 0.0, 1.0)

        if not defer_render:
            self._render_composite_region(x0, y0, x1, y1)

    # ----- render -----------------------------------------------------------

    def _render_composite(self):
        if self.display_base is None:
            return
        m = self.display_mask[:, :, None]  # (h,w,1)
        warp = self._effective_display_warp()
        comp = (
            self.display_base.astype(np.float32) * (1 - m)
            + warp.astype(np.float32) * m
        ).astype(np.uint8)
        if self._show_markers_preview:
            comp = self._draw_markers_overlay(comp)
        img = Image.fromarray(comp, mode="RGBA")
        self._current_tk_img = ImageTk.PhotoImage(img)
        if self._paint_img_id is None:
            self._paint_img_id = self.paint_canvas.create_image(
                0, 0, image=self._current_tk_img, anchor="nw"
            )
        else:
            self.paint_canvas.itemconfigure(self._paint_img_id, image=self._current_tk_img)

    def _render_composite_region(self, x0, y0, x1, y1):
        # full re-render — simples e rápido o suficiente para tamanhos de display.
        self._render_composite()

    def _draw_markers_overlay(self, rgba: np.ndarray) -> np.ndarray:
        out = rgba.copy()
        for i, (mx, my) in enumerate(self.markers_a):
            dx = int(mx * self.display_scale)
            dy = int(my * self.display_scale)
            color = self._hex_to_bgr(MARKER_COLORS[i])
            cv2.circle(out, (dx, dy), 6, (*color, 255), 2, lineType=cv2.LINE_AA)
            cv2.circle(out, (dx, dy), 2, (255, 255, 255, 255), -1, lineType=cv2.LINE_AA)
        return out

    @staticmethod
    def _hex_to_bgr(hx: str) -> tuple[int, int, int]:
        hx = hx.lstrip("#")
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        return (r, g, b)  # RGBA: deixamos como RGB para os 3 primeiros canais

    # ----- save -------------------------------------------------------------

    def _save_result(self):
        if self.display_mask is None or self.base_a_full is None:
            return
        # escala a mascara de display para resolução total
        Ah, Aw = self.base_a_full.shape[:2]
        mask_full = cv2.resize(self.display_mask, (Aw, Ah), interpolation=cv2.INTER_LINEAR)
        mask_full = np.clip(mask_full, 0.0, 1.0)
        m = mask_full[:, :, None]
        warp_full = self._effective_full_warp()
        composed = (
            self.base_a_full.astype(np.float32) * (1 - m)
            + warp_full.astype(np.float32) * m
        ).astype(np.uint8)
        out_img = Image.fromarray(composed, mode="RGBA")

        default = "faceswap.png"
        if self.path_a:
            stem, _ = os.path.splitext(os.path.basename(self.path_a))
            default = f"{stem}_faceswap.png"

        path = filedialog.asksaveasfilename(
            title="Salvar resultado",
            defaultextension=".png",
            initialfile=default,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
        )
        if not path:
            return
        try:
            if path.lower().endswith((".jpg", ".jpeg")):
                out_img.convert("RGB").save(path, quality=95)
            else:
                out_img.save(path)
            messagebox.showinfo("Salvo", f"Imagem salva em:\n{path}")
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc))


# =================================================================== marker canvas

class MarkerCanvas:
    """Canvas com imagem zoomável e 3 marcadores arrastáveis.

    - Botão esquerdo: posiciona / arrasta marcadores.
    - Scroll do mouse: zoom centrado no cursor.
    - Botão do meio (ou Shift+esquerdo): pan da imagem.
    - Duplo clique no canvas: volta para 100% (fit).
    """

    HANDLE_RADIUS = 9
    CANVAS_W = 520
    CANVAS_H = 460
    MIN_ZOOM = 0.5
    MAX_ZOOM = 8.0

    def __init__(self, parent, title: str, pil_image: Image.Image, markers: list, on_change):
        self.pil_image = pil_image
        self.markers = list(markers)
        self.on_change = on_change
        self.dragging_index: int | None = None
        self._pan_origin: tuple[int, int] | None = None

        self.frame = tk.Frame(parent, bg=PANEL)
        header = tk.Frame(self.frame, bg=PANEL)
        header.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(
            header, text=title, style="Panel.TLabel", font=("Segoe UI", 12, "bold")
        ).pack(side="left")
        # botões de zoom
        zoom_box = tk.Frame(header, bg=PANEL)
        zoom_box.pack(side="right")
        ttk.Button(zoom_box, text="−", width=3, style="Ghost.TButton",
                   command=lambda: self._zoom_by(1 / 1.25)).pack(side="left")
        self.zoom_lbl = ttk.Label(zoom_box, text="100%", style="Panel.TLabel", width=6, anchor="center")
        self.zoom_lbl.pack(side="left", padx=4)
        ttk.Button(zoom_box, text="+", width=3, style="Ghost.TButton",
                   command=lambda: self._zoom_by(1.25)).pack(side="left")
        ttk.Button(zoom_box, text="Fit", width=4, style="Ghost.TButton",
                   command=self._reset_view).pack(side="left", padx=(6, 0))

        self.hint_lbl = ttk.Label(self.frame, text="", style="Panel.TLabel")
        self.hint_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        # fit base: tamanho onde a imagem cabe no canvas em zoom 1.0
        iw, ih = pil_image.size
        fit_w, fit_h, fit_scale = fit_size(iw, ih, self.CANVAS_W, self.CANVAS_H)
        self.fit_scale = fit_scale
        self.fit_w, self.fit_h = fit_w, fit_h

        self.zoom = 1.0  # multiplicador sobre fit_scale
        # offset = posição (em pixels de canvas) onde o canto (0,0) da imagem é renderizado
        self.offset_x = (self.CANVAS_W - fit_w) / 2
        self.offset_y = (self.CANVAS_H - fit_h) / 2

        self.canvas = tk.Canvas(
            self.frame, width=self.CANVAS_W, height=self.CANVAS_H,
            bg="#15151a", highlightthickness=0, cursor="crosshair",
        )
        self.canvas.pack(padx=12, pady=(0, 12))

        self._img_id = None
        self._tk_img: ImageTk.PhotoImage | None = None
        self._handle_ids: list[tuple[int, int, int]] = []

        # interação
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Shift-Button-1>", self._on_pan_start)
        self.canvas.bind("<Shift-B1-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel)
        self.canvas.bind("<Double-Button-1>", lambda _e: self._reset_view())

        self._render_image()
        self._redraw_markers()
        self._update_hint()
        self._update_zoom_label()

    def set_markers(self, markers: list):
        self.markers = list(markers)
        self._redraw_markers()
        self._update_hint()

    # ---- coords ----

    def _effective_scale(self) -> float:
        return self.fit_scale * self.zoom

    def _to_canvas(self, x_full: float, y_full: float) -> tuple[float, float]:
        s = self._effective_scale()
        return x_full * s + self.offset_x, y_full * s + self.offset_y

    def _to_full(self, x_canvas: float, y_canvas: float) -> tuple[float, float]:
        s = self._effective_scale()
        return (x_canvas - self.offset_x) / s, (y_canvas - self.offset_y) / s

    def _hit_test(self, x: float, y: float) -> int | None:
        for i, (mx, my) in enumerate(self.markers):
            dx, dy = self._to_canvas(mx, my)
            if (dx - x) ** 2 + (dy - y) ** 2 <= (self.HANDLE_RADIUS + 4) ** 2:
                return i
        return None

    # ---- render ----

    def _render_image(self):
        s = self._effective_scale()
        iw, ih = self.pil_image.size
        dw = max(1, int(round(iw * s)))
        dh = max(1, int(round(ih * s)))
        resample = Image.LANCZOS if s <= 1.0 else Image.BICUBIC
        scaled = self.pil_image.resize((dw, dh), resample)
        self._tk_img = ImageTk.PhotoImage(scaled)
        if self._img_id is None:
            self._img_id = self.canvas.create_image(
                self.offset_x, self.offset_y, image=self._tk_img, anchor="nw"
            )
        else:
            self.canvas.coords(self._img_id, self.offset_x, self.offset_y)
            self.canvas.itemconfigure(self._img_id, image=self._tk_img)
        # garante que markers ficam por cima
        self.canvas.tag_raise("marker")

    def _redraw_markers(self):
        for ids in self._handle_ids:
            for i in ids:
                self.canvas.delete(i)
        self._handle_ids.clear()
        for i, (mx, my) in enumerate(self.markers):
            x, y = self._to_canvas(mx, my)
            color = MARKER_COLORS[i]
            r = self.HANDLE_RADIUS
            ring = self.canvas.create_oval(
                x - r, y - r, x + r, y + r, outline=color, width=3, tags="marker"
            )
            dot = self.canvas.create_oval(
                x - 2, y - 2, x + 2, y + 2, fill="#ffffff", outline="", tags="marker"
            )
            label = self.canvas.create_text(
                x + r + 6, y, anchor="w", fill=color,
                text=MARKER_LABELS[i], font=("Segoe UI", 9, "bold"), tags="marker",
            )
            self._handle_ids.append((ring, dot, label))

    def _update_hint(self):
        if len(self.markers) < 3:
            label = MARKER_LABELS[len(self.markers)]
            color = MARKER_COLORS[len(self.markers)]
            self.hint_lbl.config(text=f"Clique para posicionar: {label}", foreground=color)
        else:
            self.hint_lbl.config(
                text="Pronto. Arraste para ajustar · scroll = zoom · botão do meio = arrastar",
                foreground=MUTED,
            )

    def _update_zoom_label(self):
        pct = int(round(self.zoom * 100))
        self.zoom_lbl.config(text=f"{pct}%")

    # ---- zoom & pan ----

    def _zoom_at(self, factor: float, cx: float, cy: float):
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-4:
            return
        # ponto sob o cursor em coords full
        fx, fy = self._to_full(cx, cy)
        self.zoom = new_zoom
        # ajusta offset para o cursor continuar sobre (fx, fy)
        s = self._effective_scale()
        self.offset_x = cx - fx * s
        self.offset_y = cy - fy * s
        self._render_image()
        self._redraw_markers()
        self._update_zoom_label()

    def _zoom_by(self, factor: float):
        self._zoom_at(factor, self.CANVAS_W / 2, self.CANVAS_H / 2)

    def _reset_view(self):
        self.zoom = 1.0
        self.offset_x = (self.CANVAS_W - self.fit_w) / 2
        self.offset_y = (self.CANVAS_H - self.fit_h) / 2
        self._render_image()
        self._redraw_markers()
        self._update_zoom_label()

    def _on_wheel(self, event):
        factor = 1.2 if event.delta > 0 else 1 / 1.2
        self._zoom_at(factor, event.x, event.y)

    def _on_pan_start(self, event):
        self._pan_origin = (event.x, event.y)
        # pan tem prioridade sobre arrastar marcador
        self.dragging_index = None

    def _on_pan_move(self, event):
        if self._pan_origin is None:
            return
        dx = event.x - self._pan_origin[0]
        dy = event.y - self._pan_origin[1]
        self._pan_origin = (event.x, event.y)
        self.offset_x += dx
        self.offset_y += dy
        # mover a imagem é barato — só atualiza coords e markers
        if self._img_id is not None:
            self.canvas.coords(self._img_id, self.offset_x, self.offset_y)
        self._redraw_markers()

    # ---- markers ----

    def _on_click(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit is not None:
            self.dragging_index = hit
            return
        if len(self.markers) >= 3:
            return
        fx, fy = self._to_full(event.x, event.y)
        # se clicou totalmente fora da imagem, ignora
        iw, ih = self.pil_image.size
        if fx < 0 or fy < 0 or fx >= iw or fy >= ih:
            return
        self.markers.append((fx, fy))
        self.dragging_index = len(self.markers) - 1
        self._redraw_markers()
        self._update_hint()
        self.on_change(list(self.markers))

    def _on_drag(self, event):
        if self.dragging_index is None:
            return
        fx, fy = self._to_full(event.x, event.y)
        iw, ih = self.pil_image.size
        fx = max(0, min(iw - 1, fx))
        fy = max(0, min(ih - 1, fy))
        self.markers[self.dragging_index] = (fx, fy)
        self._redraw_markers()
        self.on_change(list(self.markers))

    def _on_release(self, _event):
        self.dragging_index = None
        self._pan_origin = None


# =================================================================== main


def main():
    root = tk.Tk()
    app = FaceSwapApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
