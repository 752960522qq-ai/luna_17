"""Closed tank treads with an integer number of UV cycles and contact-weighted lower run."""
import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull
from ..bt7.forms import unit
from ..bt7.source import Part
from ..panzer2f.build import texture as paint
from .source import AXLES, B, SCALE

def texture(src,key):
    if key!='tread':
        return paint(None, key)
    # Four separately hinged links per tile; edges have continuous, visible link pins,
    # the centre carries worn grouser ridges. Values on both tile seams are periodic.
    h, w = (384, 224)
    y, x = np.indices((h, w))
    u = (x + 0.5) / w
    v = (y + 0.5) / h
    row = np.floor(v * 4)
    p = v * 4 % 1
    phase = p - 0.1 * np.sin(u * np.pi * 2)
    groove = np.exp(-(np.minimum(p, 1 - p) / 0.065) ** 2)
    raised = np.exp(-((phase - 0.47) / 0.13) ** 4) * (abs(u - 0.5) < 0.4)
    edge = (u < 0.17) | (u > 0.83)
    pin = np.exp(-((p - 0.49) / 0.19) ** 2) * edge
    web = (np.cos((u - 0.5) * 24) + 0.7 * np.cos(6 * np.pi * p)) * ((u > 0.13) & (u < 0.87))
    L = 64 + 42 * raised - 31 * groove + 23 * pin + 4 * web + 2 * np.cos(2 * np.pi * (row / 4))
    L += np.random.default_rng(7541).normal(0, 3, (h, w))
    return Image.fromarray(np.clip(np.stack([L + 4, L + 1, L - 2], axis=2), 0, 255).astype('uint8'))

def belt(sgn):
    start = B([100 + sgn * 11.8, 100, 0])
    pts = []
    for _,kind,y,z,r in AXLES:
        a = np.linspace(0, 2 * np.pi, 96, endpoint=False)
        c = B([100, y, z])[1:]
        # radii include the body of the shoe; bottom is the contact plane, not the axle plane.
        pts.extend(c + np.column_stack([np.cos(a), np.sin(a)]) * (r * SCALE[2] + 0.087))
    p = np.array(pts)
    p = p[ConvexHull(p).vertices]
    low = np.argmin(p[:, 0] + abs(p[:, 1] + 1.3) * 0.002)
    p = np.roll(p, -low, axis=0)
    if p[1,1]<p[0,1]:
        p = p[np.r_[0, len(p) - 1:0:-1]]
    prof = []
    for a,b in zip(p,np.roll(p,-1,axis=0)):
        for t in np.linspace(0,1,max(1,int(np.ceil(np.linalg.norm(b-a)/.066))),endpoint=False):
            q = (1 - t) * a + t * b
            if min(a[0],b[0])>.98 and abs(a[1]-b[1])>.47:
                q[0] -= 0.024 * np.sin(np.pi * t) ** 2
            q[0] = max(0, q[0])
            prof.append(q)
    yz = np.asarray(prof)
    mid = yz.mean(0)
    off = np.roll(yz, -1, axis=0) - np.roll(yz, 1, axis=0)
    n = unit(np.c_[-off[:, 1], off[:, 0]])
    if np.sum(n*(yz-mid))<0:
        n *= -1
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.roll(yz, -1, axis=0) - yz, axis=1))]
    cycles = round(arc[-1] / 0.465)
    period = arc[-1] / cycles
    width = 0.435
    thick = 0.083
    vertices = []
    normals = []
    uv = []
    indices = []
    cross = [
        (-0.5, 0.18, 0),
        (-0.47, 0, 0.05),
        (0.47, 0, 0.95),
        (0.5, 0.18, 1),
        (0.5, 0.82, 1),
        (0.46, 1, 0.93),
        (-0.46, 1, 0.07),
        (-0.5, 0.82, 0)
    ]
    for i in range(len(yz)):
        j = (i + 1) % len(yz)
        for k,(a,h,u) in enumerate(cross):
            b, h2, u2 = cross[(k + 1) % len(cross)]
            uu = (u, u2) if abs(u - u2) > 0.002 else (0.82, 0.98) if a > 0 else (0.02, 0.18)
            def pt(s,xx,dh):
                return np.r_[start[0] + xx * width, yz[s] - n[s] * dh * thick]
            q = np.array([pt(i, a, h), pt(i, b, h2), pt(j, b, h2), pt(j, a, h)])
            nt = np.r_[np.sign(a + b) * abs(h2 - h) * thick, n[i] * (b - a) * width]
            if (h+h2)/2>.8:
                nt[1:] = -n[i] * abs(b - a) * width
            face = unit(np.cross(q[1] - q[0], q[2] - q[0]))
            ix = np.array([0, 1, 2, 0, 2, 3])
            if face@nt<0:
                ix = ix[[0, 2, 1, 3, 5, 4]]
                face = -face
            indices.extend(len(vertices) + ix)
            vertices.extend(q)
            normals.extend([face] * 4)
            v1, v2 = arc[i:i + 2] / period
            uv.extend([(uu[0], v1), (uu[1], v1), (uu[1], v2), (uu[0], v2)])
    part = Part(
        np.array(vertices),
        np.array(normals),
        np.array(uv),
        np.array(indices),
        'tread_' + ('l' if sgn > 0 else 'r')
    )
    return (part, period, arc[-1], cycles)
