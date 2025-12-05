import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACION SERIAL ---
# Ajustar puerto segun corresponda (/dev/ttyACM0 en Pi, COMx en Windows)
PORT_NAME = '/dev/ttyACM0' 
BAUD_RATE = 115200

# --- CONFIGURACION FISICA ---
STEPS_H = 1520
STEPS_V = 1328

# Ajuste fino (1/8 de celda)
CALIB_FINE_H = int(STEPS_H / 8)
CALIB_FINE_V = int(STEPS_V / 8)

# --- TIEMPOS DE ESPERA (Segundos) ---
# Ajustados para motor lento (periodo 2000 en STM32)
TIME_MOVE_H = 3.0  
TIME_MOVE_V = 3.0
TIME_SERVO  = 2.0

class MarbleInterfaceFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("SISTEMA DE CONTROL V6")
        self.root.geometry("1024x600")
        self.root.configure(bg="#1e293b") 

        # --- ESTADO DEL SISTEMA ---
        self.ser = None
        self.connect_serial()

        # Hilo de escucha serial (eventos de canicas)
        self.thread_serial = None
        
        self.posicion_actual = "S1"
        self.columna_virtual_destino = 1 
        
        # LISTA DE RUTAS (Cola de prioridad)
        # Formato: [{'origen': 'S1', 'camino': [1, 4, 'Destino']}, ...]
        self.rutas_programadas = [] 
        
        self.contador_canicas = 0 
        
        # Banderas de Control
        self.stop_emergencia = False
        self.ocupado = False 
        
        # Mapa Logico de Coordenadas (Fila, Columna)
        self.mapa_coords = {
            "S1": (0,0), "S2": (0,1), "S3": (0,2),
            1: (1,0), 2: (1,1), 3: (1,2),
            4: (2,0), 5: (2,1), 6: (2,2),
            7: (3,0), 8: (3,1), 9: (3,2),
            "Destino": (4,1) # Virtual, puede ser (4,0), (4,1) o (4,2)
        }

        self.setup_ui()

        # Iniciar listener solo si hay puerto serie real
        if self.ser and self.ser.is_open:
            self.thread_serial = threading.Thread(
                target=self._serial_listener,
                daemon=True
            )
            self.thread_serial.start()

    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1)
            time.sleep(2) 
            print("CONEXION SERIAL OK")
        except Exception:
            print("MODO SIMULACION (Sin Serial)")

    
    def _serial_listener(self):
        """Hilo que corre en segundo plano escuchando mensajes del STM32."""
        while True:
            # Este loop es infinito mientras viva el programa
            if self.ser and self.ser.is_open:
                try:
                    # Si hay datos esperando...
                    if self.ser.in_waiting > 0:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        
                        # Si es un mensaje de evento (#IN, #OUT, etc.)
                        if line.startswith('#'):
                            # IMPORTANTE: No actualizar GUI desde este hilo.
                            # Usamos root.after para agendar la actualización en el hilo principal.
                            self.root.after(0, lambda: self._procesar_datos_serial(line))
                            
                except Exception as e:
                    print(f"Error en listener serial: {e}")
            
            # Pequeña pausa para no saturar el CPU
            time.sleep(0.05)

    def _procesar_datos_serial(self, line):
        """Recibe la línea cruda (#TIPO,ent,sal,act), parsea y actualiza la UI."""
        try:
            # Formato esperado: #IN,5,2,3  (Tipo, Entradas, Salidas, Actuales)
            parts = line.split(',')
            if len(parts) >= 4:
                # tipo = parts[0]
                entradas = int(parts[1])
                salidas = int(parts[2])
                actuales = int(parts[3])

                # Actualizar variables internas
                self.contador_canicas = actuales
                self.canicas_entrada_stm32 = entradas
                self.canicas_salida_stm32 = salidas

                # Actualizar etiqueta en pantalla (si existe)
                if hasattr(self, 'lbl_canicas'):
                    self.lbl_canicas.config(text=f"Canicas en Estañón: {self.contador_canicas}")
                    
                print(f"Evento STM32 procesado: {line}")
                
        except ValueError:
            print(f"Error parseando trama: {line}")

    def enviar_comando(self, cmd):
        # SEGURIDAD: Si hay STOP, bloquear todo menos el frenado
        if self.stop_emergencia and cmd not in ["H0", "V0", "S65"]:
            print(f"CMD BLOQUEADO POR STOP: {cmd}")
            return

        try:
            if self.ser and self.ser.is_open:
                msg = f"{cmd}\n"
                self.ser.write(msg.encode('utf-8'))
                print(f"TX: {msg.strip()}")
            else:
                print(f"SIM: {cmd}")
        except Exception as e:
            print(f"Error Serial: {e}")

    # --- LOGICA STOP EMERGENCIA ---
    def activar_stop(self):
        self.stop_emergencia = True
        self.ocupado = False # Liberar ocupado para permitir reset manual posterior
        print("!!! STOP ACTIVADO !!!")
        
        # Enviar frenado inmediato
        self.enviar_comando("H0")
        self.enviar_comando("V0") 
        self.enviar_comando("S65") 
        
        messagebox.showwarning("STOP", "PARADA DE EMERGENCIA ACTIVADA.\nMotores detenidos y secuencia cancelada.")

    # --- LOGICA DE MOVIMIENTO ---
    def calcular_comando(self, origen, destino):
        r1, c1 = self.mapa_coords[origen]
        
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
        
        if diff_r == 1 and diff_c == 0: return f"V-{STEPS_V}"
        if diff_r == -1 and diff_c == 0: return f"V{STEPS_V}"
        if diff_c == 1 and diff_r == 0: return f"H{STEPS_H}"
        if diff_c == -1 and diff_r == 0: return f"H-{STEPS_H}"
        
        if diff_c == 0 and diff_r > 1:
            pasos_total = diff_r * STEPS_V
            return f"V-{pasos_total}" 

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

    # --- THREADING GENERAL ---
    def ejecutar_movimiento_thread(self, destino, callback=None):
        if self.stop_emergencia: return
        if self.ocupado: 
            print("SISTEMA OCUPADO")
            return

        self.ocupado = True
        self.deshabilitar_controles()
        threading.Thread(target=self._proceso_mover, args=(destino, callback)).start()

    def _proceso_mover(self, destino, callback):
        if self.stop_emergencia: 
            self.liberar_sistema()
            return
        
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            
            # Determinar tiempo de espera
            wait_time = TIME_MOVE_V if "V" in cmd else TIME_MOVE_H
            # Si baja varios pisos de golpe (reset), dar mas tiempo
            if "V-" in cmd and int(cmd.split('-')[1]) > STEPS_V: 
                 wait_time = wait_time * 2.5 

            if destino == "Destino":
                _, c_origen = self.mapa_coords[self.posicion_actual]
                self.columna_virtual_destino = c_origen
            
            self.posicion_actual = destino
            self.root.after(0, self.actualizar_grid_visual)
            
            # Espera activa chequeando STOP
            steps_wait = int(wait_time * 10)
            for _ in range(steps_wait): 
                if self.stop_emergencia: 
                    self.liberar_sistema()
                    return
                time.sleep(0.1)
            
            if callback and not self.stop_emergencia:
                self.root.after(0, callback)
            else:
                self.liberar_sistema()

    def liberar_sistema(self):
        self.ocupado = False
        self.root.after(0, self.habilitar_controles)

    def deshabilitar_controles(self):
        # Deshabilita botones del panel izquierdo para evitar clicks dobles
        if hasattr(self, 'panel_izq'):
            for w in self.panel_izq.winfo_children():
                if isinstance(w, tk.Frame):
                     for btn in w.winfo_children():
                         if isinstance(btn, tk.Button): btn.config(state="disabled")

    def habilitar_controles(self):
        if hasattr(self, 'panel_izq'):
            for w in self.panel_izq.winfo_children():
                if isinstance(w, tk.Frame):
                     for btn in w.winfo_children():
                         if isinstance(btn, tk.Button): btn.config(state="normal")

    # --- INTERFAZ UI PRINCIPAL ---
    def setup_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()

        header = tk.Frame(self.root, bg="#0f172a", height=60)
        header.pack(fill="x")
        tk.Label(header, text="CONTROL DE CANICAS V6.0", font=("Arial", 20, "bold"), 
                 bg="#0f172a", fg="#e2e8f0").pack(side="left", padx=20, pady=10)
        
        tk.Button(header, text="STOP TOTAL", bg="#dc2626", fg="white", font=("Arial", 12, "bold"),
                  command=self.activar_stop).pack(side="right", padx=20, pady=10)

        self.main_frame = tk.Frame(self.root, bg="#1e293b")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.mostrar_menu_principal()

    def mostrar_menu_principal(self):
        self.stop_emergencia = False 
        self.ocupado = False
        for w in self.main_frame.winfo_children(): w.destroy()
        
        tk.Label(self.main_frame, text="MENU PRINCIPAL", font=("Arial", 18), 
                 bg="#1e293b", fg="white").pack(pady=30)

        btn_opts = {"width": 30, "height": 2, "font": ("Arial", 14, "bold"), "bg": "#334155", "fg": "white"}
        
        tk.Button(self.main_frame, text="1. MODO MANUAL", command=self.iniciar_modo_manual, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="2. MODO PROGRAMADO", command=self.iniciar_modo_programado, **btn_opts).pack(pady=10)
        tk.Button(self.main_frame, text="3. CALIBRACION Y NIVELACION", command=self.iniciar_modo_calibracion, **btn_opts).pack(pady=10)

    def construir_pantalla_base(self, titulo, mostrar_grid=True):
        self.stop_emergencia = False 
        self.ocupado = False
        
        for w in self.main_frame.winfo_children(): w.destroy()
        
        top = tk.Frame(self.main_frame, bg="#334155")
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=titulo, font=("Arial", 14, "bold"), bg="#334155", fg="#facc15").pack(side="left", padx=10)
        tk.Button(top, text="MENU", bg="#64748b", fg="white", command=self.mostrar_menu_principal).pack(side="right", padx=10, pady=5)

        self.panel_izq = tk.Frame(self.main_frame, bg="#1e293b", width=550)
        self.panel_izq.pack(side="left", fill="y", padx=10)
        
        if mostrar_grid:
            self.panel_der = tk.Frame(self.main_frame, bg="#0f172a")
            self.panel_der.pack(side="right", fill="both", expand=True, padx=10)
            self.construir_grid_visual()
        else:
            self.panel_der = None 

        self.lbl_canicas = tk.Label(self.panel_izq, text=f"Canicas: {self.contador_canicas}", 
                                    font=("Arial", 16, "bold"), bg="#1e293b", fg="#facc15")
        self.lbl_canicas.pack(side="bottom", pady=20)

    # --- MODO 3: CALIBRACION ---
    def iniciar_modo_calibracion(self):
        self.construir_pantalla_base("CALIBRACION", mostrar_grid=False)
        
        # 1. Servo
        tk.Label(self.panel_izq, text="CONTROL SERVO", bg="#1e293b", fg="#fbbf24", font=("Arial", 10)).pack(pady=5)
        f_s = tk.Frame(self.panel_izq, bg="#1e293b"); f_s.pack()
        tk.Button(f_s, text="ABRIR", command=lambda: self.enviar_comando("S25"), bg="#d97706", fg="white").pack(side="left", padx=5)
        tk.Button(f_s, text="CERRAR", command=lambda: self.enviar_comando("S65"), bg="#059669", fg="white").pack(side="left", padx=5)

        # 2. General (1 Nivel)
        tk.Label(self.panel_izq, text="GENERAL (1 CELDA)", bg="#1e293b", fg="#fbbf24", font=("Arial", 10)).pack(pady=10)
        f_g = tk.Frame(self.panel_izq, bg="#1e293b"); f_g.pack()
        tk.Button(f_g, text="▲", command=lambda: self.mover_calib("V", 1, "FULL"), bg="#475569", fg="white", width=4).grid(row=0, column=1)
        tk.Button(f_g, text="◀", command=lambda: self.mover_calib("H", -1, "FULL"), bg="#475569", fg="white", width=4).grid(row=1, column=0)
        tk.Button(f_g, text="▶", command=lambda: self.mover_calib("H", 1, "FULL"), bg="#475569", fg="white", width=4).grid(row=1, column=2)
        tk.Button(f_g, text="▼", command=lambda: self.mover_calib("V", -1, "FULL"), bg="#475569", fg="white", width=4).grid(row=2, column=1)

        # 3. Fino (1/8 Nivel)
        tk.Label(self.panel_izq, text="AJUSTE FINO (1/8)", bg="#1e293b", fg="#fbbf24", font=("Arial", 10)).pack(pady=10)
        f_f = tk.Frame(self.panel_izq, bg="#1e293b"); f_f.pack()
        
        # M2 (IZQ) - Comando R
        tk.Label(f_f, text="M2(IZQ)", bg="#1e293b", fg="white", font=("Arial", 7)).grid(row=0, column=0, padx=5)
        tk.Button(f_f, text="▲", command=lambda: self.mover_individual("R", 1), bg="#3b82f6", fg="white").grid(row=1, column=0)
        tk.Button(f_f, text="▼", command=lambda: self.mover_individual("R", -1), bg="#3b82f6", fg="white").grid(row=2, column=0)
        
        # AMBOS VERT - Comando V
        tk.Label(f_f, text="VERT(2)", bg="#1e293b", fg="white", font=("Arial", 7)).grid(row=0, column=1, padx=5)
        tk.Button(f_f, text="▲▲", command=lambda: self.mover_calib("V", 1, "FINE"), bg="#8b5cf6", fg="white").grid(row=1, column=1)
        tk.Button(f_f, text="▼▼", command=lambda: self.mover_calib("V", -1, "FINE"), bg="#8b5cf6", fg="white").grid(row=2, column=1)
        
        # HORIZ - Comando H
        tk.Label(f_f, text="HORIZ", bg="#1e293b", fg="white", font=("Arial", 7)).grid(row=0, column=2, padx=5)
        tk.Button(f_f, text="◀", command=lambda: self.mover_calib("H", -1, "FINE"), bg="#3b82f6", fg="white").grid(row=1, column=2)
        tk.Button(f_f, text="▶", command=lambda: self.mover_calib("H", 1, "FINE"), bg="#3b82f6", fg="white").grid(row=2, column=2)

        # M1 (DER) - Comando L
        tk.Label(f_f, text="M1(DER)", bg="#1e293b", fg="white", font=("Arial", 7)).grid(row=0, column=3, padx=5)
        tk.Button(f_f, text="▲", command=lambda: self.mover_individual("L", 1), bg="#3b82f6", fg="white").grid(row=1, column=3)
        tk.Button(f_f, text="▼", command=lambda: self.mover_individual("L", -1), bg="#3b82f6", fg="white").grid(row=2, column=3)

        tk.Button(self.panel_izq, text="CONFIRMAR POSICION S1", bg="#10b981", fg="white", command=self.confirmar_s1).pack(pady=20, fill="x")

    def mover_calib(self, eje, dir, tipo):
        if self.stop_emergencia: return
        pasos = CALIB_FINE_V if tipo == "FINE" else STEPS_V
        if eje == "H" and tipo == "FINE": pasos = CALIB_FINE_H
        elif eje == "H" and tipo == "FULL": pasos = STEPS_H
        signo = "" if dir > 0 else "-"
        self.enviar_comando(f"{eje}{signo}{pasos}")

    def mover_individual(self, motor, dir):
        if self.stop_emergencia: return
        pasos = CALIB_FINE_V
        signo = "" if dir > 0 else "-"
        self.enviar_comando(f"{motor}{signo}{pasos}")

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
        if self.stop_emergencia or self.ocupado: return
        r, c = self.mapa_coords[self.posicion_actual]
        if self.posicion_actual == "Destino":
            r = 4
            c = self.columna_virtual_destino

        # --- Validación de límites horizontales (COL 0 y COL 2) ---
        if direccion == "left" and c == 0:
            messagebox.showwarning("Movimiento Prohibido", "No se puede ir más a la izquierda (Columna S1/1/4/7).")
            return
        if direccion == "right" and c == 2:
            messagebox.showwarning("Movimiento Prohibido", "No se puede ir más a la derecha (Columna S3/3/6/9).")
            return
        # -----------------------------------------------------------

        targets = {"left": (r, c-1), "right": (r, c+1), "down": (r+1, c)}
        target_coords = targets.get(direccion)
        
        destino = None
        for k, v in self.mapa_coords.items():
            if v == target_coords: destino = k; break
        
        if direccion == "down" and self.posicion_actual in [7, 8, 9]: destino = "Destino"

        if destino:
            valido, msg = self.validar_movimiento(self.posicion_actual, destino)
            if valido:
                self.ejecutar_movimiento_thread(destino, callback=self.check_fin_recorrido_manual)
            else:
                # Este else maneja movimientos no adyacentes o subir en ruta
                messagebox.showwarning("Movimiento Invalido", msg)
        else:
            messagebox.showwarning("Error", "No existe zona en esa direccion")

    def check_fin_recorrido_manual(self):
        if self.posicion_actual == "Destino" and not self.stop_emergencia:
            self.rutina_volcado_y_retorno()
        else:
            self.liberar_sistema()

    def rutina_volcado_y_retorno(self):
        if self.stop_emergencia: 
            self.liberar_sistema()
            return
        
        print("Descargando...")
        self.enviar_comando("S25")
        time.sleep(TIME_SERVO)
        self.enviar_comando("S65")
        time.sleep(1.0)             

        if not self.stop_emergencia:
            self.contador_canicas += 1
            self.lbl_canicas.config(text=f"Canicas: {self.contador_canicas}")
            # Volver por defecto a S1 tras descargar en modo manual
            # Truco: liberar ocupado solo un instante para que el thread de retorno pueda tomarlo
            self.ocupado = False 
            self.iniciar_retorno_thread("S1")
        else:
            self.liberar_sistema()

    # --- MODO 2: PROGRAMADO ---
    def iniciar_modo_programado(self):
        self.ruta_temp = []
        self.construir_pantalla_base("PROGRAMACION", mostrar_grid=True)
        
        # Panel derecho para la LISTA DE PRIORIDAD
        self.frame_lista_rutas = tk.Frame(self.panel_der, bg="#1e293b")
        self.frame_lista_rutas.pack(side="right", fill="both", expand=True, padx=5)
        
        tk.Label(self.frame_lista_rutas, text="COLA DE EJECUCIÓN", 
                 bg="#1e293b", fg="#fbbf24", font=("Arial",10,"bold")).pack(pady=5)
        
        self.container_rutas = tk.Frame(self.frame_lista_rutas, bg="#334155")
        self.container_rutas.pack(fill="both", expand=True)

        self.crear_ui_programacion()
        self.refrescar_lista_rutas()

    def crear_ui_programacion(self):
        # Limpiar panel izquierdo excepto contador
        for w in self.panel_izq.winfo_children(): 
            if w != self.lbl_canicas: w.destroy()
        
        tk.Label(self.panel_izq, text="PUNTO DE INICIO", font=("Arial", 10, "bold"), bg="#1e293b", fg="#94a3b8").pack(pady=(10,2))
        self.var_inicio = tk.StringVar(value="S1")
        f_i = tk.Frame(self.panel_izq, bg="#1e293b"); f_i.pack()
        for z in ["S1", "S2", "S3"]:
            tk.Radiobutton(f_i, text=z, variable=self.var_inicio, value=z, 
                           bg="#1e293b", fg="white", selectcolor="#0f172a",
                           command=self.reset_ruta_builder).pack(side="left", padx=5)

        tk.Label(self.panel_izq, text="CONSTRUCCIÓN DE RUTA", font=("Arial", 10, "bold"), bg="#1e293b", fg="#94a3b8").pack(pady=(15,2))
        self.lbl_ruta = tk.Label(self.panel_izq, text="...", bg="#334155", fg="white", wraplength=300, height=2)
        self.lbl_ruta.pack(fill="x", padx=10)
        
        f_n = tk.Frame(self.panel_izq, bg="#1e293b"); f_n.pack(pady=10)
        for i in range(1, 10):
            tk.Button(f_n, text=str(i), width=5, height=2, bg="#475569", fg="white",
                      command=lambda z=i: self.agregar_paso(z)).grid(row=(i-1)//3, column=(i-1)%3, padx=3, pady=3)
        
        tk.Button(self.panel_izq, text="DESTINO", bg="#10b981", fg="white", font=("Arial", 10, "bold"),
                  command=lambda: self.agregar_paso("Destino")).pack(fill="x", padx=20, pady=5)
        
        f_act = tk.Frame(self.panel_izq, bg="#1e293b"); f_act.pack(fill="x", padx=20, pady=5)
        tk.Button(f_act, text="BORRAR ÚLTIMO", command=self.undo_paso, bg="#64748b", fg="white").pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(f_act, text="AGREGAR A COLA", command=self.guardar_ruta, bg="#0ea5e9", fg="white").pack(side="right", fill="x", expand=True, padx=2)
        
        tk.Button(self.panel_izq, text="▶ INICIAR SECUENCIA", command=self.iniciar_secuencia_thread, 
                  bg="#d946ef", fg="white", font=("Arial", 12, "bold")).pack(fill="x", padx=20, pady=20)

    # --- GESTION DE LISTA DE RUTAS ---
    def guardar_ruta(self):
        if not self.ruta_temp or self.ruta_temp[-1] != "Destino":
            messagebox.showerror("Error", "La ruta debe terminar en 'Destino'")
            return
        
        nueva_ruta = {
            'origen': self.ruta_temp[0],
            'camino': self.ruta_temp[1:]
        }
        
        origen_nuevo = nueva_ruta['origen']
        
        # --- Lógica de Sobreescritura / Límite de 3 Rutas ---
        indice_existente = -1
        for i, ruta in enumerate(self.rutas_programadas):
            if ruta['origen'] == origen_nuevo:
                indice_existente = i
                break
        
        if indice_existente != -1:
            # Sobreescribir
            self.rutas_programadas[indice_existente] = nueva_ruta
            messagebox.showinfo("Ruta Actualizada", f"Ruta {origen_nuevo} sobreescrita con éxito.")
        else:
            # Verificar si ya existen 3 rutas distintas (S1, S2, S3)
            origenes_actuales = set(ruta['origen'] for ruta in self.rutas_programadas)
            if len(origenes_actuales) >= 3 and origen_nuevo not in origenes_actuales:
                messagebox.showerror("Límite de Rutas", "Solo se permiten 3 rutas, una por origen (S1, S2, S3).")
                return
            
            # Agregar
            self.rutas_programadas.append(nueva_ruta)
            messagebox.showinfo("Ruta Guardada", f"Ruta {origen_nuevo} agregada a la cola.")
        # -------------------------------------------------------
        
        self.refrescar_lista_rutas()
        self.reset_ruta_builder()

    def borrar_ruta(self, index):
        if 0 <= index < len(self.rutas_programadas):
            if messagebox.askyesno("Borrar", f"¿Eliminar ruta #{index+1}?"):
                self.rutas_programadas.pop(index)
                self.refrescar_lista_rutas()
    
    def mover_prioridad(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.rutas_programadas):
            self.rutas_programadas[index], self.rutas_programadas[new_index] = self.rutas_programadas[new_index], self.rutas_programadas[index]
            self.refrescar_lista_rutas()

    def refrescar_lista_rutas(self):
        # Limpiar lista visual
        for w in self.container_rutas.winfo_children(): w.destroy()
        
        if not self.rutas_programadas:
            tk.Label(self.container_rutas, text="Cola vacía", bg="#334155", fg="#94a3b8").pack(pady=10)
            return

        for idx, ruta in enumerate(self.rutas_programadas):
            frame_row = tk.Frame(self.container_rutas, bg="#334155", pady=2)
            frame_row.pack(fill="x", pady=1)
            
            # --- POSICIÓN Y BOTONES DE PRIORIDAD ---
            
            # 1. Flechas (Izquierda)
            f_prio = tk.Frame(frame_row, bg="#334155"); f_prio.pack(side="left")
            
            if idx > 0:
                tk.Button(f_prio, text="▲", font=("Arial", 6), height=1, bg="#475569", fg="white",
                          command=lambda i=idx: self.mover_prioridad(i, -1)).pack(side="top", padx=1)
            else:
                tk.Label(f_prio, text=" ", font=("Arial", 6), height=1, bg="#334155").pack(side="top")

            if idx < len(self.rutas_programadas) - 1:
                tk.Button(f_prio, text="▼", font=("Arial", 6), height=1, bg="#475569", fg="white",
                          command=lambda i=idx: self.mover_prioridad(i, 1)).pack(side="bottom", padx=1)
            else:
                 tk.Label(f_prio, text=" ", font=("Arial", 6), height=1, bg="#334155").pack(side="bottom")
            
            # 2. Info de la Ruta (Centro)
            origen = ruta['origen']
            # Se genera una vista simple de los primeros 4 pasos
            camino_str = "->".join(map(str, ruta['camino'][:4]))
            if len(ruta['camino']) > 4:
                camino_str += "..." 

            txt = f"[{origen}] # {idx+1}: {camino_str}"
            tk.Label(frame_row, text=txt, bg="#334155", fg="white", anchor="w", font=("Arial", 9)).pack(side="left", fill="x", expand=True, padx=5)
            
            # 3. Botón Borrar (Derecha)
            tk.Button(frame_row, text="X", bg="#ef4444", fg="white", width=3,
                      command=lambda i=idx: self.borrar_ruta(i)).pack(side="right", padx=2)

    # --- HELPERS DE CONSTRUCCION DE RUTA ---
    def reset_ruta_builder(self):
        self.ruta_temp = [self.var_inicio.get()]; self.actualizar_lbl_ruta()
    def agregar_paso(self, zona):
        if not hasattr(self, 'ruta_temp') or not self.ruta_temp: self.reset_ruta_builder()
        valido, msg = self.validar_movimiento(self.ruta_temp[-1], zona)
        if valido: self.ruta_temp.append(zona); self.actualizar_lbl_ruta()
        else: messagebox.showwarning("Invalido", msg)
    def undo_paso(self):
        if len(self.ruta_temp) > 1: self.ruta_temp.pop(); self.actualizar_lbl_ruta()
    def actualizar_lbl_ruta(self): self.lbl_ruta.config(text="->".join(map(str, self.ruta_temp)))

    # --- EJECUCION DE SECUENCIA ---
    def iniciar_secuencia_thread(self):
        if not self.rutas_programadas: messagebox.showwarning("Vacio", "No hay rutas"); return
        if self.ocupado: return
        self.ocupado = True
        self.deshabilitar_controles()
        self.stop_emergencia = False
        threading.Thread(target=self._proceso_secuencia).start()

    def _proceso_secuencia(self):
        for ruta in self.rutas_programadas:
            if self.stop_emergencia: break
            
            inicio = ruta['origen']
            camino = ruta['camino']
            
            # 1. IR INICIO
            self._logica_retorno_interna(inicio)
            
            if self.stop_emergencia: break
            evt = threading.Event()
            self.root.after(0, lambda: self._show_info_wait("Carga", f"Coloque canica en {inicio}", evt))
            evt.wait()

            # 2. EJECUTAR RUTA
            for paso in camino:
                if self.stop_emergencia: break
                self._logica_mover_interna(paso)
            
            # 3. DESCARGA SILENCIOSA
            if self.stop_emergencia: break
            print("Iniciando descarga...")
            time.sleep(0.5)
            self.enviar_comando("S25")
            time.sleep(TIME_SERVO)
            self.enviar_comando("S65")
            time.sleep(1.0)
            
            if not self.stop_emergencia:
                self.contador_canicas += 1
                self.root.after(0, lambda: self.lbl_canicas.config(text=f"Canicas: {self.contador_canicas}"))

        if not self.stop_emergencia:
            self._logica_retorno_interna("S1")
            self.root.after(0, lambda: messagebox.showinfo("Fin", "Secuencia Terminada"))
        
        self.liberar_sistema()

    def _show_info_wait(self, title, msg, event):
        if not self.stop_emergencia: messagebox.showinfo(title, msg)
        event.set()

    # --- LOGICA DE RETORNO Y WRAPPERS ---
    def iniciar_retorno_thread(self, destino):
        if self.stop_emergencia or self.ocupado: return
        self.ocupado = True
        self.deshabilitar_controles()
        threading.Thread(target=self._proceso_retorno_wrapper, args=(destino,)).start()

    def _proceso_retorno_wrapper(self, destino):
        self._logica_retorno_interna(destino)
        self.liberar_sistema()

    def _logica_retorno_interna(self, destino_final):
        if self.stop_emergencia: return
        actual = self.posicion_actual
        if actual == destino_final: return

        # 1. RETORNO SEGURO POR IZQUIERDA
        if actual == "Destino":
            col_virtual = self.columna_virtual_destino
            
            if col_virtual > 2: col_virtual = 2
            if col_virtual < 0: col_virtual = 0

            pasos_a_izq = col_virtual
            
            # Mover izquierda celda por celda
            for _ in range(pasos_a_izq):
                if self.stop_emergencia: return
                self.enviar_comando(f"H-{STEPS_H}")
                time.sleep(TIME_MOVE_H)
            
            # Subir a S1
            for _ in range(4):
                if self.stop_emergencia: return
                self.enviar_comando(f"V{STEPS_V}")
                time.sleep(TIME_MOVE_V)
            
            self.posicion_actual = "S1"
            self.root.after(0, self.actualizar_grid_visual)

        # 2. De S1 a destino_final
        _, c_curr = self.mapa_coords[self.posicion_actual]
        _, c_dest = self.mapa_coords[destino_final]
        
        while c_curr != c_dest:
            if self.stop_emergencia: return
            direction = 1 if c_dest > c_curr else -1
            cmd = f"H{STEPS_H}" if direction == 1 else f"H-{STEPS_H}"
            self.enviar_comando(cmd)
            time.sleep(TIME_MOVE_H)
            c_curr += direction
            
            k = "S1"
            if c_curr == 1: k = "S2"
            if c_curr == 2: k = "S3"
            self.posicion_actual = k
            self.root.after(0, self.actualizar_grid_visual)

        self.posicion_actual = destino_final
        self.root.after(0, self.actualizar_grid_visual)

    def _logica_mover_interna(self, destino):
        if self.stop_emergencia: return
        cmd = self.calcular_comando(self.posicion_actual, destino)
        if cmd:
            self.enviar_comando(cmd)
            wait_time = TIME_MOVE_V if "V" in cmd else TIME_MOVE_H
            if "V-" in cmd and int(cmd.split('-')[1]) > STEPS_V: wait_time *= 2.5 

            if destino == "Destino":
                _, c_origen = self.mapa_coords[self.posicion_actual]
                self.columna_virtual_destino = c_origen
            
            self.posicion_actual = destino
            self.root.after(0, self.actualizar_grid_visual)
            
            steps = int(wait_time*10)
            for _ in range(steps):
                if self.stop_emergencia: return
                time.sleep(0.1)

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
