# 🛠️ Electrical Wiring Design for Residential Harnesses

A lightweight, Tkinter-based tool for manually annotating electrical symbols on a floor plan, generating a wiring layout, and exporting manufacturing-ready documentation.


The main idea behind the program is to represent the electrical plan as a **grid of all possible paths**.  
Since every symbol is placed on a **wall or ceiling**, creating a **Hanan grid** of all annotated symbols naturally respects structural boundaries (e.g., walls).

## ✅ Requirements

- Python **3.12 or higher**

Recommended: Install required libraries via:

```bash
pip install -r requirements.txt
 ```

### 🔌 Wiring Process

The wiring is done in two steps:

1. **Room Wiring**  
   - Every symbol is connected to its room’s **junction box**.  
   - If the symbol is a **switch**, each **light it controls** is first connected to the switch, and then the switch is connected to the junction box.

2. **Home Run Wiring**  
   - Each **junction box** is connected to the **electrical panel** using the shortest valid path.

---

## ⚙️ Defaults and Configuration

Default values for:
- Symbol **height**
- Device **amperage**
- **Cost** per wire gauge

...are defined in the `config.py` file (or the container dictionary). You can modify these to suit your project needs.


## 🔁 Flow of the Program

### 🖊️ Symbol Annotator
1. Load the **Electrical Plan Image**.
2. Select two points to set the **Pixel/Ft scale**.
3. Annotate all symbols (e.g., **lights**, **switches**, **outlets**).
4. Once all symbols are annotated, click **Done**.

### 🏷️ Room Annotator
1. Define the perimeter of each room by selecting points on the grid (**always clockwise**).
2. Click **"Finish Room"** and assign a name.
3. When all rooms are assigned, click **Done**.

### 📐 Wiring Visualizer
1. The **2D wiring layout** will be automatically generated.
2. You can:
   - 🖼️ Export the image of the wiring layout.
   - 🧾 Export the **manufacturing instructions**.
   - 📦 Export the **Bill of Materials (BoM)**.


