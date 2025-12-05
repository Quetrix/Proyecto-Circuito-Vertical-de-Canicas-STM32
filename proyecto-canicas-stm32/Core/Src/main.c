/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
#include <stdlib.h>
#include <stdio.h> // Opcional, para sprintf si se quiere responder
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */

// --- VARIABLES UART ---
#define RX_BUFFER_SIZE 32
uint8_t rx_byte;               // Donde cae el byte que acaba de llegar
uint8_t rx_buffer[RX_BUFFER_SIZE]; // Donde armamos la frase completa
uint8_t rx_index = 0;          // Posición actual en el buffer
volatile uint8_t comando_listo = 0; // Bandera: 1 = ¡Llegó una orden completa!
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM4_Init(void);
static void MX_TIM3_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
// ESTA SECCIÓN AHORA CONTIENE TODAS LAS DEFINICIONES GLOBALES DE MOTORES Y EL SERVO

// --- VARIABLES DE ESTADO ---
volatile int32_t pasos_restantes_horiz = 0;

volatile int32_t pasos_restantes_v_izq = 0; // Motor M1
volatile int32_t pasos_restantes_v_der = 0; // Motor M2

// --- CONTADOR DE CANICAS (DOS SENSORES HC-SR04) ---

int canicasEntrada  = 0;
int canicasSalida   = 0;
int canicasActuales = 0;

bool canicaDetectada1 = false;
bool canicaDetectada2 = false;

const int distanciaSinCanica = 20;
const int umbralDeteccion    = 5;
const int distanciaMinima    = 2;

uint32_t tiempoUltimaDeteccion1 = 0;
uint32_t tiempoUltimaDeteccion2 = 0;
const uint32_t tiempoEspera     = 500;

uint32_t tiempoUltimaMuestra    = 0;
const uint32_t intervaloMuestreo = 100;

uint32_t tiempoUltimoEstado     = 0;
const uint32_t intervaloEstado  = 2000;


// Índices de paso actuales (0-7) para cada motor
volatile int8_t idx_h = 0;
volatile int8_t idx_vL = 0;
volatile int8_t idx_vR = 0;

// Secuencia Half-Step (8 pasos)
const uint8_t sequence[8][4] = {
  {1,0,0,0}, {1,1,0,0}, {0,1,0,0}, {0,1,1,0},
  {0,0,1,0}, {0,0,1,1}, {0,0,0,1}, {1,0,0,1}
};

// --- SERVO CONFIG ---
#define SERVO_MIN_PULSE 500
#define SERVO_MAX_PULSE 2500
#define SERVO_ANGULO_CERRADO 65  // Posición de reposo/transporte
#define SERVO_ANGULO_ABIERTO 25  // Posición de volcado


void stepper_write(int motor_id, int step_index) {
    const uint8_t* p = sequence[step_index % 8];

    // Motor 0: Horizontal (PA0, PA1, PA4, PB0)
    if(motor_id == 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, p[0]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, p[1]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, p[2]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, p[3]?GPIO_PIN_SET:GPIO_PIN_RESET);
    }
    // Motor 1: Vertical Izquierdo (PA5, PA6, PA7, PA8)
    else if(motor_id == 1) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, p[0]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_6, p[1]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, p[2]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_8, p[3]?GPIO_PIN_SET:GPIO_PIN_RESET);
    }
    // Motor 2: Vertical Derecho (PB1, PB2, PB3, PB4)
    else if(motor_id == 2) {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, p[0]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, p[1]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_3, p[2]?GPIO_PIN_SET:GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4, p[3]?GPIO_PIN_SET:GPIO_PIN_RESET);
    }
}

void Mover_Horizontal(int32_t pasos) {
    pasos_restantes_horiz = pasos; // + Derecha, - Izquierda
}

// Mover AMBOS (Comando V normal)
void Mover_Vertical_Sync(int32_t pasos) {
    pasos_restantes_v_izq = pasos;
    pasos_restantes_v_der = pasos;
}

// Mover SOLO IZQUIERDA (Nuevo Comando L)
void Mover_Vertical_L(int32_t pasos) {
    pasos_restantes_v_izq = pasos;
}

// Mover SOLO DERECHA (Nuevo Comando R)
void Mover_Vertical_R(int32_t pasos) {
    pasos_restantes_v_der = pasos;
}


