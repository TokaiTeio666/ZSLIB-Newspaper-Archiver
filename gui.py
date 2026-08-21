import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
from scraper import NewspaperScraper


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ZSLIB 近代报纸采集工具")
        self.root.geometry("700x550")
        self.root.resizable(True, True)
        self.scraper = None
        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- 搜索关键字 ----
        row0 = ttk.Frame(main_frame)
        row0.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row0, text="搜索关键字:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(row0, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.search_entry.focus_set()

        # ---- 输出目录 ----
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row1, text="输出目录:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar(value="采集结果")
        self.output_entry = ttk.Entry(row1, textvariable=self.output_var, width=40)
        self.output_entry.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        ttk.Button(row1, text="浏览...", command=self._browse_output).pack(
            side=tk.LEFT
        )

        # ---- 运行选项 ----
        row_opts = ttk.Frame(main_frame)
        row_opts.pack(fill=tk.X, pady=(0, 6))
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row_opts,
            text="后台静默运行（无浏览器窗口；首次登录请先取消勾选）",
            variable=self.headless_var,
        ).pack(side=tk.LEFT)

        # ---- 控制按钮 ----
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=(0, 6))
        self.start_btn = ttk.Button(row2, text="开始采集", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.stop_btn = ttk.Button(
            row2, text="停止", command=self._stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT)

        # ---- 日志区域 ----
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.NORMAL
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # ---- 状态栏 ----
        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 2),
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _log(self, msg):
        self.root.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)

    def _start(self):
        search_str = self.search_var.get().strip()
        if not search_str:
            self._log("请输入搜索关键字。")
            return

        output_dir = self.output_var.get().strip() or "采集结果"

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("运行中...")

        self.scraper = NewspaperScraper(
            search_str=search_str,
            output_dir=output_dir,
            log_callback=self._log,
            headless=self.headless_var.get(),
        )
        thread = threading.Thread(target=self._run_scraper, daemon=True)
        thread.start()

    def _run_scraper(self):
        try:
            self.scraper.run()
        finally:
            self.root.after(0, self._on_done)

    def _on_done(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_var.set("就绪")

    def _stop(self):
        if self.scraper:
            self.scraper.quit()
            self._log("正在停止...")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.scraper:
            self.scraper.quit()
        self.root.destroy()


if __name__ == "__main__":
    App().run()
