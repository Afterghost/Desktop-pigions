"""Scrollable family facts and recent flock activity, including empty flocks."""

import tkinter as tk
from tkinter import ttk


class StoryWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Family stories")
        self.window.geometry("610x480")
        self.window.minsize(420, 300)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        self.window.bind("<Escape>", lambda event: self.window.withdraw() or "break")
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Anchor: selected family/history record (departed birds included)").pack(anchor="w")
        self.mode = tk.StringVar(value="All")
        selector = ttk.Combobox(frame, textvariable=self.mode,
                                values=("All", "Ancestors", "Descendants", "Lineage"), state="readonly")
        selector.pack(anchor="w")
        selector.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.family = ttk.Treeview(frame, columns=("name", "generation", "parent"),
                                   show="headings", height=4)
        for name, title in (("name", "Bird"), ("generation", "Generation"), ("parent", "Parent")):
            self.family.heading(name, text=title)
            self.family.column(name, width=170, minwidth=50)
        self.family.pack(fill="x", pady=5)
        self.family.bind("<<TreeviewSelect>>", self.select)
        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, wrap="word", height=12, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)
        self.anchor = None
        self.snapshot = None

    def select(self, event=None):
        selected = self.family.selection()
        if selected:
            self.anchor = selected[0]
            self.app.select_bird(self.anchor)
            self.refresh()

    def show(self):
        selected = self.app.nest_window.family.selection()
        self.anchor = selected[0] if selected else self.app.flock.selected_id
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def refresh(self):
        flock = self.app.flock
        chronicle = flock.chronicle
        ids = chronicle.family_ids(flock, self.anchor, self.mode.get())
        birds = [b for b in flock.records if b.id in ids]
        by_id = {b.id: b for b in flock.records}
        wanted = tuple(b.id for b in birds)
        if self.family.get_children() != wanted:
            self.family.delete(*self.family.get_children())
            for bird in birds:
                self.family.insert("", "end", iid=bird.id)
        for bird in birds:
            self.family.item(bird.id, values=(bird.name, bird.generation,
                             by_id[bird.parent].name if bird.parent else "Founding line"))
        generations = sorted({b.generation for b in birds})
        lines = ["Generations: " + "; ".join(
            f"G{g}: {sum(b.generation == g for b in birds)} birds, "
            f"{sum(b.generation == g and b.status == 'active' for b in birds)} active"
            for g in generations), "", "Mutual flock bonds (separate from human friendship)"]
        lines.extend(f"{by_id[b.actors[0]].name} / {by_id[b.actors[1]].name}: "
                     f"{b.status} {b.affinity:+d} ({b.meetings} meetings)"
                     for b in flock.bonds if any(i in ids for i in b.actors))
        lines.extend(["", "Permanent family chronicle"])
        def visible(event):
            return any(i in ids or any(e.id == i and (e.parent in ids or self.mode.get() == "All")
                                      for e in flock.eggs) for i in event.actors)
        lines.extend(chronicle.prose(e, flock) for e in chronicle.core if visible(e))
        lines.extend(["", "Recent activity (latest 60; oldest activity is pruned)"])
        lines.extend(chronicle.prose(e, flock) for e in reversed(chronicle.recent) if visible(e))
        text = "\n".join(lines)
        if text != self.snapshot:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
            self.text.configure(state="disabled")
            self.snapshot = text
