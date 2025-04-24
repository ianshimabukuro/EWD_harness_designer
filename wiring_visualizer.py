import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import networkx as nx
from collections import defaultdict
from classes.wire import Wire
from datetime import datetime
import re
import csv
import os



class WiringVisualizer(tk.Frame):
    def __init__(self, master,container):

        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.container = container
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)
        self.output_path = output_dir

        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)

        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")

        self.canvas = tk.Canvas(self.canvas_frame, bg="white",
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        self.image = Image.open(self.container['image_path'])
        self.img_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        #Routine
        self.draw_symbols()
        self.create_wiring()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        #Export Buttons
        button_frame = tk.Frame(self)
        button_frame.pack(fill="x", pady=10)
        #tk.Button(button_frame, text="Export Image", command=self.export_canvas_as_image).pack(side="left", padx=10)
        #tk.Button(button_frame, text="Export BOM", command=self.export_bom_latex).pack(side="left", padx=10)
        tk.Button(button_frame, text="Export Manufacturing Instructions", command=self.export_manufacturing_instructions_latex).pack(side="left", padx=10)


    def draw_symbols(self):
        for s in self.container['symbols']:
            symbol_type = s.type
            match symbol_type:
                case 'outlet':
                    self.canvas.create_oval(s.coords[0]-3, s.coords[1]-3, s.coords[0]+3, s.coords[1]+3, fill="red")
                case 'switch':
                    self.canvas.create_oval(s.coords[0]-3, s.coords[1]-3, s.coords[0]+3, s.coords[1]+3, fill="red")
                case 'junction box':
                    self.canvas.create_rectangle(s.coords[0]-8, s.coords[1]-8, s.coords[0]+8, s.coords[1]+8, fill="red")
                case 'electrical panel':
                    self.canvas.create_rectangle(s.coords[0]-5, s.coords[1]-15, s.coords[0]+5, s.coords[1]+15, fill="black")
                case _:
                    self.canvas.create_oval(s.coords[0]-3, s.coords[1]-3, s.coords[0]+3, s.coords[1]+3, fill="red")
    def calculate_cost(self):

        wire_totals = defaultdict(float)
        breaker_count = 0
        junction_box_counts = 0

        # === Count wire lengths and connections
        for room, device_path_list in self.paths_by_room.items():
            for device_path in device_path_list:
                for device, (path, length, gauge) in device_path.items():
                    wire_totals[gauge] += length
                    if device.type == "junction box":
                        junction_box_counts += 1
            if room != "panel_connections":
                breaker_count += 1


        # === Estimate junction box pricing by # of connections

        # === Prepare table rows
        table_rows = []
        grand_total = 0.0

        # Wires
        for gauge, total_len in wire_totals.items():
            unit_price = self.container['unit_prices'].get(gauge, 0.00)
            cost = round(total_len * unit_price, 2)
            grand_total += cost
            table_rows.append((1, f"{gauge} wire", round(total_len, 2), unit_price, cost))

        # Junction Boxes
        jb_unit_cost = 5.00
        jb_total = junction_box_counts*jb_unit_cost
        grand_total +=jb_total
        table_rows.append((0, "Junction Box", junction_box_counts, jb_unit_cost, jb_total))

        # Breakers
        breaker_unit_cost = 65.00
        breaker_total = breaker_count * breaker_unit_cost
        grand_total += breaker_total
        table_rows.append((0, "20A Breaker GFCI/AFCI", breaker_count, breaker_unit_cost, breaker_total))

        #Panel
        if self.panel_max_amp <= 150:
            panel_cost = 100
            table_rows.append((0, "100-150A Electrical Panel", 1, panel_cost, panel_cost))
        else:
            panel_cost = 200
            table_rows.append((0, "200A Electrical Panel", 1, panel_cost, panel_cost))
        grand_total += panel_cost

        return grand_total, table_rows

    def create_wiring(self):


        #Create dict with key as room and value as list of devices
        symbols_by_room = defaultdict(list)
        for s in self.container['symbols']:
            if s.room and s.type != "electrical panel":
                symbols_by_room[s.room].append(s)

        #Step 1: Room by Room Wiring
        paths_by_room = {}
        total_amp_by_room = {}
        
        for room, devices in symbols_by_room.items():
            junction = next(s for s in devices if s.type == "junction box")
            junction_node = (int(junction.coords[0]), int(junction.coords[1]))

            room_paths = []
            total_amp = 0

            for device in devices:
                if device is junction:
                    continue

                # --- Switch Case: Add wires from light → switch, then switch → junction ---
                if device.type == "switch":
                    for light in device.controls:
                        try:
                            light_node = (int(light.coords[0]), int(light.coords[1]))
                            switch_node = (int(device.coords[0]), int(device.coords[1]))
                            light_path = nx.shortest_path(self.container['graph'], source=light_node, target=switch_node)
                            room_paths.append({light: Wire(light_path, light, device, self.container['scale'])})
                            total_amp += light.amperage
                        except nx.NetworkXNoPath:
                            print(f"❌ No path from light {light.id} to switch {device.id} in room '{room}'")

                    try:
                        switch_path = nx.shortest_path(self.container['graph'], source=switch_node, target=junction_node)
                        room_paths.append({device: Wire(switch_path, device, junction, self.container['scale'])})
                        total_amp += device.amperage
                    except nx.NetworkXNoPath:
                        print(f"❌ No path from switch {device.id} to junction in room '{room}'")

                # --- Other Devices (e.g. outlets) ---
                elif device.type != "light":  # lights are only added via their switch
                    try:
                        device_node = (int(device.coords[0]), int(device.coords[1]))
                        path = nx.shortest_path(self.container['graph'], source=device_node, target=junction_node)
                        room_paths.append({device: Wire(path, device, junction, self.container['scale'])})
                        total_amp += device.amperage
                    except nx.NetworkXNoPath:
                        print(f"❌ No path from {device.id} to junction in room '{room}'")

            paths_by_room[room] = room_paths
            total_amp_by_room[room] = min(total_amp * 0.3, 20)
            junction.amperage = total_amp_by_room[room]



        #Step 2: Home Run Wiring
        electrical_panel = next(s for s in self.container['symbols'] if s.type == "electrical panel")
        if electrical_panel:
            panel_node = (int(electrical_panel.coords[0]), int(electrical_panel.coords[1]))
            panel_paths = []
            for s in self.container['symbols']:
                if s.type == "junction box":
                    junction_node = (int(s.coords[0]), int(s.coords[1]))
                    try:
                        path = nx.shortest_path(self.container['graph'], source=junction_node, target=panel_node) 
                        panel_paths.append({s:Wire(path,s,electrical_panel,self.container['scale'])})
                    except nx.NetworkXNoPath:
                        print(f"No path from {s} to {electrical_panel}")
            paths_by_room["panel_connections"] = panel_paths
        else:
            print(" No electrical panel found. Skipping panel connections.")


        print(paths_by_room)
        self.paths_by_room = paths_by_room
        self.panel_max_amp = sum(total_amp_by_room.values())
        self.draw_paths(paths_by_room)

    def draw_paths(self, paths_by_room):
        for room, device_path_list in paths_by_room.items():
            for device_path in device_path_list:
                for device, wire in device_path.items():
                    path = wire.path
                    x1, y1 = path[0]
                    x2, y2 = path[-1]

                    # === Determine wire category and styling
                    if wire.start_symbol.type == "light" and wire.end_symbol.type == "switch":
                        color = "blue"
                        style = (2, 4)  # dashed
                        width = 2
                    elif wire.start_symbol.type == "switch" and wire.end_symbol.type == "junction box":
                        color = "orange"
                        style = (2, 2)
                        width = 2
                    elif wire.start_symbol.type == "junction box" and wire.end_symbol.type == "electrical panel":
                        color = "black"
                        style = None
                        width = 3
                    else:
                        color = "red"
                        style = None
                        width = 2

                    # === Draw the line path
                    for i in range(len(path) - 1):
                        x1, y1 = path[i]
                        x2, y2 = path[i + 1]
                        if style:
                            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, dash=style)
                        else:
                            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

                    # === Midpoint label
                    if path:
                        mid_index = len(path) // 2
                        mx, my = path[mid_index]
                        self.canvas.create_text(
                            mx, my - 10,
                            text=f"{wire.start_symbol.type} → {wire.end_symbol.type} ({wire.gauge})",
                            fill=color,
                            font=("Arial", 7)
                        )

        print(f"✅ Wiring paths drawn for rooms: {list(paths_by_room.keys())}")

        
    def export_canvas_as_image(self, filename="wiring_visualization.png"):
        from PIL import Image, EpsImagePlugin
        import os

        # Specify Ghostscript executable path (update this if needed)
        EpsImagePlugin.gs_windows_binary = r"C:\Program Files\gs\gs10.05.0\bin\gswin64c.exe"

        # Get full drawing area (bounding box of everything on the canvas)
        self.canvas.update()
        bbox = self.canvas.bbox("all")  # (x1, y1, x2, y2)

        if bbox is None:
            print("⚠️ Nothing to export: Canvas is empty.")
            return

        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        # Save canvas as PostScript file, using full bbox
        ps_filename = "temp_export_canvas.ps"
        self.canvas.postscript(file=ps_filename, colormode='color',
                            x=x1, y=y1, width=width, height=height, pagewidth=width, pageheight=height)

        # Convert .ps to PNG
        try:
            img = Image.open(ps_filename)
            img.load()  # Force loading
            img.save(filename, "PNG")
            print(f"🖼️ Full canvas exported to: {os.path.abspath(filename)}")
        except Exception as e:
            print("⚠️ Failed to export image:", e)
        finally:
            if os.path.exists(ps_filename):
                os.remove(ps_filename)

    def export_bom_latex(self, filename="bill_of_materials.tex"):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bill_of_materials_{timestamp}.tex"
        output = os.path.join(self.output_path, filename)

        
        grand_total, table_rows = self.calculate_cost()
        # === Create LaTeX content
        lines = [
            r"\documentclass{article}",
            r"\usepackage{booktabs}",
            r"\usepackage{graphicx}",
            r"\usepackage{geometry}",
            r"\geometry{margin=1in}",
            r"\begin{document}",
            r"\begin{center}",
            r"\includegraphics[width=0.3\textwidth]{logo.png}\\[1em]",
            r"{\LARGE \textbf{Bill of Materials Summary}}\\[0.5em]",
            r"\end{center}",
            r"\vspace{1.5em}",
            r"\section*{Component Summary}",
            r"\begin{tabular}{lllll}",
            r"\toprule",
            r"\textbf{BoM Level} & \textbf{Material} & \textbf{Quantity} & \textbf{Unit Cost (\$)} & \textbf{Total Cost (\$)} \\",
            r"\midrule"
        ]

        for level, name, qty, unit, total in table_rows:
            lines.append(f"{level} & {name} & {qty} & {unit:.2f} & {total:.2f} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            "",
            rf"\section*{{Total Cost: \${grand_total:.2f}}}",
            r"\end{document}"
        ])

        with open(output, "w") as f:
            f.write("\n".join(lines))
        print(f"LaTeX BoM with costs exported to: {os.path.abspath(output)}")

    def export_manufacturing_instructions_latex(self, filename="manufacturing_instructions.tex"):
        #Handle output path and file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manufacturing_instructinos_{timestamp}.tex"
        output = os.path.join(self.output_path, filename)


        def latex_escape(text):
            return re.sub(r'_', r'\_', str(text))

        lines = [
            r"\documentclass{article}",
            r"\usepackage{geometry}",
            r"\usepackage{enumitem}",
            r"\usepackage{titlesec}",
            r"\geometry{margin=1in}",
            r"\titleformat{\section}{\normalfont\Large\bfseries}{\thesection}{1em}{}",
            r"\begin{document}",
            r"\begin{center}",
            r"\LARGE \textbf{Wiring Harness Manufacturing Instructions}",
            r"\end{center}",
            r"\vspace{1em}",
        ]

        # === CUTTING SECTION ===
        lines.append(r"\section*{Cutting Instructions}")
        for room, device_path_list in self.paths_by_room.items():
            if room == "panel_connections":
                continue
            lines.append(fr"\subsection*{{Room: {latex_escape(room)}}}")
            lines.append(r"\begin{enumerate}[leftmargin=*]")
            for device_path in device_path_list:
                for _, wire in device_path.items():
                    lines.append(
                        fr"\item Cut \textbf{{{round(wire.length, 2)}}} ft of \textbf{{{wire.gauge}}} wire labeled \texttt{{{wire.id}}}.\\"
                        fr"Connect from \texttt{{{wire.start_symbol.type} (ID: {wire.start_symbol.id})}} to junction box \texttt{{ID: {wire.end_symbol.id}}}."
                    )
            lines.append(r"\end{enumerate}")

        # Home Run Cutting
        if "panel_connections" in self.paths_by_room:
            lines.append(r"\subsection*{Home Run Wires}")
            lines.append(r"\begin{enumerate}[leftmargin=*]")
            for device_path in self.paths_by_room["panel_connections"]:
                for _, wire in device_path.items():
                    lines.append(
                        fr"\item Cut \textbf{{{round(wire.length, 2)}}} ft of \textbf{{{wire.gauge}}} wire labeled \texttt{{{wire.id}}}.\\"
                        fr"Connect from junction box \texttt{{ID: {wire.start_symbol.id}, Room: {wire.start_symbol.room}}} "
                        fr"to Electrical Panel \texttt{{ID: {wire.end_symbol.id}}}."
                    )
            lines.append(r"\end{enumerate}")

        # === STRIPPING SECTION ===
        lines.append(r"\section*{Stripping Instructions}")
        lines.append(r"\begin{enumerate}[leftmargin=*]")
        for room_wires in self.paths_by_room.values():
            for device_path in room_wires:
                for _, wire in device_path.items():
                    lines.append(
                        fr"\item Wire \texttt{{{wire.id}}}: Strip \texttt{{{wire.start_symbol.type}}} end 0.5in, "
                        fr"Strip \texttt{{{wire.end_symbol.type}}} end 0.5in."
                    )
        lines.append(r"\end{enumerate}")

        # === JUNCTION BOX CONNECTIONS ===
        lines.append(r"\section*{Junction Box Connections}")
        for room, device_path_list in self.paths_by_room.items():
            if room == "panel_connections":
                continue
            lines.append(fr"\subsection*{{Room: {latex_escape(room)}}}")
            lines.append(r"\begin{enumerate}[leftmargin=*]")
            for device_path in device_path_list:
                for _, wire in device_path.items():
                    lines.append(
                        fr"\item Connect wire \texttt{{{wire.id}}} to junction box \texttt{{ID: {wire.end_symbol.id}, Room: {wire.end_symbol.room}}}."
                    )
            lines.append(r"\end{enumerate}")

        # === HOME RUN CONNECTIONS ===
        lines.append(r"\section*{Home Run Connections}")
        lines.append(r"\begin{enumerate}[leftmargin=*]")
        for device_path in self.paths_by_room.get("panel_connections", []):
            for _, wire in device_path.items():
                lines.append(
                    fr"\item Connect home run wire \texttt{{{wire.id}}} to junction box in Room \texttt{{{wire.start_symbol.room}}} (ID: {wire.start_symbol.id})."
                )
        lines.append(r"\end{enumerate}")

        # === ELECTRICAL PANEL CONNECTIONS ===
        lines.append(r"\section*{Electrical Panel Connections}")
        lines.append(r"\subsection*{Home Run to Breaker}")
        lines.append(r"\begin{enumerate}[leftmargin=*]")
        for idx, device_path in enumerate(self.paths_by_room.get("panel_connections", []), start=1):
            for _, wire in device_path.items():
                lines.append(
                    fr"\item Connect Home Run wire \texttt{{{wire.id}}} to breaker slot \#{idx}."
                )
        lines.append(r"\end{enumerate}")

        lines.append(r"\subsection*{Breaker to Panel}")
        lines.append(r"\begin{enumerate}[leftmargin=*]")
        for idx, device_path in enumerate(self.paths_by_room.get("panel_connections", []), start=1):
            lines.append(
                fr"\item Connect breaker \#{idx} to Electrical Panel main bus."
            )
        lines.append(r"\end{enumerate}")
        lines.append(r"\end{document}")

        #Export file
        with open(output, "w") as f:
            f.write("\n".join(lines))
        print(f"LaTeX manufacturing instructions exported to: {os.path.abspath(output)}")