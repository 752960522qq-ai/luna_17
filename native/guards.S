.text
.macro damage_guard symbol,check,original
.global \symbol
.type \symbol,%function
\symbol:
    sub sp,sp,#224
    stp x0,x1,[sp,#0]
    stp x2,x3,[sp,#16]
    stp x4,x5,[sp,#32]
    stp x6,x7,[sp,#48]
    stp x8,x30,[sp,#64]
    stp q0,q1,[sp,#80]
    stp q2,q3,[sp,#112]
    stp q4,q5,[sp,#144]
    stp q6,q7,[sp,#176]
    bl \check
    mov w17,w0
    ldp x0,x1,[sp,#0]
    ldp x2,x3,[sp,#16]
    ldp x4,x5,[sp,#32]
    ldp x6,x7,[sp,#48]
    ldp x8,x30,[sp,#64]
    ldp q0,q1,[sp,#80]
    ldp q2,q3,[sp,#112]
    ldp q4,q5,[sp,#144]
    ldp q6,q7,[sp,#176]
    add sp,sp,#224
    cbnz w17,1f
    adrp x16,:got:\original
    ldr x16,[x16,:got_lo12:\original]
    ldr x16,[x16]
    br x16
1:  ret
.size \symbol,.-\symbol
.endm
damage_guard damage_hook,mod_ignore_damage,original_damage
damage_guard set_damage_hook,mod_ignore_damage,original_set_damage
damage_guard engine_hook,mod_ignore_engine,original_engine_hit
.section .note.GNU-stack,"",%progbits
