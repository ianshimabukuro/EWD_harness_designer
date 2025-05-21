import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from PIL import Image, ImageTk
from classes.symbol import Symbol
import json
import os
from datetime import datetime
import re
from ultralytics import YOLO

class SymbolAnnotator(tk.Frame):
    """
    A GUI for placing and editing electrical symbols on an image, with
    full scale setting, symbol addition, edit (coords/amperage/height),
    and delete functionality.
    """
    def __init__(self, master, container, on_done):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.container = container
        self.on_done = on_done

        self.symbol_types = self.container['symbol_types']
        self.defaults = self.container.get('default', {})
        self.scale_point_ids = []
        self.active_switch = None

        # Load YOLOv8 model ONCE at startup
        self.yolo_model = YOLO("yolo8n_weight.pt")

        # --- Top controls ---
        ctrl = tk.Frame(self)
        ctrl.pack(fill="x", pady=5)
        tk.Button(ctrl, text="Load Image", command=self.load_image).pack(side="left", padx=5)
        tk.Button(ctrl, text="Done", command=self.finish).pack(side="left", padx=5)
        tk.Button(ctrl, text="Finish Light Selection", command=self.finish_light_selection).pack(side="left", padx=5)
        self.selected_symbol = tk.StringVar(value=self.symbol_types[0])
        tk.OptionMenu(
            ctrl,
            self.selected_symbol,
            *self.symbol_types,
            command=lambda *_: (self.update_status(), self.update_annotation_list())
        ).pack(side="left", padx=5)
        self.status_var = tk.StringVar()
        tk.Label(self, textvariable=self.status_var).pack(fill="x")

        # --- Canvas + scrollbars ---
        canvas_frame = tk.Frame(self)
        canvas_frame.pack(fill="both", expand=True)
        h_scroll = tk.Scrollbar(canvas_frame, orient="horizontal"); h_scroll.pack(side="bottom", fill="x")
        v_scroll = tk.Scrollbar(canvas_frame, orient="vertical"); v_scroll.pack(side="right", fill="y")
        self.canvas = tk.Canvas(canvas_frame, bg="white",
                                xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        h_scroll.config(command=self.canvas.xview); v_scroll.config(command=self.canvas.yview)

        # --- Annotation list ---
        summary = tk.Frame(self)
        summary.pack(fill="x", padx=10, pady=5)
        tk.Label(summary, text="Current Annotations:").pack(anchor="w")
        self.annotation_listbox = tk.Listbox(summary, height=6, width=80)
        self.annotation_listbox.pack(fill="x")
        # Bind double-click to edit
        self.annotation_listbox.bind("<Double-Button-1>", self.open_edit_dialog_for)

        # --- Event binding ---
        self.canvas.bind("<Button-1>", self.click_event)

        # --- State holders ---
        self.img_tk = None
        self.img_id = None
        self.scale_points = []
        self.scale_set = False
        
        self.update_status()
        self.update_annotation_list()
    

    def load_image(self):
        path = filedialog.askopenfilename(title="Select floor plan image")
            # Safely extract base image name without extension

        if not path:
            return
        self.container["image_path"] = path
        self.container["image_name"] = os.path.basename(path).split('.')[0]
        img = Image.open(path)
        self.img_tk = ImageTk.PhotoImage(img)

        if self.img_id:
            self.canvas.delete(self.img_id)
        self.img_id = self.canvas.create_image(0, 0, anchor="nw",
                                            image=self.img_tk,
                                            tags=("background",))
        self.canvas.config(scrollregion=(0, 0,
                                        self.img_tk.width(),
                                        self.img_tk.height()))

        # === Ask if user wants to resume ===
        if messagebox.askyesno("Continue?", "Load previous annotations?"):
            json_path = filedialog.askopenfilename(
                title="Select annotation JSON",
                filetypes=[("JSON Files", "*.json")]
            )
            if json_path:
                try:
                    with open(json_path, "r") as f:
                        raw = json.load(f)

                    self.container["symbols"].clear()
                    # First pass: load all symbols
                    symbols_raw = raw.get("symbols", [])
                    symbols = [Symbol.from_dict(entry) for entry in symbols_raw]
                    self.container["symbols"].clear()
                    self.container["symbols"].extend(symbols)

                    # Second pass: link switch.controls
                    id_map = {s.id: s for s in symbols}
                    for entry in symbols_raw:
                        if entry["type"] == "switch":
                            switch = id_map[entry["id"]]
                            control_ids = entry.get("controls", [])
                            switch.controls = [id_map[cid] for cid in control_ids if cid in id_map]

                    # Draw symbols on canvas
                    for sym in self.container["symbols"]:
                        self.draw_symbol(sym)

                    self.container["scale"] = raw.get("scale", None)
                    self.scale_set = self.container["scale"] is not None

                    if not self.scale_set:
                        messagebox.showinfo("Info", "No scale info found in annotation. Please set scale.")
                        self.begin_scale_collection()

                    self.update_annotation_list()
                    print(f"✅ Loaded {len(self.container['symbols'])} annotations.")
                    return
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load annotations: {e}")
        else:
            YOLO_CLASS_MAP = {
                0: "light",
                1: "outlet",
                2: "electrical panel",
                3: "switch"
            }
            results = self.yolo_model(self.container["image_path"])[0]
            self.container["symbols"].clear()
            for box in results.boxes:
                cls_idx = int(box.cls[0])
                symbol_type = YOLO_CLASS_MAP.get(cls_idx, "unknown")
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x_center = (x1 + x2) / 2
                y_center = (y1 + y2) / 2
                defs = self.defaults.get(symbol_type, {})
                sym = Symbol(symbol_type, (x_center, y_center), room=None,
                             amperage=defs.get("amperage"),
                             height=defs.get("height"))
                self.container["symbols"].append(sym)
                self.draw_symbol(sym)
            self.update_annotation_list()
            print(f"✅ Detected {len(self.container['symbols'])} symbols from YOLOv8.")
        self.begin_scale_collection()



    def begin_scale_collection(self):
        self.scale_points.clear()
        self.scale_set = False
        self.status_var.set("Left-click two points with known real-world distance to set the scale.")
        # Temporarily override click
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.collect_scale_point)

    def collect_scale_point(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.scale_points.append((x, y))
        dot = self.canvas.create_oval(x-3, y-3, x+3, y+3,
                                      outline="blue", width=2)
        self.scale_point_ids.append(dot)
        if len(self.scale_points) == 2:
            # Restore click handler
            self.canvas.unbind("<Button-1>")
            self.canvas.bind("<Button-1>", self.click_event)
            self.prompt_for_scale()

    def prompt_for_scale(self):
        (x1, y1), (x2, y2) = self.scale_points
        pixel_dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
        real = simpledialog.askfloat("Set Scale",
                                     "Enter real-world distance between points (feet):",
                                     parent=self.master)
        if real and pixel_dist > 0:
            scale = real / pixel_dist
            self.container['scale'] = scale
            self.scale_set = True
            self.status_var.set(f"Scale set: {scale:.4f} ft/pixel")
        else:
            self.status_var.set("Invalid scale. Reload image to retry.")
        # Clean up dots
        for d in self.scale_point_ids:
            self.canvas.delete(d)
        self.scale_point_ids.clear()
        self.scale_points.clear()

    def update_status(self, *_):
        st = self.selected_symbol.get()
        if st.lower() == "light" and self.active_switch:
            self.status_var.set("Click to place a light controlled by current switch.")
        else:
            self.status_var.set(f"Select all {st}s where they meet the wall.")

    def click_event(self, event):
        if not self.scale_set:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        # Check for click on existing symbol first
        R = 6  # pick radius slightly larger than symbol
        for sym in self.container["symbols"]:
            sx, sy = sym.coords
            if (x - sx)**2 + (y - sy)**2 <= R*R:
                self.open_edit_dialog_for(sym)
                return

        # Otherwise add a new symbol
        stype = self.selected_symbol.get()
        defs = self.defaults.get(stype, {})
        sym = Symbol(stype, (x, y), room=None,
                     amperage=defs.get("amperage"),
                     height=defs.get("height"))

        if stype.lower() == "switch":
            self.container["symbols"].append(sym)
            self.active_switch = sym
            self.selected_symbol.set("light")
            self.status_var.set("Now click the lights this switch controls.")
        elif stype.lower() == "light":
            if not self.active_switch:
                self.status_var.set("Place a switch first.")
                return
            self.active_switch.controls.append(sym)
            self.container["symbols"].append(sym)
            sx, sy = self.active_switch.coords
            self.canvas.create_line(sx, sy, x, y,
                                    fill="blue", dash=(2,2),
                                    tags=("connection",))
        else:
            self.container["symbols"].append(sym)
            self.active_switch = None

        self.draw_symbol(sym)
        self.update_annotation_list()

    def draw_symbol(self, symbol):
        x, y = symbol.coords
        tag = ("symbol", f"id_{symbol.id}")
        t = symbol.type.lower()
        if t == 'outlet':
            self.canvas.create_rectangle(x-6, y-4, x+6, y+4, fill="red", tags=tag)
            self.canvas.create_oval(x-2, y-2, x+2, y+2, fill="white", outline="", tags=tag)
        elif t == 'switch':
            self.canvas.create_polygon(
                x, y-6, x-6, y+6, x+6, y+6,
                fill="green", outline="black", tags=tag
            )
            # Add label next to switch
            self.canvas.create_text(x+15, y, text=f"S{symbol.id}", fill="black", font=("Arial", 8), tags=tag)
        elif t == 'light':
            self.canvas.create_oval(x-7, y-7, x+7, y+7, fill="yellow", outline="orange", tags=tag)
            self.canvas.create_text(x, y, text="*", fill="orange", font=("Arial", 10, "bold"), tags=tag)
            # Add label next to light
            self.canvas.create_text(x+15, y, text=f"L{symbol.id}", fill="black", font=("Arial", 8), tags=tag)
        elif t == 'electrical panel':
            self.canvas.create_rectangle(x-8, y-12, x+8, y+12, fill="blue", outline="black", width=2, tags=tag)
        elif t == 'junction box':
            self.canvas.create_polygon(
                x, y-8, x+8, y, x, y+8, x-8, y,
                fill="gray", outline="black", tags=tag
            )
        else:
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="black", tags=tag)

    def update_annotation_list(self):
        self.annotation_listbox.delete(0, tk.END)
        sel = self.selected_symbol.get()
        for sym in self.container["symbols"]:
            if sym.type == sel:
                ctrl = ""
                if sym.type.lower() == "switch" and sym.controls:
                    pts = [f"({int(l.coords[0])},{int(l.coords[1])})" for l in sym.controls]
                    ctrl = " -> " + ", ".join(pts)
                txt = (f"{sym.type} (ID:{sym.id}) at "
                       f"({int(sym.coords[0])}, {int(sym.coords[1])}) | "
                       f"Amperage: {sym.amperage} | Height: {sym.height}{ctrl}")
                self.annotation_listbox.insert(tk.END, txt)

    def open_edit_dialog_for(self, sym):
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Symbol (ID: {sym.id})")
        tk.Label(dlg, text=f"Type: {sym.type}", font=("Arial", 12, "bold"))\
          .grid(row=0, column=0, columnspan=2, pady=(10,5))

        tk.Label(dlg, text="X coordinate:").grid(row=1, column=0, sticky="e", padx=5)
        xvar = tk.StringVar(value=str(sym.coords[0]))
        tk.Entry(dlg, textvariable=xvar).grid(row=1, column=1, padx=5)

        tk.Label(dlg, text="Y coordinate:").grid(row=2, column=0, sticky="e", padx=5)
        yvar = tk.StringVar(value=str(sym.coords[1]))
        tk.Entry(dlg, textvariable=yvar).grid(row=2, column=1, padx=5)

        defs = self.defaults.get(sym.type, {})
        row = 3
        amps_var = None
        if defs.get("amperage") is not None:
            tk.Label(dlg, text="Amperage:").grid(row=row, column=0, sticky="e", padx=5)
            amps_var = tk.StringVar(value=str(sym.amperage))
            tk.Entry(dlg, textvariable=amps_var).grid(row=row, column=1, padx=5)
            row += 1

        hgt_var = None
        if defs.get("height") is not None:
            tk.Label(dlg, text="Height:").grid(row=row, column=0, sticky="e", padx=5)
            hgt_var = tk.StringVar(value=str(sym.height))
            tk.Entry(dlg, textvariable=hgt_var).grid(row=row, column=1, padx=5)
            row += 1

        # --- Controls selection for switches ---
        controls_listbox = None
        if sym.type.lower() == "switch":
            tk.Label(dlg, text="Controls lights:").grid(row=row, column=0, sticky="e", padx=5)
            controls_listbox = tk.Listbox(dlg, selectmode="multiple", height=5)
            # List all lights
            light_syms = [s for s in self.container["symbols"] if s.type.lower() == "light"]
            for idx, l in enumerate(light_syms):
                controls_listbox.insert(tk.END, f"ID:{l.id} at ({int(l.coords[0])},{int(l.coords[1])})")
                if l in sym.controls:
                    controls_listbox.selection_set(idx)
            controls_listbox.grid(row=row, column=1, padx=5)
            row += 1

        # --- Controlled by selection for lights ---
        controlled_by_listbox = None
        if sym.type.lower() == "light":
            tk.Label(dlg, text="Controlled by switch:").grid(row=row, column=0, sticky="e", padx=5)
            controlled_by_listbox = tk.Listbox(dlg, selectmode="single", height=5)
            switch_syms = [s for s in self.container["symbols"] if s.type.lower() == "switch"]
            for idx, s in enumerate(switch_syms):
                controlled_by_listbox.insert(tk.END, f"ID:{s.id} at ({int(s.coords[0])},{int(s.coords[1])})")
                if hasattr(s, "controls") and sym in s.controls:
                    controlled_by_listbox.selection_set(idx)
            controlled_by_listbox.grid(row=row, column=1, padx=5)
            row += 1

        def save():
            try:
                newx = float(xvar.get()); newy = float(yvar.get())
                sym.coords = (newx, newy)
            except ValueError:
                messagebox.showerror("Invalid input", "Coordinates must be numbers.")
                return
            if amps_var:
                try:
                    sym.amperage = int(amps_var.get())
                except ValueError:
                    messagebox.showerror("Invalid input", "Amperage must be integer.")
                    return
            if hgt_var:
                try:
                    sym.height = int(hgt_var.get())
                except ValueError:
                    messagebox.showerror("Invalid input", "Height must be integer.")
                    return
            # Save controls for switch
            if controls_listbox:
                selected = controls_listbox.curselection()
                sym.controls = [light_syms[i] for i in selected]
            # Save controlled by for light
            if controlled_by_listbox:
                selected = controlled_by_listbox.curselection()
                if selected:
                    # Remove this light from all switches' controls first
                    for s in switch_syms:
                        if hasattr(s, "controls") and sym in s.controls:
                            s.controls.remove(sym)
                    # Add to selected switch
                    switch_syms[selected[0]].controls.append(sym)
            self.refresh_canvas()
            self.update_annotation_list()
            dlg.destroy()

        def delete():
            self.delete_symbol(sym)
            dlg.destroy()

        btns = tk.Frame(dlg)
        btns.grid(row=row, column=0, columnspan=2, pady=10)
        tk.Button(btns, text="Save",   command=save).pack(side="left", padx=5)
        tk.Button(btns, text="Delete", command=delete).pack(side="left", padx=5)
        tk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

    def delete_symbol(self, sym):
        if self.active_switch == sym:
            self.active_switch = None
        if sym.type.lower() == "switch":
            sym.controls.clear()
        try:
            self.container["symbols"].remove(sym)
        except ValueError:
            pass
        self.refresh_canvas()
        self.update_annotation_list()

    def refresh_canvas(self):
        # Remove only symbols & connections
        self.canvas.delete("symbol")
        self.canvas.delete("connection")
        for sym in self.container["symbols"]:
            if sym.type.lower() == "switch":
                sx, sy = sym.coords
                for lt in sym.controls:
                    lx, ly = lt.coords
                    self.canvas.create_line(sx, sy, lx, ly,
                                        fill="blue", dash=(2,2),
                                        tags=("connection",))
            x, y = sym.coords
            tag = ("symbol", f"id_{sym.id}")
            t = sym.type.lower()
            if t == 'outlet':
                self.canvas.create_rectangle(x-6, y-4, x+6, y+4, fill="red", tags=tag)
                self.canvas.create_oval(x-2, y-2, x+2, y+2, fill="white", outline="", tags=tag)
            elif t == 'switch':
                self.canvas.create_polygon(
                    x, y-6, x-6, y+6, x+6, y+6,
                    fill="green", outline="black", tags=tag
                )
                # Add label next to switch
                self.canvas.create_text(x+15, y, text=f"S{sym.id}", fill="black", font=("Arial", 8), tags=tag)
            elif t == 'light':
                self.canvas.create_oval(x-7, y-7, x+7, y+7, fill="yellow", outline="orange", tags=tag)
                self.canvas.create_text(x, y, text="*", fill="orange", font=("Arial", 10, "bold"), tags=tag)
                # Add label next to light
                self.canvas.create_text(x+15, y, text=f"L{sym.id}", fill="black", font=("Arial", 8), tags=tag)
            elif t == 'electrical panel':
                self.canvas.create_rectangle(x-8, y-12, x+8, y+12, fill="blue", outline="black", width=2, tags=tag)
            elif t == 'junction box':
                self.canvas.create_polygon(
                    x, y-8, x+8, y, x, y+8, x-8, y,
                    fill="gray", outline="black", tags=tag
                )
            else:
                self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="black", tags=tag)

    def finish_light_selection(self):
        if self.active_switch:
            self.active_switch = None
            self.selected_symbol.set("switch")
            self.status_var.set("Select symbols as usual.")
        else:
            self.status_var.set("No active switch to finish.")

    def save_annotations_to_json(self, path="annotations.json"):
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"annotations_{str(self.container["image_name"])}_{timestamp}.json"
        path = os.path.join("output", filename)
        data = {
            "scale": self.container.get("scale", 1.0),  # default to 1.0 if not set
            "symbols": [s.to_dict() for s in self.container["symbols"]]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Annotations saved to {os.path.abspath(path)}")
    
    def validate_annotations(self):
        errors = []
        # Rule: Only one electrical panel
        panels = [s for s in self.container["symbols"] if s.type.lower() == "electrical panel"]
        if len(panels) != 1:
            errors.append(f"There must be exactly ONE electrical panel. There are {len(panels)} ")
        return errors

    def finish(self):
        errors = self.validate_annotations()
        if errors:
            messagebox.showerror("Annotation Check Failed", "\n".join(errors))
            return
        self.save_annotations_to_json()
        self.pack_forget()
        self.on_done(self.container)
