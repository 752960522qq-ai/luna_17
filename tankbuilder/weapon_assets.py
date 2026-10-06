"""Preserve inherited weapon subtrees and supply missing projectile pools."""
import struct
from .serialization import assert_roundtrip as serialized_roundtrip, encode_complete

def assert_roundtrip(obj, raw=None):
    # UnityPy ObjectReader.get_raw_data reads the original serialized bytes;
    # set_raw_data stores edits in .data. Subsequent appends must see edits,
    # otherwise the second child silently replaces the first one.
    if raw is None: raw = obj.data or obj.get_raw_data()
    return serialized_roundtrip(obj, raw)

def store(obj, tree):
    assert_roundtrip(obj)
    raw = encode_complete(obj, tree)
    assert_roundtrip(obj, raw)
    obj.set_raw_data(raw)

def clone_he_pool(adapter, launcher, parent, prefix="Hatch_HE_Pool"):
    from .unity_assets import pp, xyz, read_mb, write_mb, remap
    """Clone complete stock ShellMove/BombMove pools, including effects.

    132149 is the reviewed 85 mm HE launcher with two Shell_90mm_HE
    objects. Launcher's original Fire supplies attack info and ownership.
    """
    sf = adapter.sf
    source = read_mb('Launcher', sf.objects[132149].get_raw_data())
    if source['calibre'] != 85 or len(source['shellHeGos']) != 2: raise ValueError('HE donor layout changed')
    result = []
    for number, reference in enumerate(source['shellHeGos']):
        objects = []
        def visit(goid):
            go = sf.objects[goid]; tree = assert_roundtrip(go)
            objects.append(go)
            parts = [sf.objects[c['component']['m_PathID']] for c in tree['m_Component']]
            objects.extend(parts)
            tr = next(o for o in parts if o.type.name == 'Transform')
            for p in assert_roundtrip(tr)['m_Children']:
                visit(assert_roundtrip(sf.objects[p['m_PathID']])['m_GameObject']['m_PathID'])
        visit(reference['m_PathID'])
        ids = {o.path_id: adapter.new(o).path_id for o in objects}
        for old in objects:
            new = sf.objects[ids[old.path_id]]
            if old.type.name == 'MonoBehaviour':
                raw = bytearray(old.get_raw_data())
                # Complete donor components, exact local PPtr substitutions.
                for offset in range(0, len(raw)-11, 4):
                    fid, pid = struct.unpack_from('<iq', raw, offset)
                    if fid == 0 and pid in ids: struct.pack_into('<q', raw, offset+4, ids[pid])
                new.set_raw_data(bytes(raw))
            else: store(new, remap(assert_roundtrip(old), ids))
        root = sf.objects[ids[reference['m_PathID']]]
        gt = assert_roundtrip(root); gt['m_Name'] = prefix+'_'+str(number); gt['m_IsActive'] = False; store(root, gt)
        tr = adapter.transform(root); tree = assert_roundtrip(tr)
        tree['m_Father'] = pp(parent.path_id); tree['m_LocalPosition'] = xyz([0,0,0]); store(tr, tree)
        pt = assert_roundtrip(parent); pt['m_Children'].append(pp(tr.path_id)); store(parent, pt)
        result.append(pp(root.path_id))
    values = read_mb('Launcher', launcher.get_raw_data()); values['shellHeGos'] = result
    write_mb(launcher, 'Launcher', values)
    return result

def weapon_nodes(adapter, nodes):
    roots = []
    for go, parts in nodes:
        for part in parts:
            if part.type.name != 'MonoBehaviour':
                continue
            script = part.read_typetree(check_read=False)['m_Script']
            file = adapter.sf if script['m_FileID'] == 0 else adapter.files[
                adapter.sf.externals[script['m_FileID'] - 1].path.rsplit('/', 1)[-1]]
            kind = adapter.scripts.get((file.name, script['m_PathID']))
            if kind == 'Launcher':
                roots.append(go.path_id)
            elif kind == 'MachineGun':
                transform = adapter.transform(go).read_typetree(check_read=False)
                parent = adapter.sf.objects[transform['m_Father']['m_PathID']]
                roots.append(parent.read_typetree(check_read=False)['m_GameObject']['m_PathID'])
    protected = set()
    def visit(goid):
        if goid in protected:
            return
        protected.add(goid)
        transform = adapter.transform(adapter.sf.objects[goid])
        for child in transform.read_typetree(check_read=False)['m_Children']:
            obj = adapter.sf.objects[child['m_PathID']]
            visit(obj.read_typetree(check_read=False)['m_GameObject']['m_PathID'])
    for root in roots:
        visit(root)
    return protected
