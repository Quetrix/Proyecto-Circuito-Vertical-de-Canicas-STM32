\# Sistema de Distribución Vertical de Canicas



Este repositorio contiene el código fuente, diseño y documentación para un sistema mecatrónico de distribución de canicas en una matriz vertical de 3x3. El proyecto integra un microprocesador (Raspberry Pi) para la lógica de alto nivel y la interfaz de usuario, y un microcontrolador (STM32 Nucleo) para el control preciso de los actuadores en tiempo real.



\## Arquitectura del Sistema



El sistema utiliza un modelo Maestro-Esclavo mediante comunicación Serial (UART):



1\.  \*\*Maestro (Cerebro): Raspberry Pi\*\*

&nbsp;   \* Ejecuta la Interfaz Gráfica de Usuario (GUI) en Python (Tkinter).

&nbsp;   \* Gestiona la máquina de estados, la planificación de rutas y la lógica de calibración.

&nbsp;   \* Envía comandos de movimiento al STM32.



2\.  \*\*Esclavo (Músculo): STM32 Nucleo-F446RE\*\*

&nbsp;   \* Controla 3 motores paso a paso (28BYJ-48) para el movimiento X/Y.

&nbsp;   \* Controla 1 servomotor para el mecanismo de descarga de canicas.

&nbsp;   \* Gestiona interrupciones de hardware (Timers y UART) para movimientos precisos y no bloqueantes.

&nbsp;   \* Implementa parada de emergencia mediante botón físico.



\## Estructura del Repositorio



\* \*\*/raspberry-pi-app\*\*: Código Python para la interfaz de control y scripts de prueba serial.

\* \*\*/proyecto-canicas-stm32\*\*: Firmware en C para el STM32 (Proyecto STM32CubeIDE).

\* \*\*/docs\*\*: Diagramas, hojas de datos y documentación adicional.

\* \*\*/simulation\*\*: Prototipos web o simulaciones lógicas del sistema.



\## Requisitos Generales



\* \*\*Hardware:\*\*

&nbsp;   \* 1x Placa STM32 Nucleo-F446RE.

&nbsp;   \* 1x Raspberry Pi (3B+ o 4).

&nbsp;   \* 3x Motores 28BYJ-48 con drivers ULN2003.

&nbsp;   \* 1x Servomotor de 270 grados (Mecanismo de volcado).

&nbsp;   \* Fuente de alimentación externa de 5V (Mínimo 2A).



\* \*\*Software:\*\*

&nbsp;   \* Python 3.x con librerías `tkinter` y `pyserial`.

&nbsp;   \* STM32CubeIDE para compilar el firmware.

