#include <stdint.h>

extern int main( void );
extern void vPortSVCHandler( void );
extern void xPortPendSVHandler( void );
extern void xPortSysTickHandler( void );
extern uintptr_t _estack;

void Reset_Handler( void )
{
    (void)main();
    for ( ;; ) {}
}

void Default_Handler( void )
{
    for ( ;; ) {}
}

/* CMSDK timer0 (IRQn 8, vector index 24) on this QEMU machine (mps2-an385). Weak so every
 * build that doesn't use it (i.e. everything except case_003) still links -- only a build
 * that explicitly configures and enables that timer will ever actually take this vector. */
__attribute__((weak)) void TIMER0_Handler( void )
{
    for ( ;; ) {}
}

__attribute__((section(".isr_vector"), used))
const uintptr_t vector_table[] =
{
    (uintptr_t)&_estack,
    (uintptr_t)Reset_Handler,
    (uintptr_t)Default_Handler,    /* NMI */
    (uintptr_t)Default_Handler,    /* HardFault */
    (uintptr_t)Default_Handler,    /* MemManage */
    (uintptr_t)Default_Handler,    /* BusFault */
    (uintptr_t)Default_Handler,    /* UsageFault */
    (uintptr_t)Default_Handler,    /* reserved */
    (uintptr_t)Default_Handler,    /* reserved */
    (uintptr_t)Default_Handler,    /* reserved */
    (uintptr_t)Default_Handler,    /* reserved */
    (uintptr_t)vPortSVCHandler,    /* SVCall */
    (uintptr_t)Default_Handler,    /* Debug Monitor */
    (uintptr_t)Default_Handler,    /* reserved */
    (uintptr_t)xPortPendSVHandler, /* PendSV */
    (uintptr_t)xPortSysTickHandler,/* SysTick */
    (uintptr_t)Default_Handler,    /* IRQ0 */
    (uintptr_t)Default_Handler,    /* IRQ1 */
    (uintptr_t)Default_Handler,    /* IRQ2 */
    (uintptr_t)Default_Handler,    /* IRQ3 */
    (uintptr_t)Default_Handler,    /* IRQ4 */
    (uintptr_t)Default_Handler,    /* IRQ5 */
    (uintptr_t)Default_Handler,    /* IRQ6 */
    (uintptr_t)Default_Handler,    /* IRQ7 */
    (uintptr_t)TIMER0_Handler      /* IRQ8 -- CMSDK timer0 */
};
