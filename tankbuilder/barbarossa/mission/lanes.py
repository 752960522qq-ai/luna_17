"""Short stock AI waypoint lists on the same collision-free ground as the mission."""

import heapq, math
import numpy as np
from .. import layout
from .roster import RADIUS


class Lanes:
    def __init__(self, h, props):
        self.h = h
        self.obs = np.asarray(
            [
                (p["x"], p["z"], RADIUS[p["kind"]] * p["scale"] + 2.7)
                for p in props
                if p["kind"] in RADIUS and -455 < p["x"] < 0 and -420 < p["z"] < 315
            ]
        )
        self.cache = {}

    def clear(self, p, q):
        p, q = tuple(p), tuple(q)
        key = tuple(sorted((p, q)))
        if key in self.cache:
            return self.cache[key]
        a, b = p
        c, d = q
        dx = c - a
        dz = d - b
        den = dx * dx + dz * dz
        x, z, r = self.obs.T
        t = np.clip(((x - a) * dx + (z - b) * dz) / max(1, den), 0.0, 1.0)
        free = not np.any((x - a - t * dx) ** 2 + (z - b - t * dz) ** 2 < r * r)
        if free:
            t = np.linspace(0.0, 1.0, max(2, 1 + math.ceil(math.sqrt(den) / 4)))
            xx = a + dx * t
            zz = b + dz * t
            hh = layout.ground(self.h, xx, zz)
            free = (
                np.min(hh) > 10
                and np.min(layout.shore(xx, zz)) > 10
                and np.all(
                    np.abs(np.diff(hh)) <= 0.25 * math.sqrt(den) / (len(t) - 1) + 0.02
                )
            )
        self.cache[key] = bool(free)
        return bool(free)

    def point(self, p):
        x, z = (round(k / 8) * 8 for k in p)
        candidates = sorted(
            ((x + i, z + j) for i in range(-32, 33, 8) for j in range(-32, 33, 8)),
            key=lambda q: (math.dist(q, p), q),
        )
        return next(q for q in candidates if self.clear(p, q))

    def path(self, p, q):
        if self.clear(p, q):
            return [q]
        a, b = self.point(p), self.point(q)
        prev = {a: None}
        cost = {a: 0.0}
        todo = [(math.dist(a, b), 0.0, a)]
        while todo:
            _, dist, k = heapq.heappop(todo)
            if dist != cost[k]:
                continue
            if k == b:
                break
            for di, dj in (
                (0, 8),
                (8, 0),
                (0, -8),
                (-8, 0),
                (8, 8),
                (-8, 8),
                (8, -8),
                (-8, -8),
            ):
                n = (k[0] + di, k[1] + dj)
                v = dist + math.hypot(di, dj)
                if not (
                    -440 < n[0] < -12
                    and -398 < n[1] < 298
                    and v < cost.get(n, float("inf"))
                ):
                    continue
                if not self.clear(k, n):
                    continue
                cost[n] = v
                prev[n] = k
                heapq.heappush(todo, (v + math.dist(n, b), v, n))
        if b not in prev:
            raise ValueError(f"No passable mission lane {p}->{q}")
        nodes = [q]
        n = b
        while n is not None:
            nodes.append(n)
            n = prev[n]
        nodes.append(p)
        nodes = nodes[::-1]
        best = []
        i = 0
        while i < len(nodes) - 1:
            j = next(
                j
                for j in range(len(nodes) - 1, i, -1)
                if self.clear(nodes[i], nodes[j])
            )
            if nodes[j] != (best[-1] if best else p):
                best.append(nodes[j])
            i = j
        return best

    def bake(self, rows):
        for u in rows:
            prev = u["pos"][0], u["pos"][2]
            out = []
            for x, y, z in u["route"]:
                out.extend(self.path(prev, (x, z)))
                prev = (x, z)
            u["route"] = [[x, 0.0, z] for x, z in out]