void Mover_Servo(uint16_t angulo) {
    // Protección de límites físicos (0 a 270)
    if (angulo > 270) angulo = 270;

    // Cálculo del ancho de pulso (Pulse Width)
    // Formula: Pulso = Offset + (Angulo * (Rango / Max_Grados))
    uint32_t pulso = SERVO_MIN_PULSE + (angulo * 2000 / 270);

    // Actualizar el registro CCR1 del Timer 4
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_1, pulso);
}

// --- FUNCIÓN CRÍTICA DE INTERRUPCIÓN ---
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
    if (htim->Instance == TIM2) {

        // 1. Motor Horizontal (Sin cambios)
        if (pasos_restantes_horiz != 0) {
            int8_t dir = (pasos_restantes_horiz > 0) ? 1 : -1;
            idx_h = (idx_h + 8 + dir) % 8;
            stepper_write(0, idx_h);
            pasos_restantes_horiz -= dir;
        }

        // 2. Motor Vertical IZQUIERDO (M1) - Independiente
        if (pasos_restantes_v_izq != 0) {
            int8_t dir_L = (pasos_restantes_v_izq > 0) ? 1 : -1; // 1=Subir
            idx_vL = (idx_vL + 8 + dir_L) % 8;
            stepper_write(1, idx_vL);
            pasos_restantes_v_izq -= dir_L;
        }

        // 3. Motor Vertical DERECHO (M2) - Independiente
        if (pasos_restantes_v_der != 0) {
            // NOTA: M2 está montado en espejo, su giro físico debe ser opuesto a M1 para subir.
            // Si 'pasos_restantes' es positivo (queremos subir), dir_fisica debe ser negativa.
            int8_t dir_input = (pasos_restantes_v_der > 0) ? 1 : -1;
            int8_t dir_R = -dir_input; // INVERSION FISICA

            idx_vR = (idx_vR + 8 + dir_R) % 8;
            stepper_write(2, idx_vR);
            pasos_restantes_v_der -= dir_input; // Restamos la intención lógica
        }
    }
}

// ================== ULTRASONIDO: MEDICIÓN ==================
//
// Usamos TIM3 como contador a 1 MHz (1 tick = 1 µs).
// TIM3 ya está configurado y arrancado en USER CODE 2.

float MedirDistancia_cm(uint8_t sensor_id)
{
    GPIO_TypeDef *trig_port;
    uint16_t trig_pin;
    GPIO_TypeDef *echo_port;
    uint16_t echo_pin;

    if (sensor_id == 1)
    {
        trig_port = TRIG1_GPIO_Port;
        trig_pin  = TRIG1_Pin;
        echo_port = ECHO1_GPIO_Port;
        echo_pin  = ECHO1_Pin;
    }
    else
    {
        trig_port = TRIG2_GPIO_Port;
        trig_pin  = TRIG2_Pin;
        echo_port = ECHO2_GPIO_Port;
        echo_pin  = ECHO2_Pin;
    }

    // Asegurar TRIG en bajo
    HAL_GPIO_WritePin(trig_port, trig_pin, GPIO_PIN_RESET);
    HAL_Delay(2); // 2 ms para estabilizar

    // Generar pulso de 10 µs en TRIG usando TIM3
    __HAL_TIM_SET_COUNTER(&htim3, 0);
    HAL_GPIO_WritePin(trig_port, trig_pin, GPIO_PIN_SET);
    while (__HAL_TIM_GET_COUNTER(&htim3) < 10); // 10 µs
    HAL_GPIO_WritePin(trig_port, trig_pin, GPIO_PIN_RESET);

    // Esperar flanco de subida en ECHO (máx 30 ms)
    const uint32_t timeout_us = 30000; // 30,000 µs
    __HAL_TIM_SET_COUNTER(&htim3, 0);

    while (HAL_GPIO_ReadPin(echo_port, echo_pin) == GPIO_PIN_RESET)
    {
        if (__HAL_TIM_GET_COUNTER(&htim3) > timeout_us)
        {
            return -1.0f; // Timeout: sin eco
        }
    }

    // Medir tiempo en alto del pulso ECHO
    __HAL_TIM_SET_COUNTER(&htim3, 0);
    while (HAL_GPIO_ReadPin(echo_port, echo_pin) == GPIO_PIN_SET)
    {
        if (__HAL_TIM_GET_COUNTER(&htim3) > timeout_us)
        {
            return -1.0f; // Timeout: pulso demasiado largo
        }
    }

    uint32_t duracion_us = __HAL_TIM_GET_COUNTER(&htim3);

    // Convertir a distancia en cm (velocidad sonido 343 m/s)
    float distancia = (duracion_us * 0.0343f) / 2.0f; // ida y vuelta

    return distancia;
}

