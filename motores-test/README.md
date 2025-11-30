# ⚙️ Conexiones de Motores (STM32 Nucleo-F446RE)

Este documento detalla el mapeo de pines utilizado para conectar los tres drivers ULN2003 al microcontrolador STM32F446RE.

La configuración se basa en la compatibilidad con los headers Arduino de la placa Nucleo.

## 1. Diagrama de Referencia

Para ubicar los pines en la placa, consulte el diagrama de pinout:

![Pinout de la placa Nucleo-F446RE](pinout.jpg)

## 2. Mapeo de Pines

Los 12 pines del microcontrolador están configurados como **GPIO Output** y conectados a los 12 pines de entrada de los drivers ULN2003.

| Motor | Bobina del Motor | Pin del Microcontrolador (STM32) | Pin Arduino (Etiqueta de la Placa) | Conector del Driver |
| :--- | :--- | :--- | :--- | :--- |
| **Horizontal (M0)** | Bobina 1-4 | PA0, PA1, PA4, PB0 | A0, A1, A2, A3 | IN1, IN2, IN3, IN4 |
| **Vertical Izquierdo (M1)**| Bobina 1-4 | PA5, PA6, PA7, PA8 | D13, D12, D11, D7 | IN1, IN2, IN3, IN4 |
| **Vertical Derecho (M2)** | Bobina 1-4 | PB1, PB2, PB3, PB4 | D14, D3, D2, D5 | IN1, IN2, IN3, IN4 |

## 3. Consideraciones Eléctricas

* **Tierra Común (GND):** El negativo de la fuente de alimentación externa de 5V para los drivers debe estar conectado al **GND** de la placa Nucleo.
* **Inversión de Giro:** El giro opuesto de los motores Verticales (M1 y M2) se maneja por **software** (intercambiando el sentido del índice de pasos en el código) y puede requerir un pequeño ajuste físico en el cableado de las bobinas de un motor (intercambiar IN2 e IN3) para asegurar la rotación opuesta.