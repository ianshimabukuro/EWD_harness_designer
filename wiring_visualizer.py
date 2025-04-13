import tkinter as tk
from PIL import Image, ImageTk
import networkx as nx
from collections import defaultdict
import csv
import os

UNIT_PRICES = {
    "14 AWG": 0.12,
    "12 AWG": 0.18,
    "10 AWG": 0.25,
    "8 AWG": 0.35,
    "Consult engineer": 0.00  # default fallback
}

class WiringVisualizer(tk.Frame):
    def __init__(self, master, symbols, graph, image_path):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.master = master
        self.symbols = symbols
        self.graph = graph
        self.image_path = image_path

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

        self.image = Image.open(self.image_path)
        self.img_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.img_tk)

        self.draw_symbols()
        self.create_wiring()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        button_frame = tk.Frame(self)
        button_frame.pack(fill="x", pady=10)

        tk.Button(button_frame, text="Export Manufacturing Instructions", command=self.export_instructions).pack(side="left", padx=10)
        tk.Button(button_frame, text="Export BoM (LaTeX)", command=self.export_bom_latex).pack(side="left", padx=10)
        tk.Button(button_frame, text="Export Bill of Materials", command=self.export_bom).pack(side="left", padx=10)

    def draw_grid(self):
        x_coords = sorted(set(x for x, _ in self.graph.nodes()))
        y_coords = sorted(set(y for _, y in self.graph.nodes()))

        for x in x_coords:
            self.canvas.create_line(x, min(y_coords), x, max(y_coords), fill="gray", dash=(2, 2))
        for y in y_coords:
            self.canvas.create_line(min(x_coords), y, max(x_coords), y, fill="gray", dash=(2, 2))

        for node in self.graph.nodes():
            x, y = node
            color = "red" if self.graph.nodes[node].get("is_dot") else "blue"
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=color)


    def draw_symbols(self):
        for s in self.symbols:
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


    def generate_bom(self, scale_factor=0.05):
        bom = defaultdict(list)
        for symbol in self.symbols:
            if symbol.room and symbol.type not in ("junction box", "electrical panel"):
                junction = next((s for s in self.symbols if s.type == "junction box" and s.room == symbol.room), None)
                if not junction:
                    continue
                try:
                    path = nx.shortest_path(self.graph, source=symbol.coords, target=junction.coords)
                except nx.NetworkXNoPath:
                    continue
                total_length = sum(
                    ((path[i+1][0]-path[i][0])**2 + (path[i+1][1]-path[i][1])**2)**0.5
                    for i in range(len(path)-1)
                ) * scale_factor
                gauge = self.assign_wire_gauge(float(symbol.amperage), total_length)
                bom[symbol.room].append({
                    "type": symbol.type,
                    "amperage": symbol.amperage,
                    "length_ft": round(total_length, 2),
                    "wire_gauge": gauge
                })
        return bom


    def create_wiring(self):


        #Create dict with key as room and value as list of devices
        symbols_by_room = defaultdict(list)
        for s in self.symbols:
            if s.room and s.type != "electrical panel":
                symbols_by_room[s.room].append(s)

        #Room by Room Wiring
        paths_by_room = {}
        for room, devices in symbols_by_room.items():
            junctions = [s for s in devices if s.type == "junction box"]
            if not junctions:
                print(f"⚠️ Room '{room}' has no junction box. Skipping...")
                continue

            junction = junctions[0]
            junction_node = (int(junction.coords[0]), int(junction.coords[1]))
            room_paths = []

            for device in devices:
                if device is junction:
                    continue
                device_node = (int(device.coords[0]), int(device.coords[1]))
                try:
                    path = nx.shortest_path(self.graph, source=device_node, target=junction_node)
                    length = self.get_total_length(path,device.height,1)
                    gauge = self.assign_wire_gauge(device.amperage,length)
                    room_paths.append({device:[path,length, gauge]})
                except nx.NetworkXNoPath:
                    print(f"❌ No path between {device_node} and junction in room '{room}'")

            paths_by_room[room] = room_paths


        #Home Run Wiring
        panel_symbols = [s for s in self.symbols if s.type == "electrical panel"]
        if panel_symbols:
            panel_node = (int(panel_symbols[0].coords[0]), int(panel_symbols[0].coords[1]))
            panel_paths = []
            for s in self.symbols:
                if s.type == "junction box":
                    junction_node = (int(s.coords[0]), int(s.coords[1]))
                    try:
                        path = nx.shortest_path(self.graph, source=junction_node, target=panel_node)
                        length = self.get_total_length(path,panel_symbols[0].height,1)
                        gauge = self.assign_wire_gauge(s.amperage,length)
                        panel_paths.append({s:[path,length,gauge]})
                    except nx.NetworkXNoPath:
                        print(f"No path from junction at {junction_node} to panel")
            paths_by_room["panel_connections"] = panel_paths
        else:
            print(" No electrical panel found. Skipping panel connections.")
        print(paths_by_room)
        self.paths_by_room = paths_by_room
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

        
    def export_bom(self, filename="bill_of_materials.csv"):
        bom = self.generate_bom(scale_factor=0.05)
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Room", "Device Type", "Amperage", "Length (ft)", "Wire Gauge"])
            for room, entries in bom.items():
                for entry in entries:
                    writer.writerow([
                        room,
                        entry["type"],
                        entry["amperage"],
                        entry["length_ft"],
                        entry["wire_gauge"]
                    ])
        print(f"📦 BoM exported to {os.path.abspath(filename)}")

    def export_instructions(self, filename="wiring_instructions.csv"):
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Room", "Device Type", "Start (x,y)", "End (x,y)", "Wire Gauge", "Length (ft)"])

            for room, device_path_list in self.paths_by_room.items():
                for device_path in device_path_list:
                    for device, (path, length, gauge) in device_path.items():
                        start = path[0]
                        end = path[-1]
                        writer.writerow([
                            room,
                            device.type,
                            f"{start[0]},{start[1]}",
                            f"{end[0]},{end[1]}",
                            gauge,
                            round(length, 2)
                        ])
        print(f"🛠️ Manufacturing instructions exported to {os.path.abspath(filename)}")
    
    def export_bom_latex(self, filename="bill_of_materials.tex"):
        bom = self.generate_bom(scale_factor=0.05)
        gauge_totals = defaultdict(float)
        for entries in bom.values():
            for item in entries:
                gauge_totals[item["wire_gauge"]] += item["length_ft"]

        # === Compute costs
        table_rows = []
        grand_total = 0.0
        for gauge, length in gauge_totals.items():
            unit_cost = UNIT_PRICES.get(gauge, 0.00)
            total_cost = round(length * unit_cost, 2)
            grand_total += total_cost
            table_rows.append((gauge, round(length, 2), unit_cost, total_cost))

        # === LaTeX document
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
            r"\section*{Wire Gauge Cost Summary}",
            r"\begin{tabular}{lllll}",
            r"\toprule",
            r"\textbf{BoM Level} & \textbf{Wire Gauge} & \textbf{Length (ft)} & \textbf{Unit Cost (\$)} & \textbf{Total Cost (\$)} \\",
            r"\midrule"
        ]


        for row in table_rows:
            gauge, length, unit_cost, total_cost = row
            lines.append(f"1 & {gauge} & {length} & {unit_cost:.2f} & {total_cost:.2f} \\\\")

        num_junctions = sum(1 for s in self.symbols if s.type == "junction box")
        num_breakers = sum(1 for s in self.symbols if s.type == "junction box")  # or based on paths to panel

        breaker_unit_cost = 5.00  # placeholder
        junction_unit_cost = 3.00

        breaker_total = num_breakers * breaker_unit_cost
        junction_total = num_junctions * junction_unit_cost
        grand_total += breaker_total + junction_total

        # Add to LaTeX table
        lines.extend([
            r"\midrule",
            f"0 & Breaker & {num_breakers} & {breaker_unit_cost:.2f} & {breaker_total:.2f} \\\\",
            f"0 & Junction Box & {num_junctions} & {junction_unit_cost:.2f} & {junction_total:.2f} \\\\",
        ])

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            "",
            rf"\section*{{Total Cost: \${grand_total:.2f}}}",
            r"\end{document}"
        ])

        with open(filename, "w") as f:
            f.write("\n".join(lines))

        print(f"📄 LaTeX BoM with costs exported to: {os.path.abspath(filename)}")

        # Optional: Compile to PDF
        import subprocess
        try:
            subprocess.run(["pdflatex", filename], check=True)
            print("✅ PDF compiled successfully.")
        except Exception:
            print("⚠️ Could not compile PDF. Is pdflatex installed?")
