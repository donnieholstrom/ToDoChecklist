import json, os, ctypes, base64, struct, zlib, tkinter as tk

F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo.json")
if os.path.exists(F):
    with open(F, encoding="utf-8") as fh: d = json.load(fh)
else: d = {"lists": {}, "done": []}
d.setdefault("groups", {"Default": list(d["lists"])})  # category -> list names, in order
d.setdefault("colors", {})  # category -> color
for names in d["groups"].values(): names[:] = [n for n in names if n in d["lists"]]  # drop names of missing lists
_orphans = [n for n in d["lists"] if not any(n in v for v in d["groups"].values())]  # lists no category shows
if _orphans: d["groups"].setdefault(next(iter(d["groups"]), "Default"), []).extend(_orphans)
for k, L in d["lists"].items(): d["lists"][k] = [x if isinstance(x, dict) else {"t": x} for x in L]  # older files stored plain text
d["done"] = [x if isinstance(x, dict) else dict(zip(("l", "t"), x.split(": ", 1) if ": " in x else ("", x))) for x in d["done"]]
_sv = None
def save_soon():  # save shortly after typing stops
    global _sv
    if _sv: root.after_cancel(_sv)
    _sv = root.after(400, save)
def save():  # write a temp file, then swap it in, so a crash mid-write can't leave todo.json half-written
    with open(F + ".tmp", "w", encoding="utf-8") as fh: json.dump(d, fh, indent=1)
    os.replace(F + ".tmp", F)

BG, SIDE, HI, FG, DIM, ACC, X, RED = "#1e1f22", "#2b2d31", "#3a3c42", "#e6e6e6", "#8a8d93", "#5b8def", "#5c5f66", "#e5534b"
PALETTE = ["#f07178", "#f5a35c", "#e6c75c", "#4fc38a", "#4fc1c9", "#5b8def", "#a78bfa", "#f472b6"]
HOV_SIDE, HOV_MAIN, FOCUS = "#36383e", "#26282c", "#43464d"  # hover / focused shades
F1, F2, F3 = ("Segoe UI", 11), ("Segoe UI Semibold", 20), ("Segoe UI", 9, "bold")
R = 6  # corner radius
MAIN_TOP, HEAD_PAD = 22, 6  # main column's top padding; vertical padding of a sidebar category name
TX, GUT = 22, 11  # sidebar: text starts TX px into each row box; dots/ticks/icons sit centered at GUT
DONE = "\0done"

root = tk.Tk(); root.title("To-Do"); root.geometry(d.get("geo", "640x460")); root.configure(bg=BG)
root.minsize(480, 300); root.iconbitmap(default=os.path.join(os.path.dirname(F), "todo.ico"))
root.update(); hwnd = int(root.wm_frame(), 16)
for attr, val in ((19, 1), (20, 1), (35, 0x221f1e)):
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(val)), 4)
u32 = ctypes.windll.user32  # double-buffer all painting in the window (WS_EX_COMPOSITED) to stop flicker
u32.SetWindowLongW(hwnd, -20, u32.GetWindowLongW(hwnd, -20) | 0x02000000)
root.withdraw(); root.deiconify()

# --- rounded corners: tiny anti-aliased corner images laid over a frame's 4 corners
def mix(a, b, t):  # blend hex color a toward b by t (0..1)
    a, b = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b)]
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

_imgs = {}
def corners(inner, outer):
    if (inner, outer) not in _imgs:
        a, b = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (inner, outer)]
        mix = lambda t: "#%02x%02x%02x" % tuple(round(b[i] + (a[i] - b[i]) * t) for i in range(3))
        ims = []
        for cx, cy in ((R, R), (0, R), (R, 0), (0, 0)):  # nw, ne, sw, se
            im = tk.PhotoImage(width=R, height=R)
            for y in range(R):
                row = [mix(max(0, min(1, R + 0.5 - ((x + .5 - cx) ** 2 + (y + .5 - cy) ** 2) ** .5))) for x in range(R)]
                im.put("{" + " ".join(row) + "}", to=(0, y))
            ims.append(im)
        _imgs[inner, outer] = ims
    return _imgs[inner, outer]

def rounded(f, color, outer):
    f.outer, f.corners = outer, []
    for rx, ry, anc in ((0, 0, "nw"), (1, 0, "ne"), (0, 1, "sw"), (1, 1, "se")):
        c = tk.Label(f, bd=0, padx=0, pady=0, highlightthickness=0); c.place(relx=rx, rely=ry, anchor=anc)
        f.corners.append(c)
    paint(f, color); return f

def paint(f, color):  # recolor a frame, its children and its corners
    f.config(bg=color)
    for c in f.winfo_children():
        if c not in getattr(f, "corners", ()) and not getattr(c, "keep", False): c.config(bg=color)
        if getattr(c, "deep", False):
            for cc in c.winfo_children(): cc.config(bg=color)
    if getattr(f, "xb", None): f.xb.config(image=xmark(None))
    for c, im in zip(getattr(f, "corners", ()), corners(color, getattr(f, "outer", color))): c.config(image=im); c.lift()

def png(w, h, rgba):  # build a Tk image from RGBA pixels via a tiny in-memory PNG (real alpha = smooth on any bg)
    raw = b"".join(b"\0" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xffffffff)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return tk.PhotoImage(data=base64.b64encode(data))

def seg_dist(px, py, ax, ay, bx, by):  # distance from a point to a line segment
    dx, dy = bx - ax, by - ay; t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** .5