// ================== ULTRASONIDO: ENVÍO A RASPBERRY ==================
//
// Formato de mensaje (una línea por evento):
//   #IN,entradas,salidas,actuales\n
//   #OUT,entradas,salidas,actuales\n
//
// La Raspi simplemente escucha y parsea las líneas que empiezan con "#".

void EnviarEventoCanica(const char *tipo)  // tipo = "IN" o "OUT"
{
    char msg[64];
    int len = snprintf(msg, sizeof(msg),
                       "#%s,%d,%d,%d\n",
                       tipo,
                       canicasEntrada,
                       canicasSalida,
                       canicasActuales);

    if (len > 0)
    {
        HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)len, 50);
    }
}


/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_TIM2_Init();
  MX_TIM4_Init();
  MX_TIM3_Init();


  /* USER CODE BEGIN 2 */
    HAL_TIM_Base_Start_IT(&htim2); // Iniciar Timer Pasos
    HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_1); // Iniciar PWM Servo
    HAL_TIM_Base_Start(&htim3);   // Iniciar TIM3 como contador libre (1 MHz) para ultrasonidos


    HAL_UART_Receive_IT(&huart2, &rx_byte, 1); // Iniciar UART

    // POSICION INICIAL SEGURA (CERRADO = 65 grados)
    Mover_Servo(SERVO_ANGULO_CERRADO);


  /* USER CODE END 2 */


  /* Infinite loop */
    /* USER CODE BEGIN WHILE */
    while (1)
    {
        // ====================== UART: COMANDOS DESDE RASPBERRY ======================
        if (comando_listo)
        {
            comando_listo = 0; // Bajar bandera para no repetir

            char cmd = rx_buffer[0];
            int32_t pasos = atoi((char*)&rx_buffer[1]);

            if (cmd == 'H' || cmd == 'h')      // Comando Horizontal
            {
                Mover_Horizontal(pasos);
            }
            else if (cmd == 'V' || cmd == 'v') // Comando Vertical (ambos)
            {
                Mover_Vertical_Sync(pasos);
            }
            else if (cmd == 'L' || cmd == 'l') // Solo vertical izquierdo
            {
                Mover_Vertical_L(pasos);
            }
            else if (cmd == 'R' || cmd == 'r') // Solo vertical derecho
            {
                Mover_Vertical_R(pasos);
            }
            else if (cmd == 'S' || cmd == 's') // Servo
            {
                Mover_Servo((uint16_t)pasos);
            }
        }

        // ====================== ULTRASONIDO: MEDICIÓN Y CONTEO ======================
        uint32_t ahora = HAL_GetTick();

        // Medimos solo cada 'intervaloMuestreo' ms para no saturar
        if (ahora - tiempoUltimaMuestra >= intervaloMuestreo)
        {
            tiempoUltimaMuestra = ahora;

            // ----- SENSOR 1: ENTRADA -----
            float d1 = MedirDistancia_cm(1);

            if (d1 > 0 &&
                d1 > distanciaMinima &&
                d1 < (distanciaSinCanica - umbralDeteccion))
            {
                // Canica detectada en ENTRADA
                if (!canicaDetectada1 &&
                    (ahora - tiempoUltimaDeteccion1 > tiempoEspera))
                {
                    canicasEntrada++;
                    canicasActuales++;
                    canicaDetectada1 = true;
                    tiempoUltimaDeteccion1 = ahora;

                    EnviarEventoCanica("IN");
                }
            }
            else
            {
                canicaDetectada1 = false;
            }

            // ----- SENSOR 2: SALIDA -----
            float d2 = MedirDistancia_cm(2);

            if (d2 > 0 &&
                d2 > distanciaMinima &&
                d2 < (distanciaSinCanica - umbralDeteccion))
            {
                // Canica detectada en SALIDA
                if (!canicaDetectada2 &&
                    (ahora - tiempoUltimaDeteccion2 > tiempoEspera))
                {
                    canicasSalida++;
                    if (canicasActuales > 0)
                    {
                        canicasActuales--;
                    }
                    canicaDetectada2 = true;
                    tiempoUltimaDeteccion2 = ahora;

                    EnviarEventoCanica("OUT");
                }
            }
            else
            {
                canicaDetectada2 = false;
            }

            // (Opcional) Enviar estado periódico aunque no haya eventos
            /*
            if (ahora - tiempoUltimoEstado >= intervaloEstado)
            {
                tiempoUltimoEstado = ahora;
                EnviarEventoCanica("STATE"); // Si quisieras manejar este tipo en la Raspi
            }
            */
        }

        // No usamos delays aquí; los motores siguen avanzando por interrupción de TIM2
    }
    /* USER CODE END WHILE */


    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE3);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 16;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLR = 2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 84-1;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 1000-1;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 84-1;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 65535;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */

}

