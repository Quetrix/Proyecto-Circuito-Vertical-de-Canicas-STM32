import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACION SERIAL ---
# Ajusta el puerto si es necesario (ej: /dev/ttyUSB0)
PORT_NAME = '/dev/ttyACM0'
BAUD_RATE = 115200

# --- CONFIGURACION FISICA ---
# Pasos calibrados para 28BYJ-48 (Ajustar segun tu driver)
STEPS_H = 2048  
STEPS_V = 2048  

class MarbleInterfaceFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Control de Canicas v3.0")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e293b") # Fondo oscuro profesional

        # --- ESTADO DEL SISTEMA ---
        self.ser = None
        self.connect_serial()
        
        self.posicion_actual = "S1" # Se asume S1 al encender
        self.rutas_programadas = [] 
        self.contador_estanon = 0
        
        # Mapa de Coordenadas (Fila, Columna)
        # S1=(0,0), S2=(0,1), S3=(0,2)
        # 1=(1,0)... 9=(3,2)
        # Destino se maneja como Fila 4, cualquier columna valida para bajar
        self.mapa_coords = {
            "S1": (0,0), "S2": (0,1), "S3": (0,2),
            1: (1,0), 2: (1,1), 3: (1,2),
            4: (2,0), 5: (2,1), 6: (2,2),
            7: (3,0), 8: (3,1), 9: (3,2),
            "Destino": (4,1) # Coordenada logica
        }

        # Estilos visuales
        self.btn_style = {"font": ("Arial", 12, "bold"), "bd": 2, "relief": "raised"}
        self.setup_ui()

    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1)
            time.sleep(2) 
            print("CONEXION SERIAL OK")
        except Exception:
            print("MODO SIMULACION (Sin Serial)")

    def enviar_comando(self, cmd):
        if self.ser and self.ser.is_open:
            msg = f"{cmd}\n"
            self.ser.write(msg.encode('utf-8'))
            print(f"TX: {msg.strip()}")
        else:
            print(f"SIM: {cmd}")
        time.sleep(0.1)

    # --- LOGICA DE MOVIMIENTO ---

    def calcular_comando(self, origen, destino):
        """Genera el comando H/V basado en coordenadas."""
        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        diff_r = r2 - r1
        diff_c = c2 - c1
        
        # Regla especial: 7, 8 y 9 bajan a Destino
        if destino == "Destino" and origen in [7, 8, 9]:
            return f"V-{STEPS_V}" # Bajar

        if diff_r == 1 and diff_c == 0: return f"V-{STEPS_V}"  # Bajar
        if diff_r == -1 and diff_c == 0: return f"V{STEPS_V}"   # Subir
        if diff_c == 1 and diff_r == 0: return f"H{STEPS_H}"   # Derecha
        if diff_c == -1 and diff_r == 0: return f"H-{STEPS_H}"  # Izquierda
        
        return None 

    def mover_fisico(self, destino, velocidad_lenta=False):
        """Mueve la canasta y actualiza estado."""
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            self.posicion_actual = destino
            # Tiempo estimado movimiento fisico
            tiempo = 3.0 if velocidad_lenta else 2.0
            self.root.update() 
            time.sleep(tiempo) 
            return True
        return False

    def validar_movimiento(self, origen, destino, modo="bajada"):
        """
        Reglas estrictas.
        modo 'bajada': No sube. Ortogonal.
        """
        # Excepcion Destino: Se puede llegar desde 7, 8 o 9
        if destino == "Destino":
            if origen in [7, 8, 9]: return True, "OK"
            return False, "A Destino solo se llega desde 7, 8 o 9"

        r1, c1 = self.mapa_coords[origen]
        r2, c2 = self.mapa_coords[destino]
        
        # Adyacencia ortogonal
        if abs(r1-r2) + abs(c1-c2) != 1:
            return False, "Movimiento no adyacente."

        # Restriccion de Bajada (Con canica)
        if modo == "bajada" and r2 < r1:
            return False, "Ilegal: No se puede subir con canica."
            
        return True, "OK"

    # --- INTERFAZ DE USUARIO (UI) ---

    def setup_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()

        # Header Global
        header = tk.Frame(self.root, bg="#0f172a", height=60)
        header.pack(fill="x")
        tk.Label(header, text="CONTROL DE CANICAS", font=("Arial", 20, "bold"), 
                 bg="#0f172a", fg="#e2e8f0").pack(side="left", padx=20, pady=10)
        
        # Boton RESET SISTEMA (Panico)
        tk.Button(header, text="RESET TOTAL", bg="#dc2626", fg="white", font=("Arial", 10, "bold"),
                  command=self.reset_inteligente).pack(side="right", padx=20, pady=10)

        # Contenedor Principal
        self.main_frame = tk.Frame(self.root, bg="#1e293b")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.mostrar_menu_principal()

    def mostrar_menu_principal(self):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        tk.Label(self.main_frame, text="SELECCION DE MODO", font=("Arial", 18), 
                 bg="#1e293b", fg="white").pack(pady=30)

        # Botones de Menu Grande
        btn_opts = {"width": 25, "height": 2, "font": ("Arial", 14, "bold"), "bg": "#334155", "fg": "white"}
        
        tk.Button(self.main_frame, text="1. MODO MANUAL", command=self.iniciar_modo_manual, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="2. MODO PROGRAMADO", command=self.iniciar_modo_programado, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="3. CALIBRACION (AJUSTE)", command=self.iniciar_modo_calibracion, **btn_opts).pack(pady=10)

    def construir_pantalla_base(self, titulo):
        for w in self.main_frame.winfo_children(): w.destroy()
        
        # Barra superior de la pantalla
        top_bar = tk.Frame(self.main_frame, bg="#334155")
        top_bar.pack(fill="x", pady=(0, 10))
        
        tk.Label(top_bar, text=titulo, font=("Arial", 14, "bold"), bg="#334155", fg="#facc15").pack(side="left", padx=10, pady=5)
        tk.Button(top_bar, text="VOLVER AL MENU", bg="#64748b", fg="white",
                  command=self.mostrar_menu_principal).pack(side="right", padx=10, pady=5)

        # Division Paneles
        self.panel_izq = tk.Frame(self.main_frame, bg="#1e293b", width=350)
        self.panel_izq.pack(side="left", fill="y", padx=10)
        
        self.panel_der = tk.Frame(self.main_frame, bg="#0f172a")
        self.panel_der.pack(side="right", fill="both", expand=True, padx=10)
        
        self.construir_grid_visual()
        
        # Etiqueta Estanon
        self.lbl_estanon = tk.Label(self.panel_izq, text=f"Estanon: {self.contador_estanon}", 
                                    font=("Arial", 16, "bold"), bg="#1e293b", fg="#facc15")
        self.lbl_estanon.pack(side="bottom", pady=20)

    # --- MODO 3: CALIBRACION / AJUSTE ---

    def iniciar_modo_calibracion(self):
        self.construir_pantalla_base("MODO CALIBRACION (MOVIMIENTO LIBRE)")
        
        lbl_info = tk.Label(self.panel_izq, text="Mueva los motores libremente.\nConfirme posicion S1 al terminar.",
                            bg="#1e293b", fg="#94a3b8", justify="left")
        lbl_info.pack(pady=20)

        # Pad de movimiento libre
        pad = tk.Frame(self.panel_izq, bg="#1e293b")
        pad.pack(pady=20)
        
        # Botones de flecha TEXTUALES
        tk.Button(pad, text="ARRIBA", command=lambda: self.mover_libre("V", 1), bg="#3b82f6", fg="white", width=8, height=2).grid(row=0, column=1, pady=5)
        tk.Button(pad, text="IZQ", command=lambda: self.mover_libre("H", -1), bg="#3b82f6", fg="white", width=8, height=2).grid(row=1, column=0, padx=5)
        tk.Button(pad, text="DER", command=lambda: self.mover_libre("H", 1), bg="#3b82f6", fg="white", width=8, height=2).grid(row=1, column=2, padx=5)
        tk.Button(pad, text="ABAJO", command=lambda: self.mover_libre("V", -1), bg="#3b82f6", fg="white", width=8, height=2).grid(row=2, column=1, pady=5)

        # Boton confirmar S1
        tk.Button(self.panel_izq, text="DEFINIR ESTA POSICION COMO S1", 
                  bg="#10b981", fg="white", font=("Arial", 11, "bold"),
                  command=self.confirmar_calibracion).pack(pady=30, fill="x")

    def mover_libre(self, eje, direccion):
        # Mueve sin actualizar la logica de posicion (solo hardware)
        pasos = STEPS_V if eje == "V" else STEPS_H
        signo = "" if direccion > 0 else "-" # V positivo es subir, V negativo bajar (segun logica previa)
        
        cmd = f"{eje}{signo}{pasos}"
        self.enviar_comando(cmd)

    def confirmar_calibracion(self):
        if messagebox.askyesno("Confirmar", "¿Esta seguro que la canasta esta en S1?"):
            self.posicion_actual = "S1"
            self.actualizar_grid_visual()
            messagebox.showinfo("Listo", "Sistema calibrado en S1.")

    # --- MODO 1: MANUAL ---

    def iniciar_modo_manual(self):
        self.construir_pantalla_base("MODO MANUAL")
        
        # Pad Direccional
        pad = tk.Frame(self.panel_izq, bg="#1e293b")
        pad.pack(pady=20)
        
        tk.Button(pad, text="IZQ", command=lambda: self.accion_manual("left"), bg="#475569", fg="white", width=6, height=2).grid(row=1, column=0, padx=5)
        tk.Button(pad, text="ABAJO", command=lambda: self.accion_manual("down"), bg="#475569", fg="white", width=6, height=2).grid(row=1, column=1, padx=5)
        tk.Button(pad, text="DER", command=lambda: self.accion_manual("right"), bg="#475569", fg="white", width=6, height=2).grid(row=1, column=2, padx=5)

        # Botones de "Ir a..." (No teletransportar)
        tk.Label(self.panel_izq, text="MOVER A INICIO:", bg="#1e293b", fg="white").pack(pady=(20, 5))
        frame_ir = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ir.pack()
        
        for z in ["S1", "S2", "S3"]:
            tk.Button(frame_ir, text=f"IR A {z}", command=lambda dest=z: self.ir_a_inicio(dest),
                      bg="#0ea5e9", fg="white").pack(side="left", padx=5)

    def accion_manual(self, direccion):
        # Determinar destino
        r, c = self.mapa_coords[self.posicion_actual]
        destino = None
        
        # Logica adyacente simple
        targets = {
            "left": (r, c-1),
            "right": (r, c+1),
            "down": (r+1, c) # Puede coincidir con Destino (4,1)
        }
        
        target_coords = targets.get(direccion)
        
        # Mapeo inverso coords -> nombre zona
        for k, v in self.mapa_coords.items():
            if v == target_coords:
                destino = k
                break
        
        # Manejo especial para bajar a Destino desde 7,8,9
        if direccion == "down" and self.posicion_actual in [7, 8, 9]:
            destino = "Destino"

        if destino:
            valido, msg = self.validar_movimiento(self.posicion_actual, destino, "bajada")
            if valido:
                self.mover_fisico(destino)
                if destino == "Destino":
                    if messagebox.askyesno("Llegada", "En Destino. ¿Volcar y regresar a S1?"):
                        # Simular volcado
                        time.sleep(1)
                        self.contador_estanon += 1
                        self.lbl_estanon.config(text=f"Estanon: {self.contador_estanon}")
                        self.regresar_a_origen("S1")
            else:
                messagebox.showerror("Error", msg)
        else:
            messagebox.showerror("Error", "Movimiento invalido o sin zona.")

    def ir_a_inicio(self, destino):
        """Calcula y ejecuta la ruta desde la posicion actual hasta un Sx."""
        # Solo permitimos esto si estamos en la fila superior para simplificar, 
        # o usamos el pathfinder de retorno.
        self.regresar_a_origen(destino)

    # --- MODO 2: PROGRAMADO ---

    def iniciar_modo_programado(self):
        self.rutas_programadas = []
        self.ruta_temp = []
        self.construir_pantalla_base("PROGRAMACION DE RUTAS")
        self.fase_programacion()

    def fase_programacion(self):
        # Limpiar panel
        for w in self.panel_izq.winfo_children(): 
            if w != self.lbl_estanon: w.destroy()
        
        n_ruta = len(self.rutas_programadas) + 1
        tk.Label(self.panel_izq, text=f"RUTA #{n_ruta}", font=("Arial", 12, "bold"), bg="#1e293b", fg="#fbbf24").pack(pady=10)

        # Seleccion Inicio
        tk.Label(self.panel_izq, text="SELECCIONE INICIO:", bg="#1e293b", fg="white").pack()
        frame_ini = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_ini.pack(pady=5)
        
        self.var_inicio = tk.StringVar(value="S1")
        for z in ["S1", "S2", "S3"]:
            tk.Radiobutton(frame_ini, text=z, variable=self.var_inicio, value=z, 
                           bg="#1e293b", fg="white", selectcolor="#0f172a",
                           command=self.reset_ruta_builder).pack(side="left")

        # Constructor
        self.lbl_ruta = tk.Label(self.panel_izq, text="...", wraplength=300, bg="#334155", fg="white")
        self.lbl_ruta.pack(pady=10, fill="x")

        # Grid de botones numericos
        frame_nums = tk.Frame(self.panel_izq, bg="#1e293b")
        frame_nums.pack()
        for i in range(1, 10):
            btn = tk.Button(frame_nums, text=str(i), width=4, 
                            command=lambda z=i: self.agregar_paso(z))
            btn.grid(row=(i-1)//3, column=(i-1)%3, padx=2, pady=2)
            
        tk.Button(self.panel_izq, text="DESTINO", bg="#10b981", fg="white",
                  command=lambda: self.agregar_paso("Destino")).pack(pady=10, fill="x")

        # Acciones
        tk.Button(self.panel_izq, text="DESHACER (UNDO)", command=self.undo_paso, bg="#64748b", fg="white").pack(fill="x", pady=2)
        tk.Button(self.panel_izq, text="GUARDAR RUTA", command=self.guardar_ruta, bg="#0ea5e9", fg="white").pack(fill="x", pady=10)
        
        if len(self.rutas_programadas) > 0:
             tk.Button(self.panel_izq, text="EJECUTAR SECUENCIA", command=self.ejecutar_secuencia,
                  bg="#d946ef", fg="white", font=("Arial", 12, "bold")).pack(fill="x", pady=20)
             
             # Lista de rutas guardadas
             lbl_saved = tk.Label(self.panel_izq, text=f"Rutas Guardadas: {len(self.rutas_programadas)}", bg="#1e293b", fg="gray")
             lbl_saved.pack()

    def reset_ruta_builder(self):
        self.ruta_temp = [self.var_inicio.get()]
        self.actualizar_lbl_ruta()

    def agregar_paso(self, zona):
        if not self.ruta_temp: self.reset_ruta_builder()
        ultimo = self.ruta_temp[-1]
        valido, msg = self.validar_movimiento(ultimo, zona, "bajada")
        
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
        texto = " -> ".join(map(str, self.ruta_temp))
        self.lbl_ruta.config(text=texto)

    def guardar_ruta(self):
        if not self.ruta_temp or self.ruta_temp[-1] != "Destino":
            messagebox.showerror("Error", "La ruta debe terminar en 'Destino'")
            return
            
        self.rutas_programadas.append({
            "inicio": self.ruta_temp[0],
            "camino": self.ruta_temp[1:] 
        })
        
        if len(self.rutas_programadas) < 3:
            if messagebox.askyesno("Guardado", f"Ruta guardada.\n¿Programar otra?"):
                self.fase_programacion()
            else:
                self.fase_programacion() 
        else:
            self.fase_programacion()

    def ejecutar_secuencia(self):
        # Deshabilitar UI
        for w in self.panel_izq.winfo_children(): 
            if isinstance(w, tk.Button): w.config(state="disabled")
        
        threading.Thread(target=self.proceso_ejecucion).start()

    def proceso_ejecucion(self):
        total = len(self.rutas_programadas)
        
        for i, ruta in enumerate(self.rutas_programadas):
            inicio = ruta['inicio']
            camino = ruta['camino']
            
            # 1. Regreso automatico al inicio de esta ruta
            if self.posicion_actual != inicio:
                self.root.after(0, lambda: messagebox.showinfo("Info", f"Moviendo canasta a {inicio}..."))
                self.regresar_a_origen(inicio)
            
            # 2. Espera Confirmacion de Carga
            evento_carga = threading.Event()
            def pedir_carga():
                if messagebox.askyesno("Carga", f"Coloque canica en {inicio}.\n¿Listo?"):
                    evento_carga.set()
                else:
                    # Si dice no, bucle o abortar? Asumimos reintentar
                    pedir_carga()

            self.root.after(0, pedir_carga)
            evento_carga.wait()
            
            # 3. Ejecutar
            for paso in camino:
                self.mover_fisico(paso)
            
            # 4. Confirmacion Volcado (OBLIGATORIO)
            evento_volcado = threading.Event()
            def pedir_volcado():
                if messagebox.askyesno("Volcado", "Llegada a Destino.\n¿Confirma que la canica cayo?"):
                    evento_volcado.set()
                else:
                    pedir_volcado()

            self.root.after(0, pedir_volcado)
            evento_volcado.wait()

            self.contador_estanon += 1
            self.root.after(0, lambda: self.lbl_estanon.config(text=f"Estanon: {self.contador_estanon}"))
            
            # Ciclo continua al siguiente inicio automaticamente...
        
        self.root.after(0, lambda: messagebox.showinfo("Fin", "Secuencia completada."))
        # NO SALIMOS AL MENU AUTOMATICAMENTE, reactivamos botones
        self.root.after(0, self.fase_programacion)

    # --- UTILIDADES ---

    def regresar_a_origen(self, destino_final):
        """Calcula movimientos para volver a un S#."""
        actual = self.posicion_actual
        r_curr, c_curr = self.mapa_coords[actual]
        r_dest, c_dest = self.mapa_coords[destino_final]
        
        # Estrategia: 
        # 1. Si estamos en Destino, subir a 8 (centro fila 3)
        if actual == "Destino":
            self.mover_fisico(8)
            actual = 8
            r_curr, c_curr = self.mapa_coords[actual]

        # 2. Moverse horizontalmente a la columna destino
        while c_curr != c_dest:
            next_step = None
            if c_dest > c_curr: # Ir derecha
                # Buscar zona a la derecha
                target_coord = (r_curr, c_curr + 1)
                for k,v in self.mapa_coords.items():
                    if v == target_coord: next_step = k
            else: # Ir izquierda
                target_coord = (r_curr, c_curr - 1)
                for k,v in self.mapa_coords.items():
                    if v == target_coord: next_step = k
            
            if next_step:
                self.mover_fisico(next_step)
                r_curr, c_curr = self.mapa_coords[next_step]
            else:
                break 

        # 3. Subir verticalmente
        while r_curr > r_dest:
            target_coord = (r_curr - 1, c_curr)
            next_step = None
            for k,v in self.mapa_coords.items():
                if v == target_coord: next_step = k
            
            if next_step:
                self.mover_fisico(next_step)
                r_curr -= 1
            else:
                break
        
        # Asegurar update interno
        self.posicion_actual = destino_final
        self.actualizar_grid_visual()

    def reset_inteligente(self):
        """Logica de Reset solicitada."""
        if messagebox.askyesno("RESET", "¿Ejecutar Reset del sistema?"):
            r, c = self.mapa_coords[self.posicion_actual]
            
            # Si esta arriba (S1-S3), volver a S1 lateralmente
            if r == 0: 
                self.regresar_a_origen("S1")
                messagebox.showinfo("Reset", "Regreso a S1 completado.")
            else:
                # Si esta abajo, ir a Destino -> Volcar -> Regresar S1
                # Algoritmo simple: bajar directo
                self.enviar_comando(f"V-{STEPS_V * 4}") # Bajar fuerte
                self.posicion_actual = "Destino"
                self.actualizar_grid_visual()
                
                messagebox.showinfo("Limpieza", "Vacie el estanon y confirme.")
                self.regresar_a_origen("S1")
                
            self.rutas_programadas = []
            self.mostrar_menu_principal()

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
            f_frame = tk.Frame(self.panel_der, bg="#0f172a")
            f_frame.pack(pady=10)
            for zona in fila:
                # Caso especial Destino ancho visual
                ancho = 20 if zona == "Destino" else 8
                lbl = tk.Label(f_frame, text=str(zona), width=ancho, height=3,
                               font=("Arial", 12, "bold"), relief="ridge", bg="#475569", fg="white")
                lbl.pack(side="left", padx=10)
                self.cells[zona] = lbl
        self.actualizar_grid_visual()

    def actualizar_grid_visual(self):
        # Reset colores
        for z, lbl in self.cells.items():
            bg = "#3b82f6" if str(z).startswith("S") else "#10b981" if z == "Destino" else "#475569"
            lbl.config(bg=bg)
        
        # Resaltar actual
        if self.posicion_actual in self.cells:
            self.cells[self.posicion_actual].config(bg="#f59e0b") 

if __name__ == "__main__":
    root = tk.Tk()
    app = MarbleInterfaceFinal(root)
    root.mainloop()
