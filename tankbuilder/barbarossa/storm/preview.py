"""Draw the two actual deployment layouts to scale on their original Polesie map."""
import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageEnhance
from .. import layout
from ..cartography import cartography
from . import PZ2,PZ3,PZ4

def render(manifest,output):
    spec=json.loads(manifest.read_text())['second'];h=layout.heightgrid();props=layout.placements(h)
    mapim=cartography(h,layout.splat(props),props,n=1400).convert('RGB')
    W,H=1480,1140;img=Image.new('RGB',(W,H),'#0e2028');d=ImageDraw.Draw(img)
    root=Path('/usr/share/fonts/opentype/noto')
    def font(size,b=False):return ImageFont.truetype(str(root/('NotoSansCJK-Bold.ttc' if b else 'NotoSansCJK-Regular.ttc')),size,index=2)
    def line(x,y,t,sz=20,col='#e7f0ee',b=False,anchor='la'):d.text((x,y),t,font=font(sz,b),fill=col,anchor=anchor)
    paper='#e8eeea';ge='#ffbf70';so='#87d6df';ink='#172a30';muted='#a8c0c3'
    line(49,22,'巴巴罗萨行动     /     战役 02',22,'#9eced0',True)
    line(47,52,'暴风骤雨',59,paper,True);line(348,82,'两种阵营的开局部署',27,'#c4d6d6')
    line(1432,29,'波列西  /  村庄与田野',20,muted,False,'ra')
    line(1432,70,'敌我最近 594 m     ·     同阵营最近 42 m',25,paper,True,'ra')
    d.line((49,145,W-49,145),fill='#415760',width=2)
    panels=[(49,'SO','选择苏联','BT-7','德军 12 辆   /   苏军 10 辆'),(755,'GE','选择德国','三号 F 型','德军 10 辆   /   苏军 13 辆')]
    scale=.745;panelW=676;panelH=671;xlo=-671;ztop=655
    for left,key,title,hero,total in panels:
        line(left,157,title,29,paper,True);line(left+135,171,'驾驶 '+hero,18,'#b8d1d3');line(left+panelW,169,total,19,'#b8d1d3',False,'ra')
        top=217
        def screen(x,z):return (left+(x-xlo)*scale,top+(ztop-z)*scale)
        xr=xlo+panelW/scale;zb=ztop-panelH/scale
        base=mapim.transform((panelW,panelH),Image.Transform.EXTENT,(xlo+700,700-ztop,xr+700,700-zb),Image.Resampling.BILINEAR)
        base=Image.blend(ImageEnhance.Color(base).enhance(.62),Image.new('RGB',base.size,'#18333c'),.46)
        img.paste(base,(left,top));d.rectangle((left,top,left+panelW,top+panelH),outline='#779296',width=2)
        rows=spec['sides'][key]['units']
        for wing in ('west','east'):
            rr=next(r for r in rows if r['nation']=='GE' and r['echelon']==1 and r['lane']==wing and r['route'])
            route=[screen(rr['pos'][0],rr['pos'][2])]+[screen(p[0],p[2]) for p in rr['route']]
            for (x,y),(u,v) in zip(route,route[1:]):
                dx,dy=u-x,v-y;length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
                for k in range(0,int(length),15):
                    end=min(length,k+8);d.line((x+k*ux,y+k*uy,x+end*ux,y+end*uy),fill='#edbe7f',width=3)
            (x,y),(u,v)=route[-2:];a=math.atan2(v-y,u-x)
            d.polygon([(u,v),(u-13*math.cos(a-.52),v-13*math.sin(a-.52)),(u-13*math.cos(a+.52),v-13*math.sin(a+.52))],fill=ge)
        for r in rows:
            x,y=screen(r['pos'][0],r['pos'][2]);g=r['nation']=='GE';c=ge if g else so;first=r['echelon']==1;center=c if first else '#22383d';name={PZ2:'2',PZ4:'4',PZ3:'3','BT7':'7','T26':'26','T28':'28'}[r['tank']]
            if r['team']=='player':
                d.ellipse((x-19,y-19,x+19,y+19),outline='#fcf7d8',width=3)
            if g:
                poly=[(x,y-12),(x+13,y+11),(x-13,y+11)];d.polygon(poly,fill=center);d.line(poly+[poly[0]],fill=c,width=2)
                line(x,y+3,name,13,ink if first else c,True,'mm')
            else:
                d.ellipse((x-11,y-11,x+11,y+11),fill=center,outline=c,width=2);line(x,y-1,name,12,ink if first else c,True,'mm')
        for z,title_e in [(590,'德 Ⅱ'),(489,'德 Ⅰ'),(-110,'苏 Ⅰ'),(-209,'苏 Ⅱ')]:
            x,y=screen(xlo+14,z);d.rounded_rectangle((x,y-13,x+51,y+14),4,fill='#24393b');line(x+25,y-1,title_e,15,'#e0e9dc',True,'mm')
        x=left+panelW-18;y=top+22
        line(x,y,'北 ↑',17,paper,True,'ra');xx=left+panelW-28;yy=top+panelH-21
        d.line((xx-100*scale,yy,xx,yy),fill=paper,width=3);d.line((xx-100*scale,yy-5,xx-100*scale,yy+3),fill=paper,width=2);d.line((xx,yy-5,xx,yy+3),fill=paper,width=2);line(xx-50*scale,yy-17,'100 m',15,paper,False,'mm')
    y=905;line(50,y,'▲  德军：2 = 二号 F    3 = 三号 F    4 = 四号 C',19,ge,True);line(756,y,'●  苏军：7 = BT-7    26 = T-26    28 = T-28',19,so,True)
    line(50,y+40,'Ⅰ  实心：第一梯队     Ⅱ  空心：第二梯队     双圈：玩家座车     虚线：德军两路行进方向',19,muted)
    d.line((49,996,W-49,996),fill='#415760',width=2);line(49,1013,'战役时钟',22,paper,True)
    xx=254
    for t,lab in [('00:00','两军就位'),('05:12','德军第二梯队出动'),('07:12','苏军第二梯队投入'),('13:00','守时或歼灭结算')]:
        line(xx,1015,t,23,'#f6cd8c',True);line(xx,1051,lab,20,paper);xx+=300
    line(49,1100,'按关卡内实际坐标绘制  ·  朝北，等比例  ·  两梯队均在开局出现；阵亡或全歼可提前结束。',16,muted)
    img.save(output,optimize=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('output',type=Path);a=p.parse_args();render(a.manifest,a.output)
