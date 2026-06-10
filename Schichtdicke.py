import math
import os
import sys
import tkinter as tk
from tkinter import Menu, StringVar, ttk

import numpy as np
from PIL import Image, ImageOps, ImageTk

try:
    import photon_tools as pt
except Exception:
    pt = None

class ImageViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Browser (Notebook style)")
        self.root.geometry("1350x900")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.image_paths = []
        self.datasets = []
        self.filtered_images = []
        self.current_index = 0
        self.threshold_value = 0.0
        self._img_dir = None

        self.display_mode_var = StringVar(value="grid_sum")
        self.rows_var = tk.IntVar(value=3)
        self.cols_var = tk.IntVar(value=4)
        self.file_var = StringVar(value="")

        self._photo_refs = []
        self._img_loader_name = "scanbin_s4"

        self.setup_ui()
        self.load_images()

    def setup_ui(self):
        menu_bar = Menu(self.root)
        self.root.config(menu=menu_bar)
        file_menu = Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Pfad öffnen", command=self.open_path)
        file_menu.add_command(label="Bilder laden", command=self.load_images)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.exit_app)
        menu_bar.add_cascade(label="Datei", menu=file_menu)

        analyse_menu = Menu(menu_bar, tearoff=0)
        analyse_menu.add_command(label="Timetrace", command=self.on_timetrace)
        analyse_menu.add_command(label="Schichtdicke", command=self.on_schichtdicke)
        menu_bar.add_cascade(label="Analyse", menu=analyse_menu)

        hilfe_menu = Menu(menu_bar, tearoff=0)
        hilfe_menu.add_command(label="Über / Info", command=self.show_about)
        menu_bar.add_cascade(label="Hilfe", menu=hilfe_menu)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        control_top = tk.Frame(main_frame)
        control_top.pack(side="top", fill="x", pady=5)

        self.prev_btn_top = tk.Button(control_top, text="◀ Prev", command=self.prev_image)
        self.prev_btn_top.pack(side="left", padx=5)

        self.next_btn_top = tk.Button(control_top, text="Next ▶", command=self.next_image)
        self.next_btn_top.pack(side="left", padx=5)

        tk.Label(control_top, text="File:").pack(side="left", padx=(12, 4))
        self.file_combo = ttk.Combobox(control_top, state="readonly", width=8, textvariable=self.file_var)
        self.file_combo.bind("<<ComboboxSelected>>", self.on_file_select)
        self.file_combo.pack(side="left", padx=5)

        tk.Label(control_top, text="Display:").pack(side="left", padx=(12, 4))
        self.display_combo = ttk.Combobox(
            control_top,
            state="readonly",
            width=20,
            textvariable=self.display_mode_var,
            values=["all", "det0_det1", "detector0", "detector1", "sum", "grid_sum"],
        )
        self.display_combo.bind("<<ComboboxSelected>>", lambda _e: self.update_display())
        self.display_combo.pack(side="left", padx=5)

        tk.Label(control_top, text="Rows:").pack(side="left", padx=(12, 4))
        self.rows_spin = tk.Spinbox(control_top, from_=1, to=10, width=4, textvariable=self.rows_var, command=self.update_display)
        self.rows_spin.pack(side="left", padx=4)

        tk.Label(control_top, text="Cols:").pack(side="left", padx=(8, 4))
        self.cols_spin = tk.Spinbox(control_top, from_=1, to=10, width=4, textvariable=self.cols_var, command=self.update_display)
        self.cols_spin.pack(side="left", padx=4)

        tk.Label(control_top, text="Threshold:").pack(side="left", padx=(12, 4))
        self.threshold_scale = tk.Scale(
            control_top,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            length=230,
            command=self.update_threshold,
        )
        self.threshold_scale.set(0.0)
        self.threshold_scale.pack(side="left", padx=5)

        self.status_label = tk.Label(control_top, text="", anchor="e")
        self.status_label.pack(side="right", padx=10)

        tk.Button(control_top, text="Bilder speichern", command=self.save_images_png).pack(side="right", padx=5)

        self.image_container = tk.Frame(main_frame)
        self.image_container.pack(fill="both", expand=True, pady=10)

        self.image_canvas = tk.Canvas(self.image_container, highlightthickness=0)
        self.scrollbar_y = tk.Scrollbar(self.image_container, orient="vertical", command=self.image_canvas.yview)
        self.scrollbar_x = tk.Scrollbar(self.image_container, orient="horizontal", command=self.image_canvas.xview)
        self.image_canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)

        self.scrollbar_y.pack(side="right", fill="y")
        self.scrollbar_x.pack(side="bottom", fill="x")
        self.image_canvas.pack(side="left", fill="both", expand=True)

        self.image_frame = tk.Frame(self.image_canvas)
        self._canvas_window = self.image_canvas.create_window((0, 0), window=self.image_frame, anchor="nw")

        self.image_frame.bind("<Configure>", self._on_content_configure)
        self.image_canvas.bind("<Configure>", self._on_canvas_configure)
        self.image_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        control_bottom = tk.Frame(main_frame)
        control_bottom.pack(side="bottom", fill="x", pady=5)

        self.prev_btn_bottom = tk.Button(control_bottom, text="◀ Prev", command=self.prev_image)
        self.prev_btn_bottom.pack(side="left", padx=5)

        self.next_btn_bottom = tk.Button(control_bottom, text="Next ▶", command=self.next_image)
        self.next_btn_bottom.pack(side="left", padx=5)

        self.details_label = tk.Label(control_bottom, text="", justify="left", anchor="w")
        self.details_label.pack(side="left", padx=12)

    def open_path(self):
        if self._img_dir and os.path.isdir(self._img_dir):
            os.startfile(self._img_dir)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            fallback = os.path.join(script_dir, "img")
            os.makedirs(fallback, exist_ok=True)
            os.startfile(fallback)

    def load_images(self, img_dir=None):
        if img_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            img_dir = os.path.join(script_dir, "img")

        if not os.path.isdir(img_dir):
            self._set_empty_state(f"Ordner nicht gefunden: {img_dir}")
            return

        self._img_dir = img_dir

        allowed_extensions = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".img")
        image_paths = []
        for file_name in sorted(os.listdir(img_dir)):
            full_path = os.path.join(img_dir, file_name)
            if os.path.isfile(full_path) and file_name.lower().endswith(allowed_extensions):
                image_paths.append(full_path)

        if not image_paths:
            self._set_empty_state(f"Keine unterstützten Bilder in {img_dir}")
            return

        self.image_paths = image_paths
        self.datasets = []

        for path in self.image_paths:
            dataset = self.open_image(path)
            if dataset is not None:
                self.datasets.append(dataset)

        if not self.datasets:
            self._set_empty_state("Bilder gefunden, aber nicht lesbar")
            return

        self.current_index = 0
        self.file_combo["values"] = [f"{i + 1:03d}" for i in range(len(self.datasets))]
        self.file_var.set("001")

        self.status_label.config(text=f"{len(self.datasets)} Bild(er) geladen aus {os.path.basename(img_dir)}")
        self.update_display()

    def _set_empty_state(self, message):
        self.image_paths = []
        self.datasets = []
        self.file_combo["values"] = []
        self.file_var.set("")
        self.status_label.config(text=message)
        self.details_label.config(text="")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_canvas.yview_moveto(0.0)
        self.image_canvas.xview_moveto(0.0)

    def open_image(self, path):
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        try:
            if ext == ".img":
                if pt is not None:
                    try:
                        ds = pt.load_image(path, loader=self._img_loader_name)
                        det0 = np.asarray(ds.channels["detector0"], dtype=np.float32)
                        det1 = np.asarray(ds.channels["detector1"], dtype=np.float32)
                        return {
                            "path": path,
                            "name": os.path.basename(path),
                            "detector0": det0,
                            "detector1": det1,
                            "sum": det0 + det1,
                        }
                    except Exception:
                        pass
                return self.open_custom_img(path)

            arr = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
            zeros = np.zeros_like(arr, dtype=np.float32)
            return {
                "path": path,
                "name": os.path.basename(path),
                "detector0": arr,
                "detector1": zeros,
                "sum": arr,
            }
        except Exception:
            return None

    def _on_content_configure(self, _event=None):
        self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.image_canvas.itemconfigure(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if not self.datasets:
            return
        self.image_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def open_custom_img(self, path):
        with open(path, "rb") as file_obj:
            data = file_obj.read()

        if len(data) <= 88:
            raise ValueError(".img-Datei ist zu klein")

        header = data[:88]
        payload = data[88:]

        width = int.from_bytes(header[24:28], byteorder="big", signed=False)
        height = int.from_bytes(header[28:32], byteorder="big", signed=False)

        if width <= 0 or height <= 0:
            raise ValueError("Ungültige Bilddimensionen im .img-Header")

        raw_u16 = np.frombuffer(payload, dtype=">u2")
        pixels_per_frame = width * height
        total_values = (len(raw_u16) // pixels_per_frame) * pixels_per_frame
        if total_values == 0:
            raise ValueError("Keine vollständigen Frames in .img-Datei gefunden")

        n_frames = total_values // pixels_per_frame
        frames = raw_u16[:total_values].reshape(n_frames, height, width).astype(np.float32)

        det0_frames = frames[0::2]
        det1_frames = frames[1::2]

        detector0 = det0_frames.sum(axis=0) if det0_frames.size else np.zeros((height, width), dtype=np.float32)
        detector1 = det1_frames.sum(axis=0) if det1_frames.size else np.zeros((height, width), dtype=np.float32)

        return {
            "path": path,
            "name": os.path.basename(path),
            "detector0": detector0,
            "detector1": detector1,
            "sum": detector0 + detector1,
        }

    def update_threshold(self, value):
        self.threshold_value = float(value)
        self.update_display()

    def on_file_select(self, _event=None):
        value = self.file_var.get()
        if value and value.isdigit():
            idx = int(value) - 1
            if 0 <= idx < len(self.datasets):
                self.current_index = idx
                self.update_display()

    def _get_channel_image(self, dataset, channel):
        if channel == "detector0":
            return dataset["detector0"]
        if channel == "detector1":
            return dataset["detector1"]
        return dataset["sum"]

    def _count_spots_notebook(self, img: np.ndarray, threshold_fraction: float) -> int:
        """Notebook-equivalent spot counting from 06_full_screening_browser.ipynb.

        A pixel qualifies as a spot if it is strictly greater than every one of
        its (up to 8) neighbours and its value is at or above the threshold.
        """
        if img.ndim != 2 or img.size == 0:
            return 0
        max_val = float(np.nanmax(img))
        if max_val <= 0.0:
            return 0

        thresh_val = threshold_fraction * max_val
        padded = np.pad(img.astype(float), 1, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
        win_max = windows.max(axis=(-2, -1))
        win_second = np.partition(windows.reshape(*windows.shape[:2], -1), -2, axis=-1)[..., -2]
        local_max = (img == win_max) & (img > win_second) & (img >= thresh_val)
        return int(local_max.sum())

    def _count_spots(self, img, threshold_fraction):
        return self._count_spots_notebook(img, float(threshold_fraction))

    def _to_color_image(self, image_array):
        max_val = float(np.max(image_array)) if image_array.size else 0.0
        if max_val <= 0.0:
            norm_u8 = np.zeros_like(image_array, dtype=np.uint8)
        else:
            threshold_value = self.threshold_value * max_val
            masked = np.where(image_array >= threshold_value, image_array, 0.0) if self.threshold_value > 0.0 else image_array
            display_max = float(np.max(masked)) if masked.size else 0.0
            if display_max <= 0.0:
                norm_u8 = np.zeros_like(image_array, dtype=np.uint8)
            else:
                norm_u8 = np.clip((masked / display_max) * 255.0, 0, 255).astype(np.uint8)

        gray_img = Image.fromarray(norm_u8, mode="L")
        return ImageOps.colorize(gray_img, black="#000000", mid="#cc3300", white="#ffffcc")

    def _display_range(self, image_array):
        if image_array.size == 0:
            return 0.0, 0.0

        max_val = float(np.max(image_array))
        if max_val <= 0.0:
            return 0.0, 0.0

        threshold_value = self.threshold_value * max_val
        if self.threshold_value > 0.0:
            masked = np.where(image_array >= threshold_value, image_array, 0.0)
        else:
            masked = image_array

        disp_max = float(np.max(masked)) if masked.size else 0.0
        disp_min = float(np.min(masked)) if masked.size else 0.0
        return disp_min, disp_max

    def _add_intensity_scale(self, parent, min_value, max_value, height):
        scale_wrap = tk.Frame(parent)
        scale_wrap.pack(side="left", padx=(6, 0), fill="y")

        tk.Label(scale_wrap, text=f"{max_value:.1f}", font=("Arial", 8)).pack(anchor="w")

        grad_h = max(60, int(height))
        grad_arr = np.linspace(255, 0, grad_h, dtype=np.uint8).reshape(grad_h, 1)
        grad_img = Image.fromarray(grad_arr, mode="L").resize((18, grad_h), Image.Resampling.NEAREST)
        grad_color = ImageOps.colorize(grad_img, black="#000000", mid="#cc3300", white="#ffffcc")
        grad_photo = ImageTk.PhotoImage(grad_color)
        self._photo_refs.append(grad_photo)

        bar = tk.Label(scale_wrap, image=grad_photo, bd=1, relief="solid")
        bar.pack(anchor="w")
        bar.image = grad_photo

        tk.Label(scale_wrap, text=f"{min_value:.1f}", font=("Arial", 8)).pack(anchor="w")

    def _center_zoom_array(self, image_array, zoom_factor=5.5):
        if image_array.ndim != 2 or image_array.size == 0:
            return image_array

        if zoom_factor <= 1.0:
            return image_array

        height, width = image_array.shape
        crop_h = max(1, int(height / zoom_factor))
        crop_w = max(1, int(width / zoom_factor))
        y0 = (height - crop_h) // 2
        x0 = (width - crop_w) // 2
        return image_array[y0:y0 + crop_h, x0:x0 + crop_w]

    def show_image_viewer(self, image_array, title_text):
        color_img = self._to_color_image(image_array)
        src_w, src_h = color_img.size

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = int(screen_w * 0.88)
        win_h = int(screen_h * 0.88)

        win = tk.Toplevel(self.root)
        win.title(title_text)
        win.geometry(f"{win_w}x{win_h}")

        tk.Label(win, text=title_text, font=("Arial", 11, "bold")).pack(pady=(8, 2))

        canvas_frame = tk.Frame(win)
        canvas_frame.pack(fill="both", expand=True, padx=6, pady=2)

        sb_y = tk.Scrollbar(canvas_frame, orient="vertical")
        sb_x = tk.Scrollbar(canvas_frame, orient="horizontal")
        canvas = tk.Canvas(canvas_frame, bg="#1a1a1a", highlightthickness=0,
                           yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.config(command=canvas.yview)
        sb_x.config(command=canvas.xview)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        zoom_state = [1.0]
        photo_ref = [None]

        def redraw():
            z = zoom_state[0]
            new_w = max(1, int(src_w * z))
            new_h = max(1, int(src_h * z))
            resized = color_img.resize((new_w, new_h), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(resized)
            photo_ref[0] = photo
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas.configure(scrollregion=(0, 0, new_w, new_h))

        def on_mousewheel(event):
            cx = canvas.canvasx(event.x)
            cy = canvas.canvasy(event.y)
            old_zoom = zoom_state[0]
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            zoom_state[0] = max(0.05, min(30.0, old_zoom * factor))
            new_zoom = zoom_state[0]
            redraw()
            new_w = max(1, int(src_w * new_zoom))
            new_h = max(1, int(src_h * new_zoom))
            canvas.xview_moveto((cx * new_zoom / old_zoom - event.x) / new_w)
            canvas.yview_moveto((cy * new_zoom / old_zoom - event.y) / new_h)

        canvas.bind("<MouseWheel>", on_mousewheel)

        tk.Button(win, text="Schließen", command=win.destroy, width=12).pack(pady=(4, 10))

        def init_zoom():
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw > 1 and ch > 1 and src_w > 0 and src_h > 0:
                zoom_state[0] = min(cw / src_w, ch / src_h)
            redraw()

        win.after(50, init_zoom)

    def update_display(self):
        if not self.datasets:
            return

        mode = self.display_mode_var.get()
        if mode == "grid_sum":
            self.show_grid_view()
        else:
            self.show_single_or_multi_view(mode)

        self.file_var.set(f"{self.current_index + 1:03d}")
        self.image_canvas.yview_moveto(0.0)
        self.image_canvas.xview_moveto(0.0)

    def show_grid_view(self):
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        self._photo_refs = []
        cols = max(1, int(self.cols_var.get()))
        requested_rows = max(1, int(self.rows_var.get()))
        rows = max(requested_rows, math.ceil(len(self.datasets) / cols))

        for i, dataset in enumerate(self.datasets):
            row = i // cols
            col = i % cols

            img_array = dataset["sum"]
            color_img = self._to_color_image(img_array)
            color_img = color_img.resize((220, 220), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(color_img)
            self._photo_refs.append(photo)

            tile = tk.Frame(self.image_frame, relief="groove", bd=1)
            tile.grid(row=row, column=col, padx=5, pady=5)

            img_row = tk.Frame(tile)
            img_row.pack(padx=4, pady=4)

            label = tk.Label(img_row, image=photo)
            label.pack(side="left")
            label.bind(
                "<Button-1>",
                lambda _e, arr=img_array, name=dataset["name"]: self.show_image_viewer(arr, name),
            )

            disp_min, disp_max = self._display_range(img_array)
            self._add_intensity_scale(img_row, disp_min, disp_max, height=220)

            max_intensity = float(np.max(img_array)) if img_array.size else 0.0
            spots = self._count_spots(img_array, self.threshold_value)
            caption = tk.Label(tile, text=f"{i + 1:03d} | max: {max_intensity:.2f} | spots: {spots}")
            caption.pack()
            caption.bind(
                "<Button-1>",
                lambda _e, arr=img_array, name=dataset["name"]: self.show_image_viewer(arr, name),
            )

        for i in range(len(self.datasets), rows * cols):
            row = i // cols
            col = i % cols
            filler = tk.Frame(self.image_frame, width=220, height=250)
            filler.grid(row=row, column=col, padx=5, pady=5)

        self.details_label.config(
            text=f"Grid {rows} x {cols} (sum) for {len(self.datasets)} images | threshold={self.threshold_value:.2f}"
        )

    def show_single_or_multi_view(self, mode):
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        self._photo_refs = []
        dataset = self.datasets[self.current_index]

        if mode == "all":
            channels = ["detector0", "detector1", "sum"]
        elif mode == "det0_det1":
            channels = ["detector0", "detector1"]
        else:
            channels = [mode]

        panel = tk.Frame(self.image_frame)
        panel.pack(fill="both", expand=True)

        details_parts = []
        for channel in channels:
            image_array = self._get_channel_image(dataset, channel)
            color_img = self._to_color_image(image_array)
            color_img = color_img.resize((420, 420), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(color_img)
            self._photo_refs.append(photo)

            box = tk.Frame(panel, relief="groove", bd=1)
            box.pack(side="left", padx=8, pady=8)

            title = tk.Label(box, text=channel, font=("Arial", 11, "bold"))
            title.pack(pady=(4, 2))

            img_row = tk.Frame(box)
            img_row.pack(padx=4, pady=4)

            label = tk.Label(img_row, image=photo)
            label.pack(side="left")
            label.bind(
                "<Button-1>",
                lambda _e, arr=image_array, t=f"{dataset['name']} | {channel}": self.show_image_viewer(arr, t),
            )

            disp_min, disp_max = self._display_range(image_array)
            self._add_intensity_scale(img_row, disp_min, disp_max, height=420)

            max_intensity = float(np.max(image_array)) if image_array.size else 0.0
            spots = self._count_spots(image_array, self.threshold_value)
            info = tk.Label(
                box,
                text=(
                    f"max={max_intensity:.2f} | spots={spots} | "
                    f"thr={self.threshold_value:.2f} (>= {self.threshold_value * max_intensity:.2f})"
                ),
            )
            info.pack(pady=(2, 6))

            details_parts.append(f"{channel}: shape={image_array.shape}, max={max_intensity:.2f}")

        self.details_label.config(text=" | ".join(details_parts) + f" | file={dataset['name']}")

    def _get_output_dir(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def save_images_png(self):
        if not self.datasets:
            self.status_label.config(text="Keine Bilder zum Speichern.")
            return
        output_dir = self._get_output_dir()
        for dataset in self.datasets:
            color_img = self._to_color_image(dataset["sum"])
            name = os.path.splitext(dataset["name"])[0]
            color_img.save(os.path.join(output_dir, f"{name}.png"))
        self.status_label.config(text=f"{len(self.datasets)} PNG(s) gespeichert in output/")

    def exit_app(self):
        # quit() alone can leave the interpreter running in some launch modes.
        # destroy() + SystemExit ensures the app really stops.
        try:
            self.root.quit()
            self.root.destroy()
        finally:
            raise SystemExit(0)

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title("Über Image Browser")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text="Image Browser", font=("Arial", 14, "bold")).pack(pady=(18, 4), padx=28)
        tk.Label(win, text="Version 1.0.0", font=("Arial", 10)).pack(pady=(0, 10))
        tk.Label(
            win,
            text=(
                "Dieses Tool lädt Bilddateien aus dem lokalen img-Ordner\n"
                "und stellt sie ähnlich wie der Notebook-Image-Browser dar.\n\n"
                "Unterstützte Formate: .img (scanbin_s4), PNG, JPG, TIF, BMP\n\n"
                "Funktionen:\n"
                "  • Grid-Ansicht mit konfigurierbaren Rows/Cols\n"
                "  • Einzelkanal-Ansicht (detector0, detector1, sum)\n"
                "  • Threshold-Filter relativ zu Imax\n"
                "  • Spot-Zählung (lokale Maxima)\n"
                "  • Analyse-Tools: Timetrace, Schichtdicke"
            ),
            justify="left",
        ).pack(pady=(0, 16), padx=28)
        tk.Button(win, text="Schließen", command=win.destroy, width=12).pack(pady=(0, 16))

    def on_timetrace(self):
        win = tk.Toplevel(self.root)
        win.title("Timetrace")
        win.geometry("420x180")
        tk.Label(win, text="Timetrace", font=("Arial", 12, "bold")).pack(pady=(20, 6))
        tk.Label(win, text="Noch nicht implementiert.", font=("Arial", 10)).pack()

    def on_schichtdicke(self):
        if not self.datasets:
            self.status_label.config(text="Keine Daten für Schichtdicke-Analyse verfügbar")
            return

        win = tk.Toplevel(self.root)
        win.title("Schichtdicke")
        win.geometry("560x720")
        win.grab_set()

        idx_var = tk.IntVar(value=self.current_index)
        avg_var = tk.BooleanVar(value=False)

        # ── Titel ─────────────────────────────────────────────────────────────
        tk.Label(win, text="Schichtdicke-Analyse", font=("Arial", 12, "bold")).pack(pady=(12, 4))

        info_label = tk.Label(win, text="", justify="left")
        info_label.pack(pady=(0, 2))

        table_data = {"rows": [], "avg": False}

        table_header = tk.Frame(win)
        table_header.pack(fill="x", padx=12)
        tk.Label(table_header, text="Threshold-Tabelle", font=("Arial", 9, "bold")).pack(side="left")

        def save_table_csv():
            if not table_data["rows"]:
                return
            output_dir = self._get_output_dir()
            out_path = os.path.join(output_dir, "threshold_tabelle.csv")
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                header = "Threshold,Spots_avg\n" if table_data["avg"] else "Threshold,Spots\n"
                f.write(header)
                for row in table_data["rows"]:
                    f.write(",".join(str(v) for v in row) + "\n")

        tk.Button(table_header, text="CSV speichern", command=save_table_csv).pack(side="right")

        result_text = tk.Text(win, width=44, height=12, font=("Courier", 9))
        result_text.pack(padx=12, pady=4, fill="both", expand=True)
        result_text.config(state="disabled")

        nav_frame = tk.Frame(win)
        nav_frame.pack(pady=4)

        # ── Trennlinie ─────────────────────────────────────────────────────────
        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=12, pady=(6, 2))

        # ── Schichtdickenberechnung ────────────────────────────────────────────
        tk.Label(win, text="Schichtdickenberechnung", font=("Arial", 11, "bold")).pack(pady=(4, 2))

        input_frame = tk.Frame(win)
        input_frame.pack(padx=12, pady=2)

        tk.Label(input_frame, text="Konzentration (nM):").grid(row=0, column=0, sticky="e", padx=6, pady=2)
        conc_var = tk.StringVar(value="1.0")
        tk.Entry(input_frame, textvariable=conc_var, width=10).grid(row=0, column=1, sticky="w", padx=6, pady=2)

        tk.Label(input_frame, text="Fläche (µm²):").grid(row=1, column=0, sticky="e", padx=6, pady=2)
        area_var = tk.StringVar(value="400.0")
        tk.Entry(input_frame, textvariable=area_var, width=10).grid(row=1, column=1, sticky="w", padx=6, pady=2)

        calc_data = {"rows": [], "meta": {}}

        calc_header = tk.Frame(win)
        calc_header.pack(fill="x", padx=12, pady=(4, 0))
        tk.Label(calc_header, text="Ergebnisse", font=("Arial", 9, "bold")).pack(side="left")

        def save_calc_csv():
            if not calc_data["rows"]:
                return
            output_dir = self._get_output_dir()
            out_path = os.path.join(output_dir, "schichtdicke_ergebnisse.csv")
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                m = calc_data["meta"]
                f.write(f"# Threshold={m.get('thr', '')}, c={m.get('c_nM', '')} nM, A={m.get('A_um2', '')} µm²\n")
                f.write("Nr.,Dateiname,Spots,Schichtdicke_nm\n")
                for row in calc_data["rows"]:
                    f.write(",".join(str(v) for v in row) + "\n")
                f.write(f"Mittelwert,,, {m.get('mean_d', ''):.2f}\n")
                f.write(f"Std.-Abw.,,, {m.get('std_d', ''):.2f}\n")

        tk.Button(calc_header, text="CSV speichern", command=save_calc_csv).pack(side="right")

        calc_frame = tk.Frame(win)
        calc_frame.pack(padx=12, pady=2, fill="both", expand=True)
        calc_scrollbar = tk.Scrollbar(calc_frame, orient="vertical")
        calc_result_text = tk.Text(calc_frame, width=44, height=8, font=("Courier", 9),
                                   yscrollcommand=calc_scrollbar.set, state="disabled")
        calc_scrollbar.config(command=calc_result_text.yview)
        calc_scrollbar.pack(side="right", fill="y")
        calc_result_text.pack(side="left", fill="both", expand=True)

        def _set_calc_text(content):
            calc_result_text.config(state="normal")
            calc_result_text.delete("1.0", "end")
            calc_result_text.insert("1.0", content)
            calc_result_text.config(state="disabled")

        def calc_schichtdicke():
            N_A = 6.022e23
            try:
                c_nM = float(conc_var.get().replace(",", "."))
                A_um2 = float(area_var.get().replace(",", "."))
            except ValueError:
                _set_calc_text("Ungültige Eingabe.")
                return
            if c_nM <= 0 or A_um2 <= 0:
                _set_calc_text("Konzentration und Fläche müssen > 0 sein.")
                return

            rho = c_nM * 1e-9 * N_A / 1e15  # Moleküle/µm³
            thr = self.threshold_value

            lines = [f"Threshold: {thr:.2f}  |  c={c_nM} nM  |  A={A_um2} µm²",
                     f"{'Nr.':>4}  {'Spots':>6}  {'Schichtdicke (nm)':>18}",
                     "-" * 34]
            thicknesses = []
            for i, ds in enumerate(self.datasets):
                img_sum = self._get_channel_image(ds, "sum")
                n_spots = self._count_spots_notebook(img_sum, thr)
                d_nm = n_spots / (rho * A_um2) * 1000.0
                thicknesses.append(d_nm)
                lines.append(f"{i + 1:>4}  {n_spots:>6}  {d_nm:>18.2f}")

            values = np.array(thicknesses)
            mean_d = float(np.mean(values))
            std_d = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            lines.append("-" * 34)
            lines.append(f"Mittelwert: {mean_d:.2f} nm")
            lines.append(f"Std.-Abw.:  {std_d:.2f} nm")
            lines.append(f"n = {len(values)} Bilder")

            calc_data["rows"] = [
                (i + 1, self.datasets[i]["name"], n, round(d, 2))
                for i, (n, d) in enumerate(zip(
                    [self._count_spots_notebook(self._get_channel_image(ds, "sum"), thr) for ds in self.datasets],
                    thicknesses,
                ))
            ]
            calc_data["meta"] = {"thr": thr, "c_nM": c_nM, "A_um2": A_um2, "mean_d": mean_d, "std_d": std_d}

            _set_calc_text("\n".join(lines))

        tk.Button(win, text="Berechnen", command=calc_schichtdicke, width=14).pack(pady=4)

        # ── Schließen ──────────────────────────────────────────────────────────
        tk.Button(win, text="Schließen", command=win.destroy, width=12).pack(pady=(4, 12))

        # ── Refresh-Logik ──────────────────────────────────────────────────────
        def refresh():
            threshold_values = np.round(np.arange(0.00, 1.00, 0.05), 2)
            if avg_var.get():
                lines = ["Threshold  Spots(avg)", "---------------------"]
                rows = []
                for thr in threshold_values:
                    counts = [
                        self._count_spots_notebook(self._get_channel_image(ds, "sum"), float(thr))
                        for ds in self.datasets
                    ]
                    avg = float(np.mean(counts))
                    lines.append(f"{thr:>8.2f}  {avg:>10.1f}")
                    rows.append((round(float(thr), 2), round(avg, 1)))
                table_data["rows"] = rows
                table_data["avg"] = True
                info_label.config(text=f"Mittelwert über {len(self.datasets)} Bilder")
            else:
                idx = idx_var.get()
                dataset = self.datasets[idx]
                img_sum = self._get_channel_image(dataset, "sum")
                max_intensity = float(np.nanmax(img_sum)) if img_sum.size else 0.0
                lines = ["Threshold    Spots", "------------------"]
                rows = []
                for thr in threshold_values:
                    n_spots = self._count_spots_notebook(img_sum, float(thr))
                    lines.append(f"{thr:>8.2f}  {n_spots:>7d}")
                    rows.append((round(float(thr), 2), n_spots))
                table_data["rows"] = rows
                table_data["avg"] = False
                current_spots = self._count_spots_notebook(img_sum, float(self.threshold_value))
                info_label.config(
                    text=(
                        f"Datei: {dataset['name']}\n"
                        f"Aktueller Threshold: {self.threshold_value:.2f} | Spots: {current_spots}\n"
                        f"Max. Intensität (sum): {max_intensity:.2f}"
                    )
                )

            result_text.config(state="normal")
            result_text.delete("1.0", "end")
            result_text.insert("1.0", "\n".join(lines))
            result_text.config(state="disabled")

            prev_btn.config(state="disabled" if avg_var.get() or idx_var.get() == 0 else "normal")
            next_btn.config(state="disabled" if avg_var.get() or idx_var.get() == len(self.datasets) - 1 else "normal")

        def prev_img():
            if idx_var.get() > 0:
                idx_var.set(idx_var.get() - 1)
                refresh()

        def next_img():
            if idx_var.get() < len(self.datasets) - 1:
                idx_var.set(idx_var.get() + 1)
                refresh()

        prev_btn = tk.Button(nav_frame, text="◀ Prev", command=prev_img, width=10)
        prev_btn.pack(side="left", padx=8)

        avg_check = tk.Checkbutton(nav_frame, text="Mittelwert (alle Bilder)", variable=avg_var, command=refresh)
        avg_check.pack(side="left", padx=8)

        next_btn = tk.Button(nav_frame, text="Next ▶", command=next_img, width=10)
        next_btn.pack(side="left", padx=8)

        refresh()

    def prev_image(self):
        if not self.datasets:
            return
        self.current_index = max(0, self.current_index - 1)
        self.update_display()

    def next_image(self):
        if not self.datasets:
            return
        self.current_index = min(len(self.datasets) - 1, self.current_index + 1)
        self.update_display()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageViewer(root)
    root.mainloop()
