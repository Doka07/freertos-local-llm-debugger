#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"
#include "task.h"

#include "trace.h"

static QueueHandle_t queue_data;
static SemaphoreHandle_t mutex_data;

static void producer_task( void * argument )
{
    uint16_t value = 0U;
    (void)argument;
    for ( ;; )
    {
        value++;
        if ( xQueueSend( queue_data, &value, 0U ) == pdPASS )
        {
            trace_emit( TRACE_QUEUE_SEND, "taskA", "q1", value );
        }
        trace_emit( TRACE_TASK_RUN, "taskA", "", value );
        vTaskDelay( pdMS_TO_TICKS( 20U ) );
    }
}

static void processor_task( void * argument )
{
    uint16_t value;
    (void)argument;
    for ( ;; )
    {
        if ( xQueueReceive( queue_data, &value, portMAX_DELAY ) == pdPASS )
        {
            trace_emit( TRACE_QUEUE_RECEIVE, "taskB", "q1", value );
            if ( xSemaphoreTake( mutex_data, portMAX_DELAY ) == pdPASS )
            {
                trace_emit( TRACE_MUTEX_TAKE, "taskB", "mtx1", value );
                taskYIELD();
                xSemaphoreGive( mutex_data );
                trace_emit( TRACE_MUTEX_GIVE, "taskB", "mtx1", value );
            }
        }
    }
}

static void consumer_task( void * argument )
{
    uint32_t heartbeat = 0U;
    (void)argument;
    for ( ;; )
    {
        heartbeat++;
        trace_emit( TRACE_HEARTBEAT, "taskC", "sem1", (uint16_t)heartbeat );
        vTaskDelay( pdMS_TO_TICKS( 50U ) );
    }
}

static void logger_task( void * argument )
{
    (void)argument;
    for ( ;; )
    {
        trace_emit( TRACE_TASK_RUN, "taskD", "", 0U );
        trace_flush_uart();
        vTaskDelay( pdMS_TO_TICKS( 100U ) );
    }
}

int main( void )
{
    trace_init();
    queue_data = xQueueCreate( 8U, sizeof( uint16_t ) );
    mutex_data = xSemaphoreCreateMutex();
    configASSERT( queue_data != NULL );
    configASSERT( mutex_data != NULL );

    xTaskCreate( producer_task, "taskA", configMINIMAL_STACK_SIZE, NULL, 2U, NULL );
    xTaskCreate( processor_task, "taskB", configMINIMAL_STACK_SIZE, NULL, 3U, NULL );
    xTaskCreate( consumer_task, "taskC", configMINIMAL_STACK_SIZE, NULL, 1U, NULL );
    xTaskCreate( logger_task, "taskD", configMINIMAL_STACK_SIZE, NULL, 1U, NULL );
    vTaskStartScheduler();
    configASSERT( 0 );
    return 0;
}
