"""Reconstruct the user-supplied Ausf.F printing model in metre-scale Hatch coordinates."""
import hashlib, io, zipfile
from pathlib import Path
import numpy as np
from ..bt7.forms import unit
from ..panzer4c.source import primitive

ID = 'Panzer_III_Ausf_F'
INNER = '6879aff3c613b3dabcac40568ddf1135740c83a5b9687239c94c3fe16e399375'
CREDIT={"title":"Panzer III Pack REVISED · PZ3_AusfF", "author":"TigerAce1945",
        "source":"https://cults3d.com/en/3d-model/game/panzer-iii-pack-revised",
        "mirror":"https://pinshape.com/items/37871","use":"User-supplied source, private project adaptation; no grant of redistribution.",
        "adaptation":"Separated print shell and running gear, removed print peg, manufactured two animated track strips, painted and rigged."}
SCALE = np.array([
    2.91 / (114.76724243 - 85.23275757),
    5.38 / (126.7100067 - 73.2899933),
    2.44 / (15.83 + 0.03 + 16.6119404 - 7.191 - 0.0161702)
])
# Centrelines measured by circle fitting the cylindrical STL facets, not estimated from the bounding box.
ROOF = np.array([100.02, 97.4, 15.86])
PEG = np.array([97.351, 134.432, 7.191])
AXLES = [(
    f'{i + 1:02}',
    'road',
    y,
    3.416,
    2.5
) for i, y in enumerate([86.2, 91.709, 97.2, 102.799, 108.556, 114.217])]
AXLES += [('drive', 'drive', 78.49, 7.28, 3.72), ('idler', 'idler', 120.4, 7.45, 3.74)]
AXLES += [(
    f'return_{i + 1}',
    'return',
    y,
    z,
    1.43
) for i, (y, z) in enumerate([(89.15, 10.03), (99.76, 10.27), (110.15, 10.47)])]

def read(src):
    with zipfile.ZipFile(src) as z:
        inner = z.read(next((n for n in z.namelist() if n.endswith('/PZ3_AusfF.zip'))))
    if hashlib.sha256(inner).hexdigest()!=INNER:
        raise ValueError('Different Ausf.F source; re-audit its split planes.')
    def decode(b):
        n = int.from_bytes(b[80:84], 'little')
        assert len(b) == 84 + 50 * n
        return np.frombuffer(b[84:], dtype=[
            ('normal', '<f4', (3,)),
            ('v', '<f4', (3, 3)),
            ('tag', '<u2')
        ])['v'].astype(float)
    with zipfile.ZipFile(io.BytesIO(inner)) as z:
        return tuple((decode(z.read('PZ3_AusfF/' + n)) for n in ('pz3f_hull_revise.stl', 'pz3f_turret.stl')))

def B(v):
    return ((np.asarray(v) - [100, 100, 0.0161702]) * SCALE)[..., [0, 2, 1]] * [-1, 1, 1]
def T(v):
    return B(np.asarray(v) - PEG + ROOF)
def parts(tri,key):
    if not len(tri):
        return []
    n = unit(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]))
    ax = np.argmax(abs(n), axis=1)
    uv = np.zeros((len(tri), 3, 2))
    for j,pair in enumerate(([2,1],[0,2],[0,1])):
        m = ax == j
        uv[m] = tri[m][:, :, pair] / 1.12
    a = primitive(tri, np.broadcast_to(n[:, None, :], tri.shape), uv, key)
    return [a] if a is not None else []

def rings(sections, center, axis='x', count=72):
    a = np.linspace(0, 2 * np.pi, count, endpoint=False)
    c = np.cos(a)
    s = np.sin(a)
    lines = []
    for axial,r in sections:
        v = np.column_stack((
            a * 0 + axial,
            r * c,
            r * s
        )) if axis == 'x' else np.column_stack((r * c, r * s, a * 0 + axial))
        lines.append(v + center)
    out = []
    for A,D in zip(lines,lines[1:]):
        E = np.roll(D, -1, axis=0)
        F = np.roll(A, -1, axis=0)
        out.extend([np.stack([A, D, E], axis=1), np.stack([A, E, F], axis=1)])
    return np.concatenate(out)

