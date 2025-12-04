# ⚙️ Firmware de Control - STM32 Nucleo F446RE

Este documento detalla el mapeo de pines utilizado y el protocolo de comunicación implementado en el firmware del microcontrolador (C/HAL).

## 1. Diagrama de Referencia

Para ubicar los pines en la placa Nucleo, consulte el siguiente diagrama de pinout, el cual muestra la distribución de los puertos GPIO:

![Pinout de la placa Nucleo-F446RE](pinout.png)

## 2. Mapeo de Pines para Actuadores

El sistema de control utiliza **12 pines GPIO** para los motores paso a paso y **1 pin PWM** para el servomotor de volcado.

| Actuador | Eje / Función | Pin del Microcontrolador (STM32) | Pin Arduino (Placa) | Tipo de Control |
| :--- | :--- | :--- | :--- | :--- |
| **Motor 0** | Horizontal (X) | PA0, PA1, PA4, PB0 | A0, A1, A2, A3 | GPIO Output |
| **Motor 1** | Vertical Izquierdo | PA5, PA6, PA7, PA8 | D13, D12, D11, D7 | GPIO Output |
| **Motor 2** | Vertical Derecho | **PB4, PA10, PB3, PB1** | D5, D2, D3, D14 | GPIO Output |
| **Servomotor** | Volcado (Descarga) | **PB6 (TIM4_CH1)** | **D10** | PWM (50 Hz) |

## 3. Configuración y Periféricos

El firmware implementa programación no bloqueante utilizando interrupciones para las tareas principales:

* **TIM2:** Generación de pulsos para el movimiento de los motores paso a paso.
* **TIM4:** Generación de señal **PWM** para el control del servomotor.
* **USART2:** Recepción de comandos seriales (UART) de la Raspberry Pi.
* **EXTI (PC13):** Interrupción externa para la función de **Parada de Emergencia** (Botón Azul).

## 4. Protocolo de Comunicación Serial (UART / RS-232)

El STM32 escucha comandos a una velocidad de **115200 baudios**. Todos los comandos deben terminar obligatoriamente con un salto de línea (`\n`).

### 4.1. Comandos Aceptados (STM32)

| Comando | Formato | Descripción |
| :--- | :--- | :--- |
| **Horizontal** | `H` o `h` + número | Controla el eje X. Valores positivos/negativos definen la dirección. |
| **Vertical** | `V` o `v` + número | Controla el eje Y. Valores positivos/negativos definen la dirección (Arriba/Abajo). |
| **Servomotor** | **`S`** o **`s`** + ángulo | Mueve el servomotor al ángulo absoluto (0-270). |

| Parámetro del Servo | Ángulo (grados) |
| :--- | :--- |
| **Posición Cerrada (Reposo)** | **65** |
| **Posición Abierta (Volcado)** | **25** |

**Nota Crítica:** El carácter `\n` es la señal que la interrupción del STM32 usa para finalizar el comando y comenzar el parseo.

## 5. Consideraciones de Seguridad

* **Frenado:** La interrupción del botón de usuario (EXTI) detiene inmediatamente los motores paso a paso (`pasos_restantes = 0`) y sitúa el servo en la posición segura de **Cerrado (65 grados)**.
* **GND:** El polo negativo de la fuente de alimentación externa del servo y los drivers debe estar conectado al **GND** de la placa Nucleo.