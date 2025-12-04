\# Interfaz de Control - Python (Raspberry Pi)



Esta carpeta contiene la aplicación de control de alto nivel desarrollada en Python. Provee una interfaz gráfica (GUI) robusta para operar el sistema en modos manual, programado y de mantenimiento.



\## Archivos Principales



\* \*\*interfaz\_canicas.py\*\*: Aplicación principal. Contiene la lógica de la máquina de estados, manejo de hilos (threading) para evitar congelamientos de la interfaz, y la gestión de rutas.

\* \*\*prueba\_serial.py\*\*: Script de utilidad para probar la conexión serial y enviar comandos crudos (Raw) al STM32 para depuración.



\## Requisitos de Instalación



El sistema requiere Python 3 y las siguientes librerías:



```bash

sudo apt-get update

sudo apt-get install python3-tk

pip3 install pyserial

