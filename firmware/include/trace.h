#ifndef TRACE_H
#define TRACE_H

#include <stdint.h>
#include "FreeRTOS.h"
#include "task.h"

#define TRACE_CAPACITY 1024U

typedef enum
{
    TRACE_BOOT = 1,
    TRACE_TASK_READY,
    TRACE_TASK_RUN,
    TRACE_QUEUE_SEND,
    TRACE_QUEUE_RECEIVE,
    TRACE_MUTEX_TAKE,
    TRACE_MUTEX_GIVE,
    TRACE_HEARTBEAT,
    TRACE_ASSERT,
    TRACE_FAULT
} trace_event_type_t;

typedef struct
{
    uint32_t sequence;
    TickType_t timestamp;
    uint8_t type;
    uint8_t priority;
    uint16_t value;
    char task[ 8 ];
    char object[ 8 ];
} trace_event_t;

void trace_init( void );
void trace_emit( trace_event_type_t type, const char * task, const char * object, uint16_t value );
/* ISR-safe variant: uses xTaskGetTickCountFromISR() instead of xTaskGetTickCount() and never
 * calls uxTaskPriorityGet() (not ISR-safe, has no FromISR form). Priority is always reported
 * as 0. Guarded by taskENTER/EXIT_CRITICAL_FROM_ISR() since the ring buffer counters are
 * shared with task-context trace_emit(). */
void trace_emit_from_isr( trace_event_type_t type, const char * task, const char * object, uint16_t value );
void trace_flush_uart( void );
void trace_assert_failed( const char * file, unsigned long line );

#endif
