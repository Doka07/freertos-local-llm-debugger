#include "trace.h"

#include <stddef.h>

#define UART0_BASE 0x40004000UL
#define UARTDR (*(volatile uint32_t *)(UART0_BASE + 0x000U))
#define UARTSTATE (*(volatile uint32_t *)(UART0_BASE + 0x004U))
#define UARTCTRL (*(volatile uint32_t *)(UART0_BASE + 0x008U))
#define UARTSTATE_TXBF (1UL << 0)
#define UARTCTRL_TXEN (1UL << 0)

static trace_event_t trace_ring[ TRACE_CAPACITY ];
static volatile uint32_t trace_next;
static volatile uint32_t trace_sequence;
static uint32_t trace_flushed;
static TickType_t trace_last_seen[ 4 ];
static void trace_monitor_task( void * argument );

static void uart_putc( char c )
{
    while ( ( UARTSTATE & UARTSTATE_TXBF ) != 0U ) {}
    UARTDR = (uint32_t)c;
}

static void uart_text( const char * text )
{
    while ( *text != '\0' )
    {
        uart_putc( *text++ );
    }
}

static void uart_uint( uint32_t value )
{
    char buffer[ 11 ];
    uint32_t i = sizeof( buffer );

    buffer[ --i ] = '\0';
    do
    {
        buffer[ --i ] = (char)( '0' + ( value % 10U ) );
        value /= 10U;
    } while ( value != 0U );
    uart_text( &buffer[ i ] );
}

static void copy_name( char * destination, const char * source )
{
    size_t i;
    for ( i = 0; i < 7U; i++ )
    {
        destination[ i ] = ( source != NULL ) ? source[ i ] : '\0';
        if ( destination[ i ] == '\0' )
        {
            break;
        }
    }
    for ( ; i < 8U; i++ )
    {
        destination[ i ] = '\0';
    }
}

void trace_init( void )
{
    UARTCTRL |= UARTCTRL_TXEN;
    trace_next = 0U;
    trace_sequence = 0U;
    trace_flushed = 0U;
    trace_last_seen[ 0 ] = 0U;
    trace_last_seen[ 1 ] = 0U;
    trace_last_seen[ 2 ] = 0U;
    trace_last_seen[ 3 ] = 0U;
    uart_text( "BOOT freertos-baseline\r\n" );
    configASSERT( xTaskCreate( trace_monitor_task, "monitor", configMINIMAL_STACK_SIZE,
                               NULL, configMAX_PRIORITIES - 1U, NULL ) == pdPASS );
}

void trace_emit( trace_event_type_t type, const char * task, const char * object, uint16_t value )
{
    trace_event_t * event = &trace_ring[ trace_next % TRACE_CAPACITY ];
    event->sequence = trace_sequence++;
    event->timestamp = xTaskGetTickCount();
    event->type = (uint8_t)type;
    event->priority = ( xTaskGetSchedulerState() == taskSCHEDULER_RUNNING ) ?
                      (uint8_t)uxTaskPriorityGet( NULL ) : 0U;
    event->value = value;
    copy_name( event->task, task );
    copy_name( event->object, object );
    if ( task != NULL && task[ 0 ] == 't' && task[ 1 ] == 'a' && task[ 2 ] == 's' &&
         task[ 3 ] == 'k' && task[ 4 ] >= 'A' && task[ 4 ] <= 'D' )
    {
        trace_last_seen[ (uint32_t)( task[ 4 ] - 'A' ) ] = event->timestamp;
    }
    trace_next++;
}

void trace_emit_from_isr( trace_event_type_t type, const char * task, const char * object, uint16_t value )
{
    UBaseType_t saved_status = taskENTER_CRITICAL_FROM_ISR();
    trace_event_t * event = &trace_ring[ trace_next % TRACE_CAPACITY ];
    event->sequence = trace_sequence++;
    event->timestamp = xTaskGetTickCountFromISR();
    event->type = (uint8_t)type;
    event->priority = 0U;
    event->value = value;
    copy_name( event->task, task );
    copy_name( event->object, object );
    trace_next++;
    taskEXIT_CRITICAL_FROM_ISR( saved_status );
}

void trace_flush_uart( void )
{
    uint32_t available = trace_next;
    while ( trace_flushed < available )
    {
        const trace_event_t * event = &trace_ring[ trace_flushed % TRACE_CAPACITY ];
        uart_text( "TRC seq=" ); uart_uint( event->sequence );
        uart_text( " ts=" ); uart_uint( (uint32_t)event->timestamp );
        uart_text( " type=" ); uart_uint( event->type );
        uart_text( " prio=" ); uart_uint( event->priority );
        uart_text( " task=" ); uart_text( event->task );
        uart_text( " obj=" ); uart_text( event->object );
        uart_text( " value=" ); uart_uint( event->value );
        uart_text( "\r\n" );
        trace_flushed++;
    }
}

void trace_assert_failed( const char * file, unsigned long line )
{
    (void)file;
    trace_emit( TRACE_ASSERT, "system", "assert", (uint16_t)line );
    trace_flush_uart();
    uart_text( "HALT assert\r\n" );
    for ( ;; ) {}
}

void vApplicationMallocFailedHook( void )
{
    trace_emit( TRACE_FAULT, "system", "malloc", 0U );
    trace_flush_uart();
    for ( ;; ) {}
}

void vApplicationStackOverflowHook( TaskHandle_t task, char * name )
{
    (void)task;
    trace_emit( TRACE_FAULT, name, "stack", 0U );
    trace_flush_uart();
    for ( ;; ) {}
}

void vApplicationIdleHook( void )
{
    __asm volatile ( "wfi" );
}


static void trace_monitor_task( void * argument )
{
    TickType_t now;
    uint32_t i;
    (void)argument;

    for ( ;; )
    {
        vTaskDelay( pdMS_TO_TICKS( 100U ) );
        now = xTaskGetTickCount();
        for ( i = 0U; i < 4U; i++ )
        {
            if ( ( now - trace_last_seen[ i ] ) > pdMS_TO_TICKS( 500U ) )
            {
                trace_emit( TRACE_FAULT, "monitor", "stall", (uint16_t)i );
                trace_flush_uart();
                taskDISABLE_INTERRUPTS();
                for ( ;; ) {}
            }
        }
        trace_emit( TRACE_HEARTBEAT, "monitor", "progress", (uint16_t)trace_next );
    }
}