/**
  * @brief TIM4 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM4_Init(void)
{

  /* USER CODE BEGIN TIM4_Init 0 */

  /* USER CODE END TIM4_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM4_Init 1 */

  /* USER CODE END TIM4_Init 1 */
  htim4.Instance = TIM4;
  htim4.Init.Prescaler = 84-1;
  htim4.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim4.Init.Period = 20000-1;
  htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim4, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim4, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim4, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM4_Init 2 */

  /* USER CODE END TIM4_Init 2 */
  HAL_TIM_MspPostInit(&htim4);

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOC, Trig1_Pin|Trig2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_4|GPIO_PIN_5
                          |GPIO_PIN_6|GPIO_PIN_7|GPIO_PIN_8, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_3
                          |GPIO_PIN_4, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : Trig1_Pin Trig2_Pin */
  GPIO_InitStruct.Pin = Trig1_Pin|Trig2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pins : ECHO1_Pin ECHO2_Pin */
  GPIO_InitStruct.Pin = ECHO1_Pin|ECHO2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pins : PA0 PA1 PA4 PA5
                           PA6 PA7 PA8 */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_4|GPIO_PIN_5
                          |GPIO_PIN_6|GPIO_PIN_7|GPIO_PIN_8;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PB0 PB1 PB2 PB3
                           PB4 */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_3
                          |GPIO_PIN_4;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
// Callback: Se llama cada vez que llega un byte por UART
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  // Verificar que la interrupción viene del UART2 (USB)
  if (huart->Instance == USART2)
  {
    // CASO 1: Recibimos el caracter de final de linea ('\n')
    // Aquí es donde procesamos el comando completo
    if (rx_byte == '\n')
    {
      rx_buffer[rx_index] = '\0'; // Terminamos el string
      rx_index = 0;               // Reiniciamos índice para el próximo

      // --- PARSEO DE COMANDOS ---
      char cmd_char = rx_buffer[0];           // La letra (H, V, S)
      int valor = atoi((char*)&rx_buffer[1]); // El número (convertido a int)

      // Ejecutar directamente usando tus funciones existentes
      if (cmd_char == 'H' || cmd_char == 'h')
      {
          Mover_Horizontal(valor);
      }

      else if (cmd_char == 'V' || cmd_char == 'v')
      {
          Mover_Vertical_Sync(valor); // Mueve ambos
      }
      // NUEVO: Solo Izquierda
      else if (cmd_char == 'L' || cmd_char == 'l')
      {
          Mover_Vertical_L(valor);
      }
      // NUEVO: Solo Derecha
      else if (cmd_char == 'R' || cmd_char == 'r')
      {
          Mover_Vertical_R(valor);
      }

      // --- NUEVO: CONTROL DE SERVO ---
      else if (cmd_char == 'S' || cmd_char == 's')
      {
          Mover_Servo(valor);
      }
    }
    // CASO 2: Buffer lleno (Seguridad)
    else if (rx_index >= RX_BUFFER_SIZE - 1)
    {
        rx_index = 0; // Reiniciar si se llena sin recibir \n
    }
    // CASO 3: Recibimos un caracter normal
    else
    {
        // Guardar caracter (ignorando el 'Carriage Return' \r de Windows)
        if(rx_byte != '\r')
        {
            rx_buffer[rx_index++] = rx_byte;
        }
    }

    // IMPORTANTE: Volver a activar la escucha para el siguiente byte SIEMPRE
    HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
  }
}
// ... Las funciones de escritura y movimiento de motores estan en USER CODE 0

// Callback para el Botón de Usuario (PC13)
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin == B1_Pin) // Botón Azul (PC13)
  {
      // 1. FRENADO DE EMERGENCIA
      pasos_restantes_horiz = 0;
      pasos_restantes_v_der = 0;
      pasos_restantes_v_izq = 0;

      
      // 2. SERVO A POSICION SEGURA (Cerrado = 65 grados)
      Mover_Servo(SERVO_ANGULO_CERRADO);
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
