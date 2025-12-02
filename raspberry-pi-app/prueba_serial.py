import serial
import time

# --- CONFIGURACIÓN SERIAL ---
# 1. Identificamos el puerto que encontraste
PORT_NAME = '/dev/ttyACM0' 
# 2. Usamos la misma velocidad que configuraste en el STM32
BAUD_RATE = 115200 

def enviar_comando(comando):
    """Envía un comando serial al STM32 y espera una respuesta (opcional)."""
    
    # CRÍTICO: El comando debe terminar en '\n' (salto de línea) para que el STM32
    # sepa que el mensaje ha terminado (según tu código de interrupción C).
    mensaje = comando + '\n'
    
    try:
        # Abrir el puerto serial
        ser = serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1)
        
        # Esperar un momento para que la conexión se estabilice
        time.sleep(0.1) 
        
        # Enviar el comando codificado en bytes (UTF-8)
        ser.write(mensaje.encode('utf-8'))
        print(f"✅ Enviado: {comando}")
        
        # Cerrar el puerto
        ser.close()

    except serial.SerialException as e:
        print(f"❌ Error de conexión serial: {e}")
        print("Asegúrate de que el STM32 esté conectado y que el puerto no esté abierto en RealTerm.")
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")


# --- BUCLE DE PRUEBA INTERACTIVO ---
print("--- TEST DE COMANDOS STM32 ---")
print("Protocolo: H[pasos] o V[pasos]. Ejemplo: H4096, V-2000")

while True:
    try:
        comando = input("Comando a enviar (o 'q' para salir): ").strip()
        
        if comando.lower() == 'q':
            break
        
        if comando:
            enviar_comando(comando)
            
    except KeyboardInterrupt:
        break
    
print("Prueba finalizada.")