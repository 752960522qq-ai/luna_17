"""Execute the production ARM64 spawn path and original AI prefab factory.

Camera/physics calls are bounded test doubles, not an Android scene trial.
"""
import argparse, json, math, struct, unittest
from pathlib import Path
from test_native import Machine, GAME

class EnemySpawnTests(unittest.TestCase):
    def machine(self):
        m=Machine(ARGS.module,ARGS.game_library)
        for name, fn in [('sqrtf',math.sqrt),('sinf',math.sin),('cosf',math.cos)]:
            if name in m.imports:
                m.at(m.imports[name],lambda fn=fn: m.sf(0,fn(m.f(0))))
        if 'atan2f' in m.imports:m.at(m.imports['atan2f'],lambda:m.sf(0,math.atan2(m.f(0),m.f(1))))
        return m

    def target(self, hits):
        m=self.machine();game=m.object();control=m.object();camera=m.object();m.qwrite(game+0x20,control);m.qwrite(control+0x28,camera)
        screen,physics,hitclass=[m.alloc() for _ in range(3)]
        m.global_i('hatch_engine_ok',1)
        assemblies=m.alloc(8);m.qwrite(assemblies,m.alloc())
        m.global_q('ha_domain',m.stub(lambda:1))
        def assembly_list():m.qwrite(m.x(1),1);return assemblies
        m.global_q('ha_assemblies',m.stub(assembly_list));m.global_q('ha_image',m.stub(lambda:1))
        m.global_q('ha_class',m.stub(lambda:{'Screen':screen,'Physics':physics,'RaycastHit':hitclass}.get(m.c_string(m.x(2)),0)))
        def klass():
            return {'Screen':screen,'Physics':physics,'RaycastHit':hitclass}.get(m.c_string(m.x(1)),0)
        m.at(m.symbols['hatch_class'],klass)
        methods={name:m.alloc(96) for name in ['get_width','get_height','ScreenPointToRay','Raycast','get_collider']}
        current=[0];own=m.object();ground=m.object();calls=[]
        m.qwrite(methods['get_collider'],m.stub(lambda:own if current[0]==1 else ground))
        m.global_q('class_method',m.stub(lambda:methods.get(m.c_string(m.x(1)),0)))
        m.at(m.symbols['enemy_own_collider'],lambda:int(m.x(0)==own))
        def box(data):
            b=m.alloc(16+len(data));m.u.mem_write(b+16,data);return b
        def invoke():
            met,obj,args=m.x(0),m.x(1),m.x(2)
            if met==methods['get_width']:return box(struct.pack('<i',1920))
            if met==methods['get_height']:return box(struct.pack('<i',1080))
            if met==methods['ScreenPointToRay']:
                self.assertEqual(struct.unpack('<3f',m.read(m.qread(args),12)),(960.,540.,0.))
                return box(struct.pack('<6f',0,3,0,0,-.6,.8))
            self.assertEqual(met,methods['Raycast']);q=[m.qread(args+i*8) for i in range(6)]
            self.assertEqual(struct.unpack('<i',m.read(q[4],4))[0],-5);self.assertEqual(m.qread(q[5])&0xffffffff,1)
            origin=struct.unpack('<3f',m.read(q[0],12));calls.append(origin)
            if not hits:return box(b'\0')
            kind=hits.pop(0)
            if kind=='miss':return box(b'\0')
            current[0]=1 if kind=='self' else 2
            normal_y=0 if kind=='wall' else 1
            m.u.mem_write(q[2],struct.pack('<6fIf2fi',10,0,20,0,normal_y,0,0,5,0,0,current[0]))
            return box(b'\1')
        m.global_q('ha_invoke',m.stub(invoke));point=m.alloc(12);direction=m.alloc(12)
        value=m.call('enemy_target_point',game,point,direction)
        return value,m,point,calls

    def test_center_ray_hits_ground(self):
        value,m,p,calls=self.target(['ground']);self.assertEqual(value,1);self.assertEqual(struct.unpack('<3f',m.read(p,12)),(10.,0.,20.));self.assertEqual(len(calls),1)
    def test_camera_ray_skips_player_collider(self):
        value,m,p,calls=self.target(['self','ground']);self.assertEqual(value,1);self.assertEqual(len(calls),2);self.assertNotEqual(calls[0],calls[1])
    def test_sky_does_not_supply_spawn_position(self):self.assertEqual(self.target(['miss'])[0]&0xffffffff,0xfffffffd)
    def test_wall_is_rejected(self):self.assertEqual(self.target(['wall'])[0]&0xffffffff,0xfffffffc)

    def test_original_ai_factory_all_six_countries_and_enemy_identity(self):
        for nation in range(6):
            with self.subTest(nation=nation):
                m=self.machine();game=m.object();gen=m.object();params=m.object();prefab=m.object();old=m.object();new=m.object();ps=m.object();ns=m.object();array=m.object(64)
                m.qwrite(game+0x48,gen);m.qwrite(game+0x110,old);m.iwrite(params+0x5c,nation);m.iwrite(array+24,1);m.qwrite(array+32,prefab);m.qwrite(gen+0x60+nation*8,array)
                m.iwrite(m.symbols['enemy_count']+nation*4,1);m.qwrite(m.symbols['enemy_source']+nation*8,array);m.global_i('state',3);m.u.mem_write(ps+0x20,b'\1')
                m.original_factory(params,new);ai=m.string('AI');m.global_q('ha_string',m.stub(lambda:ai))
                m.at(m.symbols['enemy_status'],lambda:ps if m.x(0)==prefab else ns)
                def point():
                    m.u.mem_write(m.x(1),struct.pack('<3f',11,0,22));m.u.mem_write(m.x(2),struct.pack('<3f',0,0,1));return 1
                m.at(m.symbols['enemy_target_point'],point)
                def instantiate():
                    self.assertEqual(m.x(0),prefab);self.assertEqual(m.read(ps+0x20,1),b'\2');self.assertAlmostEqual(m.f(0),11);self.assertAlmostEqual(m.f(1),.15,places=5);self.assertAlmostEqual(m.f(2),22);m.calls.append(('enemy-instantiated',nation));return new
                m.at(GAME+0x1d7f94c,instantiate);m.call('spawn_enemy',game,nation<<16)
                self.assertEqual(m.read(ps+0x20,1),b'\1');self.assertEqual(m.read(ns+0x20,1),b'\2');self.assertEqual(m.read(ns+0x202,1),b'\0');self.assertEqual(m.qread(game+0x110),old);self.assertEqual(m.read(params+0x5c,4),struct.pack('<i',nation));self.assertEqual(m.qread(m.symbols['player_control']),0);self.assertEqual(m.read(m.symbols['enemy_result'],4),struct.pack('<i',1))

    def test_online_and_busy_requests_are_rejected(self):
        m=self.machine();m.global_i('ready',1);m.global_i('state',4);m.iwrite(m.symbols['enemy_count'],1)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_spawnEnemy',0,0,0,0),0)

        m.global_i('state',3);m.global_q('last_update_ms',100000);m.global_i('pending',0)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_spawnEnemy',0,0,0,0),0)
        m.global_i('pending',-1);self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_spawnEnemy',0,0,0,0),1)
        self.assertEqual(m.call('Java_com_luna17_aot_NativeBridge_spawnEnemy',0,0,0,0),0)

    def lifecycle(self):
        m=self.machine();game=m.object();params=m.object()
        m.global_i('ready',1);m.global_q('original_game_update',m.stub(lambda:0))
        m.at(GAME+0x1931cfc,lambda:params)
        return m,game,params

    def test_completed_result_survives_later_nonbattle_frames(self):
        for result in (1,-2,-3,-4,-5,-7,-8):
            with self.subTest(result=result):
                m,game,params=self.lifecycle();m.global_i('enemy_pending',-1);m.global_i('enemy_result',result)
                for _ in range(3):m.call('game_update',game,0)
                self.assertEqual(m.read(m.symbols['enemy_result'],4),struct.pack('<i',result))

    def test_leaving_battle_cancels_only_pending_request(self):
        m,game,params=self.lifecycle();m.global_i('enemy_pending',0);m.global_i('enemy_result',0)
        m.call('game_update',game,0)
        self.assertEqual(m.read(m.symbols['enemy_pending'],4),struct.pack('<i',-1))
        self.assertEqual(m.read(m.symbols['enemy_result'],4),struct.pack('<i',-6))

    def test_request_waits_for_swap_then_runs_once(self):
        m,game,params=self.lifecycle();status=m.object();m.qwrite(game+0x118,status)
        m.global_i('pending',-1);m.global_i('enemy_pending',0);m.global_i('enemy_result',0)
        m.qwrite(m.symbols['swap']+32,m.object())
        m.at(m.symbols['advance_swap'],lambda:0)
        calls=[]
        m.at(m.symbols['spawn_enemy'],lambda:calls.append(m.x(1)))
        m.call('game_update',game,0)
        self.assertEqual(calls,[]);self.assertEqual(m.qread(m.symbols['enemy_pending'])&0xffffffff,0)
        m.qwrite(m.symbols['swap']+32,0)
        m.call('game_update',game,0);m.call('game_update',game,0)
        self.assertEqual(calls,[0])

    def test_original_friend_getter_treats_explicit_iff_two_as_enemy(self):
        m=self.machine();address=GAME+0x1975cd0
        m.u.mem_write(address,m.game_read(0x1975cd0,0xa0));m.u.mem_write(GAME+0x3bcc1f2,b'\1')
        status=m.object();m.u.mem_write(status+0x20,b'\2')
        self.assertEqual(m.call(address,status,0),0)
        m.u.mem_write(status+0x20,b'\1');self.assertEqual(m.call(address,status,0),1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--module',required=True);parser.add_argument('--game-library',required=True);parser.add_argument('--report',type=Path);ARGS,rest=parser.parse_known_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EnemySpawnTests))
    if ARGS.report:ARGS.report.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),android_device_test='not performed'),indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
