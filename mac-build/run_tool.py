import os, sys, random
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, ttk, colorchooser, messagebox

try:
    from PIL import Image, ImageOps, ImageFilter, ImageTk
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageOps, ImageFilter, ImageTk

# --- 颜色主题 ---
BG       = "#f5f7fa"
CARD_BG  = "#ffffff"
PRIMARY  = "#4a90d9"
PRIMARY_DARK = "#357abd"
SUCCESS  = "#52c41a"
SUCCESS_DARK = "#3da50f"
WARN     = "#fa8c16"
WARN_DARK = "#d87a12"
BORDER   = "#e0e4ea"
TEXT     = "#333333"
TEXT2    = "#888888"
HOVER_BG = "#e8f0fe"

# --- 悬停提示类 ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left',
                       background="#333333", foreground="#ffffff",
                       relief='flat', borderwidth=0,
                       font=("Arial", 9), padx=10, pady=6,
                       wraplength=250)
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class SmartResizer:
    def __init__(self, root):
        self.root = root
        self.root.title("小包图片助手")
        self.root.geometry("560x750")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.file_list = []
        self.bg_color = None
        self.current_preview_path = None
        self.setup_ui()

    def make_section(self, parent, title, num):
        frame = tk.LabelFrame(parent, text=f" {num}. {title} ",
                              bg=CARD_BG, fg=PRIMARY,
                              font=("Arial", 10, "bold"),
                              padx=10, pady=8, relief="groove", bd=1,
                              highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="x", padx=16, pady=(0, 6))
        return frame

    def make_button(self, parent, text, command, bg_color, hover_color, font_size=10, height=None):
        btn = tk.Button(parent, text=text, command=command,
                        bg=bg_color, fg="white", activebackground=hover_color, activeforeground="white",
                        font=("Arial", font_size, "bold"),
                        relief="flat", bd=0, cursor="hand2", padx=12,
                        highlightthickness=0)
        if height:
            btn.configure(height=height)
        btn.bind("<Enter>", lambda e, b=btn, c=hover_color: b.configure(bg=c))
        btn.bind("<Leave>", lambda e, b=btn, c=bg_color: b.configure(bg=c))
        return btn

    def setup_ui(self):
        # 1
        f1 = self.make_section(self.root, "导入素材", "1")
        self.make_button(f1, "选择图片文件（支持多选）", self.select_files,
                         PRIMARY, PRIMARY_DARK).pack(fill="x")
        self.lbl_count = tk.Label(f1, text="待处理素材：0 张", bg=CARD_BG, fg=TEXT2,
                                   font=("Arial", 9))
        self.lbl_count.pack(pady=(4, 0))

        # 2
        f2 = self.make_section(self.root, "设置分辨率", "2")
        row_size = tk.Frame(f2, bg=CARD_BG); row_size.pack(fill="x")

        self.sizes = ["329x480", "300x250", "800x800", "1200x627", "1200x628", "1080x1920", "1920x1080", "自定义"]
        self.size_var = tk.StringVar(value=self.sizes[0])

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=CARD_BG, background=PRIMARY, borderwidth=0)

        self.cb_size = ttk.Combobox(row_size, textvariable=self.size_var, values=self.sizes,
                                     state="readonly", width=14, font=("Arial", 9))
        self.cb_size.pack(side="left", padx=(0, 8))
        self.cb_size.bind("<<ComboboxSelected>>", self.on_size_change)

        self.custom_f = tk.Frame(row_size, bg=CARD_BG)
        tk.Label(self.custom_f, text="宽:", bg=CARD_BG, fg=TEXT, font=("Arial", 9)).pack(side="left")
        self.ent_w = tk.Entry(self.custom_f, width=6, font=("Arial", 9), relief="solid", bd=1,
                               highlightbackground=BORDER, highlightthickness=1)
        self.ent_w.pack(side="left", padx=(2, 6))
        self.ent_w.bind("<KeyRelease>", lambda e: self.refresh_preview())
        tk.Label(self.custom_f, text="高:", bg=CARD_BG, fg=TEXT, font=("Arial", 9)).pack(side="left")
        self.ent_h = tk.Entry(self.custom_f, width=6, font=("Arial", 9), relief="solid", bd=1,
                               highlightbackground=BORDER, highlightthickness=1)
        self.ent_h.pack(side="left", padx=2)
        self.ent_h.bind("<KeyRelease>", lambda e: self.refresh_preview())

        # 3
        f3 = self.make_section(self.root, "处理模式", "3")
        modes_info = {
            "拉伸": "无视比例，直接将图片强行填满目标尺寸（图片会变形）。",
            "裁切": "保持比例放大，填满尺寸并切掉多余部分（类似头像效果）。",
            "智能填充": "图片完整显示，自动识别图片边缘颜色来填充留白部分。",
            "背景虚化": "图片完整显示，背景使用原图的高斯模糊效果填充。",
            "手动选色": "图片完整显示，留白部分由你点击下方颜色框自行定义。"
        }
        self.mode_var = tk.StringVar(value="智能填充")
        row_a = tk.Frame(f3, bg=CARD_BG); row_a.pack(fill="x")
        row_b = tk.Frame(f3, bg=CARD_BG); row_b.pack(fill="x", pady=(2, 0))

        for i, (m, info) in enumerate(modes_info.items()):
            rb = tk.Radiobutton(row_a if i < 3 else row_b, text=m, variable=self.mode_var, value=m,
                                command=self.on_mode_click, cursor="hand2",
                                bg=CARD_BG, fg=TEXT, selectcolor="#e8f0fe",
                                activebackground=CARD_BG, activeforeground=PRIMARY,
                                font=("Arial", 9, "bold"), highlightthickness=0, bd=0)
            rb.pack(side="left", padx=(0, 12))
            ToolTip(rb, info)

        self.extra_f = tk.Frame(f3, bg=CARD_BG)
        self.extra_f.pack(fill="x", pady=(4, 0))
        self.btn_color = self.make_button(self.extra_f, "选色", self.choose_color,
                                           "#6c5ce7", "#5a4bd1", font_size=9)
        self.lbl_color = tk.Label(self.extra_f, text="    ", bg="white", width=3, relief="solid", bd=1)
        self.lbl_blur = tk.Label(self.extra_f, text=" 虚化强度:", bg=CARD_BG, fg=TEXT2, font=("Arial", 9))
        self.blur_scale = tk.Scale(self.extra_f, from_=0.1, to=1.0, resolution=0.1,
                                    orient="horizontal", length=120, showvalue=False,
                                    bg=CARD_BG, fg=TEXT, troughcolor=HOVER_BG,
                                    highlightthickness=0, bd=0, activebackground=PRIMARY,
                                    command=lambda e: self.refresh_preview())
        self.blur_scale.set(0.5)

        # 4
        f4 = self.make_section(self.root, "效果预览", "4")
        self.pre_canvas = tk.Label(f4, text="请先选择图片", bg="#f0f2f5", fg=TEXT2,
                                    font=("Arial", 10), relief="flat", bd=0)
        self.pre_canvas.pack(fill="both", expand=True, ipady=20)
        btn_row = tk.Frame(f4, bg=CARD_BG); btn_row.pack(fill="x", pady=(6, 0))
        self.make_button(btn_row, "随机预览", self.show_preview,
                         WARN, WARN_DARK).pack(side="left", fill="x", expand=True, padx=(0, 4))

        # run
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=16, pady=(6, 12))
        self.make_button(bottom, "开始批量转换", self.process_all,
                         SUCCESS, SUCCESS_DARK, font_size=12, height=1).pack(fill="x", ipady=4)
        ToolTip(self.root.winfo_children()[-1], "将所有已选图片按当前设置进行批量处理")

    def on_size_change(self, e):
        if self.size_var.get() == "自定义": self.custom_f.pack(side="left", padx=4)
        else: self.custom_f.pack_forget()
        self.refresh_preview()

    def on_mode_click(self):
        m = self.mode_var.get()
        self.btn_color.pack_forget(); self.lbl_color.pack_forget()
        self.lbl_blur.pack_forget(); self.blur_scale.pack_forget()
        if m == "手动选色":
            self.btn_color.pack(side="left", padx=(0, 6)); self.lbl_color.pack(side="left")
        elif m == "背景虚化":
            self.lbl_blur.pack(side="left"); self.blur_scale.pack(side="left", padx=4)
        self.refresh_preview()

    def select_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("图片", "*.jpg *.jpeg *.png *.webp *.bmp")])
        if paths:
            self.file_list = list(paths)
            self.lbl_count.config(text=f"待处理素材：{len(self.file_list)} 张")
            self.show_preview()

    def choose_color(self):
        c = colorchooser.askcolor()[1]
        if c: self.bg_color = c; self.lbl_color.config(bg=c); self.refresh_preview()

    def get_smart_color(self, img):
        t = img.convert("RGB").resize((10, 10))
        px = [t.getpixel((0,0)), t.getpixel((9,0)), t.getpixel((0,9)), t.getpixel((9,9))]
        return tuple(sum(c)//4 for c in zip(*px))

    def apply_effect(self, img_path):
        try:
            if self.size_var.get() == "自定义":
                tw = int(self.ent_w.get() or 800); th = int(self.ent_h.get() or 800)
            else:
                tw, th = map(int, self.size_var.get().split('x'))
        except: tw, th = 800, 800
        img = Image.open(img_path).convert("RGBA"); mode = self.mode_var.get()
        if mode == "拉伸": return img.resize((tw, th), Image.Resampling.LANCZOS)
        if mode == "裁切": return ImageOps.fit(img, (tw, th), Image.Resampling.LANCZOS)
        cp = img.copy(); cp.thumbnail((tw, th), Image.Resampling.LANCZOS); iw, ih = cp.size
        if mode == "背景虚化":
            res = ImageOps.fit(img, (tw, th)).filter(ImageFilter.GaussianBlur(self.blur_scale.get()*30))
        else:
            res = Image.new("RGBA", (tw, th), self.bg_color if mode == "手动选色" and self.bg_color else self.get_smart_color(img))
        res.paste(cp, ((tw-iw)//2, (th-ih)//2), cp); return res

    def refresh_preview(self):
        if self.file_list and self.current_preview_path: self._render(self.current_preview_path)

    def show_preview(self):
        if self.file_list: self.current_preview_path = random.choice(self.file_list); self._render(self.current_preview_path)

    def _render(self, path):
        try:
            r = self.apply_effect(path); r.thumbnail((400, 400))
            self.tk_img = ImageTk.PhotoImage(r); self.pre_canvas.config(image=self.tk_img, text="")
        except: pass

    def process_all(self):
        if not self.file_list: messagebox.showwarning("提示", "请先选择图片文件！"); return
        out = os.path.join(os.path.expanduser("~"), "Desktop", "处理结果")
        os.makedirs(out, exist_ok=True)
        ds = datetime.now().strftime("%y%m%d")
        try:
            v = self.size_var.get(); rs = f"{self.ent_w.get()}-{self.ent_h.get()}" if v == "自定义" else v.replace("x", "-")
        except: rs = "800-800"
        for i, p in enumerate(self.file_list, 1):
            self.apply_effect(p).convert("RGB").save(os.path.join(out, f"{ds}_{rs}_{i:02d}.jpg"), "JPEG", quality=90)
        messagebox.showinfo("成功", f"处理完成！图片在桌面【处理结果】文件夹中")

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartResizer(root)
    root.mainloop()
