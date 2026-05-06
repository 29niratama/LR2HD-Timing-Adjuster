import sys, json, re, threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

try:
    import pymem, pymem.process
except ImportError:
    import subprocess; subprocess.run([sys.executable, "-m", "pip", "install", "pymem"])
    import pymem, pymem.process

try:
    import keyboard as kb
    HAS_KB = True
except ImportError:
    HAS_KB = False

# PyInstaller exe対応
if getattr(sys, "frozen", False):
    CONFIG_PATH = Path(sys.executable).parent / "config.json"
else:
    CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "process_name": "LRHbody.exe",
    "timing_address": 1046668,
    "auto_adjust_address": 1046664,
    "step": 1,
    "hotkeys_enabled": True,
    "presets": [
        {"name": "NORMAL", "value": 0, "hotkey": "num 7"},
        {"name": "EARLY", "value": -10, "hotkey": "num 8"},
        {"name": "LATE", "value": 10, "hotkey": "num 9"},
    ],
    "hotkey_minus": "num 1",
    "hotkey_plus": "num 3",
    "hotkey_direct_key": "num 5",
    "hotkey_direct_val": 0,
    "hotkey_auto_off": "num 0",
    "hotkey_auto_on": "num 2",
    "hotkey_auto_silent": "num .",
}

BG="#1e1e2e"; BG2="#313244"; BG3="#45475a"
FG="#cdd6f4"; ACC="#89b4fa"; RED="#f38ba8"
GRN="#a6e3a1"; YEL="#f9e2af"; PUR="#cba6f7"; GRAY="#6c7086"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items(): cfg.setdefault(k, v)
        return cfg
    save_config(DEFAULT_CONFIG); return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class LR2Mem:
    def __init__(self, name):
        self.pm = None; self.name = name; self.ok = False
    def attach(self):
        try: self.pm = pymem.Pymem(self.name); self.ok = True; return True
        except: self.ok = False; return False
    def read(self, a):
        try: return self.pm.read_int(a)
        except: self.ok = False; return None
    def write(self, a, v):
        try: self.pm.write_int(a, v); return True
        except: self.ok = False; return False

def mk_btn(p, t, cmd, fg=FG, bg=BG2, font=("Consolas", 9), **kw):
    return tk.Button(p, text=t, command=cmd, bg=bg, fg=fg, relief="flat",
                     font=font, pady=3, cursor="hand2",
                     activebackground=BG3, activeforeground=FG, **kw)

def mk_lbl(p, t="", fg=FG, font=("Consolas", 9), **kw):
    return tk.Label(p, text=t, bg=BG, fg=fg, font=font, **kw)

def mk_ent(p, var, w=7, justify="center"):
    return tk.Entry(p, textvariable=var, width=w, bg=BG2, fg=FG,
                    relief="flat", font=("Consolas", 9),
                    justify=justify, insertbackground=FG)