def fixed(h):
    c = h.mean(1)
    y = c[:, 1]
    z = c[:, 2]
    outside = abs(c[:, 0] - 100) > 9.54
    roof=np.interp(y,[72.5,74.4,76.8,79,89.15,99.76,110.15,119.9,122.5,125.2,127],
                     [8.0,10.4,11.42,12.00,12.26,12.52,12.68,12.15,11.82,9.95,9.5])
    keep = ~outside | (z > roof)
    # Exclude the inside faces of the welded print belts exactly on the hull sidewall.
    sideplane = (abs(abs(c[:, 0] - 100) - 9.59) < 0.055) & (z < roof) & (np.ptp(h[:, :, 0], axis=1) < 0.16)
    fixed = h[keep & ~sideplane]
    fc = fixed.mean(1)
    key = np.full(len(fixed), 'panzer_grau', object)
    key[(fc[:, 1] > 118) & (fc[:, 2] < 8.7) & (abs(fc[:, 0] - 100) < 7.1)] = 'exhaust'
    key[(abs(fc[:, 0] - 100) > 11.6) & (fc[:, 1] > 101) & (fc[:, 2] > 14.95)] = 'steel'
    ps = []
    for k in np.unique(key):
        ps += parts(B(fixed[key == k]), k)
    # The print fused both track sidewalls to the lower hull. Close that hidden cut with
    # a separate depth-correct hull side, so it cannot rotate with a wheel.
    for s in [-1,1]:
        yz = [
            (74.3, 8.85),
            (77.1, 5.8),
            (84.9, 3.88),
            (114.8, 3.88),
            (122.9, 6.32),
            (125.3, 10.12),
            (121.8, 12.65),
            (84.6, 12.68),
            (77, 11.38)
        ]
        v = np.array([[100 + s * 9.52, y, z] for y, z in yz])
        tri = np.array([[v[0], v[i], v[i + 1]] for i in range(1, len(v) - 1)])
        if np.cross(tri[0,1]-tri[0,0],tri[0,2]-tri[0,0])[0]*s<0:
            tri = tri[:, [0, 2, 1]]
        ps += parts(B(tri), 'panels')
    return (ps, B(fixed))

def wheel(h,sgn,y,z,r,kind):
    # Retain the embossed original wheel faces, hub bolts, and sprocket/idler spokes.
    # A closed turned core backs the print-only junction with the original rigid tread.
    c = h.mean(1)
    rad = np.linalg.norm(h[:, :, [1, 2]] - [y, z], axis=2)
    xa = (h[:, :, 0] - 100) * sgn
    mask = (xa.mean(1) > 10.05) & (xa.max(1) < 13.98) & (rad.max(1) < r + 0.15) & (rad.mean(1) < r + 0.055)
    w = h[mask]
    wc = w.mean(1)
    dist = np.linalg.norm(wc[:, 1:] - [y, z], axis=1)
    rub = dist > r * 0.87 if kind in ('road', 'return') else dist > 100000.0
    ps = parts(B(w[~rub]), 'running_gear') + parts(B(w[rub]), 'rubber')
    # The neutral backing sits behind the original outer face on both sides.
    center = B([100 + sgn * 11.83, y, z])
    R = r * SCALE[2]
    inner = -0.197
    outer = 0.108 if kind == 'road' else 0.093
    xsg = -sgn
    sections = [
        (outer, 0),
        (outer, R * 0.86),
        (outer - 0.008, R * 0.98),
        (outer - 0.018, R),
        (inner + 0.014, R),
        (inner, R * 0.94),
        (inner, 0)
    ]
    tri = rings([(xsg * d, rr) for d, rr in sections], center)
    if xsg>0:
        tri = tri[:, [0, 2, 1]] if np.cross(tri[2, 1] - tri[2, 0], tri[2, 2] - tri[2, 0])[0] < 0 else tri
    # Orient the lathe by its known cap winding rather than the degenerate centre.
    valid = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) > 1e-12
    tri = tri[valid]
    nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ci = tri.mean(1)
    if np.median(nn[abs(ci[:,0]-center[0]-outer*xsg)<1e-6,0])*xsg<0:
        tri = tri[:, [0, 2, 1]]
    dist = np.linalg.norm((tri.mean(1) - center)[:, 1:], axis=1)
    rr = dist > R * 0.88 if kind in ('road', 'return') else dist > 100000.0
    return (ps + parts(tri[~rr], 'running_gear') + parts(tri[rr], 'rubber'), center, R, int(mask.sum()))
