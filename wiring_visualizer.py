import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import networkx as nx
from collections import defaultdict
import csv
import os

UNIT_PRICES = {
    "14 AWG": 0.5,
    "12 AWG": 0.6,
    "10 AWG": 0.8,
    "8 AWG": 1,
    "Consult engineer": 0.00  # default fallback
}

class WiringVisualizer(tk.Frame):
    def __init__(self, master,container):

        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.container = container

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
        tk.Button(button_frame, text="Export Image", command=self.export_canvas_as_image).pack(side="left", padx=10)
        tk.Button(button_frame, text="Export BOM", command=self.export_bom_latex).pack(side="left", padx=10)
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

    def assign_wire_gauge(self, amperage, length_ft):
        if amperage <= 15:
            return "14 AWG" if length_ft <= 50 else "12 AWG"
        elif amperage <= 20:
            return "12 AWG" if length_ft <= 50 else "10 AWG"
        elif amperage <= 30:
            return "10 AWG" if length_ft <= 50 else "8 AWG"
        else:
            return "Consult engineer"
    
    def get_total_length(self, path, height, scale):
        total_length = sum(
                    ((path[i+1][0]-path[i][0])**2 + (path[i+1][1]-path[i][1])**2)**0.5
                    for i in range(len(path)-1)
                ) * scale
        
        return total_length+float(height)

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
            unit_price = UNIT_PRICES.get(gauge, 0.00)
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

        #Room by Room Wiring
        paths_by_room = {}
        total_amp_by_room = {}

        for room, devices in symbols_by_room.items():

            #If room has no junction box, skip it
            junctions = [s for s in devices if s.type == "junction box"]
            if not junctions:
                print(f"⚠️ Room '{room}' has no junction box. Skipping...")
                continue
            

            #Start Device to Junction Wiring for the current room
            junction = junctions[0]
            junction_node = (int(junction.coords[0]), int(junction.coords[1]))
            room_paths = []
            total_amp = 0

            for device in devices:
                if device is junction:
                    continue
                device_node = (int(device.coords[0]), int(device.coords[1]))
                try:
                    path = nx.shortest_path(self.container['graph'], source=device_node, target=junction_node) # Get path
                    total_amp+=device.amperage #Get room total amperage
                    length = self.get_total_length(path,device.height,self.container['scale']) #Get total lenght of path
                    gauge = self.assign_wire_gauge(device.amperage,length) #Get correct Gauge for the Path
                    room_paths.append({device:[path,length, gauge]}) #Append results to the main dict
                except nx.NetworkXNoPath:
                    print(f"❌ No path between {device_node} and junction in room '{room}'")

            paths_by_room[room] = room_paths #Get all paths
            total_amp_by_room[room] = min(total_amp*0.3, 20) #Get all rooms amps


        #Home Run Wiring
        panel_symbols = [s for s in self.container['symbols'] if s.type == "electrical panel"]
        if panel_symbols:
            panel_node = (int(panel_symbols[0].coords[0]), int(panel_symbols[0].coords[1]))
            panel_paths = []
            for s in self.container['symbols']:
                if s.type == "junction box":
                    junction_node = (int(s.coords[0]), int(s.coords[1]))
                    try:
                        path = nx.shortest_path(self.container['graph'], source=junction_node, target=panel_node)
                        total_amp = total_amp_by_room[s.room]
                        length = self.get_total_length(path,panel_symbols[0].height,self.container['scale'])
                        gauge = self.assign_wire_gauge(total_amp,length)
                        panel_paths.append({s:[path,length,gauge]})
                    except nx.NetworkXNoPath:
                        print(f"No path from junction at {junction_node} to panel")
            paths_by_room["panel_connections"] = panel_paths
        else:
            print(" No electrical panel found. Skipping panel connections.")
        print(paths_by_room)
        self.paths_by_room = paths_by_room
        self.panel_max_amp = sum(total_amp_by_room.values())
        self.draw_paths(paths_by_room)

    def draw_paths(self, paths_by_room):
        colors = ["red", "green", "blue", "orange", "purple", "cyan"]
        for i, (room, device_path_list) in enumerate(paths_by_room.items()):
            color = colors[i % len(colors)]
            for device_path in device_path_list:
                for device, (path, length, gauge) in device_path.items():
                    for j in range(len(path) - 1):
                        x1, y1 = path[j]
                        x2, y2 = path[j + 1]
                        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

                    # Optional: label at the midpoint
                    if path:
                        mid_index = len(path) // 2
                        mx, my = path[mid_index]
                        self.canvas.create_text(
                            mx, my - 10,
                            text=f"{device.type.capitalize()} ({gauge})",
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

        with open(filename, "w") as f:
            f.write("\n".join(lines))
        print(f"LaTeX BoM with costs exported to: {os.path.abspath(filename)}")

    def export_manufacturing_instructions_latex(self, filename="manufacturing_instructions.tex"):
        from collections import defaultdict
        import re

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
            r"\vspace{1em}"
        ]

        wire_id_counter = defaultdict(int)

        # === Room Assemblies ===
        for room, device_path_list in self.paths_by_room.items():
            if room == "panel_connections":
                continue
            lines.append(fr"\section*{{Room: {latex_escape(room)}}}")
            lines.append(r"\begin{enumerate}[leftmargin=*]")

            for device_path in device_path_list:
                for device, (path, length, gauge) in device_path.items():
                    wire_id_counter[room] += 1
                    wire_label = latex_escape(f"{room}_wire_{wire_id_counter[room]}")
                    start = tuple(map(int, path[0]))
                    end = tuple(map(int, path[-1]))
                    symbol_type = device.type

                    lines.append(
                        fr"\item Cut \textbf{{{round(length, 2)}}} ft of \textbf{{{gauge}}} wire labeled \textbf{{{wire_label}}}.\\"
                        fr"Connect from \texttt{{{start}}} ({symbol_type}) to junction box at \texttt{{{end}}}."
                    )

            lines.append(r"\end{enumerate}")

        # === Home Run Wiring ===
        if "panel_connections" in self.paths_by_room:
            lines.append(r"\section*{Home Run Wiring}")
            lines.append(r"\begin{enumerate}[leftmargin=*]")
            home_run_id = 1
            for device_path in self.paths_by_room["panel_connections"]:
                for junction, (path, length, gauge) in device_path.items():
                    label = f"home_run_{home_run_id}"
                    start = tuple(map(int, path[0]))
                    end = tuple(map(int, path[-1]))
                    lines.append(
                        fr"\item Cut \textbf{{{round(length, 2)}}} ft of \textbf{{{gauge}}} wire labeled \textbf{{{latex_escape(label)}}}.\\"
                        fr"Connect from junction box at \texttt{{{start}}} to electrical panel at \texttt{{{end}}}."
                    )
                    home_run_id += 1
            lines.append(r"\end{enumerate}")

        # === Panel Assembly ===
        lines.append(r"\section*{Electrical Panel Assembly}")
        lines.append(r"\begin{enumerate}[leftmargin=*]")
        for i in range(1, home_run_id):
            lines.append(
                fr"\item Connect \textbf{{home\_run\_{i}}} to breaker slot \#{i}. Use 20A GFCI/AFCI breaker."
            )
        lines.append(r"\end{enumerate}")

        lines.append(r"\end{document}")

        with open(filename, "w") as f:
            f.write("\n".join(lines))

        print(f"LaTeX manufacturing instructions exported to: {os.path.abspath(filename)}")

