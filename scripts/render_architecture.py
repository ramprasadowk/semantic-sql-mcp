"""Render the shareable animated architecture diagram; requires Pillow."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
W, H = 1200, 1020
BG, INK, MUTED, BLUE = "#F5F7FC", "#14233D", "#52647C", "#2563EB"


def font(size, bold=False):
    options = [
        "/System/Library/Fonts/Supplemental/Arial" + (" Bold" if bold else "") + ".ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in options:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def centered(d, xy, text, size, fill=INK, bold=False):
    d.text(xy, text, font=font(size, bold), fill=fill, anchor="mm")


nodes = [
    (65, 200, "01", "Your question", "Revenue by month?"),
    (465, 200, "02", "AI client", "Uses definitions to frame SQL"),
    (865, 200, "03", "Python MCP tools", "Discover - verify - query"),
    (865, 460, "04", "Semantic layer", "Business meaning + schema"),
    (465, 460, "05", "Neon PostgreSQL", "Read-only query execution"),
    (65, 460, "06", "Answer + chart", "Jan $250 / Feb $450"),
]
BW, BH = 270, 150
paths = [((335,275),(465,275)), ((735,275),(865,275)),
         ((1000,350),(1000,460)), ((865,535),(735,535)),
         ((465,535),(335,535))]
labels = ["QUESTION", "TOOL CALL", "CHECK", "VALID SQL", "RESULTS"]
steps = ["Understand the business question", "Read the catalog and generate SQL",
         "Call the Python MCP tools", "Read business definitions; verify schema and validate SQL",
         "Execute with a read-only database login", "Explain results and show a chart"]
COLORS = [
    ("#2563EB", "#EAF1FF"),
    ("#0891B2", "#E5F9FC"),
    ("#EA580C", "#FFF0E4"),
    ("#7C3AED", "#F3EDFF"),
    ("#0D9488", "#E2F7F1"),
    ("#DB2777", "#FDEAF3"),
]
frames=[]
for frame in range(120):
    im=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(im)
    # Soft color bands frame the architecture without competing with labels.
    d.rectangle((0,0,W,8),fill="#7C3AED")
    for stripe, color in enumerate(["#2563EB", "#0891B2", "#EA580C", "#7C3AED", "#0D9488", "#DB2777"]):
        d.rectangle((stripe*200,0,(stripe+1)*200,8),fill=color)
    d.rounded_rectangle((48,36,338,77),radius=18,fill="#E2EAFF")
    centered(d,(193,57),"semantic-sql-mcp",22,BLUE,True)
    d.text((60,99),"From a question to a database-backed answer",font=font(35,True),fill=INK)
    d.text((60,151),"The semantic layer gives business meaning to database columns.",font=font(22),fill=MUTED)
    phase=frame / 20
    active=min(int(phase),5)
    progress=phase-int(phase)
    for i,((x1,y1),(x2,y2)) in enumerate(paths):
        color=COLORS[i][0] if active==i else "#A6B6D1"
        d.line((x1,y1,x2,y2),fill=color,width=4)
        angle=math.atan2(y2-y1,x2-x1)
        tip=(x2,y2)
        wing=[(x2-13*math.cos(angle-s),y2-13*math.sin(angle-s)) for s in (0.45,-0.45)]
        d.polygon([tip,*wing],fill=color)
        if x1==x2:
            d.text((x1+15,(y1+y2)/2),labels[i],font=font(14,True),fill=MUTED,anchor="lm")
        else:
            centered(d,((x1+x2)/2,y1-22),labels[i],14,MUTED,True)
        if active==i:
            for offset in (0,0.28):
                t=(progress+offset)%1
                x,y=x1+(x2-x1)*t,y1+(y2-y1)*t
                d.ellipse((x-11,y-11,x+11,y+11),fill=COLORS[i][1])
                d.ellipse((x-6,y-6,x+6,y+6),fill=COLORS[i][0])
    for i,(x,y,number,title,subtitle) in enumerate(nodes):
        selected=i==active
        semantic=i==3
        accent, tint=COLORS[i]
        d.rounded_rectangle((x+3,y+5,x+BW+3,y+BH+5),radius=20,fill="#E5EAF3")
        d.rounded_rectangle((x,y,x+BW,y+BH),radius=20,fill=tint,outline=accent,width=4 if selected else 2)
        d.rounded_rectangle((x+18,y+17,x+63,y+49),radius=10,fill=accent)
        centered(d,(x+40,y+33),number,17,"white",True)
        centered(d,(x+BW/2,y+78),title,23,accent,True)
        centered(d,(x+BW/2,y+115),subtitle,16,MUTED)
    # Keep the semantic explanation visible throughout the animation.
    pulse=3 if active==3 else 2
    d.rounded_rectangle((65,650,1135,892),radius=20,fill="#F3EDFF",outline="#7C3AED",width=pulse)
    d.text((92,672),"WHY A SEMANTIC LAYER?",font=font(20,True),fill="#6D28D9")
    d.text((92,712),"Schema: where the data lives.",font=font(24,True),fill=INK)
    d.text((92,750),"Semantics: what the numbers mean.",font=font(24,True),fill=INK)
    d.text((92,795),"Shared definitions guide the AI's SQL.",font=font(19),fill=MUTED)
    d.line((625,706,625,825),fill="#CEB9F4",width=2)
    d.text((654,711),"Example: REVENUE",font=font(22,True),fill="#6D28D9")
    d.text((654,751),"SUM(quantity x sale price)",font=font(24,True),fill=INK)
    d.text((654,793),"Completed orders only  |  USD",font=font(21),fill=MUTED)
    centered(d,(600,858),"Metric definitions guide meaning. SQL validation checks query structure.",19,MUTED)
    d.rounded_rectangle((65,922,1135,981),radius=16,fill="#14233D")
    centered(d,(600,952),steps[active],22,"white",True)
    frames.append(im)
OUT.mkdir(exist_ok=True)
# One shared palette avoids color flicker between GIF frames.
palette=frames[0].quantize(colors=128)
indexed=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
indexed[0].save(OUT/"architecture.gif",save_all=True,append_images=indexed[1:],duration=65,loop=0,disposal=2,optimize=False)
frames[60].save(OUT/"architecture.png")
print("Created docs/architecture.gif and docs/architecture.png")