_icons = {}
def icon(kind, color, S=12, gap=7):  # anti-aliased icons drawn on a 12-unit grid, scaled to S px; gap = space before text
    if (kind, color, gap, S) not in _icons:
        c = [int(color[i:i + 2], 16) for i in (1, 3, 5)]; W = S + gap; px = []; u = 12 / S
        for y in range(S):
            for x in range(W):
                X, Y = (x + .5) * u, (y + .5) * u
                if kind == "note":  # three lines, the last one shorter
                    dist, w = min(seg_dist(X, Y, 2.5, 3.5, 9.5, 3.5), seg_dist(X, Y, 2.5, 6, 9.5, 6), seg_dist(X, Y, 2.5, 8.5, 6.5, 8.5)), 1.3
                elif kind == "plus": dist, w = min(seg_dist(X, Y, 6, 2.5, 6, 9.5), seg_dist(X, Y, 2.5, 6, 9.5, 6)), 1.6
                elif kind == "check": dist, w = min(seg_dist(X, Y, 2.0, 6.6, 4.9, 9.4), seg_dist(X, Y, 4.9, 9.4, 10.2, 3.0)), 1.8
                else:  # "box": rounded-square checkbox outline (distance to a rounded rectangle's edge)
                    qx, qy = abs(X - 6) - 4.9 + 1.8, abs(Y - 6) - 4.9 + 1.8
                    dist, w = abs((max(qx, 0) ** 2 + max(qy, 0) ** 2) ** .5 + min(max(qx, qy), 0) - 1.8), 1.4
                px += c + [round(255 * max(0, min(1, (w / 2 - dist) / u + .5)))]
        _icons[kind, color, gap, S] = png(W, S, px)
    return _icons[kind, color, gap, S]

_xs = {}
def xmark(color, W=28, H=20, r=4, w=1.5):  # delete "X": two round-capped strokes, centered in a W x H click area
    if color not in _xs:
        c = [int(color[i:i + 2], 16) for i in (1, 3, 5)] if color else [0, 0, 0]; px = []; cx, cy = W / 2, H / 2
        for y in range(H):
            for x in range(W):
                dist = min(seg_dist(x + .5, y + .5, cx - r, cy - r, cx + r, cy + r), seg_dist(x + .5, y + .5, cx + r, cy - r, cx - r, cy + r))
                px += c + [round(255 * max(0, min(1, w / 2 - dist + .5))) if color else 0]
        _xs[color] = png(W, H, px)
    return _xs[color]

_dots = {}
def dot_img(color, bg, D=8):  # smooth round dot drawn as an image (font "●" glyphs sit on the baseline, off-center)
    if (color, bg) not in _dots:
        im = tk.PhotoImage(width=D, height=D); r = D / 2
        for y in range(D):
            im.put("{" + " ".join(mix(bg, color, max(0, min(1, r + .5 - ((x + .5 - r) ** 2 + (y + .5 - r) ** 2) ** .5))) for x in range(D)) + "}", to=(0, y))
        _dots[color, bg] = im
    return _dots[color, bg]

def caps_mid(font):  # vertical offset from a label's center to the middle of its CAPITAL letters
    m = {k: int(root.tk.call("font", "metrics", font, "-" + k)) for k in ("ascent", "descent")}
    size = float(root.tk.call("font", "actual", font, "-size"))
    px = abs(size) if size < 0 else size * root.winfo_fpixels("1i") / 72
    return round((m["ascent"] - m["descent"] - .7 * px) / 2)  # cap height ≈ 0.7 em

def within(w, parent):  # is widget w the parent or inside it? (".!frame2" must not count as inside ".!frame")
    w, parent = str(w or ""), str(parent); return w == parent or w.startswith(parent + ".")

