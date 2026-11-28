"""Two distributed echelons on the original game terrain, with a separate manifest per player side."""
from collections import Counter
from itertools import combinations
from math import hypot, atan2, degrees
from .. import layout
from ..mission.lanes import Lanes
from ..mission.roster import perspective
from . import PZ2,PZ3,PZ4

# Listed west wing then east wing in each row; the two wings stay separate until their final sectors.
FORMATION = {
 'SO': {'GE': (([PZ3,PZ2,PZ2],[PZ2,PZ3,PZ2]),([PZ4,PZ3,PZ2],[PZ4,PZ2,PZ3])),
        'SO': ((['BT7','T26','T26'],['T26','BT7']),(['T26','BT7'],['T28','T26','BT7']))},
 'GE': {'GE': (([PZ3,PZ2,PZ2],[PZ2,PZ3]),([PZ4,PZ2],[PZ4,PZ2,PZ3])),
        'SO': ((['BT7','T26','T26'],['BT7','BT7','T26']),(['T26','BT7','BT7'],['T28','T26','BT7','T26']))}}

def deployment(h, props, side):
    nav=Lanes(h,props); rows=[]; positions=[]; goals=[]; counts=Counter()
    def clear(x,z,occupied=(),spacing=0):
        for dx,dz in sorted(((dx,dz) for dx in range(-42,43,3) for dz in range(-42,43,3)),key=lambda p:(hypot(*p),p)):
            a,b=x+dx,z+dz
            if not (-435<a<-15 and -392<b<634):continue
            if all(hypot(a-c,b-d)>=spacing for c,d in occupied) and nav.clear((a,b),(a,b)):
                y=float(layout.ground(h,a,b))
                if all(abs(float(layout.ground(h,a+vx,b+vz))-y)<.80 for vx,vz in [(3,0),(0,3),(-3,0),(0,-3)]):return a,b
        raise ValueError(('No clear station',x,z))
    for nation,lines in FORMATION[side.code].items():
        for rank,wings in enumerate(lines):
            for wing,platoon in enumerate(wings):
                for j,tank in enumerate(platoon):
                    # Separate columns even in the 4-vehicle Soviet reserve. Alternate depth and route endpoints.
                    x=(-360 if wing==0 else -175)+j*42+rank*9
                    z=(488+rank*100 if nation=='GE' else -112-rank*100)+(j%2)*10
                    a,b=clear(x,z,positions,36); positions.append((a,b)); counts[nation,tank]+=1
                    direction='west' if not wing else 'east'
                    if nation=='GE':
                        lane=(-405 if not wing else -143)+j*26+rank*5
                        endx=(-324 if not wing else -177)+j*35+rank*7
                        endz=(-80 if rank==0 else -153)+(j%2)*12
                        points=[clear(lane,325-rank*16),clear(lane,110+j*10),clear(endx,endz,goals,24)]
                    else:
                        endx=(-367 if not wing else -173)+j*37+rank*8
                        endz=(-55 if not rank else -123)+(j%2)*9
                        points=[clear(endx,endz,goals,24)]
                    goals.append(points[-1]); aim=points[0] if nation=='GE' else (a,b+20)
                    y=round(float(layout.ground(h,a,b)),4)
                    rows.append(dict(nation=nation,tank=tank,phase='reserve' if rank else 'opening',
                        echelon=rank+1,lane=direction,id=f'{nation}_{tank}_{counts[nation,tank]:02}',
                        pos=[a,round(y+.35,4),b],ground=y,yaw=round(degrees(atan2(aim[0]-a,aim[1]-b)),4),
                        route=[[x,0.,z] for x,z in points]))
    nav.bake(rows)
    out=perspective(rows,side); metrics=measure(out)
    assert 575<=metrics['nearestEnemyM']<=625 and metrics['minimumFriendlyM']>=36
    for u in out:
        p=u['pos'][::2]
        for q in u['route']:
            assert nav.clear(p,q[::2]);p=q[::2]
    return out,metrics

def measure(rows):
    dist=lambda a,b:hypot(a['pos'][0]-b['pos'][0],a['pos'][2]-b['pos'][2])
    pairs=list(combinations(rows,2))
    return dict(nearestEnemyM=round(min(dist(a,b) for a,b in pairs if a['nation']!=b['nation']),1),
                minimumFriendlyM=round(min(dist(a,b) for a,b in pairs if a['nation']==b['nation']),1),
                lineDepthM={n:round(abs(sum(x['pos'][2] for x in rows if x['nation']==n and x['echelon']==1)/sum(1 for x in rows if x['nation']==n and x['echelon']==1)-sum(x['pos'][2] for x in rows if x['nation']==n and x['echelon']==2)/sum(1 for x in rows if x['nation']==n and x['echelon']==2)),1) for n in ('GE','SO')})
