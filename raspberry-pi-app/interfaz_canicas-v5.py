import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACION SERIAL ---
PORT_NAME = '/dev/ttyACM0'
BAUD_RATE = 115200

# --- CONFIGURACION FISICA ---
# Pasos ajustados a multiplos de 8
STEPS_H = 1536
STEPS_V = 1408

# Ajuste fino (1/8)
CALIB_FINE_H = int(STEPS_H / 8)
CALIB_FINE_V = int(STEPS_V / 8)

class MarbleInterfaceFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("SISTEMA DE CONTROL V5.0")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e293b") 

        # --- ESTADO DEL SISTEMA ---
        self.ser = None
        self.connect_serial()
        
        # Variable critica de posicion
        self.posicion_actual = "S1"
        self.columna_virtual_destino = 1 
        
        self.rutas_programadas = {} 
        self.contador_estanon = 0
        
        # Mapa Logico (Fila, Columna)
        self.mapa_coords = {
            "S1": (0,0), "S2": (0,1), "S3": (0,2),
            1: (1,0), 2: (1,1), 3: (1,2),
            4: (2,0), 5: (2,1), 6: (2,2),
            7: (3,0), 8: (3,1), 9: (3,2),
            "Destino": (4,1) # Logico base
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
        try:
            if self.ser and self.ser.is_open:
                msg = f"{cmd}\n"
                self.ser.write(msg.encode('utf-8'))
                print(f"TX: {msg.strip()}")
            else:
                print(f"SIM: {cmd}")
        except Exception as e:
            print(f"Error Serial: {e}")

    # --- LOGICA DE MOVIMIENTO ---

    def calcular_comando(self, origen, destino):
        r1, c1 = self.mapa_coords[origen]
        
        # Manejo especial Destino
        if origen == "Destino":
            r1 = 4
            c1 = self.columna_virtual_destino
        
        if destino == "Destino":
            r2 = 4
            if origen in [7, 8, 9]:
                _, c_temp = self.mapa_coords[origen]
                c2 = c_temp
            else:
                c2 = 1 
        else:
            r2, c2 = self.mapa_coords[destino]

        diff_r = r2 - r1
        diff_c = c2 - c1
        
        if diff_r == 1 and diff_c == 0: return f"V-{STEPS_V}"  # Bajar
        if diff_r == -1 and diff_c == 0: return f"V{STEPS_V}"   # Subir
        if diff_c == 1 and diff_r == 0: return f"H{STEPS_H}"   # Derecha
        if diff_c == -1 and diff_r == 0: return f"H-{STEPS_H}"  # Izquierda
        
        # Si es un salto vertical mayor a 1 (ej: Reset), calculamos pasos totales
        if diff_c == 0 and diff_r > 1:
            pasos_total = diff_r * STEPS_V
            return f"V-{pasos_total}" # Bajar N filas

        return None 

    def validar_movimiento(self, origen, destino):
        if destino == "Destino":
            if origen in [7, 8, 9]: return True, "OK"
            return False, "A Destino solo se baja desde 7, 8 o 9"

        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        if abs(r1-r2) + abs(c1-c2) != 1:
            return False, "Movimiento no adyacente"
        
        if r2 < r1:
            return False, "No se puede subir en ruta"
            
        return True, "OK"

    # --- THREADING ---

    def ejecutar_movimiento_thread(self, destino, callback=None):
        threading.Thread(target=self._proceso_mover, args=(destino, callback)).start()

    def _proceso_mover(self, destino, callback):
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            
            if destino == "Destino":
                _, c_origen = self.mapa_coords[self.posicion_actual]
                self.columna_virtual_destino = c_origen
            
            self.posicion_actual = destino
            self.root.after(0, self.actualizar_grid_visual)
            time.sleep(2.5) 
            
            if callback:
                # Ejecutar callback en el hilo principal si es UI, o directo si es logica
                self.root.after(0, callback)

    # --- INTERFAZ UI ---

    def setup_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()

        header = tk.Frame(self.root, bg="#0f172a", height=60)
        header.pack(fill="x")
        tk.Label(header, text="CONTROL DE CANICAS", font=("Arial", 20, "bold"), 
                 bg="#0f172a", fg="#e2e8f0").pack(side="left", padx=20, pady=10)
        
        tk.Button(header, text="RESET TOTAL", bg="#dc2626", fg="white", font=("Arial", 10, "bold"),
                  command=self.iniciar_reset_total).pack(side="right", padx=20, pady=10)

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
        tk.Button(self.main_frame, text="3. CALIBRACION", command=self.iniciar_modo_calibracion, **btn_opts).pack(pady=10)

    def construir_pantalla_base(self, titulo, mostrar_grid=True):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        top = tk.Frame(self.main_frame, bg="#334155")
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=titulo, font=("Arial", 14, "bold"), bg="#334155", fg="#facc15").pack(side="left", padx=10)
        tk.Button(top, text="MENU", bg="#64748b", fg="white", command=self.mostrar_menu_principal).pack(side="right", padx=10, pady=5)

        self.panel_izq = tk.Frame(self.main_frame, bg="#1e293b", width=400)
        self.panel_izq.pack(side="left", fill="y", padx=10)
        
        if mostrar_grid:
            self.panel_der = tk.Frame(self.main_frame, bg="#0f172a")
            self.panel_der.pack(side="right", fill="both", expand=True, padx=10)
            self.construir_grid_visual()
        else:
            self.panel_der = None 

        self.lbl_estanon = tk.Label(self.panel_izq, text=f"Estanon: {self.contador_estanon}", 
                                    font=("Arial", 16, "bold"), bg="#1e293b", fg="#facc15")
        self.lbl_estanon.pack(side="bottom", pady=20)

    # --- MODO 3: CALIBRACION DUAL ---

    def iniciar_modo_calibracion(self):
        self.construir_pantalla_base("CALIBRACION Y MANTENIMIENTO", mostrar_grid=False)
        
        lbl = tk.Label(self.panel_izq, text="Use estos controles para ajustar la posicion.\nAl finalizar, confirme que esta en S1.", 
                       bg="#1e293b", fg="#94a3b8", justify="left")
        lbl.pack(pady=10)

        # Seccion Fina
        tk.Label(self.panel_izq, text="AJUSTE FINO (1/8 PASO)", bg="#1e293b", fg="#fbbf24", font=("Arial", 10, "bold")).pack(pady=(20,5))
        frame_fino = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_fino.pack()
        
        tk.Button(frame_fino, text="▲", command=lambda: self.mover_calib("V", 1, "FINE"), bg="#3b82f6", fg="white", width=4).grid(row=0, column=1)
        tk.Button(frame_fino, text="◀", command=lambda: self.mover_calib("H", -1, "FINE"), bg="#3b82f6", fg="white", width=4).grid(row=1, column=0, padx=5)
        tk.Button(frame_fino, text="▶", command=lambda: self.mover_calib("H", 1, "FINE"), bg="#3b82f6", fg="white", width=4).grid(row=1, column=2, padx=5)
        tk.Button(frame_fino, text="▼", command=lambda: self.mover_calib("V", -1, "FINE"), bg="#3b82f6", fg="white", width=4).grid(row=2, column=1)

        # Seccion Completa
        tk.Label(self.panel_izq, text="MOVIMIENTO GENERAL (1 CELDA)", bg="#1e293b", fg="#fbbf24", font=("Arial", 10, "bold")).pack(pady=(20,5))
        frame_gros = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_gros.pack()
        
        tk.Button(frame_gros, text="▲", command=lambda: self.mover_calib("V", 1, "FULL"), bg="#475569", fg="white", width=4).grid(row=0, column=1)
        tk.Button(frame_gros, text="◀", command=lambda: self.mover_calib("H", -1, "FULL"), bg="#475569", fg="white", width=4).grid(row=1, column=0, padx=5)
        tk.Button(frame_gros, text="▶", command=lambda: self.mover_calib("H", 1, "FULL"), bg="#475569", fg="white", width=4).grid(row=1, column=2, padx=5)
        tk.Button(frame_gros, text="▼", command=lambda: self.mover_calib("V", -1, "FULL"), bg="#475569", fg="white", width=4).grid(row=2, column=1)

        tk.Button(self.panel_izq, text="CONFIRMAR POSICION S1", bg="#10b981", fg="white", font=("Arial", 11, "bold"),
                  command=self.confirmar_s1).pack(pady=30, fill="x")

    def mover_calib(self, eje, dir, tipo):
        if tipo == "FINE":
            pasos = CALIB_FINE_V if eje == "V" else CALIB_FINE_H
        else:
            pasos = STEPS_V if eje == "V" else STEPS_H
            
        signo = "" if dir > 0 else "-"
        self.enviar_comando(f"{eje}{signo}{pasos}")

    def confirmar_s1(self):
        if messagebox.askyesno("Confirmar", "¿Posicion actual es S1?"):
            self.posicion_actual = "S1"
            self.columna_virtual_destino = 0
            messagebox.showinfo("Listo", "Sistema calibrado en S1")

    # --- MODO 1: MANUAL ---

    def iniciar_modo_manual(self):
        self.construir_pantalla_base("MODO MANUAL")
        
        pad = tk.Frame(self.panel_izq, bg="#1e293b")
        pad.pack(pady=20)
        
        tk.Button(pad, text="IZQ", command=lambda: self.accion_manual_click("left"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=0, padx=5)
        tk.Button(pad, text="ABAJO", command=lambda: self.accion_manual_click("down"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=1, padx=5)
        tk.Button(pad, text="DER", command=lambda: self.accion_manual_click("right"), bg="#475569", fg="white", width=8, height=2).grid(row=1, column=2, padx=5)

        tk.Label(self.panel_izq, text="RETORNO RAPIDO:", bg="#1e293b", fg="white").pack(pady=(20, 5))
        frame_ir = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ir.pack()
        
        for z in ["S1", "S2", "S3"]:
            tk.Button(frame_ir, text=z, command=lambda dest=z: self.iniciar_retorno_thread(dest),
                      bg="#0ea5e9", fg="white", width=5).pack(side="left", padx=2)

    def accion_manual_click(self, direccion):
        # 1. Validacion sincrona (en hilo principal) para que salga el popup
        r, c = self.mapa_coords[self.posicion_actual]
        if self.posicion_actual == "Destino":
            r = 4
            c = self.columna_virtual_destino

        targets = {"left": (r, c-1), "right": (r, c+1), "down": (r+1, c)}
        target_coords = targets.get(direccion)
        
        destino = None
        for k, v in self.mapa_coords.items():
            if v == target_coords: destino = k; break
        
        if direccion == "down" and self.posicion_actual in [7, 8, 9]: destino = "Destino"

        if destino:
            valido, msg = self.validar_movimiento(self.posicion_actual, destino)
            if valido:
                # 2. Si es valido, lanzamos hilo
                self.ejecutar_movimiento_thread(destino, callback=self.check_fin_recorrido_manual)
            else:
                messagebox.showwarning("Movimiento Invalido", msg)
        else:
            messagebox.showwarning("Error", "No existe zona en esa direccion")

    def check_fin_recorrido_manual(self):
        # Se llama despues de que el movimiento termina
        if self.posicion_actual == "Destino":
            self.rutina_volcado_y_retorno()

    def rutina_volcado_y_retorno(self):
        # 1. Popup bloqueante
        messagebox.showinfo("Llegada", "Canica en Destino.\nEl sistema volcará la canasta ahora.")
        
        # 2. Secuencia de Volcado con los NUEVOS ANGULOS
        print("Volcando canasta...")
        self.enviar_comando("S25")  # ABRIR (25 grados)
        time.sleep(1.5)             # Esperar a que caiga la canica
        self.enviar_comando("S65")  # CERRAR (65 grados)
        time.sleep(1.0)             # Esperar a que se cierre bien
        
        # 3. Actualizar contador y regresar
        self.contador_estanon += 1
        self.lbl_estanon.config(text=f"Estanon: {self.contador_estanon}")
        
        self.iniciar_retorno_thread("S1")

    # --- MODO 2: PROGRAMADO ---

    def iniciar_modo_programado(self):
        self.ruta_temp = []
        self.construir_pantalla_base("PROGRAMACION", mostrar_grid=True)
        
        self.frame_lista_rutas = tk.Frame(self.panel_der, bg="#1e293b", width=200)
        self.frame_lista_rutas.pack(side="right", fill="y", padx=5)
        tk.Label(self.frame_lista_rutas, text="RUTAS", bg="#1e293b", fg="white", font=("Arial",10,"bold")).pack()
        self.refrescar_lista_rutas()

        self.fase_programacion_ui()

    def refrescar_lista_rutas(self):
        for w in self.frame_lista_rutas.winfo_children(): 
            if isinstance(w, tk.Frame): w.destroy()
        
        # QUITAMOS "sorted()" para ver el orden real de ejecución en la pantalla
        for k, camino in self.rutas_programadas.items():
            f = tk.Frame(self.frame_lista_rutas, bg="#334155")
            f.pack(fill="x", pady=2)
            
            txt_camino = "->".join(map(str, camino))
            lbl_text = f"{k}: {txt_camino}"
            
            tk.Label(f, text=lbl_text, bg="#334155", fg="#facc15", anchor="w", font=("Arial", 8)).pack(side="left", fill="x", expand=True)
            tk.Button(f, text="X", bg="#ef4444", fg="white", width=2,
                      command=lambda key=k: self.borrar_ruta(key)).pack(side="right")

    def fase_programacion_ui(self):
        for w in self.panel_izq.winfo_children(): 
            if w != self.lbl_estanon: w.destroy()

        tk.Label(self.panel_izq, text="CREAR RUTA", font=("Arial", 12, "bold"), bg="#1e293b", fg="#fbbf24").pack(pady=5)
        
        self.var_inicio = tk.StringVar(value="S1")
        frame_ini = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ini.pack()
        for z in ["S1", "S2", "S3"]:
            tk.Radiobutton(frame_ini, text=z, variable=self.var_inicio, value=z, 
                           bg="#1e293b", fg="white", selectcolor="#0f172a",
                           command=self.reset_ruta_builder).pack(side="left")

        self.lbl_ruta = tk.Label(self.panel_izq, text="...", wraplength=350, bg="#334155", fg="white")
        self.lbl_ruta.pack(pady=5, fill="x")

        frame_nums = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_nums.pack()
        for i in range(1, 10):
            tk.Button(frame_nums, text=str(i), width=4, command=lambda z=i: self.agregar_paso(z)).grid(row=(i-1)//3, column=(i-1)%3, padx=2, pady=2)
        
        tk.Button(self.panel_izq, text="DESTINO", bg="#10b981", fg="white", command=lambda: self.agregar_paso("Destino")).pack(pady=5, fill="x")

        tk.Button(self.panel_izq, text="BORRAR ULTIMO", command=self.undo_paso, bg="#64748b", fg="white").pack(fill="x", pady=2)
        tk.Button(self.panel_izq, text="GUARDAR RUTA", command=self.guardar_ruta, bg="#0ea5e9", fg="white").pack(fill="x", pady=5)
        
        tk.Button(self.panel_izq, text="INICIAR RECORRIDO", command=self.iniciar_secuencia_thread,
                  bg="#d946ef", fg="white", font=("Arial", 12, "bold")).pack(fill="x", pady=20)

    # ... (Metodos borrar_ruta, reset_ruta_builder, agregar_paso, undo_paso igual que v4) ...
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
        
        # LOGICA DE ORDEN:
        # Si la ruta ya existe, la borramos primero.
        # Al insertarla de nuevo, Python la coloca al FINAL del diccionario.
        if inicio in self.rutas_programadas:
            del self.rutas_programadas[inicio]
            
        self.rutas_programadas[inicio] = self.ruta_temp[1:]
        
        self.refrescar_lista_rutas()
        self.reset_ruta_builder()

    # --- EJECUCION SECUENCIA ---

    def iniciar_secuencia_thread(self):
        if not self.rutas_programadas:
            messagebox.showwarning("Vacio", "No hay rutas programadas")
            return
        for w in self.panel_izq.winfo_children(): 
            if isinstance(w, tk.Button): w.config(state="disabled")
        threading.Thread(target=self._proceso_secuencia).start()

    def _proceso_secuencia(self):
        # Iteramos directamente sobre el diccionario para respetar el orden de inserción
        # (S1 -> S2 -> S3 o como haya decidido el usuario)
        for inicio, camino in self.rutas_programadas.items():
            
            self._proceso_retorno(inicio)
            
            # Pedir Carga
            evt = threading.Event()
            self.root.after(0, lambda: self._show_info_wait("Carga", f"Coloque canica en {inicio}", evt))
            evt.wait()

            # Ejecutar Ruta
            for paso in camino:
                self._proceso_mover(paso, None)
            
            # Pedir Volcado
            evt_dump = threading.Event()
            self.root.after(0, lambda: self._show_info_wait("Llegada", "Vacie la canasta", evt_dump))
            evt_dump.wait()
            
            self.contador_estanon += 1
            self.root.after(0, lambda: self.lbl_estanon.config(text=f"Estanon: {self.contador_estanon}"))

        self._proceso_retorno("S1")
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Secuencia Terminada"))
        self.root.after(0, self.fase_programacion_ui)

    def _show_info_wait(self, title, msg, event):
        messagebox.showinfo(title, msg)
        event.set()

    # --- RETORNO Y RESET ---

    def iniciar_retorno_thread(self, destino):
        threading.Thread(target=self._proceso_retorno, args=(destino,)).start()

    def _proceso_retorno(self, destino_final):
        actual = self.posicion_actual
        if actual == destino_final: return

        if actual == "Destino":
            col = self.columna_virtual_destino
            targets = {0: 7, 1: 8, 2: 9}
            target_up = targets.get(col, 8)
            
            self.enviar_comando(f"V{STEPS_V}")
            time.sleep(2.5)
            self.posicion_actual = target_up
            self.root.after(0, self.actualizar_grid_visual)
            actual = target_up

        _, c_curr = self.mapa_coords[actual]
        _, c_dest = self.mapa_coords[destino_final]

        while c_curr != c_dest:
            direction = 1 if c_dest > c_curr else -1
            cmd = f"H{STEPS_H}" if direction == 1 else f"H-{STEPS_H}"
            self.enviar_comando(cmd)
            time.sleep(2.5)
            c_curr += direction
        
        r_curr, _ = self.mapa_coords[actual]
        while r_curr > 0:
            self.enviar_comando(f"V{STEPS_V}")
            time.sleep(2.5)
            r_curr -= 1
        
        self.posicion_actual = destino_final
        self.root.after(0, self.actualizar_grid_visual)

    def iniciar_reset_total(self):
        threading.Thread(target=self._proceso_reset).start()

    def _proceso_reset(self):
        # Calculo matematico de distancia
        r_actual, _ = self.mapa_coords[self.posicion_actual] if self.posicion_actual != "Destino" else (4,1)
        
        filas_a_bajar = 4 - r_actual
        
        if filas_a_bajar > 0:
            pasos_total = filas_a_bajar * STEPS_V
            self.enviar_comando(f"V-{pasos_total}")
            
            self.posicion_actual = "Destino"
            self.root.after(0, self.actualizar_grid_visual)
            
            tiempo_espera = 2.0 * filas_a_bajar
            time.sleep(tiempo_espera) 
            
            evt = threading.Event()
            self.root.after(0, lambda: self._show_info_wait("Reset", "Vacie estanon", evt))
            evt.wait()

        self._proceso_retorno("S1")
        self.rutas_programadas = {}
        self.root.after(0, self.mostrar_menu_principal)

    # --- VISUALIZACION ---

    def construir_grid_visual(self):
        self.cells = {}
        for w in self.panel_der.winfo_children(): 
            if w != self.frame_lista_rutas: w.destroy()
        
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