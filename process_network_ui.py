# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import os
import threading
import tkinter as tk
import tkinter.font as tkfont
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk

from network_common import (
    NetworkUiError,
    block_program,
    get_block_status,
    is_admin,
    list_processes,
    relaunch_as_admin,
    unblock_program,
)


class ProcessNetworkUi(tk.Tk):
    BG = "#08111f"
    PANEL = "#0f1b2d"
    PANEL_ALT = "#13243a"
    PANEL_SOFT = "#172d49"
    INPUT = "#0a1525"
    BORDER = "#233954"
    TEXT = "#eff5ff"
    MUTED = "#8ea3bf"
    ACCENT = "#54d2c5"
    ACCENT_HOVER = "#75e5db"
    ACCENT_PRESS = "#39b8ac"
    DANGER = "#f06d6d"
    DANGER_HOVER = "#ff8a8a"
    DANGER_PRESS = "#d85a5a"
    SUCCESS = "#67d49b"
    WARNING = "#f1c96a"
    INFO = "#74a7ff"

    def __init__(self) -> None:
        super().__init__()
        self.title("Process Network Toggle")
        self.geometry("1220x820")
        self.minsize(1040, 700)
        self.configure(bg=self.BG)

        self.filter_var = tk.StringVar()
        self.selected_path_var = tk.StringVar()
        self.duration_var = tk.IntVar(value=10)
        self.status_var = tk.StringVar(value="Готово к работе")
        self.selection_title_var = tk.StringVar(value="Процесс не выбран")
        self.selection_meta_var = tk.StringVar(value="Выберите процесс слева или укажите .exe вручную.")

        self._timers: dict[str, str] = {}
        self._selected_path: str | None = None
        self._refresh_in_progress = False
        self._fonts: dict[str, tkfont.Font] = {}

        self._setup_fonts()
        self._setup_styles()
        self._build_ui()

        self.after(100, self.on_refresh)
        self.log("Интерфейс готов. Выберите приложение и управляйте его сетью.")

    def _setup_fonts(self) -> None:
        base = tkfont.nametofont("TkDefaultFont").copy()
        base.configure(family="Segoe UI", size=10)
        self.option_add("*Font", base)
        self._fonts["title"] = tkfont.Font(family="Segoe UI Semibold", size=22)
        self._fonts["section"] = tkfont.Font(family="Segoe UI Semibold", size=12)
        self._fonts["label"] = tkfont.Font(family="Segoe UI", size=10)
        self._fonts["small"] = tkfont.Font(family="Segoe UI", size=9)
        self._fonts["button"] = tkfont.Font(family="Segoe UI Semibold", size=10)
        self._fonts["mono"] = tkfont.Font(family="Consolas", size=10)
        self._fonts["group"] = tkfont.Font(family="Segoe UI Semibold", size=10)

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.TEXT)
        style.configure("Shell.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.PANEL, relief="solid", borderwidth=1)
        style.configure("Hero.TFrame", background=self.PANEL_ALT, relief="solid", borderwidth=1)
        style.configure("Accent.TFrame", background=self.PANEL_ALT, relief="solid", borderwidth=1)
        style.configure("Title.TLabel", background=self.PANEL_ALT, foreground=self.TEXT, font=self._fonts["title"])
        style.configure("Section.TLabel", background=self.PANEL, foreground=self.TEXT, font=self._fonts["section"])
        style.configure("SectionAlt.TLabel", background=self.PANEL_ALT, foreground=self.TEXT, font=self._fonts["section"])
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.MUTED, font=self._fonts["label"])
        style.configure("MutedAlt.TLabel", background=self.PANEL_ALT, foreground=self.MUTED, font=self._fonts["label"])
        style.configure("BodyAlt.TLabel", background=self.PANEL_ALT, foreground=self.TEXT, font=self._fonts["label"])
        style.configure("Selection.TLabel", background=self.PANEL_ALT, foreground=self.TEXT, font=self._fonts["section"])
        style.configure(
            "Modern.TEntry",
            fieldbackground=self.INPUT,
            background=self.INPUT,
            foreground=self.TEXT,
            bordercolor=self.BORDER,
            darkcolor=self.BORDER,
            lightcolor=self.BORDER,
            insertcolor=self.TEXT,
            relief="flat",
            padding=(10, 8),
        )
        style.configure(
            "Modern.TSpinbox",
            fieldbackground=self.INPUT,
            background=self.INPUT,
            foreground=self.TEXT,
            bordercolor=self.BORDER,
            darkcolor=self.BORDER,
            lightcolor=self.BORDER,
            insertcolor=self.TEXT,
            relief="flat",
            arrowsize=12,
            padding=(8, 6),
        )
        for name, bg, hov, press, fg in (
            ("Primary.TButton", self.ACCENT, self.ACCENT_HOVER, self.ACCENT_PRESS, "#04161e"),
            ("Secondary.TButton", self.PANEL_SOFT, "#24415f", "#1c344d", self.TEXT),
            ("Danger.TButton", self.DANGER, self.DANGER_HOVER, self.DANGER_PRESS, "#2f0606"),
        ):
            style.configure(name, background=bg, foreground=fg, borderwidth=0, focusthickness=0, padding=(16, 10), font=self._fonts["button"])
            style.map(name, background=[("active", hov), ("pressed", press)])
        style.configure("Ghost.TButton", background=self.PANEL, foreground=self.MUTED, borderwidth=0, focusthickness=0, padding=(12, 8), font=self._fonts["label"])
        style.map("Ghost.TButton", background=[("active", self.PANEL_SOFT)], foreground=[("active", self.TEXT)])
        style.configure("Modern.Treeview", background=self.INPUT, fieldbackground=self.INPUT, foreground=self.TEXT, borderwidth=0, rowheight=34, relief="flat")
        style.map("Modern.Treeview", background=[("selected", "#14395b")])
        style.configure("Modern.Treeview.Heading", background=self.PANEL_SOFT, foreground=self.TEXT, borderwidth=0, relief="flat", padding=(10, 10), font=self._fonts["button"])
        style.map("Modern.Treeview.Heading", background=[("active", "#27496f")])
        style.configure("Thin.Horizontal.TProgressbar", troughcolor=self.INPUT, bordercolor=self.INPUT, background=self.ACCENT, lightcolor=self.ACCENT, darkcolor=self.ACCENT, thickness=5)
        style.configure("Modern.Vertical.TScrollbar", background=self.PANEL_SOFT, troughcolor=self.INPUT, bordercolor=self.INPUT, darkcolor=self.PANEL_SOFT, lightcolor=self.PANEL_SOFT, arrowcolor=self.TEXT, relief="flat")

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="Shell.TFrame", padding=20)
        shell.pack(fill="both", expand=True)

        hero = ttk.Frame(shell, style="Hero.TFrame", padding=(22, 20))
        hero.pack(fill="x")
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="Process Network Toggle", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(hero, text="Удобное управление сетевым доступом приложений для тестов reconnect, локальной отладки и проверки поведения клиента при обрывах.", style="MutedAlt.TLabel", wraplength=780, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.hero_badge = tk.Label(hero, textvariable=self.status_var, bg=self.PANEL_SOFT, fg=self.TEXT, font=self._fonts["small"], padx=12, pady=8)
        self.hero_badge.grid(row=0, column=1, rowspan=2, sticky="e")

        controls = ttk.Frame(shell, style="Card.TFrame", padding=16)
        controls.pack(fill="x", pady=(16, 14))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Фильтр", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.filter_entry = ttk.Entry(controls, textvariable=self.filter_var, style="Modern.TEntry", width=36)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=(12, 14))
        self.filter_entry.bind("<KeyRelease>", lambda _event: self.refresh_processes())
        self.refresh_button = ttk.Button(controls, text="Обновить", style="Secondary.TButton", command=self.on_refresh)
        self.refresh_button.grid(row=0, column=2, padx=4)
        ttk.Button(controls, text="Выбрать .exe", style="Secondary.TButton", command=self.on_choose_exe).grid(row=0, column=3, padx=(4, 0))

        content = ttk.Frame(shell, style="Shell.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=7)
        content.columnconfigure(1, weight=4)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="Card.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(4, weight=1)
        ttk.Label(left, text="Активные процессы", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Одинаковые процессы схлопнуты по одному .exe. Родительская строка позволяет сразу блокировать все экземпляры.", style="Muted.TLabel", wraplength=720, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 12))
        self.progress = ttk.Progressbar(left, mode="indeterminate", style="Thin.Horizontal.TProgressbar")
        self.progress.grid(row=2, column=0, sticky="ew")

        status_row = ttk.Frame(left, style="Card.TFrame")
        status_row.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        status_row.columnconfigure(1, weight=1)
        self.process_badge = tk.Label(status_row, text="Список приложений", bg="#143253", fg=self.INFO, font=self._fonts["small"], padx=10, pady=6)
        self.process_badge.grid(row=0, column=0, sticky="w")
        self.process_hint = ttk.Label(status_row, text="Здесь отображаются процессы с определяемым путем к .exe.", style="Muted.TLabel")
        self.process_hint.grid(row=0, column=1, sticky="w", padx=(12, 0))

        tree_wrap = ttk.Frame(left, style="Card.TFrame")
        tree_wrap.grid(row=4, column=0, sticky="nsew")
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_wrap, columns=("process_id", "blocked", "path"), show="tree headings", style="Modern.Treeview", selectmode="browse")
        self.tree.heading("#0", text="Процесс")
        self.tree.heading("process_id", text="PID")
        self.tree.heading("blocked", text="Сеть")
        self.tree.heading("path", text="Путь")
        self.tree.column("#0", width=250, anchor="w")
        self.tree.column("process_id", width=90, anchor="center")
        self.tree.column("blocked", width=90, anchor="center")
        self.tree.column("path", width=680, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)
        self.tree.tag_configure("group", font=self._fonts["group"], foreground=self.TEXT)
        self.tree.tag_configure("blocked", foreground=self.WARNING)
        self.tree.tag_configure("child", foreground="#d2e2ff")
        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview, style="Modern.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        right = ttk.Frame(content, style="Accent.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Панель действий", style="SectionAlt.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="Выбранное приложение", style="MutedAlt.TLabel").grid(row=1, column=0, sticky="w", pady=(14, 4))
        ttk.Label(right, textvariable=self.selection_title_var, style="Selection.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(right, textvariable=self.selection_meta_var, style="MutedAlt.TLabel", wraplength=320, justify="left").grid(row=3, column=0, sticky="w", pady=(6, 16))
        ttk.Label(right, text="Путь к .exe", style="MutedAlt.TLabel").grid(row=4, column=0, sticky="w")
        self.path_box = tk.Text(right, height=5, wrap="word", relief="flat", bd=0, bg=self.INPUT, fg=self.TEXT, insertbackground=self.TEXT, highlightthickness=1, highlightbackground=self.BORDER, highlightcolor=self.ACCENT, font=self._fonts["small"], padx=10, pady=10)
        self.path_box.grid(row=5, column=0, sticky="ew", pady=(8, 18))
        self.path_box.configure(state="disabled")
        settings = ttk.Frame(right, style="Accent.TFrame")
        settings.grid(row=6, column=0, sticky="ew")
        settings.columnconfigure(0, weight=1)
        ttk.Label(settings, text="Секунды для временного блока", style="MutedAlt.TLabel").grid(row=0, column=0, sticky="w")
        self.duration_spin = ttk.Spinbox(settings, from_=1, to=3600, width=8, textvariable=self.duration_var, style="Modern.TSpinbox")
        self.duration_spin.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Button(right, text="Блокировать на N секунд", style="Primary.TButton", command=self.on_block_temporary).grid(row=7, column=0, sticky="ew", pady=(18, 8))
        ttk.Button(right, text="Блокировать сеть", style="Danger.TButton", command=self.on_block).grid(row=8, column=0, sticky="ew", pady=8)
        ttk.Button(right, text="Снять блокировку", style="Secondary.TButton", command=self.on_unblock).grid(row=9, column=0, sticky="ew", pady=8)
        ttk.Button(right, text="Проверить статус", style="Ghost.TButton", command=self.on_status).grid(row=10, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(right, text="Для Electron и браузеров блокировка идет по .exe, поэтому удобно выбирать родительскую группу процесса целиком.", style="MutedAlt.TLabel", wraplength=320, justify="left").grid(row=11, column=0, sticky="w", pady=(20, 0))

        log_card = ttk.Frame(shell, style="Card.TFrame", padding=16)
        log_card.pack(fill="both", pady=(14, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        ttk.Label(log_card, text="Журнал действий", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        log_wrap = ttk.Frame(log_card, style="Card.TFrame")
        log_wrap.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        log_wrap.columnconfigure(0, weight=1)
        log_wrap.rowconfigure(0, weight=1)
        self.log_box = tk.Text(log_wrap, height=9, wrap="word", state="disabled", relief="flat", bd=0, bg="#050d18", fg=self.TEXT, insertbackground=self.TEXT, selectbackground="#1d4f7e", font=self._fonts["mono"], padx=12, pady=12)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log_box.yview, style="Modern.Vertical.TScrollbar")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=log_scroll.set)
        self.filter_entry.focus_set()
        self._write_path_preview("")

    def log(self, message: str) -> None:
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, message: str, tone: str = "info") -> None:
        palette = {"info": ("#143253", self.INFO), "warning": ("#3b2910", self.WARNING), "success": ("#123625", self.SUCCESS), "danger": ("#401818", self.DANGER_HOVER), "muted": (self.PANEL_SOFT, self.TEXT)}
        bg, fg = palette.get(tone, palette["info"])
        self.status_var.set(message)
        self.hero_badge.configure(bg=bg, fg=fg)
        self.process_badge.configure(bg=bg, fg=fg)

    def _write_path_preview(self, path: str) -> None:
        value = path or "Путь появится здесь после выбора процесса или файла."
        self.path_box.configure(state="normal")
        self.path_box.delete("1.0", "end")
        self.path_box.insert("1.0", value)
        self.path_box.configure(state="disabled")

    def _update_selection(self, title: str, meta: str, path: str | None = None) -> None:
        self.selection_title_var.set(title)
        self.selection_meta_var.set(meta)
        self._write_path_preview(path or self.selected_path_var.get().strip())

    def _set_loading(self, loading: bool, message: str | None = None) -> None:
        if loading:
            self.progress.start(12)
            self.refresh_button.state(["disabled"])
            self._set_status(message or "Обновление списка…", "info")
            self.process_hint.configure(text="Сканирую процессы и проверяю правила брандмауэра.")
        else:
            self.progress.stop()
            self.refresh_button.state(["!disabled"])

    def refresh_processes(self) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        self._set_loading(True, "Обновляю список процессов…")
        self.log("Загружаю процессы…")
        threading.Thread(target=self._refresh_processes_worker, args=(self.filter_var.get(), self.selected_path_var.get().strip()), daemon=True).start()

    def _refresh_processes_worker(self, filter_value: str, selected_path: str) -> None:
        try:
            processes = list_processes(filter_value)
            self.after(0, lambda: self._finish_refresh(processes=processes, selected_path=selected_path))
        except Exception as exc:
            self.after(0, lambda: self._finish_refresh(error=exc))

    def _finish_refresh(self, *, processes: list | None = None, selected_path: str = "", error: Exception | None = None) -> None:
        self._refresh_in_progress = False
        self._set_loading(False)
        if error is not None:
            self._set_status("Ошибка загрузки", "danger")
            self.process_hint.configure(text="Не удалось обновить список процессов.")
            self.log(f"Ошибка обновления: {error}")
            messagebox.showerror("Ошибка", str(error))
            return
        processes = processes or []
        self.tree.delete(*self.tree.get_children())
        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for item in processes:
            grouped[(item.process_name, item.path)].append(item)
        group_count = 0
        for (name, path), items in sorted(grouped.items(), key=lambda pair: (pair[0][0].lower(), pair[0][1].lower())):
            blocked = any(item.blocked for item in items)
            tags = ["group"] + (["blocked"] if blocked else [])
            parent = self.tree.insert("", "end", text=f"{name} ({len(items)})" if len(items) > 1 else name, values=("", "Да" if blocked else "Нет", path), open=False, tags=tuple(tags))
            if len(items) > 1:
                for item in sorted(items, key=lambda row: row.process_id):
                    child_tags = ["child"] + (["blocked"] if item.blocked else [])
                    self.tree.insert(parent, "end", text=name, values=(item.process_id, "Да" if item.blocked else "Нет", item.path), tags=tuple(child_tags))
            group_count += 1
        if selected_path:
            self.selected_path_var.set(selected_path)
        self._set_status("Список обновлен", "success")
        self.process_hint.configure(text=f"Найдено процессов: {len(processes)}. Групп по .exe: {group_count}.")
        self.log(f"Загружено процессов: {len(processes)}")
        if not self.selected_path_var.get().strip():
            self._update_selection("Процесс не выбран", "Выберите процесс слева или нажмите «Выбрать .exe», чтобы работать с файлом напрямую.")

    def on_refresh(self) -> None:
        self.refresh_processes()

    def on_choose_exe(self) -> None:
        selected = filedialog.askopenfilename(title="Выберите исполняемый файл", filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if selected:
            path = os.path.abspath(selected)
            self._selected_path = path
            self.selected_path_var.set(path)
            self._update_selection(os.path.basename(path), "Файл выбран вручную. Можно блокировать его даже без активного процесса.", path)
            self._set_status("Выбран .exe файл", "info")
            self.log(f"Выбран файл: {path}")

    def on_select_row(self, _event: object | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        values = item.get("values", ())
        if len(values) >= 3:
            path = str(values[2])
            pid = str(values[0]) if len(values) >= 1 else ""
            blocked = str(values[1]).lower() if len(values) >= 2 else "нет"
            self._selected_path = path
            self.selected_path_var.set(path)
            meta = f"Экземпляр процесса, PID {pid}. Сеть: {blocked}." if pid else f"Группа процессов по одному .exe. Сеть: {blocked}."
            self._update_selection(item.get("text", "Процесс"), meta, path)
            self._set_status("Процесс выбран", "info")

    def require_selected_path(self) -> str:
        path = (self.selected_path_var.get() or "").strip()
        if not path:
            raise NetworkUiError("Сначала выберите процесс в списке или укажите .exe файл.")
        return os.path.abspath(path)

    def on_block(self) -> None:
        try:
            path = self.require_selected_path()
            block_program(path)
            self._set_status("Сеть заблокирована", "danger")
            self._update_selection(os.path.basename(path), "Сетевой доступ заблокирован для выбранного .exe.", path)
            self.log(f"Сеть для '{path}' заблокирована.")
            self.refresh_processes()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def on_block_temporary(self) -> None:
        try:
            path = self.require_selected_path()
            seconds = int(self.duration_var.get())
            block_program(path)
            self._set_status(f"Временный блок на {seconds} сек.", "warning")
            self._update_selection(os.path.basename(path), f"Сетевой доступ временно заблокирован на {seconds} сек.", path)
            self.log(f"Сеть для '{path}' заблокирована на {seconds} сек.")
            self.refresh_processes()
            if path in self._timers:
                self.after_cancel(self._timers[path])
            self._timers[path] = self.after(seconds * 1000, lambda p=path: self._auto_unblock(p))
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _auto_unblock(self, path: str) -> None:
        self._timers.pop(path, None)
        try:
            unblock_program(path)
            self._set_status("Автоматическая разблокировка", "success")
            self._update_selection(os.path.basename(path), "Таймер завершен, сетевой доступ восстановлен.", path)
            self.log(f"Авторазблокировка: сеть для '{path}' возвращена.")
            self.refresh_processes()
        except Exception as exc:
            self.log(f"Ошибка авторазблокировки для '{path}': {exc}")

    def on_unblock(self) -> None:
        try:
            path = self.require_selected_path()
            if path in self._timers:
                self.after_cancel(self._timers.pop(path))
            unblock_program(path)
            self._set_status("Сеть разблокирована", "success")
            self._update_selection(os.path.basename(path), "Сетевой доступ восстановлен.", path)
            self.log(f"Сеть для '{path}' разблокирована.")
            self.refresh_processes()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def on_status(self) -> None:
        try:
            path = self.require_selected_path()
            status = get_block_status(path)
            blocked_text = "заблокирована" if status.is_blocked else "не заблокирована"
            self._set_status("Статус обновлен", "warning" if status.is_blocked else "success")
            self._update_selection(os.path.basename(path), f"Проверка завершена: сеть {blocked_text}.", path)
            self.log(f"Статус '{path}': сеть {blocked_text}.")
            self.refresh_processes()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))


def main() -> None:
    if not is_admin():
        if not relaunch_as_admin():
            raise SystemExit("Не удалось запросить права администратора.")
        return
    app = ProcessNetworkUi()
    app.mainloop()


if __name__ == "__main__":
    main()
