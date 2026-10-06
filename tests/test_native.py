"""Execute the built ARM64 module with Unicorn; no Android device is required.

These checks validate native control flow, the original encrypted-int codec,
and the original tank factory with its real managed string comparison.
Unity scene initialization and Android launch still require a device test.
Run: python tests/test_native.py --module FILE --game-library FILE
"""
import argparse
import ctypes
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R

LIB = 0x10000000
GAME = 0x20000000
HEAP = 0x40000000
STACK = 0x50000000
STUB = 0x70000000
HALT = STUB+0xf000

class Machine:
    def __init__(self, module, game):
        self.u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        self.u.mem_map(GAME,0x4000000)
        self.u.mem_map(HEAP,0x1000000)
        self.u.mem_map(STACK,0x100000)
        self.u.mem_map(STUB,0x10000)
        self.next_alloc=HEAP
        self.next_stub=STUB
        self.callbacks={}
        self.symbols={}
        self.calls=[]
        with Path(game).open('rb') as file:
            elf=ELFFile(file)
            self.game_segments=[(s['p_vaddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
        # Execute the original integer, byte and float constructors. Never
        # install a successful constructor stub at an address from the profile:
        # that would hide a wrong method entry (the r4 Tier crash).
        for address,size in [(0x18f2600,0x400),(0x18d3100,0x200),(0x1982c34,0x40),
                             (0x18daa20,0x138),(0x18db128,0x10),
                             (0x18f0a4c,0xb0),(0x1913900,0x14),
                             (0x1d82f0c,0x100)]:
            self.u.mem_write(GAME+address,self.game_read(address,size))
        with Path(module).open('rb') as file:
            elf=ELFFile(file)
            load=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            low=min(s['p_vaddr']&~4095 for s in load)
            high=max((s['p_vaddr']+s['p_memsz']+4095)&~4095 for s in load)
            self.u.mem_map(LIB+low,high-low)
            for s in load:self.u.mem_write(LIB+s['p_vaddr'],s.data())
            self.symbols={s.name:LIB+s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
            dynamic=elf.get_section_by_name('.dynsym')
            imports={
                'memcpy':self.memcpy,'memset':self.memset,'mmap':self.mmap,
                'mprotect':lambda:0,'munmap':lambda:0,'getpagesize':lambda:4096,
                'clock_gettime':self.clock,
                'strcmp':lambda: 0 if self.read(self.x(0),64).split(b'\0')[0]==self.read(self.x(1),64).split(b'\0')[0] else 1,
            }
            for section in elf.iter_sections():
                if section['sh_type']!='SHT_RELA':continue
                for relocation in section.iter_relocations():
                    kind=relocation['r_info_type']; add=relocation['r_addend']
                    if kind==1027:value=LIB+add
                    elif kind in (1025,1026,257):
                        symbol=dynamic.get_symbol(relocation['r_info_sym'])
                        if symbol['st_shndx']!='SHN_UNDEF':value=LIB+symbol['st_value']+add
                        else:value=self.stub(imports.get(symbol.name,lambda:0))+add
                    else:raise AssertionError(f'Unexpected relocation: {kind}')
                    self.qwrite(LIB+relocation['r_offset'],value)
        self.u.hook_add(UC_HOOK_CODE,self.on_code)
        self.global_q('base',GAME)
        self.at(GAME+0x18d4704,lambda:0x1a2b3c4d)
        self.at(GAME+0x18d4328,lambda:0x5a)
        self.at(GAME+0x19084e0,lambda:1)
        self.at(GAME+0x17ca9e4,lambda:0)

    def game_read(self, address, size):
        for start,data in self.game_segments:
            if start<=address<=address+size<=start+len(data):return data[address-start:address-start+size]
        raise AssertionError(hex(address))
    def read(self, address, size):return bytes(self.u.mem_read(address,size))
    def qread(self,address):return struct.unpack('<Q',self.read(address,8))[0]
    def qwrite(self,address,value):self.u.mem_write(address,struct.pack('<Q',value))
    def iwrite(self,address,value):self.u.mem_write(address,struct.pack('<I',value&0xffffffff))
    def global_q(self,name,value):self.qwrite(self.symbols[name],value)
    def global_i(self,name,value):self.iwrite(self.symbols[name],value)
    def x(self,n):return self.u.reg_read(getattr(R,f'UC_ARM64_REG_X{n}'))
    def sx(self,n,v):self.u.reg_write(getattr(R,f'UC_ARM64_REG_X{n}'),v)
    def sf(self,n,v):self.u.reg_write(getattr(R,f'UC_ARM64_REG_S{n}'),struct.unpack('<I',struct.pack('<f',v))[0])
    def f(self,n):return struct.unpack('<f',struct.pack('<I',self.u.reg_read(getattr(R,f'UC_ARM64_REG_S{n}'))))[0]
    def alloc(self,size=0x400):
        result=self.next_alloc;self.next_alloc+=(size+15)&~15;return result
    def object(self,size=0x400,klass=0x123):
        p=self.alloc(size);self.qwrite(p,klass);self.qwrite(p+0x10,0x123456);return p
    def string(self,text):
        encoded=text.encode('utf-16-le');p=self.alloc(0x16+len(encoded))
        self.qwrite(p,0x456);self.iwrite(p+0x10,len(encoded)//2)
        self.u.mem_write(p+0x14,encoded+b'\0\0');return p
    def original_factory(self,params,new_go):
        # Execute the game's _GenerateUnit and System.String operators, rather
        # than replacing the factory with an unconditional success callback.
        for address,size in [(0x1994a88,0x428),(0x2c3ed60,0x4c),
                             (0x2c3f054,0x1c),(0x17caa40,0x14)]:
            self.u.mem_write(GAME+address,self.game_read(address,size))
        player=self.string('Player');ai=self.string('AI')
        player_cell=GAME+0x3a94b20
        self.qwrite(GAME+0x394f100,player_cell)
        self.qwrite(player_cell,player) # Already initialized by the match's spawn.
        for address,value in [(0x394f0f8,ai),(0x394f048,self.alloc()),
                              (0x3951550,self.string('invalid tag')),
                              (0x3951548,self.string('missing player prefab')),
                              (0x3951558,self.string('missing AI prefab'))]:
            cell=self.alloc(8);self.qwrite(GAME+address,cell);self.qwrite(cell,value)
        for address in [0x394ca80,0x394ccc0]:
            klass=self.alloc();self.iwrite(klass+0xe4,1)
            cell=self.alloc(8);self.qwrite(cell,klass);self.qwrite(GAME+address,cell)
        self.u.mem_write(GAME+0x3bcc260,b'\1')
        def resolve_literal():
            if self.x(0)!=player_cell:raise AssertionError('Unexpected metadata slot')
            self.qwrite(player_cell,player)
        self.at(GAME+0x1830098,resolve_literal)
        self.at(GAME+0x1931cfc,lambda:params)
        self.at(GAME+0x343294c,lambda:int(self.x(0)==self.x(1)))
        self.at(GAME+0x2dc0ef4,lambda:int(self.read(self.x(0),self.x(2))==self.read(self.x(1),self.x(2))))
        self.at(GAME+0x33f9b98,lambda:self.calls.append(('factory_error',self.x(0))))
        def instantiate():
            self.calls.append(('instantiate',self.x(0),[self.f(i) for i in range(7)]))
            return new_go
        self.at(GAME+0x1d7f94c,instantiate)
        def unexpected():raise AssertionError('Factory raised an exception')
        self.at(GAME+0x17cacbc,unexpected);self.at(GAME+0x17cacc4,unexpected)
        return player
    def at(self,address,fn):
        self.u.mem_write(address,b'\xc0\x03\x5f\xd6');self.callbacks[address]=fn;return address
    def stub(self,fn):
        address=self.next_stub;self.next_stub+=16;return self.at(address,fn)
    def on_code(self,u,address,size,ignored):
        if address in self.callbacks:
            result=self.callbacks[address]()
            if result is not None:self.sx(0,result)
            u.reg_write(R.UC_ARM64_REG_PC,u.reg_read(R.UC_ARM64_REG_LR))
    def memcpy(self):
        out=self.x(0);self.u.mem_write(out,self.read(self.x(1),self.x(2)));return out
    def memset(self):
        out=self.x(0);self.u.mem_write(out,bytes([self.x(1)&255])*self.x(2));return out
    def mmap(self):return (self.alloc(self.x(1)+4096)+4095)&~4095
    def clock(self):self.u.mem_write(self.x(1),struct.pack('<2q',100,0));return 0
    def call(self,name,*args):
        for n,value in enumerate(args):self.sx(n,value)
        self.u.reg_write(R.UC_ARM64_REG_SP,STACK+0xff000)
        self.u.reg_write(R.UC_ARM64_REG_LR,HALT)
        self.u.emu_start(self.symbols.get(name,name),HALT,count=1000000)
        if self.u.reg_read(R.UC_ARM64_REG_PC)!=HALT:raise AssertionError('Function did not return')
        return self.x(0)

class NativeTests(unittest.TestCase):
    def setUp(self):self.m=Machine(ARGS.module,ARGS.game_library)

    def external_config(self, ident="MagazineTest", capacity=5, interval=.25, reload=8.):
        m=self.m
        class Config(ctypes.Structure):
            _fields_=[('id',ctypes.c_uint64)] + [(n,ctypes.c_int) for n in ['penetration','caliber','speed','reload']] + [('reload_offset',ctypes.c_float),('power',ctypes.c_int),('max_speed',ctypes.c_int),('reverse_speed',ctypes.c_float),('turret_speed',ctypes.c_int),('weight',ctypes.c_float)] + [(n,ctypes.c_int) for n in ['elevation','depression','crew','tier']] + [(n,ctypes.c_int*size) for n,size in [('body_armor',4),('turret_armor',4),('ammo',5)]] + [('mg_ammo',ctypes.c_int),('shell_penetration',ctypes.c_int*5),('wheel_count',ctypes.c_int)] + [(n,ctypes.c_float) for n in ['travel','rest','spring','damper','radius','track_length']] + [('magazine_capacity',ctypes.c_int),('shot_interval',ctypes.c_float),('magazine_reload',ctypes.c_float)]
        entry=m.symbols['hatch_tanks'];m.u.mem_write(entry,ident.encode()+b'\0')
        c=Config(id=entry,penetration=89,caliber=20,speed=780,reload=8,elevation=20,depression=10,magazine_capacity=capacity,shot_interval=interval,magazine_reload=reload)
        c.shell_penetration[0]=89
        m.u.mem_write(entry+592,bytes(c));m.global_i('hatch_count',1)
        status=m.object();m.qwrite(status+0x68,m.string(ident))
        return status,entry+592

    def test_original_shell_instructions_confirm_scale_and_gravity_step(self):
        m=self.m;shell,info,transform=[m.object() for _ in range(3)]
        m.qwrite(shell+0x20,transform);m.qwrite(shell+0x90,info)
        m.u.mem_write(info+0x18,struct.pack('<f',895./.23))
        m.u.mem_write(GAME+0x9a9214,m.game_read(0x9a9214,4))
        self.assertAlmostEqual(struct.unpack('<f',m.read(GAME+0x9a9214,4))[0],.23,places=6)
        m.u.mem_write(GAME+0x1960904,m.game_read(0x1960904,0x38))
        def forward():
            for i,v in enumerate([0.,0.,1.]):m.sf(i,v)
        m.at(GAME+0x343e264,forward)
        m.at(GAME+0x196093c,lambda:m.sx(30,HALT))
        m.sx(19,shell);m.sx(8,info);m.sx(0,transform);m.call(GAME+0x1960904)
        self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x98,4))[0],895.,places=3)
        self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x8c,4))[0],895.,places=3)
        m.u.mem_write(GAME+0x1960880,m.game_read(0x1960880,0x24))
        m.u.mem_write(shell+0x7c,struct.pack('<f',9.81));m.at(GAME+0x343a824,lambda:m.sf(0,.02))
        m.at(GAME+0x19608a4,lambda:m.sx(30,HALT))
        for _ in range(50):m.sx(19,shell);m.call(GAME+0x1960880)
        self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x88,4))[0],-9.81,places=4)

    def test_stock_scope_uses_new_vehicle_limits_and_restores_input(self):
        m=self.m;camera,pc,status,ui,turret,gun,params=[m.object() for _ in range(7)]
        m.qwrite(status+0x68,m.string('StockVehicle'));m.iwrite(status+0xc0,35);m.iwrite(status+0xc4,10)
        m.global_q('player_status',status);m.global_q('player_control',pc);m.global_i('state',3)
        m.at(GAME+0x1931cfc,lambda:params);m.at(GAME+0x3402abc,lambda:100)
        m.qwrite(pc+0x28,turret);m.qwrite(pc+0x30,gun);m.qwrite(camera+0x68,turret);m.qwrite(camera+0xe8,ui)
        m.iwrite(ui+0x30,2)
        for off,value in [(0x50,100.),(0x4c,1.)]:m.u.mem_write(camera+off,struct.pack('<f',value))
        observed=[]
        def original():
            observed.append(struct.unpack('<i',m.read(camera+0x58,4))[0])
            pitch=struct.unpack('<f',m.read(camera+0xa8,4))[0]-sum(struct.unpack('<f',m.read(camera+o,4))[0] for o in [0xd4,0xdc])
            m.u.mem_write(camera+0xa8,struct.pack('<f',pitch))
        m.global_q('original_camera_late_update',m.stub(original))
        for elevation,depression in [(35,10),(20,20)]:
            m.iwrite(status+0xc0,elevation);m.iwrite(status+0xc4,depression)
            for delta,expected in [(100.,-float(elevation)),(-100.,float(depression))]:
                m.u.mem_write(camera+0xd4,struct.pack('<f',delta));m.call('camera_late_update',camera,0)
                self.assertAlmostEqual(struct.unpack('<f',m.read(camera+0xa8,4))[0],expected)
                self.assertAlmostEqual(struct.unpack('<f',m.read(camera+0xd4,4))[0],delta)
        self.assertEqual(observed,[35,35,20,20])

    def test_aircraft_view_changes_clear_reticle_calibration_preserve_secondary(self):
        m=self.m;camera,pc,status,ui,game,params,air,secondary=[m.object() for _ in range(8)]
        m.global_q('player_status',status);m.global_q('player_control',pc);m.global_i('state',3)
        m.qwrite(ui+0x300,game);m.qwrite(game+0x118,status);m.qwrite(ui+0x218,secondary)
        m.qwrite(camera+0xe8,ui);m.qwrite(camera+0x68,air);m.iwrite(camera+0x38,1)
        m.at(GAME+0x1931cfc,lambda:params);m.global_q('original_camera_late_update',m.stub(lambda:0))
        m.global_q('original_sight_type',m.stub(lambda:0))
        for mode in [1,2,3]:
            m.iwrite(camera+0x38,mode);m.u.mem_write(ui+0x2c0,struct.pack('<f',19.))
            m.call('camera_late_update',camera,0)
            self.assertEqual(m.read(ui+0x2c0,4),b'\0'*4);self.assertEqual(m.qread(camera+0x68),air)
        m.iwrite(ui+0x2c,0);m.u.mem_write(ui+0x2c0,struct.pack('<f',12.));m.call('sight_type',ui,2,0)
        self.assertEqual(m.qread(ui+0x218),secondary);self.assertEqual(m.read(ui+0x2c0,4),b'\0'*4)
        m.u.mem_write(ui+0x2c0,struct.pack('<f',7.));m.call('camera_late_update',camera,0)
        self.assertEqual(struct.unpack('<f',m.read(ui+0x2c0,4))[0],7.) # Stable view retains new calibration.

    def test_imported_shell_uses_physical_speed_without_mutating_shared_info(self):
        m=self.m;status,config=self.external_config(ident='BallisticsTest',capacity=0);m.iwrite(config+16,895)
        launcher,info,shell=[m.object() for _ in range(3)]
        m.qwrite(launcher+0x38,status)
        m.u.mem_write(launcher+0x54,struct.pack('<f',1000.));m.u.mem_write(info+0x18,struct.pack('<f',1100.))
        m.global_q('original_attack_info',m.stub(lambda:info));m.call('attack_info',launcher,2,1,0)
        physical=895.*1.1;self.assertAlmostEqual(struct.unpack('<f',m.read(info+0x18,4))[0],physical,places=3)
        m.qwrite(shell+0x90,info)
        observed=[]
        def original():
            observed.append(struct.unpack('<f',m.read(info+0x18,4))[0])
            if not m.read(shell+0x9c,1)[0]:
                speed=observed[-1]*.23;m.u.mem_write(shell+0x98,struct.pack('<f',speed));m.u.mem_write(shell+0x9c,b'\1')
        m.global_q('original_shell_fixed_update',m.stub(original))
        for _ in range(2):m.call('shell_fixed_update',shell,0)
        self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x98,4))[0],physical,places=3)
        self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x7c,4))[0],9.81,places=5)
        self.assertAlmostEqual(observed[0],physical/.23,places=2);self.assertAlmostEqual(observed[1],physical,places=3)
        self.assertAlmostEqual(struct.unpack('<f',m.read(info+0x18,4))[0],physical,places=3)
        # The same managed address reused by stock ammunition must lose its imported profile.
        m.qwrite(status+0x68,m.string('Stock'));m.u.mem_write(info+0x18,struct.pack('<f',800.))
        m.call('attack_info',launcher,0,1,0);m.u.mem_write(shell+0x9c,b'\0');m.u.mem_write(shell+0x7c,struct.pack('<f',8.))
        m.call('shell_fixed_update',shell,0)
        self.assertEqual(observed[-1],800.);self.assertAlmostEqual(struct.unpack('<f',m.read(shell+0x98,4))[0],184.,places=4)
        self.assertEqual(struct.unpack('<f',m.read(shell+0x7c,4))[0],8.)

    def test_magazine_counts_main_shots_and_waits_for_full_reload(self):
        m=self.m;status,config=self.external_config();launcher=m.object();m.qwrite(launcher+0x38,status)
        info=m.object();clock=[10.];m.at(GAME+0x343a6dc,lambda:m.sf(0,clock[0]))
        m.global_q('original_launcher_fire',m.stub(lambda:m.global_q('firing_info',info)))
        state=m.symbols.get('magazine_state',m.symbols.get('magazine_state.0'))
        turret=m.object();m.qwrite(turret+0x40,status);seen=[]
        def original_update():
            raw=struct.unpack('<4I',m.read(status+0xdc,16));whole=((raw[1]-raw[2])&0xffffffff)^raw[2]
            seen.append(whole+struct.unpack('<f',m.read(turret+0x80,4))[0])
        m.global_q('original_turret_update',m.stub(original_update))
        def delay():
            m.call('turret_update',turret,0);return seen[-1]
        self.assertAlmostEqual(delay(),.25)
        for remaining in [4,3,2,1,0]:
            m.call('launcher_fire',launcher,0,1,0)
            self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],remaining)
            clock[0]+=.25
        self.assertEqual(delay(),8.)
        for _ in range(3):self.assertEqual(delay(),8.) # Pause: game time unchanged.
        clock[0]=18.9;self.assertEqual(delay(),8.)
        clock[0]=19.;self.assertAlmostEqual(delay(),.25);self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],5)
        m.global_q('original_launcher_fire',m.stub(lambda:0));m.call('launcher_fire',launcher,0,1,0)
        self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],5) # Failed shot.
        m.global_q('original_launcher_fire',m.stub(lambda:m.global_q('firing_info',info)));m.u.mem_write(launcher+0xa0,b'\1')
        m.call('launcher_fire',launcher,0,1,0);self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],5) # Coax.
        m.u.mem_write(launcher+0xa0,b'\0');m.call('launcher_fire',launcher,0,1,0)
        clock[0]=0.;self.assertAlmostEqual(delay(),.25);self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],5) # New match.
        other=m.object();m.qwrite(other+0x68,m.string('MagazineTest'));m.qwrite(launcher+0x38,other)
        m.call('launcher_fire',launcher,0,1,0);self.assertEqual(m.qread(state),other);self.assertEqual(struct.unpack('<i',m.read(state+8,4))[0],4)

    def test_magazine_feeds_original_reload_machine_and_restores_transient_fields(self):
        m=self.m;status,config=self.external_config(capacity=2,interval=.2,reload=7.5);turret=m.object();m.qwrite(turret+0x40,status)
        m.u.mem_write(turret+0x80,struct.pack('<f',42.));m.u.mem_write(turret+0xde,b'\0')
        m.at(GAME+0x343a6dc,lambda:m.sf(0,10.));seen=[]
        def original():
            raw=struct.unpack('<4I',m.read(status+0xdc,16));whole=((raw[1]-raw[2])&0xffffffff)^raw[2]
            seen.append(whole+struct.unpack('<f',m.read(turret+0x80,4))[0])
        m.global_q('original_turret_update',m.stub(original));m.call('turret_update',turret,0)
        self.assertAlmostEqual(seen[-1],.2,places=5)
        state=m.symbols.get('magazine_state',m.symbols.get('magazine_state.0'));m.iwrite(state+8,0);m.u.mem_write(state+12,struct.pack('<f',10.));m.call('turret_update',turret,0)
        self.assertEqual(seen[-1],7.5);self.assertEqual(struct.unpack('<f',m.read(turret+0x80,4))[0],42.);self.assertEqual(m.read(turret+0xde,1),b'\0')

    def test_only_current_offline_player_is_protected(self):
        m=self.m;s=m.object();hit=m.object();m.qwrite(hit+0x38,s);m.qwrite(hit+0x40,s)
        m.global_i('ready',1);m.global_i('state',3);m.global_i('god',1);m.global_q('player_status',s)
        for fn in ['mod_ignore_damage','mod_ignore_engine']:
            self.assertEqual(m.call(fn,hit),1)
            m.global_i('state',4);self.assertEqual(m.call(fn,hit),0)
            m.global_i('state',3);m.global_i('god',0);self.assertEqual(m.call(fn,hit),0)
            m.global_i('god',1);m.global_q('player_status',m.object());self.assertEqual(m.call(fn,hit),0)
            m.global_q('player_status',s);m.global_i('ready',0xffffffff);self.assertEqual(m.call(fn,hit),0)
            m.global_i('ready',1)

    def test_guards_preserve_integer_float_and_stack_arguments(self):
        m=self.m
        for hook,check,original in [('damage_hook','mod_ignore_damage','original_damage'),('set_damage_hook','mod_ignore_damage','original_set_damage'),('engine_hook','mod_ignore_engine','original_engine_hit')]:
            seen=[];expected=[0x123400+i for i in range(9)];vectors=[(i+7)*0x123456789abcdef for i in range(8)]
            def receive():
                seen.append(([m.x(i) for i in range(9)],[m.u.reg_read(getattr(R,f'UC_ARM64_REG_Q{i}')) for i in range(8)],m.read(STACK+0xff000,32)))
                return None
            m.global_q(original,m.stub(receive))
            def clobber():
                for i in range(1,9):m.sx(i,0xdead)
                for i in range(8):m.u.reg_write(getattr(R,f'UC_ARM64_REG_Q{i}'),0xbad)
                return 0
            m.callbacks[m.symbols[check]]=clobber
            for i,v in enumerate(vectors):m.u.reg_write(getattr(R,f'UC_ARM64_REG_Q{i}'),v)
            m.u.mem_write(STACK+0xff000,b'x'*32)
            m.call(hook,*expected)
            self.assertEqual(seen,[(expected,vectors,b'x'*32)])
            m.callbacks[m.symbols[check]]=lambda:1
            m.call(hook,*expected);self.assertEqual(len(seen),1)

    def test_original_codec_restores_initial_ammo_and_preserves_empty_slots(self):
        m=self.m;status=m.object();array=m.alloc(0x100);m.iwrite(array+0x18,3);m.qwrite(status+0xf0,array)
        for i,n in enumerate([16,0,6]):m.call('write_ammo_slot',array,i,n)
        before=m.read(array+0x20,48);m.u.mem_write(array+0x50,b'\x55'*16)
        m.call('refill',status)
        m.call('write_ammo_slot',array,0,15);m.call('write_ammo_slot',array,2,5)
        m.call('refill',status)
        self.assertEqual(m.read(array+0x20,48),before)
        self.assertEqual(m.read(array+0x50,16),b'\x55'*16)
        m.call('write_ammo_slot',array,9,999)
        self.assertEqual(m.read(array+0x20,48),before)

    def test_trampoline_relocates_the_real_game_adrp(self):
        m=self.m;rva=0x1984348;entry=GAME+rva;original=m.game_read(rva,16)
        m.u.mem_write(entry,original);destination=m.stub(lambda:0);out=m.alloc(8)
        self.assertEqual(m.call('install',rva,destination,out),1)
        self.assertEqual(m.read(entry,8),struct.pack('<2I',0x58000050,0xd61f0200))
        self.assertEqual(m.qread(entry+8),destination)
        trampoline=m.qread(out);m.u.reg_write(R.UC_ARM64_REG_SP,STACK+0xff000)
        # Two copied STPs, four MOV-wide instructions replacing ADRP, then MOV.
        m.u.emu_start(trampoline,trampoline+28,count=7)
        self.assertEqual(m.x(20),GAME+0x3bcc000)

    def swap_scene(self):
        m=self.m;game=m.object();params=m.object();gen=m.object();old_go=m.object();old_s=m.object();old_pc=m.object();new_go=m.object();new_s=m.object();new_pc=m.object()
        camera=m.object();ui=m.object();m.qwrite(game+0x38,ui);m.u.mem_write(ui+0x278,b"\1");m.u.mem_write(ui+0x2bc,struct.pack("<f",777.));old_tr=m.object();new_tr=m.object();old_tur=m.object();new_tur=m.object()
        m.qwrite(old_pc+0x20,old_tr);m.qwrite(new_pc+0x20,new_tr);m.qwrite(old_pc+0x28,old_tur);m.qwrite(new_pc+0x28,new_tur)
        old_gun,new_gun=m.object(),m.object();m.qwrite(old_pc+0x30,old_gun);m.qwrite(new_pc+0x30,new_gun)
        literal=m.alloc(8);m.qwrite(literal,m.string('Gun'));m.qwrite(GAME+0x394f0b8,literal)
        m.at(GAME+0x343fb40,lambda:new_gun if m.x(0)==new_tur else old_gun)
        m.qwrite(old_pc+0x70,old_s);m.qwrite(new_pc+0x70,new_s)
        m.iwrite(old_s+0x64,0);m.iwrite(new_s+0x64,1)
        launcher=m.object();launcher_tr=m.object();ls=m.alloc(0x40);m.iwrite(ls+0x18,1);m.qwrite(ls+0x20,launcher);m.qwrite(new_pc+0x58,ls);m.qwrite(launcher+0x20,launcher_tr)
        shells=m.alloc(0x80);m.iwrite(shells+0x18,5);m.qwrite(new_s+0xf0,shells)
        m.call('set_stat',new_s,0x78,212);m.call('set_stat',new_s,0xa8,895)
        m.qwrite(game+0x48,gen);m.qwrite(game+0x110,old_go);m.qwrite(game+0x118,old_s);m.qwrite(game+0x20,camera)
        m.u.mem_write(old_s+0x20,b'\x01\x01');m.qwrite(camera+0x60,old_tur);m.qwrite(camera+0x68,old_tr)
        array=m.alloc(0x40);m.iwrite(array+0x18,2);m.qwrite(array+0x20,m.object());m.qwrite(array+0x28,m.object());m.qwrite(gen+0x28,array)
        m.global_i('ready',1);m.global_i('state',3);m.global_i('pending',1);m.global_q('player_control',old_pc)
        m.global_q('original_game_update',m.stub(lambda:0));m.at(GAME+0x1931cfc,lambda:params)
        def position():
            for i,v in enumerate([11.,22.,33.]):m.sf(i,v)
        def rotation():
            for i,v in enumerate([0.,0.,0.,1.]):m.sf(i,v)
        m.at(GAME+0x343dbc4,position);m.at(GAME+0x343de40,rotation)
        m.original_factory(params,new_go)
        m.at(GAME+0x17caa40,lambda:0) # Both Player and Gun literals are initialized.
        active={old_go:True,new_go:True}
        def set_active():
            active[m.x(0)]=bool(m.x(1));m.calls.append(('active',m.x(0),m.x(1)))
        m.at(GAME+0x3431140,set_active)
        m.at(GAME+0x191f324,lambda:m.calls.append(('camera',m.x(0),m.x(1))))
        pc_type=m.alloc();status_type=m.alloc()
        get_type=m.alloc(32);m.qwrite(get_type,m.stub(lambda:pc_type if m.x(0)==old_pc else status_type))
        # The shipped T34_85_Player and ZiS_3_Player prefabs have PlayerControl
        # on the root, but UnitStatus on the child "Unit Info". Root-only
        # GetComponent(UnitStatus) must fail; PlayerControl.uStatus points at it.
        def component():
            m.calls.append(('component',m.x(0),m.x(1)))
            return new_pc if m.x(0)==new_go and m.x(1)==pc_type else 0
        get_component=m.alloc(32);m.qwrite(get_component,m.stub(component))
        get_active=m.alloc(32);m.qwrite(get_active,m.stub(lambda:int(active.get(m.x(0),False))))
        def lookup():
            name=m.read(m.x(1),32).split(b'\0')[0]
            return get_type if name==b'GetType' else get_component if name==b'GetComponent' else get_active if name==b'get_activeSelf' else 0
        m.global_q('class_method',m.stub(lookup))
        fields=[]
        for offset in [0x60,0x68]:
            typ=m.alloc(16);m.iwrite(typ+8,0x120000);field=m.alloc(32);m.qwrite(field+8,typ);m.iwrite(field+24,offset);fields.append(field)
        def next_field():
            iterator=m.x(1);index=m.qread(iterator)
            if index>=len(fields):return 0
            m.qwrite(iterator,index+1);return fields[index]
        m.global_q('class_fields',m.stub(next_field))
        return SimpleNamespace(game=game,params=params,old_go=old_go,old_s=old_s,
            old_pc=old_pc,new_go=new_go,new_s=new_s,new_pc=new_pc,camera=camera,
            old_tr=old_tr,new_tr=new_tr,old_tur=old_tur,new_tur=new_tur,array=array,ui=ui,launcher=launcher,
            pc_type=pc_type,get_component=get_component,old_gun=old_gun,new_gun=new_gun,active=active)

    def test_queued_swap_preserves_pose_and_updates_camera(self):
        m=self.m;s=self.swap_scene();m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.game+0x110),s.old_go)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0),0)
        m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.game+0x110),s.new_go);self.assertEqual(m.qread(s.game+0x118),s.new_s)
        self.assertEqual(m.qread(s.camera+0x60),s.new_tur);self.assertEqual(m.qread(s.camera+0x68),s.new_tr)
        self.assertEqual(m.read(s.new_s+0x20,2),b'\x01\x01')
        self.assertEqual(m.qread(m.symbols['player_control']),s.new_pc)
        self.assertEqual(m.qread(m.symbols['player_status']),s.new_s)
        self.assertEqual(struct.unpack('<I',m.read(s.params+0x64,4))[0],0)
        self.assertEqual(m.read(s.new_s+0x64,4),m.read(s.old_s+0x64,4))
        self.assertEqual(m.read(s.ui+0x278,1),b'\0')
        self.assertEqual(m.read(s.ui+0x2bc,4),b'\0'*4)
        self.assertEqual(m.qread(s.launcher+0x38),s.new_s)
        self.assertEqual(m.qread(s.launcher+0xb0),s.game)
        self.assertEqual(m.read(s.launcher+0x50,4),struct.pack('<i',212))
        self.assertEqual(m.read(s.launcher+0x54,4),struct.pack('<f',895.))
        self.assertEqual([c for c in m.calls if c[0]=='component'],[('component',s.new_go,s.pc_type)])
        self.assertIn(('instantiate',m.qread(s.array+0x28),[11.,22.,33.,0.,0.,0.,1.]),m.calls)
        self.assertIn(('active',s.old_go,0),m.calls)
        self.assertIn(('camera',s.camera,s.new_tur),m.calls)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0),0)
        m.call('game_update',s.game,0)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0),1)

    def test_unusable_new_components_keep_current_tank_and_camera(self):
        for component,state,expected in [('controller','null',-4),('controller','destroyed',-4),
                                         ('status','null',-5),('status','destroyed',-5)]:
            with self.subTest(component=component,state=state):
                self.m=Machine(ARGS.module,ARGS.game_library);m=self.m;s=self.swap_scene()
                if state=='null':
                    if component=='controller':m.qwrite(s.get_component,m.stub(lambda:0))
                    else:m.qwrite(s.new_pc+0x70,0)
                else:m.qwrite((s.new_pc if component=='controller' else s.new_s)+0x10,0)
                m.call('game_update',s.game,0)
                self.assertEqual(m.qread(s.game+0x110),s.old_go);self.assertEqual(m.qread(s.game+0x118),s.old_s)
                self.assertEqual(m.qread(s.camera+0x60),s.old_tur);self.assertEqual(m.qread(s.camera+0x68),s.old_tr)
                self.assertEqual(m.qread(m.symbols['player_control']),s.old_pc)
                self.assertEqual(m.qread(m.symbols['player_status']),s.old_s)
                self.assertEqual(m.read(s.params+0x5c,4),b'\0'*4);self.assertEqual(m.read(s.params+0x64,4),b'\0'*4)
                self.assertEqual([c for c in m.calls if c[0]=='active'],[('active',s.new_go,0)])
                self.assertEqual([c for c in m.calls if c[0]=='camera'],[])
                self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0)&0xffffffff,expected&0xffffffff)

    def test_weapon_not_initialized_waits_then_rolls_back(self):
        m=self.m;s=self.swap_scene();m.call('set_stat',s.new_s,0xa8,0)
        for _ in range(120):m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.game+0x110),s.old_go)
        self.assertNotIn(('active',s.old_go,0),m.calls)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0)&0xffffffff,(-7)&0xffffffff)

    def test_missing_direct_gun_cancels_before_camera_handover(self):
        m=self.m;s=self.swap_scene();m.at(GAME+0x343fb40,lambda:0)
        for _ in range(4):m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.game+0x110),s.old_go)
        self.assertEqual(m.qread(s.camera+0x60),s.old_tur)
        self.assertFalse(any(c[0]=='camera' for c in m.calls))
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0)&0xffffffff,(-9)&0xffffffff)

    def test_completed_swap_does_not_overwrite_aircraft_target(self):
        m=self.m;s=self.swap_scene()
        m.call('game_update',s.game,0);m.call('game_update',s.game,0)
        aircraft=m.object();m.qwrite(s.camera+0x68,aircraft)
        for _ in range(5):m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.camera+0x68),aircraft)
        self.assertEqual([c for c in m.calls if c[0]=='camera'],[('camera',s.camera,s.new_tur)])
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0),1)

    def test_failed_retirement_restores_original_player(self):
        m=self.m;s=self.swap_scene()
        m.call('game_update',s.game,0);m.call('game_update',s.game,0)
        s.active[s.old_go]=True # Simulate a Unity callback reactivating old GO.
        m.call('game_update',s.game,0)
        self.assertEqual(m.qread(s.game+0x110),s.old_go)
        self.assertEqual(m.qread(s.game+0x118),s.old_s)
        self.assertFalse(s.active[s.new_go])
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_switchResult',0,0)&0xffffffff,(-8)&0xffffffff)

    def test_single_gun_clears_old_secondary_sight_and_dual_gun_rebinds(self):
        m=self.m;ui,pc,status,tm,main,secondary=[m.object() for _ in range(6)]
        m.qwrite(pc+0x30,main);m.qwrite(pc+0x50,tm)
        old_second=m.object();old_sight=m.object();m.qwrite(ui+0x328,old_second);m.qwrite(ui+0x218,old_sight)
        m.at(GAME+0x342de34,lambda:m.x(0));m.at(GAME+0x3431140,lambda:m.calls.append(('sight_active',m.x(0),m.x(1))))
        m.call('rebuild_player_ui',ui,pc,status)
        self.assertEqual(m.qread(ui+0x320),main);self.assertEqual(m.qread(ui+0x328),0);self.assertEqual(m.qread(ui+0x218),0)
        self.assertIn(('sight_active',old_sight,0),m.calls)
        array=m.alloc(0x40);m.iwrite(array+0x18,2);m.qwrite(array+0x20,main);m.qwrite(array+0x28,secondary);m.qwrite(tm+0x48,array)
        m.u.mem_write(status+0x23,b'\1');m.call('rebuild_player_ui',ui,pc,status)
        self.assertEqual(m.qread(ui+0x328),secondary)
        m.u.mem_write(status+0x23,b'\0');m.call('rebuild_player_ui',ui,pc,status)
        self.assertEqual(m.qread(ui+0x328),0)

    def test_vehicle_scope_does_not_change_battle_nation(self):
        m=self.m;ui,game,status,params=[m.object() for _ in range(4)]
        m.at(GAME+0x1931cfc,lambda:params);m.qwrite(ui+0x300,game);m.qwrite(game+0x118,status)
        m.global_q('player_status',status);m.global_q('vehicle_nation_owner',status);m.global_i('player_vehicle_nation',2)
        m.iwrite(params+0x5c,0);m.iwrite(status+0x64,0)
        sights=m.alloc(0x80);m.iwrite(sights+0x18,10);scopes=[m.object() for _ in range(10)]
        for i,obj in enumerate(scopes):m.qwrite(sights+0x20+i*8,obj)
        m.qwrite(ui+0x200,sights)
        def original():m.qwrite(ui+0x210,scopes[0])
        m.global_q('original_sight_type',m.stub(original));m.at(GAME+0x342de34,lambda:m.x(0));m.at(GAME+0x3431140,lambda:m.calls.append(('active_scope',m.x(0),m.x(1))))
        m.call('sight_type',ui,0,0)
        self.assertEqual(m.qread(ui+0x210),scopes[2])
        self.assertEqual(m.read(params+0x5c,4),b'\0'*4);self.assertEqual(m.read(status+0x64,4),b'\0'*4)
        self.assertIn(('active_scope',scopes[0],0),m.calls);self.assertIn(('active_scope',scopes[2],1),m.calls)
        m.iwrite(params+0x58,2);m.call('sight_type',ui,0,0)
        self.assertEqual(m.qread(ui+0x210),scopes[0]) # Online mode untouched.

    def test_scope_follows_live_world_gun_pose_and_leaves_air_view_alone(self):
        m=self.m;camera,pc,status,ui,turret,gun,transform,params=[m.object() for _ in range(8)]
        m.qwrite(status+0x68,m.string('T54_1949'));m.global_q('player_status',status);m.global_q('player_control',pc);m.global_i('state',3)
        m.at(GAME+0x1931cfc,lambda:params);m.at(GAME+0x3402abc,lambda:100)
        m.qwrite(pc+0x28,turret);m.qwrite(pc+0x30,gun);m.qwrite(camera+0x68,turret);m.qwrite(camera+0xe8,ui);m.qwrite(camera+0x20,transform)
        m.iwrite(ui+0x30,2);m.u.mem_write(camera+0x50,struct.pack('<f',100.));m.u.mem_write(camera+0x4c,struct.pack('<f',1.))
        pose=[0.1,0.2,0.3,0.92736185];seen=[]
        def get_rotation():
            for i,value in enumerate(pose):m.sf(i,value)
        m.at(GAME+0x343de40,get_rotation)
        setter=m.alloc(32);m.qwrite(setter,m.stub(lambda:seen.append(tuple(m.f(i) for i in range(4)))))
        m.global_q('class_method',m.stub(lambda:setter if m.read(m.x(1),32).split(b'\0')[0]==b'set_rotation' else 0))
        def original_late():
            value=struct.unpack('<f',m.read(camera+0xa8,4))[0]
            delta=sum(struct.unpack('<f',m.read(camera+o,4))[0] for o in [0xd4,0xdc])
            m.u.mem_write(camera+0xa8,struct.pack('<f',value-delta))
        m.global_q('original_camera_late_update',m.stub(original_late))
        for delta,expected in [(100.,-17.),(-100.,4.)]:
            m.u.mem_write(camera+0xd4,struct.pack('<f',delta));m.call('camera_late_update',camera,0)
            self.assertAlmostEqual(struct.unpack('<f',m.read(camera+0xa8,4))[0],expected)
        pose[:]=[-0.1,0.0,0.3,0.9486833];m.call('camera_late_update',camera,0)
        for got,want in zip(seen[-1],pose):self.assertAlmostEqual(got,want,places=6)
        count=len(seen);aircraft=m.object();m.qwrite(camera+0x68,aircraft);m.call('camera_late_update',camera,0)
        self.assertEqual(len(seen),count);self.assertEqual(m.qread(camera+0x68),aircraft)
        m.qwrite(camera+0x68,turret);m.iwrite(ui+0x30,3);m.call('camera_late_update',camera,0)
        self.assertEqual(len(seen),count)

    def test_tracks_use_visible_materials_even_without_suspension_cache(self):
        m=self.m;body,status,move,params,left,right,mat_left,mat_right=[m.object() for _ in range(8)]
        m.qwrite(status+0x68,m.string('T54_1949'));m.qwrite(body+0x38,status);m.qwrite(body+0x28,move)
        m.at(GAME+0x1931cfc,lambda:params)
        rends=m.alloc(0x40);m.iwrite(rends+0x18,2);m.qwrite(rends+0x20,left);m.qwrite(rends+0x28,right);m.qwrite(body+0x48,rends)
        # No suspension wheels/centers, no BodyMove.Start material cache.
        getter=m.alloc(32);setter=m.alloc(32);seen=[]
        m.qwrite(getter,m.stub(lambda:mat_left if m.x(0)==left else mat_right))
        m.qwrite(setter,m.stub(lambda:seen.append((m.x(0),m.f(0),m.f(1)))))
        def lookup():
            name=m.read(m.x(1),32).split(b'\0')[0]
            return getter if name==b'get_material' else setter if name==b'SetTextureOffsetImpl' else 0
        m.global_i('track_texture_property_ready',1);m.global_i('track_texture_property',37)
        m.global_q('class_method',m.stub(lookup));clock=[10.]
        m.at(GAME+0x343a6dc,lambda:m.sf(0,clock[0]));m.u.mem_write(move+0x78,struct.pack('<f',5.))
        m.call('body_update',body,0);clock[0]+=.02;m.call('body_update',body,0)
        self.assertEqual([x[0] for x in seen],[mat_left,mat_right]);self.assertTrue(all(x[2]>0 for x in seen))
        first=[x[2] for x in seen];seen.clear();m.u.mem_write(move+0x78,struct.pack('<f',-2.));clock[0]+=.02;m.call('body_update',body,0)
        self.assertTrue(all(x[2]<v for x,v in zip(seen,first)))
        seen.clear();m.u.mem_write(move+0x78,struct.pack('<f',0.));m.u.mem_write(move+0x84,struct.pack('<f',60.));clock[0]+=.02;m.call('body_update',body,0)
        self.assertNotEqual(seen[0][2],seen[1][2])

    def test_custom_names_armor_ammo_penetration_and_reload(self):
        if getattr(ARGS,'tank_configs',None):docs=json.loads(ARGS.tank_configs.read_text())
        else:
            root=Path(__file__).resolve().parents[1]/'tanks/T54_1949'
            docs=[{k:json.loads((root/(k+'.json')).read_text()) for k in ['manifest','tank','weapon','armor']}]
        for doc in docs:
            with self.subTest(tank=doc['manifest']['id']):
                m=self.m;s=m.object();name=m.string(doc['manifest']['id']);gun=m.string(doc['weapon']['name']);t=doc['tank'];w=doc['weapon'];a=doc['armor']
                m.qwrite(s+0x68,name);m.qwrite(s+0x70,gun)
                def array(n,size):
                    p=m.object(0x20+n*size);m.iwrite(p+0x18,n);return p
                body=array(16,4);turret=array(8,4);shells=array(5,16);mg=array(1,16)
                for offset,p in [(0x1b8,body),(0x1c0,turret),(0xf0,shells),(0xf8,mg)]:m.qwrite(s+offset,p)
                def original_enable():
                    m.qwrite(m.x(0)+0x68,m.string('T34_85'));m.qwrite(m.x(0)+0x70,m.string('S-53'))
                m.global_q('original_status_enable',m.stub(original_enable));m.global_q('original_status_start',m.stub(lambda:0))
                m.call('status_enable',s,0);m.call('status_start',s,0)
                self.assertEqual(m.qread(s+0x68),name);self.assertEqual(m.qread(s+0x70),gun)
                self.assertEqual(struct.unpack('<16i',m.read(body+0x20,64)),tuple([a['body']['front']]*4+[a['body']['side']]*8+[a['body']['rear']]*4))
                self.assertEqual(struct.unpack('<8i',m.read(turret+0x20,32)),tuple([a['turret']['front']]*2+[a['turret']['side']]*4+[a['turret']['rear']]*2))
                def plain(address):
                    _,hidden,key,_=struct.unpack('<4I',m.read(address,16));return ((hidden-key)&0xffffffff)^key
                self.assertEqual([plain(shells+0x20+i*16) for i in range(5)],[w['ammo'].get(k,0) for k in ['AP','HE','APCR','WP','HEAT']]);self.assertEqual(plain(mg+0x20),w['machineGun']['ammo'])
                self.assertEqual([plain(s+o) for o in [0x78,0xa8,0xdc,0x104,0x114,0x124]],[w['shells']['AP']['penetrationMm'],w['muzzleVelocity'],__import__('math').ceil(w['reload']),t['enginePower'],t['maxForwardSpeed'],t['turretRotation']])
                tier=struct.unpack('<Q',m.read(s+0x174,8))[0]
                raw=struct.pack('<Q',tier)
                self.assertEqual(((raw[4]-raw[5])&255)^raw[5],doc['manifest']['tier'])
                self.assertEqual(raw[6],doc['manifest']['tier'])  # Detector-enabled fake value is consistent.
                _,hidden,key,fake,_=struct.unpack('<5I',m.read(s+0x184,20))
                encrypted=bytearray(struct.pack('<I',hidden))
                encrypted[1],encrypted[2]=encrypted[2],encrypted[1]
                bits=struct.unpack('<I',encrypted)[0]^key
                acceleration=struct.unpack('<f',struct.pack('<I',bits))[0]
                self.assertAlmostEqual(acceleration,(t['enginePower']/t['weightTonnes'])*.5/17.8571434,places=6)
                self.assertEqual(fake,struct.unpack('<I',struct.pack('<f',acceleration))[0])
                launcher=m.object();info=m.object();owner=m.object();m.qwrite(s+0x260,owner);m.qwrite(launcher+0x38,s)
                m.u.mem_write(launcher+0x54,struct.pack('<f',w['muzzleVelocity']))
                def original_info():
                    ratio=1.1 if m.x(1)==2 else .95 if m.x(1) in (1,4) else 1.0
                    m.u.mem_write(info+0x18,struct.pack('<f',w['muzzleVelocity']*ratio));return info
                m.global_q('original_attack_info',m.stub(original_info))
                for shell,penetration in [(0,w['shells']['AP']['penetrationMm']),(4,w['shells']['HEAT']['penetrationMm']),(2,w['shells']['APCR']['penetrationMm'])]:
                    self.assertEqual(m.call('attack_info',launcher,shell,1,0),info)
                    self.assertEqual(struct.unpack('<i',m.read(info+0x1c,4))[0],penetration)
                    self.assertAlmostEqual(struct.unpack('<f',m.read(info+0x18,4))[0],w['muzzleVelocity']*(1.1 if shell==2 else .95 if shell==4 else 1.),places=3);self.assertEqual(m.qread(info+0x20),owner)
                controller=m.object();m.qwrite(controller+0x40,s);m.u.mem_write(controller+0x80,struct.pack('<f',1.5))
                observed=[]
                m.global_q('original_turret_update',m.stub(lambda:observed.append((struct.unpack('<f',m.read(controller+0x80,4))[0],m.read(controller+0xde,1)))))
                m.call('turret_update',controller,0)
                self.assertAlmostEqual(observed[0][0],w['reload']-__import__('math').ceil(w['reload']),places=5);self.assertEqual(observed[0][1],b'\1')
                self.assertEqual(m.read(controller+0x80,4),struct.pack('<f',1.5));self.assertEqual(m.read(controller+0xde,1),b'\0')

    def test_original_fire_routes_he_to_explosive_pool_and_heat_to_ap_pool(self):
        # Execute the real game's Fire branch and activation/attack binding.
        # Unity effects and component lookup are the mocked boundary here.
        m=self.m;entry=GAME+0x195b660
        m.u.mem_write(entry,m.game_read(0x195b660,0x840))
        launcher,status,ap,he,transform,shell,bomb,info=[m.object() for _ in range(8)]
        m.qwrite(launcher+0x38,status)
        for offset in [0x28,0x60,0x68]:m.qwrite(launcher+offset,m.object())
        for offset,go in [(0x78,ap),(0x80,he)]:
            array=m.alloc(0x30);m.iwrite(array+0x18,1);m.qwrite(array+0x20,go);m.qwrite(launcher+offset,array)
        cls=m.object();m.iwrite(cls+0xe4,1);cell=m.alloc(8);m.qwrite(cell,cls)
        m.qwrite(GAME+0x394ccc0,cell)
        literals={}
        for address in [0x394f040,0x3950950,0x39509a8]:
            value=m.alloc();cell=m.alloc(8);m.qwrite(cell,value);m.qwrite(GAME+address,cell);literals[address]=value
        m.u.mem_write(GAME+0x3bcc19c,b'\1')
        for address in [0x33ebe10,0x33ec048,0x34954a0,0x3496288,0x3495120]:m.at(GAME+address,lambda:0)
        m.at(GAME+0x3494ef4,lambda:1);m.at(GAME+0x1980194,lambda:2)
        m.at(GAME+0x342e704,lambda:0);m.at(GAME+0x3430c74,lambda:int(m.x(0)!=m.x(1)))
        m.at(GAME+0x343294c,lambda:int(m.x(0)==m.x(1)))
        m.at(GAME+0x3431204,lambda:0);m.at(GAME+0x3430ef8,lambda:transform)
        m.at(GAME+0x343f6e0,lambda:0);m.at(GAME+0x197640c,lambda:0)
        active=[];types=[]
        m.at(GAME+0x3431140,lambda:active.append(m.x(0)))
        m.at(GAME+0x1d4afe8,lambda:bomb if m.x(1)==literals[0x394f040] else shell)
        m.at(GAME+0x195c6ec,lambda:types.append(m.x(1)) or info)
        def unexpected():raise AssertionError('Original Fire hit an error path')
        for address in [0x17cacbc,0x17cacc4,0x33f9b98]:m.at(GAME+address,unexpected)
        for kind,go in [(0,ap),(2,ap),(1,he),(4,ap),(1,he),(4,ap)]:
            active.clear();types.clear();m.qwrite(shell+0x90,0);m.qwrite(bomb+0x88,0)
            m.call(entry,launcher,kind,1,0)
            self.assertEqual(active,[go]);self.assertEqual(m.qread(shell+0x90),info)
            self.assertEqual(types,[kind,1] if kind==1 else [kind])
            self.assertEqual(m.qread(bomb+0x88),info if kind==1 else 0)

    def test_offline_launch_scope_preserves_other_keys_and_network_checks(self):
        m=self.m;params=m.object();m.at(GAME+0x1931cfc,lambda:params)
        m.global_q('original_product_check',m.stub(lambda:1));m.global_q('original_load_flag',m.stub(lambda:42));m.global_q('original_hnz_check',m.stub(lambda:1));m.global_q('original_iap_sanity',m.stub(lambda:1))
        cls=m.alloc();static=m.alloc();key=m.string('anomaly');cell=m.alloc(8);m.qwrite(cell,cls);m.qwrite(cls+0xb8,static);m.qwrite(static,key);m.qwrite(GAME+0x394f778,cell);m.at(GAME+0x17caa40,lambda:0)
        self.assertEqual(m.call('product_check',params,0),1)
        m.global_i('offline_title_scope',1)
        self.assertEqual(m.call('product_check',params,0),0)
        self.assertEqual(m.call('load_flag',m.string('anomaly'),0),0)
        self.assertEqual(m.call('load_flag',m.string('currency'),0),42)
        self.assertEqual(m.call('hnz_check',0),0)
        self.assertEqual(m.call('iap_sanity',m.object(),0),0)
        m.iwrite(params+0x58,2)
        self.assertEqual(m.call('product_check',params,0),1)
        self.assertEqual(m.call('load_flag',key,0),42)
        self.assertEqual(m.call('hnz_check',0),1)
        self.assertEqual(m.call('iap_sanity',m.object(),0),1)

    def test_all_new_hook_prologues_can_be_relocated(self):
        m=self.m
        profile=json.loads((Path(__file__).resolve().parents[1]/'profiles/attack-on-tank-5.1.0.json').read_text())
        for name in ['TITLE_START','IS_PRODUCT','LOAD_FLAG','IS_HNZ2','IAP_SANITY','STATUS_ENABLE','STATUS_START','BODY_UPDATE','ATTACK_INFO','TURRET_UPDATE','LAUNCHER_FIRE','SHELL_FIXED_UPDATE','CAMERA_LATE_UPDATE','UI_SIGHT']:
            rva=int(profile['native_macros']['RVA_'+name],16);m.u.mem_write(GAME+rva,m.game_read(rva,16))
            with self.subTest(name=name):self.assertEqual(m.call('install',rva,m.stub(lambda:0),m.alloc(8)),1)

    def test_original_factory_rejects_type_object_and_selects_all_player_nations(self):
        m=self.m;params=m.object();gen=m.object();new_go=m.object()
        tag=m.original_factory(params,new_go)
        m.qwrite(GAME+0x3a94b20,tag)
        prefabs=[]
        for offset in [0x28,0x30,0x40,0x48,0x50,0x58]:
            a=m.alloc(0x30);m.iwrite(a+0x18,1);prefab=m.object()
            m.qwrite(a+0x20,prefab);m.qwrite(gen+offset,a);prefabs.append(prefab)
        for i,v in enumerate([11.,22.,33.,0.,0.,0.,1.]):m.sf(i,v)
        # Reproduce the released version's System.Type argument: the original
        # factory must reject it and never reach Unity's Instantiate boundary.
        self.assertEqual(m.call(GAME+0x1994a88,gen,m.alloc(),0,0,0,0),0)
        self.assertEqual([c for c in m.calls if c[0]=='instantiate'],[])
        # Equal strings at different addresses also exercise the real length
        # and UTF-16 comparison path, not only the pointer-equality fast path.
        cloned_tag=m.string('Player')
        for nation,prefab in enumerate(prefabs):
            for i,v in enumerate([11.,22.,33.,0.,0.,0.,1.]):m.sf(i,v)
            self.assertEqual(m.call(GAME+0x1994a88,gen,cloned_tag,nation,0,0,0),new_go)
            self.assertEqual(m.calls[-1],('instantiate',prefab,[11.,22.,33.,0.,0.,0.,1.]))
        before=len([c for c in m.calls if c[0]=='instantiate'])
        self.assertEqual(m.call(GAME+0x1994a88,gen,tag,0,1,0,0),0)
        self.assertEqual(len([c for c in m.calls if c[0]=='instantiate']),before)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tank-configs',type=Path);p.add_argument('--module',required=True);p.add_argument('--game-library',required=True);p.add_argument('--report',type=Path)
    ARGS, remaining=p.parse_known_args()
    program=unittest.main(argv=['test_native']+remaining,verbosity=2,exit=False)
    result=program.result
    if ARGS.report:
        ARGS.report.write_text(json.dumps({'runner':'Unicorn ARM64','tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
            'module_sha256':hashlib.sha256(Path(ARGS.module).read_bytes()).hexdigest(),
            'game_library_sha256':hashlib.sha256(Path(ARGS.game_library).read_bytes()).hexdigest()},indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)


