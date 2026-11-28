"""Stage a playable Hatch, native player/AI prefab and cumulative catalog; never writes an APK."""
import argparse, hashlib, json, zipfile
from pathlib import Path
from hatch.pack import pack_project
from ..barbarossa.mission.release import Members, dumps, digest
from ..barbarossa.mission.refit import context, verify_plates
from ..barbarossa.bundle import append_members, metadata
from ..bt7.integrate import reg, reg_object, one_file
from ..enemy_prefabs import create
from ..enemy_visuals import read_model
from ..enemy_verify import verify
from ..enemy_assets import script_class
from ..extra_campaign import file
from ..serialization import parse_complete, apply_reviewed_typetrees
from ..unity_assets import read_mb, pp
from .source import ID

def inspect(a,sf,e,player):
    coll = {}
    for p,o in sf.objects.items():
        if o.type.name=='MonoBehaviour':
            cls = script_class(a, o)
            coll.setdefault(cls, []).append(p)
    def mb(k):
        p, = coll[k]
        return (p, read_mb(k, sf.objects[p].get_raw_data()))
    def tr(p):
        return parse_complete(sf.objects[p])
    def refs(l):
        return [x['m_PathID'] for x in l]
    root = tr(e['root_path_id'])
    roottr = next((o['component']['m_PathID'] for o in root['m_Component'] if sf.objects[o['component']['m_PathID']].type.name == 'Transform'))
    ct = e['model_control_path_ids']
    st, u = mb('UnitStatus')
    lp, launch = mb('Launcher')
    _, bm = mb('BodyMove')
    _, tm = mb('TurretMove')
    assert len(coll.get('PlayerControl', [])) == int(player) and len(coll.get('AIControl', [])) == int(not player)
    assert root['m_Name'] == e['prefab'] and u['unitName'] == ID and (u['iFFNum'] == (0 if player else 2))
    assert launch['uStatus'] == pp(st) and launch['weaponName'] == '' and (u['mainGunName'] == e['gameplay']['weapon']['name'])
    assert launch['initSpeed'] == e['gameplay']['weapon']['muzzleVelocity'] and all((launch[k] for k in ['shellApGos', 'shellHeGos']))
    assert tr(ct['yaw'])['m_Father'] == pp(roottr if player else ct['hull']) and tr(ct['pitch'])['m_Father'] == pp(ct['yaw'])
    assert tr(launch['thisTrf']['m_PathID'])['m_Father'] == pp(ct['pitch']) and launch['barrelTrf'] == pp(ct['recoil'])
    assert tm['thisTrf'] == pp(ct['yaw']) and tm['gunTrfs'] == [pp(ct['pitch'])]
    assert len(set(refs(bm['largeWheelLodTrfs']))) == 12 and len(set(refs(bm['smallWheelLodTrfs']))) == 10 and (len(set(refs(bm['scrollLodRends']))) == 2)
    return dict(
        controller='PlayerControl' if player else 'AIControl',
        root=root['m_Name'],
        roadWheels=12,
        otherWheels=10,
        tracks=2,
        suspensionContacts=len(bm['susWheelTrfs']),
        mainShellPool=len(launch['shellApGos']),
        heShellPool=len(launch['shellHeGos']),
        primaryLauncher=True,
        cameraTurretAtRoot=bool(player)
    )

