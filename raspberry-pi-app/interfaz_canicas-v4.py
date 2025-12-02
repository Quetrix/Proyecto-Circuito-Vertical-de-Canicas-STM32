import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACION SERIAL ---
PORT_NAME = '/dev/ttyACM0'
BAUD_RATE = 115200

# --- CONFIGURACION FISICA ---
STEPS_H = 1536
STEPS_V = 1408
# Ajuste fino para calibracion (1/8 del movimiento normal)
CALIB_H = int(STEPS_H / 8)
CALIB_V = int(STEPS_V / 8)

class MarbleInterfaceFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("SISTEMA DE CONTROL V4.0")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e293b") 

        # --- ESTADO DEL SISTEMA ---
        self.ser = None
        self.connect_serial()
        
        self.posicion_actual = "S1"
        self.columna_virtual_destino = 1 # Para recordar si bajamos por col 0, 1 o 2
        
        # Diccionario de rutas: Clave=Inicio (S1, S2...), Valor=Lista de pasos
        self.rutas_programadas = {} 
        self.contador_estanon = 0
        
        # Mapa Logico (Fila, Columna)
        self.mapa_coords = {
            "S1": (0,0), "S2": (0,1), "S3": (0,2),
            1: (1,0), 2: (1,1), 3: (1,2),
            4: (2,0), 5: (2,1), 6: (2,2),
            7: (3,0), 8: (3,1), 9: (3,2),
            "Destino": (4,1) # Coordenada base, pero dinamica en logica
        }

        self.setup_ui()

    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1)
            time.sleep(2) 
            print("CONEXION SERIAL OK")
        except Exception:
            print("MODO SIMULACION (Sin Serial)")

    def enviar_comando(self, cmd):
        """Envia comando por Serial (Thread-safe)"""
        try:
            if self.ser and self.ser.is_open:
                msg = f"{cmd}\n"
                self.ser.write(msg.encode('utf-8'))
                print(f"TX: {msg.strip()}")
            else:
                print(f"SIM: {cmd}")
        except Exception as e:
            print(f"Error Serial: {e}")

    # --- LOGICA DE CALCULO ---

    def calcular_comando(self, origen, destino):
        r1, c1 = self.mapa_coords[origen]
        
        # Manejo especial de coordenadas para DESTINO
        if origen == "Destino":
            # Si estamos en Destino, usamos la columna virtual donde realmente estamos
            r1 = 4
            c1 = self.columna_virtual_destino
        
        if destino == "Destino":
            # Si vamos a destino, la columna logica depende de donde venimos
            r2 = 4
            # Si venimos de 7, 8 o 9, mantenemos su columna
            if origen in [7, 8, 9]:
                _, c_temp = self.mapa_coords[origen]
                c2 = c_temp
            else:
                c2 = 1 # Default (no deberia pasar por validacion)
        else:
            r2, c2 = self.mapa_coords[destino]

        diff_r = r2 - r1
        diff_c = c2 - c1
        
        # Logica de Hardware
        if diff_r == 1 and diff_c == 0: return f"V-{STEPS_V}"  # Bajar
        if diff_r == -1 and diff_c == 0: return f"V{STEPS_V}"   # Subir
        if diff_c == 1 and diff_r == 0: return f"H{STEPS_H}"   # Derecha
        if diff_c == -1 and diff_r == 0: return f"H-{STEPS_H}"  # Izquierda
        
        return None 

    def validar_movimiento(self, origen, destino):
        # Regla 1: A Destino solo se baja desde 7, 8, 9
        if destino == "Destino":
            if origen in [7, 8, 9]: return True, "OK"
            return False, "A Destino solo se baja desde 7, 8 o 9"

        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        # Adyacencia
        if abs(r1-r2) + abs(c1-c2) != 1:
            return False, "Movimiento no adyacente"
        
        # No subir (Regla general de programacion, no aplica a retorno vacio)
        if r2 < r1:
            return False, "No se puede subir en ruta"
            
        return True, "OK"

    # --- THREADING Y MOVIMIENTO ---

    def ejecutar_movimiento_thread(self, destino, callback=None):
        """Hilo para mover sin congelar UI"""
        threading.Thread(target=self._proceso_mover, args=(destino, callback)).start()

    def _proceso_mover(self, destino, callback):
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            
            # Actualizar logica especial de Destino
            if destino == "Destino":
                # Guardar en que columna bajamos (0, 1 o 2)
                _, c_origen = self.mapa_coords[self.posicion_actual]
                self.columna_virtual_destino = c_origen
            
            # Actualizar posicion logica
            self.posicion_actual = destino
            
            # Actualizar UI desde el hilo principal
            self.root.after(0, self.actualizar_grid_visual)
            
            # Esperar tiempo fisico (Simulacion de tiempo de motor)
            time.sleep(2.5) 
            
            if callback:
                self.root.after(0, callback)

    # --- INTERFAZ UI ---

    def setup_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()

        # Header
        header = tk.Frame(self.root, bg="#0f172a", height=60)
        header.pack(fill="x")
        tk.Label(header, text="CONTROL DE CANICAS", font=("Arial", 20, "bold"), 
                 bg="#0f172a", fg="#e2e8f0").pack(side="left", padx=20, pady=10)
        
        # Boton RESET TOTAL
        tk.Button(header, text="RESET TOTAL", bg="#dc2626", fg="white", font=("Arial", 10, "bold"),
                  command=self.iniciar_reset_total).pack(side="right", padx=20, pady=10)

        # Main Frame
        self.main_frame = tk.Frame(self.root, bg="#1e293b")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.mostrar_menu_principal()

    def mostrar_menu_principal(self):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        tk.Label(self.main_frame, text="MENU PRINCIPAL", font=("Arial", 18), 
                 bg="#1e293b", fg="white").pack(pady=30)

        btn_opts = {"width": 30, "height": 2, "font": ("Arial", 14, "bold"), "bg": "#334155", "fg": "white"}
        
        tk.Button(self.main_frame, text="1. MODO MANUAL", command=self.iniciar_modo_manual, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="2. MODO PROGRAMADO", command=self.iniciar_modo_programado, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="3. CALIBRACION (AJUSTE FINO)", command=self.iniciar_modo_calibracion, **btn_opts).pack(pady=10)

    def construir_pantalla_base(self, titulo, mostrar_grid=True):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        # Barra Titulo
        top = tk.Frame(self.main_frame, bg="#334155")
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=titulo, font=("Arial", 14, "bold"), bg="#334155", fg="#facc15").pack(side="left", padx=10)
        tk.Button(top, text="MENU", bg="#64748b", fg="white", command=self.mostrar_menu_principal).pack(side="right", padx=10, pady=5)

        # Paneles
        self.panel_izq = tk.Frame(self.main_frame, bg="#1e293b", width=400)
        self.panel_izq.pack(side="left", fill="y", padx=10)
        
        if mostrar_grid:
            self.panel_der = tk.Frame(self.main_frame, bg="#0f172a")
            self.panel_der.pack(side="right", fill="both", expand=True, padx=10)
            self.construir_grid_visual()
        else:
            self.panel_der = None # Sin mapa en calibracion

        self.lbl_estanon = tk.Label(self.panel_izq, text=f"Estanon: {self.contador_estanon}", 
                                    font=("Arial", 16, "bold"), bg="#1e293b", fg="#facc15")
        self.lbl_estanon.pack(side="bottom", pady=20)

    # --- MODO 3: CALIBRACION (1/8 PASOS) ---

    def iniciar_modo_calibracion(self):
        self.construir_pantalla_base("CALIBRACION (AJUSTE FINO 1/8)", mostrar_grid=False)
        
        lbl = tk.Label(self.panel_izq, text="Mueve los motores para ajustar S1.\nEl mapa visual esta desactivado.", 
                       bg="#1e293b", fg="#94a3b8", justify="left")
        lbl.pack(pady=20)

        # Pad Calibracion
        pad = tk.Frame(self.panel_izq, bg="#1e293b")
        pad.pack(pady=20)
        
        tk.Button(pad, text="ARRIBA", command=lambda: self.mover_calib("V", 1), bg="#3b82f6", fg="white", width=10, height=2).grid(row=0, column=1, pady=5)
        tk.Button(pad, text="IZQUIERDA", command=lambda: self.mover_calib("H", -1), bg="#3b82f6", fg="white", width=10, height=2).grid(row=1, column=0, padx=5)
        tk.Button(pad, text="DERECHA", command=lambda: self.mover_calib("H", 1), bg="#3b82f6", fg="white", width=10, height=2).grid(row=1, column=2, padx=5)
        tk.Button(pad, text="ABAJO", command=lambda: self.mover_calib("V", -1), bg="#3b82f6", fg="white", width=10, height=2).grid(row=2, column=1, pady=5)

        tk.Button(self.panel_izq, text="DEFINIR ESTO COMO S1", bg="#10b981", fg="white", font=("Arial", 11, "bold"),
                  command=self.confirmar_s1).pack(pady=30, fill="x")

    def mover_calib(self, eje, dir):
        # Mueve 1/8 de paso sin logica
        pasos = CALIB_V if eje == "V" else CALIB_H
        signo = "" if dir > 0 else "-"
        self.enviar_comando(f"{eje}{signo}{pasos}")

    def confirmar_s1(self):
        if messagebox.askyesno("Confirmar", "¿Posicion actual es S1?"):
            self.posicion_actual = "S1"
            self.columna_virtual_destino = 0 # Reset de variables
            messagebox.showinfo("Listo", "Calibrado en S1")

    # --- MODO 1: MANUAL ---

    def iniciar_modo_manual(self):
        self.construir_pantalla_base("MODO MANUAL")
        
        pad = tk.Frame(self.panel_izq, bg="#1e293b")
        pad.pack(pady=20)
        
        tk.Button(pad, text="IZQ", command=lambda: self.accion_manual_thread("left"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=0, padx=5)
        tk.Button(pad, text="ABAJO", command=lambda: self.accion_manual_thread("down"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=1, padx=5)
        tk.Button(pad, text="DER", command=lambda: self.accion_manual_thread("right"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=2, padx=5)

        tk.Label(self.panel_izq, text="MOVER A INICIO:", bg="#1e293b", fg="white").pack(pady=(20, 5))
        frame_ir = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ir.pack()
        
        for z in ["S1", "S2", "S3"]:
            tk.Button(frame_ir, text=z, command=lambda dest=z: self.iniciar_retorno_thread(dest),
                      bg="#0ea5e9", fg="white", width=5).pack(side="left", padx=2)

    def accion_manual_thread(self, direccion):
        # Logica rapida para determinar destino
        r, c = self.mapa_coords[self.posicion_actual]
        if self.posicion_actual == "Destino": # Si estamos en destino
            r = 4
            c = self.columna_virtual_destino

        targets = {"left": (r, c-1), "right": (r, c+1), "down": (r+1, c)}
        target_coords = targets.get(direccion)
        
        destino = None
        for k, v in self.mapa_coords.items():
            if v == target_coords: destino = k; break
        
        # Caso especial bajada a Destino
        if direccion == "down" and self.posicion_actual in [7, 8, 9]: destino = "Destino"

        if destino:
            valido, msg = self.validar_movimiento(self.posicion_actual, destino)
            if valido:
                self.ejecutar_movimiento_thread(destino)
            else:
                messagebox.showerror("Error", msg)

    # --- MODO 2: PROGRAMADO ---

    def iniciar_modo_programado(self):
        self.ruta_temp = []
        self.construir_pantalla_base("PROGRAMACION", mostrar_grid=True)
        
        # Panel derecho dividido: Grid y Lista de Rutas
        self.frame_lista_rutas = tk.Frame(self.panel_der, bg="#1e293b", width=150)
        self.frame_lista_rutas.pack(side="right", fill="y", padx=5)
        tk.Label(self.frame_lista_rutas, text="RUTAS", bg="#1e293b", fg="white").pack()
        self.refrescar_lista_rutas()

        self.fase_programacion_ui()

    def fase_programacion_ui(self):
        # Limpiar panel izq (excepto estanon)
        for w in self.panel_izq.winfo_children(): 
            if w != self.lbl_estanon: w.destroy()

        tk.Label(self.panel_izq, text="CREAR RUTA", font=("Arial", 12, "bold"), bg="#1e293b", fg="#fbbf24").pack(pady=5)
        
        # Seleccion Inicio
        self.var_inicio = tk.StringVar(value="S1")
        frame_ini = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ini.pack()
        for z in ["S1", "S2", "S3"]:
            tk.Radiobutton(frame_ini, text=z, variable=self.var_inicio, value=z, 
                           bg="#1e293b", fg="white", selectcolor="#0f172a",
                           command=self.reset_ruta_builder).pack(side="left")

        self.lbl_ruta = tk.Label(self.panel_izq, text="...", wraplength=350, bg="#334155", fg="white")
        self.lbl_ruta.pack(pady=5, fill="x")

        # Botones Numericos
        frame_nums = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_nums.pack()
        for i in range(1, 10):
            tk.Button(frame_nums, text=str(i), width=4, command=lambda z=i: self.agregar_paso(z)).grid(row=(i-1)//3, column=(i-1)%3, padx=2, pady=2)
        
        tk.Button(self.panel_izq, text="DESTINO", bg="#10b981", fg="white", command=lambda: self.agregar_paso("Destino")).pack(pady=5, fill="x")

        # Control
        tk.Button(self.panel_izq, text="BORRAR ULTIMO", command=self.undo_paso, bg="#64748b", fg="white").pack(fill="x", pady=2)
        tk.Button(self.panel_izq, text="GUARDAR RUTA", command=self.guardar_ruta, bg="#0ea5e9", fg="white").pack(fill="x", pady=5)
        
        tk.Button(self.panel_izq, text="INICIAR RECORRIDO", command=self.iniciar_secuencia_thread,
                  bg="#d946ef", fg="white", font=("Arial", 12, "bold")).pack(fill="x", pady=20)

    def refrescar_lista_rutas(self):
        for w in self.frame_lista_rutas.winfo_children(): 
            if isinstance(w, tk.Frame): w.destroy() # Limpiar items previos
        
        for k in sorted(self.rutas_programadas.keys()):
            f = tk.Frame(self.frame_lista_rutas, bg="#334155")
            f.pack(fill="x", pady=2)
            tk.Label(f, text=k, bg="#334155", fg="#facc15", width=4).pack(side="left")
            tk.Button(f, text="X", bg="#ef4444", fg="white", width=2,
                      command=lambda key=k: self.borrar_ruta(key)).pack(side="right")

    def borrar_ruta(self, key):
        if messagebox.askyesno("Borrar", f"¿Eliminar ruta {key}?"):
            del self.rutas_programadas[key]
            self.refrescar_lista_rutas()

    def reset_ruta_builder(self):
        self.ruta_temp = [self.var_inicio.get()]
        self.actualizar_lbl_ruta()

    def agregar_paso(self, zona):
        if not hasattr(self, 'ruta_temp') or not self.ruta_temp: self.reset_ruta_builder()
        ultimo = self.ruta_temp[-1]
        valido, msg = self.validar_movimiento(ultimo, zona)
        if valido:
            self.ruta_temp.append(zona)
            self.actualizar_lbl_ruta()
        else:
            messagebox.showwarning("Invalido", msg)

    def undo_paso(self):
        if len(self.ruta_temp) > 1:
            self.ruta_temp.pop()
            self.actualizar_lbl_ruta()

    def actualizar_lbl_ruta(self):
        self.lbl_ruta.config(text="->".join(map(str, self.ruta_temp)))

    def guardar_ruta(self):
        if not self.ruta_temp or self.ruta_temp[-1] != "Destino":
            messagebox.showerror("Error", "Debe terminar en Destino")
            return
        
        inicio = self.ruta_temp[0]
        # Guardamos en diccionario (Sobrescribe si existe)
        self.rutas_programadas[inicio] = self.ruta_temp[1:]
        self.refrescar_lista_rutas()
        self.reset_ruta_builder()

    # --- EJECUCION DE SECUENCIA (THREAD) ---

    def iniciar_secuencia_thread(self):
        if not self.rutas_programadas:
            messagebox.showwarning("Vacio", "No hay rutas programadas")
            return
        # Bloquear UI
        for w in self.panel_izq.winfo_children(): 
            if isinstance(w, tk.Button): w.config(state="disabled")
        threading.Thread(target=self._proceso_secuencia).start()

    def _proceso_secuencia(self):
        orden_ejecucion = ["S1", "S2", "S3"]
        
        for inicio in orden_ejecucion:
            if inicio not in self.rutas_programadas: continue
            
            camino = self.rutas_programadas[inicio]
            
            # 1. Mover a Inicio
            self._proceso_retorno(inicio)
            
            # 2. Pedir Carga
            evt = threading.Event()
            self.root.after(0, lambda: self._ask_yes_no("Carga", f"Coloque canica en {inicio}", evt))
            evt.wait()
            if not getattr(self, '_last_dialog_result', False): continue # Si cancela, salta

            # 3. Ejecutar Ruta
            for paso in camino:
                self._proceso_mover(paso, None)
            
            # 4. Pedir Volcado (EN DESTINO)
            evt_dump = threading.Event()
            self.root.after(0, lambda: self._ask_yes_no("Llegada", "Vacie la canasta", evt_dump))
            evt_dump.wait()
            
            self.contador_estanon += 1
            self.root.after(0, lambda: self.lbl_estanon.config(text=f"Estanon: {self.contador_estanon}"))

        # Fin de todas las rutas -> Volver a S1
        self._proceso_retorno("S1")
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Secuencia Terminada"))
        self.root.after(0, self.fase_programacion_ui) # Reactivar UI

    def _ask_yes_no(self, title, msg, event):
        self._last_dialog_result = messagebox.askyesno(title, msg)
        event.set()

    # --- LOGICA DE RETORNO Y RESET (THREAD) ---

    def iniciar_retorno_thread(self, destino):
        threading.Thread(target=self._proceso_retorno, args=(destino,)).start()

    def _proceso_retorno(self, destino_final):
        """Algoritmo de retorno inteligente"""
        actual = self.posicion_actual
        if actual == destino_final: return

        # Si estamos en Destino, Subir a fila 3 (columna virtual)
        if actual == "Destino":
            # Si bajamos por 7 (col 0), subimos a 7
            # Si bajamos por 8 (col 1), subimos a 8
            # Si bajamos por 9 (col 2), subimos a 9
            col = self.columna_virtual_destino
            targets = {0: 7, 1: 8, 2: 9}
            target_up = targets.get(col, 8)
            
            # Subir fisico
            self.enviar_comando(f"V{STEPS_V}")
            time.sleep(2.5)
            self.posicion_actual = target_up
            self.root.after(0, self.actualizar_grid_visual)
            actual = target_up

        # Ahora estamos en fila 1, 2 o 3. Mover horizontal a col destino
        _, c_curr = self.mapa_coords[actual]
        _, c_dest = self.mapa_coords[destino_final]

        while c_curr != c_dest:
            direction = 1 if c_dest > c_curr else -1
            cmd = f"H{STEPS_H}" if direction == 1 else f"H-{STEPS_H}"
            self.enviar_comando(cmd)
            time.sleep(2.5)
            c_curr += direction
            # Actualizar visual (truco: buscar key por coord)
            # Simplificacion: no actualizamos visual intermedio en retorno rapido
        
        # Subir filas
        r_curr, _ = self.mapa_coords[actual] # Fila actual aprox
        # En realidad necesitamos tracking preciso, pero asumimos retorno seguro
        # Algoritmo simplificado: Subir hasta Fila 0
        while r_curr > 0:
            self.enviar_comando(f"V{STEPS_V}")
            time.sleep(2.5)
            r_curr -= 1
        
        self.posicion_actual = destino_final
        self.root.after(0, self.actualizar_grid_visual)

    def iniciar_reset_total(self):
        threading.Thread(target=self._proceso_reset).start()

    def _proceso_reset(self):
        # 1. Bajar a fondo (Seguridad)
        r, _ = self.mapa_coords[self.posicion_actual] if self.posicion_actual != "Destino" else (4,1)
        
        if r > 0: # Si no estamos arriba
            self.enviar_comando(f"V-{STEPS_V * 4}")
            self.posicion_actual = "Destino"
            self.root.after(0, self.actualizar_grid_visual)
            time.sleep(4) # Esperar bajada
            
            # 2. Confirmar Vaciado
            evt = threading.Event()
            self.root.after(0, lambda: self._ask_yes_no("Reset", "Vacie estanon", evt))
            evt.wait()

        # 3. Regresar a S1
        self._proceso_retorno("S1")
        self.rutas_programadas = {}
        self.root.after(0, self.mostrar_menu_principal)

    # --- VISUALIZACION ---

    def construir_grid_visual(self):
        self.cells = {}
        for w in self.panel_der.winfo_children(): w.destroy()
        
        filas = [["S1", "S2", "S3"], [1, 2, 3], [4, 5, 6], [7, 8, 9], ["Destino"]]
        for fila in filas:
            f = tk.Frame(self.panel_der, bg="#0f172a")
            f.pack(pady=10)
            for z in fila:
                w = 20 if z == "Destino" else 8
                l = tk.Label(f, text=str(z), width=w, height=3, bg="#475569", fg="white", relief="ridge", font=("Arial", 12, "bold"))
                l.pack(side="left", padx=10)
                self.cells[z] = l
        self.actualizar_grid_visual()

    def actualizar_grid_visual(self):
        for z, l in self.cells.items():
            color = "#3b82f6" if str(z).startswith("S") else "#10b981" if z=="Destino" else "#475569"
            if z == self.posicion_actual: color = "#f59e0b"
            l.config(bg=color)

if __name__ == "__main__":
    root = tk.Tk()
    app = MarbleInterfaceFinal(root)
    root.mainloop()