def sep(parent):
    tk.Frame(parent, bg=BG2, height=1).pack(fill="x", padx=8, pady=3)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LR2HD Timing Adjuster")
        self.resizable(False, False); self.configure(bg=BG)
        self.cfg = load_config()
        self.mem = LR2Mem(self.cfg["process_name"])
        self._hk = []; self._preset_btns = []; self._active = -1
        self._build(); self._connect(); self._reg_hk(); self._poll()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        P = 8
        sf = tk.Frame(self, bg=BG); sf.pack(fill="x", padx=P, pady=(P, 0))
        self.dot = tk.Label(sf, text="●", fg=RED, bg=BG, font=("Consolas", 10))
        self.dot.pack(side="left")
        self.stlbl = mk_lbl(sf, "disconnected", fg=GRAY); self.stlbl.pack(side="left", padx=4)
        mk_btn(sf, "connect", self._connect).pack(side="right")

        tf = tk.Frame(self, bg=BG2); tf.pack(fill="x", padx=P, pady=(6, 0))
        mk_lbl(tf, "TIMING", fg=GRAY).pack(pady=(4, 0))
        self.tv = tk.StringVar(value="---")
        tk.Label(tf, textvariable=self.tv, fg=ACC, bg=BG2,
                 font=("Consolas", 32, "bold")).pack(pady=(0, 4))

        cf = tk.Frame(self, bg=BG); cf.pack(padx=P, pady=6)
        mk_btn(cf, "  ー  ", self._minus, fg=RED, font=("Consolas", 13, "bold")).pack(side="left", padx=4)
        sf2 = tk.Frame(cf, bg=BG); sf2.pack(side="left", padx=4)
        mk_lbl(sf2, "STEP", fg=GRAY, font=("Consolas", 7)).pack()
        self.stepv = tk.StringVar(value=str(self.cfg.get("step", 1)))
        sp = tk.Spinbox(sf2, from_=1, to=100, textvariable=self.stepv, width=4,
                      bg=BG2, fg=FG, relief="flat", font=("Consolas", 11),
                      justify="center", buttonbackground=BG2, command=self._save_step)
        sp.pack(); sp.bind("<FocusOut>", lambda e: self._save_step())
        mk_btn(cf, "  ＋  ", self._plus, fg=GRN, font=("Consolas", 13, "bold")).pack(side="left", padx=4)

        sep(self)

        ph = tk.Frame(self, bg=BG); ph.pack(fill="x", padx=P)
        mk_lbl(ph, "PRESET", fg=GRAY, font=("Consolas", 7), width=7, anchor="w").pack(side="left", padx=2)
        mk_lbl(ph, "name", fg=GRAY, font=("Consolas", 7), width=8, anchor="w").pack(side="left", padx=2)
        mk_lbl(ph, "value", fg=GRAY, font=("Consolas", 7), width=6, anchor="w").pack(side="left", padx=2)
        mk_lbl(ph, "hotkey", fg=GRAY, font=("Consolas", 7), width=9, anchor="w").pack(side="left", padx=2)
        mk_btn(ph, "+", self._add_preset, font=("Consolas", 8)).pack(side="right", padx=2)

        self._pf = tk.Frame(self, bg=BG); self._pf.pack(fill="x", padx=P)
        self._build_presets()

        sep(self)

        df = tk.Frame(self, bg=BG); df.pack(fill="x", padx=P, pady=(0, 2))
        mk_lbl(df, "direct:", fg=GRAY).pack(side="left")
        self.dirv = tk.StringVar()
        e = mk_ent(df, self.dirv, w=7); e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self._direct())
        mk_btn(df, "SET", self._direct).pack(side="left")

        sep(self)

        af_top = tk.Frame(self, bg=BG); af_top.pack(fill="x", padx=P, pady=(2, 2))
        mk_lbl(af_top, "Auto Adjust:", fg=GRAY).pack(side="left")
        self.aav = tk.StringVar(value="OFF")
        self.aalbl = mk_lbl(af_top, textvariable=self.aav, fg=YEL, font=("Consolas", 10, "bold"))
        self.aalbl.pack(side="left", padx=5)

        af_btn = tk.Frame(self, bg=BG); af_btn.pack(fill="x", padx=P, pady=(0, 2))
        mk_btn(af_btn, "OFF", lambda: self._set_auto_val(0), fg=RED, width=6).pack(side="left", padx=2, expand=True, fill="x")
        mk_btn(af_btn, "ON", lambda: self._set_auto_val(1), fg=GRN, width=6).pack(side="left", padx=2, expand=True, fill="x")
        mk_btn(af_btn, "SILENT", lambda: self._set_auto_val(2), fg=PUR, width=6).pack(side="left", padx=2, expand=True, fill="x")

        sep(self)

        bf = tk.Frame(self, bg=BG); bf.pack(fill="x", padx=P, pady=(0, 2))
        self.hk_on = self.cfg.get("hotkeys_enabled", True)
        self.hklbl = tk.StringVar(value="Hotkeys: ON" if self.hk_on else "Hotkeys: OFF")
        self.hkbtn = mk_btn(bf, "", self._toggle_hk, fg=GRN if self.hk_on else RED,
                          textvariable=self.hklbl)
        self.hkbtn.pack(side="left", padx=2)
        mk_btn(bf, "Hotkey Settings", self._hk_settings).pack(side="left", padx=2)

        cf2 = tk.Frame(self, bg=BG); cf2.pack(fill="x", padx=P, pady=(2, P))
        mk_btn(cf2, "Save Config", self._save_cfg_as).pack(side="left", padx=2)
        mk_btn(cf2, "Load Config", self._load_cfg_from).pack(side="left", padx=2)

    def _build_presets(self):
        for w in self._pf.winfo_children(): w.destroy()
        self._preset_btns.clear()
        for i, p in enumerate(self.cfg.get("presets", [])):
            row = tk.Frame(self._pf, bg=BG); row.pack(fill="x", pady=1)
            b = mk_btn(row, "SET", lambda idx=i: self._apply_preset(idx), font=("Consolas", 8))
            b.pack(side="left", padx=2)
            self._preset_btns.append(b)

            nv = tk.StringVar(value=p.get("name", f"P{i+1}"))
            e = mk_ent(row, nv, w=8, justify="left"); e.pack(side="left", padx=2)
            e.bind("<FocusOut>", lambda ev, idx=i, v=nv: self._sp(idx, "name", v.get()))

            vv = tk.StringVar(value=str(p.get("value", 0)))
            e2 = mk_ent(row, vv, w=6); e2.pack(side="left", padx=2)
            e2.bind("<FocusOut>", lambda ev, idx=i, v=vv: self._sp_int(idx, "value", v.get()))
            e2.bind("<Return>", lambda ev, idx=i: self._apply_preset(idx))

            hv = tk.StringVar(value=p.get("hotkey", ""))
            hbtn = mk_btn(row, hv.get() or "(none)", None, fg=ACC, font=("Consolas", 8))
            hbtn.pack(side="left", padx=2)
            hbtn.config(command=lambda idx=i, v=hv, b=hbtn: self._cap_hk_preset(idx, v, b))

            mk_btn(row, "✕", lambda idx=i: self._del_preset(idx), fg=RED, font=("Consolas", 8)).pack(side="left", padx=2)

        self._hl_preset()

    def _sp(self, idx, key, val):
        self.cfg["presets"][idx][key] = val; save_config(self.cfg); self._reg_hk()

    def _sp_int(self, idx, key, val):
        try: self.cfg["presets"][idx][key] = int(val); save_config(self.cfg)
        except: pass

    def _add_preset(self):
        self.cfg.setdefault("presets", []).append({"name": f"P{len(self.cfg['presets'])+1}", "value": 0, "hotkey": ""})
        save_config(self.cfg); self._build_presets(); self._reg_hk()

    def _del_preset(self, idx):
        self.cfg["presets"].pop(idx); save_config(self.cfg)
        self._build_presets(); self._reg_hk()

    def _apply_preset(self, idx):
        if not self.mem.ok: self._connect(); return
        v = self.cfg["presets"][idx]["value"]
        self.mem.write(self.cfg["timing_address"], v)
        self._active = idx; self._hl_preset()

    def _hl_preset(self):
        for i, b in enumerate(self._preset_btns):
            b.config(bg=PUR if i==self._active else BG2)

    def _cap_hk_preset(self, idx, var, hbtn):
        if not HAS_KB: return
        hbtn.config(text="...", fg=YEL)
        def wait():
            try:
                ev = kb.read_event(suppress=True)
                while ev.event_type != "down": ev = kb.read_event(suppress=True)
                k = ev.name; var.set(k)
                hbtn.config(text=k or "(none)", fg=ACC)
                self.cfg["presets"][idx]["hotkey"] = k
                save_config(self.cfg); self._reg_hk()
            except: hbtn.config(text=var.get() or "(none)", fg=ACC)
        threading.Thread(target=wait, daemon=True).start()

    def _connect(self):
        if self.mem.attach():
            self.dot.config(fg=GRN)
            self.stlbl.config(text=f"connected  PID:{self.mem.pm.process_id}")
        else:
            self.dot.config(fg=RED); self.stlbl.config(text="disconnected")

    def _poll(self):
        if self.mem.ok:
            v = self.mem.read(self.cfg["timing_address"])
            if v is not None:
                self.tv.set(f"{v:+d}" if v!=0 else "0")
            else:
                self._connect()
            
            av = self.mem.read(self.cfg.get("auto_adjust_address", 1046664))
            if av is not None: self._update_auto_ui(av)

        self.after(500, self._poll)

    def _get_step(self):
        try: return max(1, int(self.stepv.get()))
        except: return 1

    def _save_step(self):
        self.cfg["step"] = self._get_step(); save_config(self.cfg)

    def _minus(self):
        if not self.mem.ok: self._connect(); return
        v = self.mem.read(self.cfg["timing_address"])
        if v is not None: self.mem.write(self.cfg["timing_address"], v-self._get_step())

    def _plus(self):
        if not self.mem.ok: self._connect(); return
        v = self.mem.read(self.cfg["timing_address"])
        if v is not None: self.mem.write(self.cfg["timing_address"], v+self._get_step())

    def _direct(self):
        if not self.mem.ok: self._connect(); return
        try:
            self.mem.write(self.cfg["timing_address"], int(self.dirv.get()))
            self.dirv.set("")
        except: messagebox.showerror("エラー", "数値を入力してください")

    def _set_auto_val(self, val):
        if not self.mem.ok: self._connect(); return
        addr = self.cfg.get("auto_adjust_address", 1046664)
        if self.mem.write(addr, val):
            self._update_auto_ui(val)

    def _update_auto_ui(self, val):
        lbls = {0: "OFF", 1: "ON", 2: "SILENT"}
        colors = {0: RED, 1: GRN, 2: PUR}
        self.aav.set(lbls.get(val, "OFF"))
        self.aalbl.config(fg=colors.get(val, RED))

    def _reg_hk(self):
        if not HAS_KB: return
        for h in self._hk:
            try: kb.remove_hotkey(h)
            except: pass
        self._hk.clear()
        if not self.cfg.get("hotkeys_enabled", True): return

        def reg(key, fn):
            if key:
                try: self._hk.append(kb.add_hotkey(key, fn))
                except: pass

        reg(self.cfg.get("hotkey_minus", ""), self._minus)
        reg(self.cfg.get("hotkey_plus", ""), self._plus)
        
        dk = self.cfg.get("hotkey_direct_key", "")
        dv = self.cfg.get("hotkey_direct_val", 0)
        if dk:
            reg(dk, lambda: self.mem.write(self.cfg["timing_address"], dv) if self.mem.ok else None)

        reg(self.cfg.get("hotkey_auto_off", ""), lambda: self._set_auto_val(0))
        reg(self.cfg.get("hotkey_auto_on", ""), lambda: self._set_auto_val(1))
        reg(self.cfg.get("hotkey_auto_silent", ""), lambda: self._set_auto_val(2))

        for i, p in enumerate(self.cfg.get("presets", [])):
            reg(p.get("hotkey", ""), lambda idx=i: self._apply_preset(idx))

    def _toggle_hk(self):
        self.hk_on = not self.hk_on
        self.cfg["hotkeys_enabled"] = self.hk_on; save_config(self.cfg)
        self.hklbl.set("Hotkeys: ON" if self.hk_on else "Hotkeys: OFF")
        self.hkbtn.config(fg=GRN if self.hk_on else RED)
        self._reg_hk()

    def _hk_settings(self):
        w = tk.Toplevel(self); w.title("Hotkey Settings"); w.configure(bg=BG)
        w.resizable(False, False)

        hk_items = [
            ("hotkey_minus", "Minus"),
            ("hotkey_plus", "Plus"),
            ("hotkey_direct_key", "Direct key"),
            ("hotkey_auto_off", "Auto OFF"),
            ("hotkey_auto_on", "Auto ON"),
            ("hotkey_auto_silent", "Auto SILENT")
        ]

        for key, label in hk_items:
            row = tk.Frame(w, bg=BG); row.pack(fill="x", padx=8, pady=3)
            mk_lbl(row, f"{label}:", fg=GRAY, width=14, anchor="w").pack(side="left")
            cur = self.cfg.get(key, "")
            b = mk_btn(row, cur or "(none)", None, fg=ACC, font=("Consolas", 8))
            b.pack(side="left", padx=4)
            b.config(command=lambda k=key, bt=b: self._cap_hk_cfg(k, bt))

        drow = tk.Frame(w, bg=BG); drow.pack(fill="x", padx=8, pady=3)
        mk_lbl(drow, "Direct value:", fg=GRAY, width=14, anchor="w").pack(side="left")
        dv = tk.StringVar(value=str(self.cfg.get("hotkey_direct_val", 0)))
        de = mk_ent(drow, dv, w=6); de.pack(side="left", padx=4)
        de.bind("<FocusOut>", lambda ev: self._save_dv(dv.get()))
        de.bind("<Return>", lambda ev: self._save_dv(dv.get()))

        mk_btn(w, "閉じる", w.destroy).pack(pady=(4, 8))

    def _cap_hk_cfg(self, key, btn_w):
        if not HAS_KB: return
        btn_w.config(text="...", fg=YEL)
        def wait():
            try:
                ev = kb.read_event(suppress=True)
                while ev.event_type != "down": ev = kb.read_event(suppress=True)
                k = ev.name; self.cfg[key] = k; save_config(self.cfg); self._reg_hk()
                btn_w.config(text=k or "(none)", fg=ACC)
            except: btn_w.config(text=self.cfg.get(key, "") or "(none)", fg=ACC)
        threading.Thread(target=wait, daemon=True).start()

    def _save_dv(self, val):
        try: self.cfg["hotkey_direct_val"] = int(val); save_config(self.cfg); self._reg_hk()
        except: pass

    def _save_cfg_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("JSON", "*.json")], initialfile="config.json")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)

    def _load_cfg_from(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f: self.cfg = json.load(f)
            save_config(self.cfg)
            for w in self.winfo_children(): w.destroy()
            self._preset_btns = []; self._build()
            self._connect(); self._reg_hk()

    def _close(self):
        for h in self._hk:
            try: kb.remove_hotkey(h)
            except: pass
        self.destroy()

if __name__ == "__main__":
    App().mainloop()