def stage(apk,index,project,out):
    game = out / 'assets'
    hatch = game / 'Hatch'
    data = game / 'bin/Data'
    aiout = out / 'AI'
    aiout.mkdir(parents=True, exist_ok=True)
    work = out / 'prefabs'
    work.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    name = ID + '.hatch'
    unit = hatch / 'mods' / name
    info = pack_project(project, unit)
    print('Compiled', name, flush=True)
    with zipfile.ZipFile(apk) as z:
        base = z.read('assets/bin/Data/data.unity3d')
        catalog = json.loads(z.read('assets/Hatch/catalog.json'))
    idx = json.loads(index.read_text())
    beforeMods = list(catalog['mods'])
    beforePrefabs = list(idx['prefabs'])
    assert ID not in {m['id'] for m in beforeMods + beforePrefabs}
    pack = Members(base)
    a, named, names = context(pack)
    print('Read original stock dependencies', flush=True)
    donor = 'Panzer_III_J_Player'
    named[donor], = [p for p, o in a.sf.objects.items() if o.type.name == 'GameObject' and parse_complete(o)['m_Name'] == donor]
    mgr = pack.read('globalgamemanagers')
    origmgr = one_file(mgr)
    origregs = dict(parse_complete(reg_object(origmgr))['m_Container'])
    files = {}
    binds = {}
    checks = {}
    models = {}
    with zipfile.ZipFile(unit) as m:
        h = json.loads(m.read('hatch.json'))
        _, ns, ims = read_model(m.read('runtime.bin'), h)
        for player in [False,True]:
            kind = 'player' if player else 'ai'
            e = create(a, named, m, work, player=player)
            fn = e['file']
            binary = (work / fn).read_bytes()
            sf = file(binary)
            print('Created', fn, flush=True)
            checks[kind] = inspect(a, sf, e, player)
            if not player:
                e['validation'] = verify(a, work / fn, e, (ns, ims, h))
            k = 'unit/ge/' + ID.lower() + '/' + ID.lower()
            e['resource_path'] = k + '_' + kind
            e['profile_resource_path'] = k + ('_player_profile' if player else '_profile')
            mgr, binds[kind] = reg(a, mgr, work / fn, e)
            files[fn] = binary
            models[kind] = e
            if not player:
                idx['prefabs'].append(e)
    idx['use'] = f"All {len(idx['prefabs'])} AI roots and profiles are registered in Unity Resources."
    catalog['mods'].append(dict(
        id=ID,
        name=info['name'],
        sha256=digest(unit.read_bytes()),
        size=unit.stat().st_size
    ))
    (hatch / 'catalog.json').write_bytes(dumps(catalog))
    (aiout / 'Hatch-Enemy-AI-index.json').write_bytes(dumps(idx))
    changes = [('globalgamemanagers', mgr), *files.items()]
    result = append_members(base, changes, {n: 'resources.assets' for n in files})
    print('Registered both prefabs and wrote additive Unity data', flush=True)
    final = Members(result)
    _, start, end, _, _ = metadata(base)
    assert final.members.keys() == pack.members.keys() | files.keys()
    assert all((final.members[n] == pack.members[n] for n in pack.members if n != 'globalgamemanagers'))
    assert result[start:end] == base[start:end] and all((final.read(n) == b for n, b in changes))
    finalmanager = one_file(final.read('globalgamemanagers'))
    keys = dict(parse_complete(reg_object(finalmanager))['m_Container'])
    assert {k: keys[k] for k in origregs} == origregs and len(keys) == len(origregs) + 4
    for e in models.values():
        for key,id_key in [('resource_path','root_path_id'),('profile_resource_path','profile_path_id')]:
            ptr = keys[e[key]]
            assert finalmanager.externals[ptr['m_FileID'] - 1].path == e['file'] and ptr['m_PathID'] == e[id_key]
    assert idx['prefabs'][:-1] == beforePrefabs and catalog['mods'][:-1] == beforeMods
    label = verify_plates(result, {'prefabs': [models['ai']]}, names)[ID]
    (data / 'data.unity3d').write_bytes(result)
    delta = result[:start] + result[end:]
    (out / 'PanzerIII-F-Resources.overlay').write_bytes(delta)
    assert delta[:start] + base[start:end] + delta[start:] == result
    rec = dict(
        format=1,
        vehicle=ID,
        baseResourceSha256=digest(base),
        resultResourceSha256=digest(result),
        overlaySha256=digest(delta),
        headerBytes=start,
        retainStart=start,
        retainEnd=end,
        vehicleFile=name,
        vehicleSha256=digest(unit.read_bytes()),
        runtimeSha256=info['runtime_sha256'],
        catalog=catalog,
        aiIndex=idx,
        player=models['player'],
        assetValidation=checks,
        nameplate=label,
        registration=binds,
        oldResourceKeys=len(origregs),
        unchangedGameMembers=len(pack.members) - 1,
        nativeGameSessionTest=False
    )
    (out / 'PanzerIII-F-Integration.json').write_bytes(dumps(rec))
    print(json.dumps(dict(
        checks=checks,
        label=label,
        assets=len(final.members),
        mods=len(catalog['mods']),
        ai=len(idx['prefabs'])
    ), indent=2))
if __name__=='__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for n in ['apk','index','project','out']:
        ap.add_argument('--' + n, type=Path, required=True)
    stage(**vars(ap.parse_args()))