def hover_bg(f, on, off):  # hover highlight (and ✕ / tools reveal) that survives moving onto the row's children
    inside = lambda: within(root.winfo_containing(*root.winfo_pointerxy()), f)
    def hot(h):
        if on != off: paint(f, on if h else off)
        xb = getattr(f, "xb", None)
        if xb: xb.config(image=xmark(X) if h else xmark(None))  # hidden = transparent, so nothing shifts
        n = getattr(f, "cnt", None)  # list rows: the ✕ takes the task count's spot while hovered
        if n and h: n.place_forget()
        elif n: n.place(relx=.5, rely=.5, anchor="center"); n.lift()
        if hasattr(f, "on_hot"): f.on_hot(h)
        p = getattr(f, "tools", None)
        if p and h:  # float it just left of the row's right-side buttons, over the end of the name
            pad = lambda w: (lambda v: sum(v) if isinstance(v, tuple) else int(v))(w.pack_info()["padx"])
            right = sum(w.winfo_reqwidth() + pad(w) for w in f.pack_slaves() if w.pack_info()["side"] == "right")
            for c in p.winfo_children(): c.config(bg=f["bg"])
            if hasattr(f, "title_lbl"):  # task rows: centered on the title line, not the whole (maybe two-line) row
                p.place(relx=1, x=-right - 4, y=6 + f.title_lbl.winfo_reqheight() // 2, anchor="e")  # 6 = title's top padding
            else: p.place(relx=1, x=-right - 4, rely=.5, anchor="e")
            p.lift()
        elif p: p.place_forget()
    f.bind("<Enter>", lambda e: hot(True))
    f.bind("<Leave>", lambda e: root.after(1, lambda: f.winfo_exists() and not drag.get("g") and hot(inside())))

PLUS = lambda color: icon("plus", color, S=11, gap=0)  # every "+" in the app

def addbtn(parent, cmd, bg=SIDE, hov=HOV_SIDE, text=None):  # "+" (and maybe a label) on no background; soft box + accent on hover
    b = tk.Frame(parent, cursor="hand2"); p = tk.Label(b, image=PLUS(DIM), bd=0); l = None
    if text:  # plus in the gutter, text styled like a category name, both centered to the pixel on the box
        off = caps_mid(F3)  # Segoe's capitals sit below the middle of its line box
        l = tk.Label(b, text=text, fg=DIM, font=F3, anchor="w", padx=TX, pady=0); l.pack(fill="x", pady=(HEAD_PAD - off, HEAD_PAD + off))  # spaced like a category name
        b.bind("<Configure>", lambda e: (p.place(x=GUT - 11 // 2, y=(e.height - 11) // 2, anchor="nw"), p.lift()), add="+")  # over the text label
    else: p.pack(padx=6, pady=5)  # (image labels ignore their own padx)
    rounded(b, bg, bg); hover_bg(b, hov, bg)
    b.on_hot = lambda h: (p.config(image=PLUS(ACC if h else DIM)), l and l.config(fg=ACC if h else DIM))
    for w in (b, p, l):
        if w: w.bind("<Button-1>", lambda e: root.after_idle(cmd))
    return b

def fit(l, text=None):  # cut text to the label's width with "…"; refits whenever the label resizes
    if text is not None: l.full = text
    if not hasattr(l, "fitted"): l.fitted = True; l.bind("<Configure>", lambda e: fit(l), add="+")
    s, w = l.full, l.winfo_width() - 2 * int(str(l["padx"])) - 4
    measure = lambda t: int(l.tk.call("font", "measure", l["font"], t))
    if w > 0 and measure(s) > w:
        while s and measure(s + "…") > w: s = s[:-1]
        s = s.rstrip() + "…"
    l.config(text=s)

def hover(w, on, off):
    w.bind("<Enter>", lambda e: w.config(fg=on), add="+"); w.bind("<Leave>", lambda e: w.config(fg=off), add="+")

def xlabel(parent, bg, cmd, on=RED):  # delete "X", transparent until its row is hovered
    x = tk.Label(parent, image=xmark(None), bg=bg, bd=0, cursor="hand2")
    x.bind("<Button-1>", lambda e: root.after_idle(cmd))
    x.bind("<Enter>", lambda e: x.config(image=xmark(on))); x.bind("<Leave>", lambda e: x.config(image=xmark(X)))
    return x

def xbtn(parent, bg, cmd, on=RED):  # delete button at the row's right end, only visible while the row is hovered
    x = parent.xb = xlabel(parent, bg, cmd, on); x.pack(side="right", padx=(0, 4))
    return x

def on_text(e):  # did this click land on a label's text, rather than the empty space beside it?
    w = e.widget
    if not isinstance(w, tk.Label) or not w["text"]: return False
    pad = int(str(w["padx"])); return pad - 2 <= e.x <= pad + int(w.tk.call("font", "measure", w["font"], w["text"])) + 2

side = tk.Frame(root, bg=SIDE, width=d.get("side", 200)); side.pack(side="left", fill="y"); side.pack_propagate(False)
# draggable divider between the columns; sidebar stays 150-400px and leaves the main column 320px
div = tk.Frame(root, bg=BG, width=6, cursor="sb_h_double_arrow"); div.pack(side="left", fill="y")
div.bind("<Enter>", lambda e: div.config(bg=HI)); div.bind("<Leave>", lambda e: div.config(bg=BG))
def resize(e):
    w = max(150, min(400, root.winfo_width() - 326, e.x_root - root.winfo_rootx()))
    side.config(width=w); d["side"] = w
div.bind("<B1-Motion>", resize); div.bind("<ButtonRelease-1>", lambda e: save())

# top gap sized so the first category name lines up with the "● CATEGORY" label over the list title (its pady=1)
tk.Frame(side, bg=SIDE, height=MAIN_TOP + 1 - HEAD_PAD).pack(fill="x")
catsbox = tk.Frame(side, bg=SIDE); cats = tk.Frame(catsbox, bg=SIDE); cats.pack(fill="x")
ncholder = tk.Frame(side, bg=SIDE); ncholder.pack(fill="x")  # holds the "New category" button or its name box
donebtn = tk.Frame(side, cursor="hand2"); donebtn.pack(side="bottom", fill="x", padx=8, pady=10)
donelbl = tk.Label(donebtn, fg=DIM, font=F1, anchor="w", padx=TX, pady=7); donelbl.pack(fill="x")
donechk = tk.Label(donebtn, image=icon("check", DIM, gap=0), bd=0); donechk.place(x=GUT, rely=.5, anchor="center")
rounded(donebtn, SIDE, SIDE)

main = tk.Frame(root, bg=BG); main.pack(side="left", fill="both", expand=True, padx=28, pady=MAIN_TOP)
crumbf = tk.Frame(main, bg=BG)  # "● CATEGORY" above the list title
crumb = tk.Label(crumbf, bg=BG, font=F3, anchor="w", width=1, padx=0, pady=1); crumb.pack(fill="x", padx=(16, 0)); crumb.target = DIM
crumbdot = tk.Label(crumbf, bg=BG, bd=0); crumbdot.place(x=4, rely=.5, y=caps_mid(F3), anchor="center")
titlebar = tk.Frame(main, bg=BG); titlebar.pack(fill="x")
title = tk.Label(titlebar, bg=BG, fg=FG, font=F2, anchor="w", width=1); title.pack(fill="x")
title.bind("<Button-1>", lambda e: sel and sel != DONE and on_text(e) and root.after_idle(start, "title", sel))  # click to rename
title.bind("<Motion>", lambda e: title.config(cursor="xterm" if sel and sel != DONE and on_text(e) else ""))
rowsbox = tk.Frame(main, bg=BG); rowsbox.pack(fill="both", expand=True, pady=(12, 0))
rows = tk.Frame(rowsbox, bg=BG); rows.pack(fill="both", expand=True)

sel = next(iter(d["lists"]), None)
drag = {}
editing = None  # e.g. ("rename", category) while an inline rename box is open
flash = None    # task to briefly highlight after it's added / restored
inline_e = None  # the inline text box (or note editor) currently open
undo_stack = [] # (list, index, task) for each check-off, so Ctrl+Z can put it back
toast_w = None
confirm, confirm_w = None, None  # ("list"|"group", name) while a row is asking "Delete?"
side_sig, side_rows, shown_sel = None, {}, None  # what the sidebar / main column were last built for

def pick(c):
    global sel; sel = c; render()

# --- drag & drop: row = the frame being moved (has .key), handles = widgets you grab it by
def dnd(row, handles, text, click, commit):
    for w in handles:
        w.bind("<ButtonPress-1>", lambda e: drag.update(row=row, y=e.y_root, g=None, text=text, w=e.widget, hit=on_text(e)))
        # only react to a press that started on this same row: buttons (✕, ≡, ✎) re-render on press, so the
        # matching release can land on a freshly drawn row that was never pressed
        w.bind("<B1-Motion>", lambda e: drag.get("row") is row and motion(e))
        w.bind("<ButtonRelease-1>", lambda e: drag.get("row") is row and release(click, commit))

def motion(e):
    r = drag["row"]
    if not drag["g"]:
        if abs(e.y_root - drag["y"]) < 6: return
        g = drag["g"] = tk.Frame(root)
        tk.Label(g, text=drag["text"], fg="#fff", font=F1, padx=14, pady=6).pack()
        rounded(g, ACC, SIDE if r.master is cats else BG); paint(r, HI)
    drag["g"].place(x=e.x_root - root.winfo_rootx() + 14, y=e.y_root - root.winfo_rooty() + 6)
    drag["g"].lift()
    box = r.master; rs = [w for w in box.pack_slaves() if w is not r]
    y, acc, j = e.y_root - box.winfo_rooty() - r.winfo_height() / 2, 0, 0
    for w in rs:
        if acc + w.winfo_height() / 2 < y: j += 1
        acc += w.winfo_height()
    if box is cats: j = max(j, 1)  # a list can't go above the first category
    # move only the dragged row (unpacking it would drop the mouse grab and lose the release)
    if j < len(rs): r.pack(before=rs[j])
    else: r.pack(after=rs[-1])

def release(click, commit):
    g, w, hit = drag.get("g"), drag.get("w"), drag.get("hit"); drag.clear()
    if not g: return click(w, hit)
    g.destroy(); commit(); save(); render()

def move_tasks():
    L = d["lists"][sel]; L[:] = [L[w.key] for w in rows.pack_slaves() if isinstance(getattr(w, "key", None), int)]

def move_lists():  # rebuild categories from the sidebar's on-screen order
    gs, cur = {}, None
    for w in cats.pack_slaves():
        k = getattr(w, "key", None)
        if k and k[0] == "g": cur = gs.setdefault(k[1], [])
        elif k: cur.append(k[1])
    d["groups"] = gs

# --- inline text box for renaming a category / list / task
def inline(text, key=None, parent=None, font=F1):
    parent = parent or cats; sb = parent in (cats, ncholder)  # sidebar box?
    box = tk.Frame(parent); box.pack(fill="x", padx=8 if sb else 0, pady=2 if font == F1 else 0); box.key = key
    e = tk.Entry(box, fg=FG, insertbackground=FG, relief="flat", font=font, highlightthickness=0, bd=0)
    tr = parent is rows  # task row: text lines up with task names, checkbox in the icon spot
    e.pack(fill="x", padx=(TX if sb else 31 if tr else 16, 10) if font == F1 else (8, 8), pady=7 if font == F1 else 1)
    if tr: tk.Label(box, image=icon("box", DIM, gap=0), bd=0).place(x=12, rely=.5, anchor="w")
    rounded(box, FOCUS, SIDE if sb else BG)
    global inline_e; inline_e = e
    e.insert(0, text); e.select_range(0, "end"); e.focus_set()
    e.bind("<Return>", lambda _: finish(e.get().strip()))
    e.bind("<Escape>", lambda _: finish(""))
    e.bind("<FocusOut>", lambda _: e is inline_e and finish(""))  # ignore boxes being replaced by a re-render

def start(mode, g):
    global editing; editing = (mode, g); render()

def finish(val):
    global editing, sel
    if not editing: return
    (mode, g), editing = editing, None
    if mode == "rename" and val and val not in d["groups"]:
        d["groups"] = {(val if k == g else k): v for k, v in d["groups"].items()}
        if g in d["colors"]: d["colors"][val] = d["colors"].pop(g)
        save()
    if mode in ("rename_list", "title") and val and val not in d["lists"]:
        d["lists"] = {(val if k == g else k): v for k, v in d["lists"].items()}
        for names in d["groups"].values(): names[:] = [val if n == g else n for n in names]
        for x in d["done"]:
            if x["l"] == g: x["l"] = val
        if sel == g: sel = val
        save()
    if mode == "rename_task" and val:
        d["lists"][sel][g]["t"] = val; save()
    if mode == "new_list" and val: return root.after_idle(add_list, g, val)
    if mode == "new_task" and val:  # add it and keep the box open for the next one
        global flash
        flash = {"t": val}; d["lists"][g].append(flash); save(); editing = ("new_task", g)
    if mode == "new_cat" and val: d["groups"].setdefault(val, []); save()
    root.after_idle(render)

pal = None
def palette(g, w):  # little row of color swatches under a category's dot
    global pal
    close_pal(); pal = tk.Frame(root)
    for c in PALETTE + [None]:
        s = tk.Label(pal, text="●" if c else "○", fg=c or DIM, font=("Segoe UI", 13), padx=3, cursor="hand2")
        s.pack(side="left"); s.bind("<Button-1>", lambda e, c=c: set_color(g, c))
    rounded(pal, HI, SIDE); pal.config(padx=6, pady=2)
    pal.place(x=w.winfo_rootx() - root.winfo_rootx() - 6, y=w.winfo_rooty() - root.winfo_rooty() + w.winfo_height() + 2)

def close_pal():
    global pal
    if pal: pal.destroy(); pal = None

def set_color(g, c):
    if c: d["colors"][g] = c
    else: d["colors"].pop(g, None)
    close_pal(); save(); render()

def swap(old, new):  # show a freshly built frame in place of the old one in a single step
    new.pack(fill="x" if new.master is catsbox else "both", expand=new.master is rowsbox); old.destroy()

def show(w, on, **kw):  # pack/unpack only when needed (repacking makes widgets blink)
    if on and w.winfo_manager() != "pack": w.pack(**kw)
    elif not on and w.winfo_manager() == "pack": w.pack_forget()

fade_gen = 0
def fade(pairs, steps=6, ms=20):  # text fades in from the background color
    global fade_gen; fade_gen += 1; gen = fade_gen  # a newer fade cancels an older one still running
    for w, c in pairs: w.config(fg=BG)
    for k in range(1, steps + 1):
        root.after(k * ms, lambda k=k: gen == fade_gen and [w.winfo_exists() and w.config(fg=mix(BG, c, k / steps)) for w, c in pairs])

def style_list(c):  # selection / count look of one sidebar list row
    f, n, bar, col = side_rows[c]; on = c == sel; cnt = len(d["lists"][c]) or ""
    if getattr(f, "state", None) == (on, cnt): return
    f.state = (on, cnt)
    bg = (mix(HI, col, .12) if col else HI) if on else SIDE  # selected row gets a hint of the color
    paint(f, bg); hover_bg(f, bg if on else HOV_SIDE, bg)
    n.config(text=cnt, fg=(col or ACC) if on else DIM)
    if bar: bar.config(bg=col if on else mix(SIDE, col, .5))

def render():
    global flash, cats, rows, side_sig, shown_sel
    sig = (repr(d["groups"]), repr(d["colors"]), confirm, editing if editing and editing[0] in ("rename", "rename_list", "new_list", "new_cat") else None)
    if sig != side_sig: build_side(); side_sig = sig
    for c in side_rows: style_list(c)
    build_main()

def divider():  # thin line across the sidebar
    sep = tk.Frame(cats, bg=SIDE, height=13); sep.pack(fill="x"); sep.key = None
    tk.Frame(sep, bg=HI, height=1).place(x=8, relwidth=1, width=-16, rely=.5)

def build_side():
    global cats
    old, cats = cats, tk.Frame(catsbox, bg=SIDE); side_rows.clear()
    for gi, (g, names) in enumerate(d["groups"].items()):
        col = d["colors"].get(g)
        if gi: divider()  # thin line between categories
        if editing == ("rename", g): inline(g, ("g", g))
        elif confirm == ("group", g): confirm_row(f"{g.upper()}  +{len(names)}", ("g", g), F3)
        else:
            h = tk.Frame(cats, bg=SIDE); h.pack(fill="x", padx=8); h.key = ("g", g)
            xbtn(h, SIDE, lambda g=g: delgroup(g))
            hover_bg(h, SIDE, SIDE)
            dot = tk.Label(h, image=dot_img(col or X, SIDE), bg=SIDE, bd=0, padx=4, pady=4, cursor="hand2")
            dot.bind("<Button-1>", lambda e, g=g, w=dot: root.after_idle(palette, g, w))
            l = tk.Label(h, bg=SIDE, fg=mix(col, FG, .25) if col else DIM, font=F3, padx=TX, pady=HEAD_PAD, anchor="w", width=1)
            l.pack(side="left", fill="x", expand=True); fit(l, g.upper())
            dot.place(x=GUT, rely=.5, y=caps_mid(F3), anchor="center"); dot.lift()
            l.bind("<Button-1>", lambda e, g=g: on_text(e) and root.after_idle(start, "rename", g))
            l.bind("<Motion>", lambda e, l=l: l.config(cursor="xterm" if on_text(e) else ""))
        for c in names:
            if editing == ("rename_list", c): inline(c, ("l", c)); continue
            if confirm == ("list", c): confirm_row(c, ("l", c)); continue
            f = tk.Frame(cats, cursor="hand2"); f.pack(fill="x", padx=8); f.key = ("l", c)
            slot = tk.Frame(f, width=28); slot.deep = True  # right end: the task count, or the ✕ while hovered
            slot.pack(side="right", fill="y", padx=(0, 4)); slot.pack_propagate(False)
            f.xb = xlabel(slot, SIDE, lambda c=c: delcat(c)); f.xb.place(relx=.5, rely=.5, anchor="center")
            n = f.cnt = tk.Label(slot, fg=DIM, font=F1, bd=0, padx=0, pady=0); n.place(relx=.5, rely=.5, anchor="center")
            t = tk.Label(f, fg=FG, font=F1, padx=TX, pady=6, anchor="w", width=1)
            t.pack(side="left", fill="x", expand=True); fit(t, c)
            rounded(f, SIDE, SIDE); bar = None
            if col:  # small color tick at the left edge; muted unless selected
                bar = tk.Frame(f, width=3, height=14, bg=mix(SIDE, col, .5)); bar.keep = True
                bar.place(x=GUT, rely=.5, anchor="center")
            # click another list to open it; click the open list's name to rename it
            dnd(f, (f, slot, n, t), c, lambda w, hit, c=c, t=t: pick(c) if c != sel else w is t and hit and start("rename_list", c), move_lists)
            t.bind("<Motion>", lambda e, c=c, t=t: t.config(cursor="xterm" if c == sel and on_text(e) else "hand2"))
            side_rows[c] = (f, n, bar, col)
        if editing == ("new_list", g): inline("")
        else: addbtn(cats, lambda g=g: start("new_list", g)).pack(anchor="w", padx=8, pady=(2, 4))  # plus centered on the ticks
    if d["groups"]: divider()  # and one above "New category"
    swap(old, cats)
    show(catsbox, bool(d["groups"]), fill="x", before=ncholder)  # empty frames keep their old height
    for w in ncholder.winfo_children(): w.destroy()
    if editing == ("new_cat", ""): inline("", None, ncholder)
    else: addbtn(ncholder, lambda: start("new_cat", ""), text="NEW CATEGORY").pack(fill="x", padx=8)

def build_main():
    global flash, rows, shown_sel
    old, rows = rows, tk.Frame(rowsbox, bg=BG)
    switched = sel != shown_sel; shown_sel = sel
    donelbl.config(text=f"Completed   {len(d['done']) or ''}")
    paint(donebtn, HI if sel == DONE else SIDE)
    hover_bg(donebtn, HI if sel == DONE else HOV_SIDE, HI if sel == DONE else SIDE)
    for w in titlebar.winfo_children():
        if w is not title: w.destroy()
    show(title, editing != ("title", sel), fill="x")
    if editing == ("title", sel): inline(sel, None, titlebar, F2)
    grp = next((k for k, v in d["groups"].items() if sel in v), None) if sel != DONE else None
    show(crumbf, bool(grp), fill="x", before=titlebar)
    if sel == DONE:
        fit(title, "Completed")
        for x in reversed(d["done"]): row("check", x, DIM, lambda x=x: restore(x), lambda x=x: drop(d["done"], x), label=f"{x['l']}: {x['t']}" if x["l"] else x["t"])
        if not d["done"]: tk.Label(rows, text="Nothing finished yet.", bg=BG, fg=DIM, font=F1).pack(anchor="w", padx=12)
    elif sel:
        L = d["lists"][sel]
        fit(title, sel)
        if grp:
            col = d["colors"].get(grp)
            crumb.target = mix(col, FG, .25) if col else DIM; crumb.config(fg=crumb.target); fit(crumb, grp.upper()); crumbdot.config(image=dot_img(col or X, BG))
        for i, t in enumerate(L): row("box", t, FG, lambda t=t: check(t), lambda t=t: drop(L, t), i)
        if not L:  # empty list: a big, faint checkmark in the background
            bgc = tk.Label(rows, image=icon("check", mix(BG, DIM, .16), S=110, gap=0), bg=BG, bd=0)
            bgc.place(relx=.5, rely=.45, anchor="center"); bgc.lower()
        if editing == ("new_task", sel): inline("", None, rows)
        else: addbtn(rows, lambda: start("new_task", sel), BG, HOV_MAIN).pack(anchor="w", padx=6, pady=(2, 0))  # under the checkboxes
    else:
        fit(title, "Add a list in the sidebar  ←")
    swap(old, rows)
    if switched:  # soft fade-in of the newly opened list
        fade([(title, FG), (crumb, crumb.target)] + [(c, c["fg"]) for f in rows.winfo_children() for c in [f, *f.winfo_children()]
              if isinstance(c, tk.Label) and c["text"]])  # title/crumb: their real colors, not mid-fade ones
    flash = None

def drop(L, it):  # remove this exact item (two tasks can have the same text)
    for k, x in enumerate(L):
        if x is it: del L[k]; return

def tool(parent, img, cmd):  # small image button that brightens on hover
    b = tk.Label(parent, image=img(DIM), cursor="hand2"); b.pack(side="left", padx=3)
    b.bind("<Button-1>", lambda e: root.after_idle(cmd))
    b.bind("<Enter>", lambda e: b.config(image=img(ACC))); b.bind("<Leave>", lambda e: b.config(image=img(DIM)))

def row(kind, it, color, click, delete, i=None, label=None):
    text, note = label or it["t"], (it.get("n") or "").strip()
    if i is not None and editing == ("rename_task", i): return inline(it["t"], i, rows)
    noting = i is not None and editing == ("note", i)
    f = tk.Frame(rows); f.pack(fill="x"); f.key = i
    xbtn(f, BG, lambda: (delete(), save(), render())).pack_configure(anchor="n", pady=6)  # stays on the title line
    tools = f.tools = tk.Frame(f)  # shown on hover
    if i is not None:
        tool(tools, lambda c: icon("note", c, gap=0), lambda: start("note", i))
    else:  # Completed rows
        b = tk.Label(tools, text="↩ Return to list", fg=DIM, font=("Segoe UI", 9), padx=5, cursor="hand2"); b.pack()
        b.bind("<Button-1>", lambda e: root.after_idle(click)); hover(b, ACC, DIM)
    # the name (click it to rename) and, in front of it, the checkbox (click it to check the task off)
    l = f.title_lbl = tk.Label(f, text=text, fg=color, font=F1, anchor="w", cursor="xterm" if i is not None else "", padx=0, pady=0)
    l.pack(side="top", anchor="w", padx=(31, 0), pady=(6, 1 if note or noting else 6))
    cb = tk.Label(f, image=icon(kind, color, gap=0), bd=0, padx=0, pady=0, cursor="hand2")
    cb.place(x=12, y=6 + l.winfo_reqheight() // 2, anchor="w")  # 6 = the name's top padding
    cb.bind("<Enter>", lambda e: cb.config(image=icon("check", ACC, gap=0)))  # preview the check
    cb.bind("<Leave>", lambda e: cb.config(image=icon(kind, color, gap=0)))
    cb.bind("<Button-1>", lambda e: root.after_idle(click) if i is None else root.after_idle(tick, l, cb, click))
    nl = None
    if noting: note_editor(f, it)
    elif note:  # the whole note in dim text under the title, wrapped to the row's width
        nl = tk.Label(f, text=note, fg=mix(DIM, BG, .15), font=("Segoe UI", 9), anchor="w", justify="left", width=1, padx=0, pady=0)
        nl.pack(side="top", fill="x", padx=(31, 8), pady=(0, 6))
        nl.bind("<Configure>", lambda e: e.width > 1 and nl.config(wraplength=e.width), add="+")
        if i is not None:  # click a task's note to edit it
            nl.config(cursor="xterm"); hover(nl, ACC, nl["fg"]); nl.bind("<Button-1>", lambda e: root.after_idle(start, "note", i))
    rounded(f, BG, BG)
    if not noting: hover_bg(f, HOV_MAIN, BG)
    if flash is it and i is not None:  # new or restored: start in accent, settle to normal
        l.config(fg=ACC); cb.config(image=icon(kind, ACC, gap=0))
        root.after(500, lambda: l.winfo_exists() and (l.config(fg=color), cb.config(image=icon(kind, color, gap=0))))
    if i is not None:  # drag the row (or its name) to reorder; a plain click on the name renames it
        dnd(f, (f, l), text, lambda w, hit: w is l and start("rename_task", i), move_tasks)

def note_editor(f, it):  # multi-line notes box under the title; saves as you type, grows with the text
    global inline_e
    box = tk.Frame(f); box.keep = True; box.pack(side="top", fill="x", padx=(26, 8), pady=(3, 8))
    t = inline_e = tk.Text(box, height=2, wrap="word", font=("Segoe UI", 10), fg=FG, insertbackground=FG, relief="flat",
                           bd=0, highlightthickness=0, padx=0, pady=0, undo=True)
    t.pack(fill="x", padx=6, pady=6); rounded(box, FOCUS, BG)
    t.insert("1.0", it.get("n", "")); t.mark_set("insert", "end"); t.focus_set()
    def grow():
        if t.winfo_exists(): t.config(height=max(2, min(10, (t.count("1.0", "end-1c", "displaylines") or (0,))[0] + 1)))
    def keep(_=None):
        n = t.get("1.0", "end-1c").strip()
        if n: it["n"] = n
        else: it.pop("n", None)  # an emptied note is removed
        save_soon(); grow()
    def close(_=None):
        keep(); finish(""); return "break"
    t.bind("<KeyRelease>", keep); t.bind("<Escape>", close); t.bind("<Control-Return>", close)
    t.bind("<FocusOut>", lambda e: t is inline_e and close())
    t.bind("<Configure>", lambda e: grow())  # first real width is only known once it's laid out

def tick(l, cb, then):  # little check-off moment before the task leaves the list
    cb.config(image=icon("check", ACC, gap=0)); cb.unbind("<Leave>"); l.config(fg=ACC, font=(*F1, "overstrike"))
    root.after(220, then)

def toast(msg):  # small message that fades out at the bottom of the main column
    global toast_w
    if toast_w: toast_w.destroy()
    fr = toast_w = tk.Frame(root)
    tk.Label(fr, text=msg, fg=FG, font=F1, padx=14, pady=7).pack(); rounded(fr, HI, BG)
    fr.place(in_=main, relx=.5, rely=1, anchor="s", y=-4)
    root.after(2500, lambda: fr.winfo_exists() and fr.destroy())

short = lambda t: t if len(t) <= 28 else t[:27] + "…"

def check(it):
    L = d["lists"].get(sel, [])
    i = next((k for k, x in enumerate(L) if x is it), None)
    if i is None: return
    del L[i]; x = {"l": sel, **it}; d["done"].append(x); undo_stack.append((sel, i, x))  # note goes along
    save(); render(); toast(f"Checked off “{short(it['t'])}”  ·  Ctrl+Z to undo")

def put_back(x, i=None):  # return a finished item to its list (recreating the list if it was deleted)
    global flash
    c = x["l"] or next(iter(d["lists"]), "Tasks")
    if c not in d["lists"]:
        d["lists"][c] = []; d["groups"].setdefault(next(iter(d["groups"]), "Default"), []).append(c)
    it = flash = {k: v for k, v in x.items() if k != "l"}
    L = d["lists"][c]; L.insert(len(L) if i is None else min(i, len(L)), it); return c

def restore(x):
    drop(d["done"], x); c = put_back(x)
    save(); render(); toast(f"Returned to {short(c)}")

def undo(e=None):
    global sel
    if isinstance(root.focus_get(), (tk.Entry, tk.Text)): return  # let text boxes keep their own Ctrl+Z
    while undo_stack:
        c, i, x = undo_stack.pop()
        if not any(y is x for y in d["done"]): continue  # already returned or deleted by hand
        drop(d["done"], x); sel = put_back(x, i); save(); render(); return toast(f"Restored “{short(x['t'])}”")

def first_list(): return next(iter(d["lists"]), None)

# --- deleting lists / categories asks right in the row: "Delete …?  Cancel  Delete"
def confirm_row(text, key, font=F1):  # same size as the row it replaces: name, then ✓ (delete) and ✕ (cancel)
    global confirm_w
    f = confirm_w = tk.Frame(cats); f.pack(fill="x", padx=8); f.key = key
    no = tk.Label(f, image=xmark(DIM), bd=0, cursor="hand2"); no.pack(side="right", padx=(0, 4))  # where the X was
    yes = tk.Label(f, image=icon("check", RED, gap=0), padx=8, cursor="hand2"); yes.pack(side="right")
    t = tk.Label(f, fg=FG, font=font, padx=TX, pady=6, anchor="w", width=1); t.pack(side="left", fill="x", expand=True); fit(t, text)
    rounded(f, mix(SIDE, RED, .18), SIDE)
    no.bind("<Enter>", lambda e: no.config(image=xmark(FG))); no.bind("<Leave>", lambda e: no.config(image=xmark(DIM)))
    yes.bind("<Enter>", lambda e: yes.config(image=icon("check", "#ff8a80", gap=0))); yes.bind("<Leave>", lambda e: yes.config(image=icon("check", RED, gap=0)))
    yes.bind("<Button-1>", lambda e: root.after_idle(do_delete)); no.bind("<Button-1>", lambda e: root.after_idle(ask, None))

def ask(c):  # c = ("list", name) / ("group", name), or None to cancel
    global confirm; confirm = c; render()

def delcat(c): ask(("list", c))

def delgroup(g):
    if d["groups"][g]: ask(("group", g))
    else: del d["groups"][g]; d["colors"].pop(g, None); save(); render()  # empty: nothing to lose

def do_delete():
    global confirm
    kind, name = confirm; confirm = None
    if kind == "list":
        del d["lists"][name]
        for names in d["groups"].values():
            if name in names: names.remove(name)
        return save(), pick(first_list() if sel == name else sel)
    g = name; names = d["groups"][g]
    for c in names: del d["lists"][c]
    d["colors"].pop(g, None)
    del d["groups"][g]; save(); pick(first_list() if sel in names else sel)

def add_list(g, n):
    if n not in d["lists"]: d["lists"][n] = []; d["groups"][g].append(n); save(); pick(n); start("new_task", n)
    else: render()

for w in (donebtn, donelbl, donechk): w.bind("<Button-1>", lambda e: sel != DONE and pick(DONE))
root.bind("<Escape>", lambda e: confirm and ask(None))
# Ctrl+A selects everything in text boxes (Tk's default jumps to the line start instead)
root.bind_class("Entry", "<Control-a>", lambda e: (e.widget.select_range(0, "end"), e.widget.icursor("end"), "break")[-1])
root.bind_class("Text", "<Control-a>", lambda e: (e.widget.tag_add("sel", "1.0", "end-1c"), "break")[-1])
root.bind("<Control-n>", lambda e: start("new_cat", "")); root.bind("<Control-z>", undo); root.bind("<Control-Z>", undo)
def on_click(e):  # clicking outside text boxes deselects them; clicking outside the palette / a "Delete?" row closes it
    global confirm
    if confirm and not within(e.widget, confirm_w): confirm = None; root.after_idle(render)
    if pal and not within(e.widget, pal): close_pal()
    if not (isinstance(e.widget, (tk.Entry, tk.Text)) or getattr(e.widget, "is_box", False)): root.focus_set()
root.bind_all("<Button-1>", on_click)

def close():
    d["max"] = root.state() == "zoomed"
    if not d["max"]: d["geo"] = root.geometry()  # size + position, e.g. "700x500+120+80"
    save(); root.destroy()
root.protocol("WM_DELETE_WINDOW", close)
if d.get("max"): root.state("zoomed")

render(); root.mainloop()
