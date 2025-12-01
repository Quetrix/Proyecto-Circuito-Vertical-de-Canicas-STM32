import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACIÓN SERIAL ---
PORT_NAME = '/dev/ttyACM0'
BAUD_RATE = 115200

# --- CONFIGURACIÓN FÍSICA ---
# Ajusta estos pasos según tu calibración real (4076 para 28BYJ-48)
STEPS_H = 2048  
STEPS_V = 2048  

class MarbleInterfacePro:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Control de Canicas v2.0")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e293b") # Slate 800

        # --- ESTADO DEL SISTEMA ---
        self.ser = None
        self.connect_serial()
        
        self.posicion_actual = "S1" # Asumimos inicio en S1 tras encendido/homing
        self.rutas_programadas = [] # Lista de rutas: [{'inicio': 'S1', 'camino': [...]}, ...]
        self.ruta_actual_idx = 0
        self.contador_estanon = 0
        
        # Mapa de Coordenadas (Fila, Columna)
        # S1=(0,0), S2=(0,1), S3=(0,2)
        # 1=(1,0)... 9=(3,2)
        # Destino=(4,1)
        self.mapa_coords = {
            "S1": (0,0), "S2": (0,1), "S3": (0,2),
            1: (1,0), 2: (1,1), 3: (1,2),
            4: (2,0), 5: (2,1), 6: (2,2),
            7: (3,0), 8: (3,1), 9: (3,2),
            "Destino": (4,1)
        }

        self.setup_ui()

    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1)
            time.sleep(2) 
            print("✅ Conexión Serial OK")
        except Exception:
            print("⚠️ Ejecutando en MODO SIMULACIÓN (Sin Serial)")

    def enviar_comando(self, cmd):
        """Envía comando al STM32 y actualiza log."""
        if self.ser and self.ser.is_open:
            msg = f"{cmd}\n"
            self.ser.write(msg.encode('utf-8'))
            print(f"📡 TX: {msg.strip()}")
        else:
            print(f"🖥️ SIM: {cmd}")
        time.sleep(0.1) # Pequeña pausa para evitar saturación

    # --- LÓGICA DE MOVIMIENTO ---

    def calcular_comando(self, origen, destino):
        """Genera el comando H/V basado en coordenadas."""
        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        diff_r = r2 - r1
        diff_c = c2 - c1
        
        if diff_r == 1 and diff_c == 0: return f"V-{STEPS_V}"  # Bajar (V negativo)
        if diff_r == -1 and diff_c == 0: return f"V{STEPS_V}"   # Subir (V positivo)
        if diff_c == 1 and diff_r == 0: return f"H{STEPS_H}"   # Derecha
        if diff_c == -1 and diff_r == 0: return f"H-{STEPS_H}"  # Izquierda
        
        return None # Movimiento inválido (diagonal o salto)

    def mover_fisico(self, destino, velocidad_lenta=False):
        """Mueve la canasta y actualiza estado."""
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            self.posicion_actual = destino
            self.actualizar_grid_visual()
            # Tiempo de espera estimado para completar movimiento físico
            tiempo_espera = 2.0 if not velocidad_lenta else 3.0
            self.root.update() # Refrescar UI
            time.sleep(tiempo_espera) 
            return True
        return False

    def validar_movimiento(self, origen, destino, modo="bajada"):
        """
        Reglas estrictas del PDF.
        modo 'bajada': No puede subir. Ortogonal.
        modo 'libre': Puede subir (retorno vacía).
        """
        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        # Solo movimientos adyacentes (Ortogonales)
        if abs(r1-r2) + abs(c1-c2) != 1:
            return False, "Movimiento no adyacente (salto o diagonal)."

        # Restricción de Bajada (Con canica)
        if modo == "bajada" and r2 < r1:
            return False, "🚫 Ilegal: La canica no puede subir."
            
        return True, "OK"

    # --- INTERFAZ DE USUARIO (UI) ---

    def setup_ui(self):
        # Limpiar ventana
        for widget in self.root.winfo_children():
            widget.destroy()

        # Header
        header = tk.Frame(self.root, bg="#0f172a", height=80)
        header.pack(fill="x")
        tk.Label(header, text="CONTROL DE CANICAS - NUCLEO F446RE", 
                 font=("Segoe UI", 24, "bold"), bg="#0f172a", fg="#38bdf8").pack(pady=20)
        
        # Botón RESET SISTEMA (Pánico)
        btn_reset = tk.Button(header, text="🚨 RESET TOTAL", bg="#dc2626", fg="white",
                              font=("Arial", 12, "bold"), command=self.secuencia_emergencia)
        btn_reset.place(x=850, y=20)

        # Contenedor Principal
        self.main_frame = tk.Frame(self.root, bg="#1e293b")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.mostrar_menu_principal()

    def mostrar_menu_principal(self):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        tk.Label(self.main_frame, text="Seleccione Modo de Operación", 
                 font=("Arial", 18), bg="#1e293b", fg="white").pack(pady=40)

        btn_manual = tk.Button(self.main_frame, text="🛠️ MODO MANUAL", 
                               font=("Arial", 16, "bold"), bg="#7c3aed", fg="white",
                               width=20, height=3, command=self.iniciar_modo_manual)
        btn_manual.pack(pady=20)

        btn_prog = tk.Button(self.main_frame, text="📅 MODO PROGRAMADO", 
                             font=("Arial", 16, "bold"), bg="#059669", fg="white",
                             width=20, height=3, command=self.iniciar_modo_programado)
        btn_prog.pack(pady=20)

    # --- MODO MANUAL ---

    def iniciar_modo_manual(self):
        self.construir_layout_basico("Modo Manual")
        
        # Panel de Control Manual
        lbl_inst = tk.Label(self.panel_control, text="Controles", font=("Arial", 14, "bold"), 
                            bg="#334155", fg="#94a3b8")
        lbl_inst.pack(pady=10)

        # Pad Direccional
        pad = tk.Frame(self.panel_control, bg="#334155")
        pad.pack(pady=20)
        
        btn_cfg = {"width": 6, "height": 2, "font": ("Arial", 12, "bold"), "bg": "#475569", "fg": "white"}
        
        self.btn_left = tk.Button(pad, text="◀", command=lambda: self.accion_manual("left"), **btn_cfg)
        self.btn_left.grid(row=1, column=0, padx=5)
        
        self.btn_down = tk.Button(pad, text="▼", command=lambda: self.accion_manual("down"), **btn_cfg)
        self.btn_down.grid(row=1, column=1, padx=5)
        
        self.btn_right = tk.Button(pad, text="▶", command=lambda: self.accion_manual("right"), **btn_cfg)
        self.btn_right.grid(row=1, column=2, padx=5)

        # Selección de Inicio
        tk.Label(self.panel_control, text="Teletransportar (Reset)", bg="#334155", fg="white").pack(pady=10)
        frame_start = tk.Frame(self.panel_control, bg="#334155")
        frame_start.pack()
        for zona in ["S1", "S2", "S3"]:
            tk.Button(frame_start, text=zona, command=lambda z=zona: self.set_posicion_manual(z),
                      bg="#0ea5e9", fg="white").pack(side="left", padx=5)

    def accion_manual(self, direccion):
        # Determinar destino hipotético
        r, c = self.mapa_coords[self.posicion_actual]
        destino = None
        
        if direccion == "left":
            # Buscar en mapa inverso
            target = (r, c-1)
        elif direccion == "right":
            target = (r, c+1)
        elif direccion == "down":
            target = (r+1, c)
            
        # Buscar nombre de zona por coordenadas
        for k, v in self.mapa_coords.items():
            if v == target: # Target puede no existir en mapa (fuera de límites)
                # Hack para S1->1 (S1 es 0,0, 1 es 1,0. Coincide)
                destino = k
                break
        
        # Validar
        if destino:
            valido, msg = self.validar_movimiento(self.posicion_actual, destino, "bajada")
            if valido:
                self.mover_fisico(destino)
                if destino == "Destino":
                    if messagebox.askyesno("Destino", "Llegó a Destino. ¿Volcar y regresar a S1?"):
                        self.mover_fisico("Destino") # Hack para asegurar posición
                        self.contador_estanon += 1
                        self.lbl_estanon.config(text=f"Estañón: {self.contador_estanon}")
                        self.regresar_a_origen("S1")
            else:
                messagebox.showerror("Movimiento Ilegal", msg)
        else:
            messagebox.showerror("Error", "No existe zona en esa dirección.")

    def set_posicion_manual(self, zona):
        """Simula que pusimos la canasta ahí manualmente (Teleport lógico)"""
        self.posicion_actual = zona
        self.actualizar_grid_visual()

    # --- MODO PROGRAMADO ---

    def iniciar_modo_programado(self):
        self.rutas_programadas = []
        self.construir_layout_basico("Programación de Rutas")
        self.fase_programacion()

    def fase_programacion(self):
        # Limpiar panel control
        for w in self.panel_control.winfo_children(): w.destroy()
        
        n_ruta = len(self.rutas_programadas) + 1
        tk.Label(self.panel_control, text=f"Configurando Ruta #{n_ruta}", 
                 font=("Arial", 14, "bold"), bg="#334155", fg="#fbbf24").pack(pady=10)

        # Selección Inicio
        tk.Label(self.panel_control, text="1. Zona de Inicio:", bg="#334155", fg="white").pack()
        frame_ini = tk.Frame(self.panel_control, bg="#334155")
        frame_ini.pack(pady=5)
        
        self.var_inicio = tk.StringVar(value="S1")
        for z in ["S1", "S2", "S3"]:
            tk.Radiobutton(frame_ini, text=z, variable=self.var_inicio, value=z, 
                           bg="#334155", fg="white", selectcolor="#0f172a",
                           command=self.reset_ruta_builder).pack(side="left")

        # Constructor de Ruta
        tk.Label(self.panel_control, text="2. Construir Camino:", bg="#334155", fg="white").pack(pady=5)
        self.ruta_temp = []
        self.lbl_ruta = tk.Label(self.panel_control, text="...", wraplength=280, bg="#1e293b", fg="#94a3b8")
        self.lbl_ruta.pack(pady=5)

        # Botones de Zonas (Grid numérico)
        frame_nums = tk.Frame(self.panel_control, bg="#334155")
        frame_nums.pack()
        for i in range(1, 10):
            btn = tk.Button(frame_nums, text=str(i), width=4, 
                            command=lambda z=i: self.agregar_paso_ruta(z))
            btn.grid(row=(i-1)//3, column=(i-1)%3, padx=2, pady=2)
            
        tk.Button(self.panel_control, text="DESTINO", bg="#10b981", fg="white",
                  command=lambda: self.agregar_paso_ruta("Destino")).pack(pady=10, fill="x")

        # Botones Acción
        tk.Button(self.panel_control, text="↩ Deshacer (Undo)", command=self.undo_ruta,
                  bg="#64748b", fg="white").pack(fill="x", pady=2)
        
        tk.Button(self.panel_control, text="💾 Guardar Ruta", command=self.guardar_ruta,
                  bg="#0ea5e9", fg="white").pack(fill="x", pady=10)
        
        if len(self.rutas_programadas) > 0:
             tk.Button(self.panel_control, text="▶ COMENZAR EJECUCIÓN", command=self.ejecutar_secuencia_rutas,
                  bg="#d946ef", fg="white", font=("Arial", 12, "bold")).pack(fill="x", pady=20)

    def reset_ruta_builder(self):
        self.ruta_temp = [self.var_inicio.get()]
        self.actualizar_lbl_ruta()

    def agregar_paso_ruta(self, zona):
        if not self.ruta_temp: self.reset_ruta_builder()
        
        ultimo = self.ruta_temp[-1]
        valido, msg = self.validar_movimiento(ultimo, zona, "bajada")
        
        if valido:
            self.ruta_temp.append(zona)
            self.actualizar_lbl_ruta()
        else:
            messagebox.showwarning("Invalido", msg)

    def undo_ruta(self):
        if len(self.ruta_temp) > 1:
            self.ruta_temp.pop()
            self.actualizar_lbl_ruta()

    def actualizar_lbl_ruta(self):
        self.lbl_ruta.config(text=" -> ".join(map(str, self.ruta_temp)))

    def guardar_ruta(self):
        if not self.ruta_temp or self.ruta_temp[-1] != "Destino":
            messagebox.showerror("Error", "La ruta debe terminar en 'Destino'")
            return
            
        self.rutas_programadas.append({
            "inicio": self.ruta_temp[0],
            "camino": self.ruta_temp[1:] # Guardamos solo los pasos siguientes
        })
        
        if len(self.rutas_programadas) < 3:
            if messagebox.askyesno("Guardado", f"Ruta {len(self.rutas_programadas)} guardada.\n¿Programar otra?"):
                self.fase_programacion()
            else:
                self.fase_programacion() # Refresca para mostrar botón Ejecutar
        else:
            self.fase_programacion()

    # --- EJECUCIÓN DE RUTAS (AUTOMATIZACIÓN) ---

    def ejecutar_secuencia_rutas(self):
        # Deshabilitar controles
        for w in self.panel_control.winfo_children(): w.config(state="disabled") if isinstance(w, tk.Button) else None
        
        # Hilo separado para no congelar la UI mientras se mueven los motores
        threading.Thread(target=self.proceso_ejecucion).start()

    def proceso_ejecucion(self):
        total = len(self.rutas_programadas)
        for i, ruta in enumerate(self.rutas_programadas):
            inicio = ruta['inicio']
            camino = ruta['camino']
            
            # 1. Mover canasta vacía al inicio
            self.root.after(0, lambda: messagebox.showinfo("Fase 1", f"Moviendo canasta a {inicio} para Ruta {i+1}/{total}"))
            self.regresar_a_origen(inicio)
            
            # 2. Solicitar Carga
            resp = False
            while not resp:
                # Usamos una variable de control para esperar al usuario en el hilo principal
                # Esto es un truco simple para esperar input en threading
                self.root.after(0, lambda: self.dialogo_carga(inicio))
                time.sleep(3) # Espera a que el usuario responda el dialog
                if self.confirmacion_carga: resp = True
            
            # 3. Ejecutar Ruta
            for paso in camino:
                self.mover_fisico(paso)
            
            # 4. Volcado
            self.root.after(0, lambda: messagebox.showinfo("Destino", "Llegada a Destino.\nVolcando canasta..."))
            time.sleep(2)
            self.contador_estanon += 1
            self.root.after(0, lambda: self.lbl_estanon.config(text=f"Estañón: {self.contador_estanon}"))
            
            # 5. Si hay más rutas, repetir. Si no, fin.
        
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Secuencia completada exitosamente."))
        self.root.after(0, lambda: self.mostrar_menu_principal())

    def dialogo_carga(self, zona):
        self.confirmacion_carga = messagebox.askyesno("Carga Requerida", 
            f"La canasta está en {zona}.\nPor favor coloque la canica.\n\n¿Listo para continuar?")

    def regresar_a_origen(self, destino_final):
        """Calcula ruta de retorno libre (Subida)"""
        # Algoritmo simple: Subir primero a la fila de destino, luego moverse lateral
        # Asumiendo que estamos en 'Destino' o abajo
        
        # 1. Subir a fila 3 (7,8,9) desde Destino
        if self.posicion_actual == "Destino":
            self.mover_fisico(8) # Subir a 8 (Centro)
            
        actual = self.posicion_actual
        target = destino_final
        
        # Como "subir libremente" es permitido vacio, usamos teleport lógico
        # para simular el movimiento complejo de retorno, O hacemos paso a paso inverso.
        # Haremos paso a paso vertical hacia arriba para ser realistas.
        
        r_curr, c_curr = self.mapa_coords[actual]
        r_dest, c_dest = self.mapa_coords[target]
        
        # Moverse lateralmente primero para alinearse a la columna destino
        while c_curr != c_dest:
            next_step = actual + 1 if c_dest > c_curr else actual - 1
            self.mover_fisico(next_step)
            actual = self.posicion_actual
            r_curr, c_curr = self.mapa_coords[actual]
            
        # Subir verticalmente
        while r_curr > r_dest:
            # Encontrar nodo arriba
            # Mapa inverso r,c -> nombre
            nodo_arriba = None
            for k,v in self.mapa_coords.items():
                if v == (r_curr - 1, c_curr):
                    nodo_arriba = k
                    break
            if nodo_arriba:
                self.mover_fisico(nodo_arriba)
                r_curr -= 1
            else:
                break

    # --- RESET / EMERGENCIA ---
    def secuencia_emergencia(self):
        if messagebox.askyesno("EMERGENCIA", "¿Desea abortar todo y reiniciar el sistema?\nEsto bajará la canasta a Destino y reiniciará."):
            # 1. Bajar a lo bruto
            self.enviar_comando(f"V-{STEPS_V * 4}") # Bajar mucho por si acaso
            self.posicion_actual = "Destino"
            self.actualizar_grid_visual()
            
            # 2. Reset lógico
            self.rutas_programadas = []
            self.mostrar_menu_principal()

    # --- UTILIDADES VISUALES ---

    def construir_layout_basico(self, titulo_panel):
        # Limpiar
        self.main_frame.destroy()
        self.main_frame = tk.Frame(self.root, bg="#1e293b")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Panel Izquierdo (Controles)
        self.panel_control = tk.Frame(self.main_frame, bg="#334155", width=350)
        self.panel_control.pack(side="left", fill="y", padx=10)
        self.panel_control.pack_propagate(False)
        
        tk.Button(self.panel_control, text="⬅ MENÚ PRINCIPAL", command=self.mostrar_menu_principal,
                  bg="#64748b", fg="white").pack(fill="x", pady=5)
        
        tk.Label(self.panel_control, text=titulo_panel, font=("Arial", 16, "bold"), 
                 bg="#334155", fg="white").pack(pady=10)

        # Panel Derecho (Grid)
        self.panel_viz = tk.Frame(self.main_frame, bg="#0f172a")
        self.panel_viz.pack(side="right", fill="both", expand=True, padx=10)
        
        self.construir_grid_visual()
        
        # Estañón display
        self.lbl_estanon = tk.Label(self.panel_control, text=f"Estañón: {self.contador_estanon}", 
                                    font=("Arial", 18, "bold"), bg="#334155", fg="#facc15")
        self.lbl_estanon.pack(side="bottom", pady=20)

    def construir_grid_visual(self):
        self.cells = {}
        filas = [
            ["S1", "S2", "S3"],
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
            ["Destino"]
        ]
        
        for r, fila in enumerate(filas):
            f_frame = tk.Frame(self.panel_viz, bg="#0f172a")
            f_frame.pack(pady=10)
            for zona in fila:
                lbl = tk.Label(f_frame, text=str(zona), width=8, height=3,
                               font=("Arial", 12, "bold"), relief="ridge", bg="#475569", fg="white")
                lbl.pack(side="left", padx=10)
                self.cells[zona] = lbl
        self.actualizar_grid_visual()

    def actualizar_grid_visual(self):
        # Reset colores
        for z, lbl in self.cells.items():
            bg = "#3b82f6" if str(z).startswith("S") else "#10b981" if z == "Destino" else "#475569"
            lbl.config(bg=bg)
        
        # Highlight actual
        if self.posicion_actual in self.cells:
            self.cells[self.posicion_actual].config(bg="#f59e0b") # Amber

if __name__ == "__main__":
    root = tk.Tk()
    app = MarbleInterfacePro(root)
    root.mainloop()
