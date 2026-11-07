"""Erzeugt das Hai-Modell fuer Poolrooms mit Blender (bpy) und schreibt shark_mesh.js.

Aufruf (Blender als Python-Modul, z. B. in einem venv mit `pip install bpy`):
    python make_shark.py ../shark_mesh.js

Koordinaten im Spiel (Three.js): x = rechts, y = oben, z = vorwaerts (Nase bei +z).
In Blender wird mit Z oben und Vorwaerts = -Y gebaut; beim Export wird zurueckgerechnet.
"""
import sys, os, math, random, base64, struct
import bpy, bmesh
from mathutils import Vector

random.seed(11)
OUT = sys.argv[-1] if sys.argv[-1].endswith('.js') else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shark_mesh.js')
PIVOT = -2.2                      # Schwanz dreht um diese z-Position

bpy.ops.wm.read_factory_settings(use_empty=True)
P = lambda x, y, z: Vector((x, -z, y))      # Three-Koordinaten -> Blender

def make_obj(name, bm):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    return ob

# ---------- Koerper: Querschnitte entlang z ----------
# (z, halbe Breite, Hoehe oben, Hoehe unten, Mittellinie)
ST = [(3.65, .07, .07, .06, -.03), (3.50, .30, .26, .18, -.03), (3.10, .52, .42, .30, 0), (2.50, .68, .58, .42, 0),
      (1.80, .80, .74, .52, 0), (0.80, .88, .92, .64, .02), (-0.20, .80, .82, .60, .02), (-1.20, .62, .64, .50, 0),
      (-2.20, .44, .46, .38, -.02), (-3.00, .26, .28, .26, -.02), (-3.55, .13, .16, .16, -.02)]

def cr(p0, p1, p2, p3, t):     # Catmull-Rom
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)

def station(zq):
    for k in range(len(ST) - 1):
        if ST[k][0] >= zq >= ST[k + 1][0]:
            t = (ST[k][0] - zq) / (ST[k][0] - ST[k + 1][0])
            a, b = ST[max(k - 1, 0)], ST[min(k + 2, len(ST) - 1)]
            return [cr(a[i], ST[k][i], ST[k + 1][i], b[i], t) for i in range(1, 5)]
    return list(ST[-1][1:])

def loft(zs, name, seg=26, noise=0.012):
    bm = bmesh.new(); rings = []
    for zq in zs:
        w, ht, hb, cy = station(zq); ring = []
        for s in range(seg):
            th = 2 * math.pi * s / seg
            h = ht if math.sin(th) > 0 else hb
            n = 1 + random.uniform(-noise, noise)
            ring.append(bm.verts.new(P(w * math.cos(th) * n, cy + h * math.sin(th) * n, zq)))
        rings.append(ring)
    for r in range(len(rings) - 1):
        for s in range(seg):
            a, b = rings[r][s], rings[r][(s + 1) % seg]; c, d = rings[r + 1][(s + 1) % seg], rings[r + 1][s]
            bm.faces.new((a, b, c, d))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return make_obj(name, bm)

zs_body = [3.65 - i * (3.65 - PIVOT) / 40 for i in range(41)]
zs_tail = [PIVOT - i * (PIVOT + 3.55) / 14 for i in range(15)]
body = loft(zs_body, 'body'); tail = loft(zs_tail, 'tail')

# ---------- Flossen: duenne Prismen aus 3D-Polygonen ----------
def fin(name, pts, mirror=False, rag=0.0):
    """pts: (x, y, z, dicke) in Three-Koordinaten; Polygon, Normale per Newell."""
    pts = [(-x if mirror else x, y, z, t) for x, y, z, t in pts]
    if mirror: pts = pts[::-1]
    pts = [(x + random.uniform(-rag, rag), y + random.uniform(-rag, rag), z + random.uniform(-rag, rag), t) if 0 < i < len(pts) - 1 else (x, y, z, t)
           for i, (x, y, z, t) in enumerate(pts)] if rag else pts
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = Vector(pts[i][:3]), Vector(pts[(i + 1) % len(pts)][:3])
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    n.normalize()
    bm = bmesh.new(); top = []; bot = []
    for x, y, z, t in pts:
        top.append(bm.verts.new(P(*(Vector((x, y, z)) + n * t / 2)))); bot.append(bm.verts.new(P(*(Vector((x, y, z)) - n * t / 2))))
    bm.faces.new(top); bm.faces.new(bot[::-1])
    for i in range(len(pts)):
        j = (i + 1) % len(pts); bm.faces.new((top[i], bot[i], bot[j], top[j]))
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return make_obj(name, bm)

fins = []
fins.append(fin('dorsal', [(0, .66, 1.30, .16), (0, 1.25, 1.08, .10), (0, 1.80, .78, .06), (0, 2.28, .38, .03), (0, 1.92, .26, .03), (0, 1.52, .08, .04),
                           (0, 1.18, -.08, .06), (0, .86, -.30, .10), (0, .55, -.30, .12), (0, .55, 1.30, .16)], rag=.015))
pec = [(.55, -.28, 1.70, .10), (1.15, -.48, 1.40, .08), (1.90, -.84, .90, .05), (2.35, -1.10, .42, .025), (1.60, -.80, .52, .03), (1.00, -.56, .58, .05), (.55, -.28, .78, .09)]
fins.append(fin('pecR', pec, rag=.015)); fins.append(fin('pecL', pec, mirror=True, rag=.015))
pel = [(.30, -.58, -.55, .08), (.62, -.80, -.80, .04), (.95, -.98, -1.05, .02), (.55, -.76, -1.15, .03), (.28, -.55, -1.05, .06)]
fins.append(fin('pelR', pel)); fins.append(fin('pelL', pel, mirror=True))
fins.append(fin('anal', [(0, -.46, -1.55, .08), (0, -.92, -1.85, .03), (0, -.80, -2.00, .03), (0, -.40, -2.00, .06)]))
fins.append(fin('dorsal2', [(0, .50, -1.35, .08), (0, .88, -1.62, .03), (0, .50, -1.95, .06)]))
caudal = fin('caudal', [(0, .10, PIVOT - 1.15, .10), (0, .55, PIVOT - 1.50, .07), (0, 1.40, PIVOT - 2.05, .05), (0, 2.05, PIVOT - 2.70, .025),
                        (0, 1.20, PIVOT - 2.42, .03), (0, .20, PIVOT - 2.32, .035), (0, -.60, PIVOT - 2.55, .03), (0, -1.20, PIVOT - 2.35, .02),
                        (0, -.60, PIVOT - 1.75, .05), (0, -.10, PIVOT - 1.15, .08)], rag=.02)

# ---------- Maul: dunkle Platte an der Unterseite + Zahnreihen ----------
def bottom_y(zq):
    w, ht, hb, cy = station(zq); return cy - hb
bm = bmesh.new(); MZ, MR_X, MR_Z = 2.78, .36, .62
center = bm.verts.new(P(0, bottom_y(MZ) - .012, MZ)); ring = []
for k in range(24):
    ph = 2 * math.pi * k / 24; zq = MZ + MR_Z * math.sin(ph)
    ring.append(bm.verts.new(P(MR_X * math.cos(ph), bottom_y(zq) - .012, zq)))
for k in range(24): bm.faces.new((center, ring[(k + 1) % 24], ring[k]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mouth = make_obj('mouth', bm)

bm = bmesh.new()
def tooth(x, z, length, rad, lean):
    y = bottom_y(z) - .012
    base = [Vector((x + rad * math.cos(a), y, z + rad * math.sin(a))) for a in (0, 2.094, 4.189)]
    tip = Vector((x + lean[0] * length, y - length, z + lean[1] * length))
    vs = [bm.verts.new(P(*b)) for b in base]; vt = bm.verts.new(P(*tip))
    bm.faces.new(vs); bm.faces.new((vs[0], vs[1], vt)); bm.faces.new((vs[1], vs[2], vt)); bm.faces.new((vs[2], vs[0], vt))
for k in range(34):
    ph = 2 * math.pi * k / 34 + random.uniform(-.05, .05); x = MR_X * math.cos(ph); z = MZ + MR_Z * math.sin(ph)
    tooth(x, z, random.uniform(.12, .22), .030, (x * .25, (z - MZ) * .25 + random.uniform(-.05, .05)))
for k in range(22):
    ph = 2 * math.pi * k / 22 + .1; x = .65 * MR_X * math.cos(ph); z = MZ + .65 * MR_Z * math.sin(ph)
    tooth(x, z, random.uniform(.08, .15), .022, (x * .1, (z - MZ) * .1))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
teeth = make_obj('teeth', bm)

# ---------- Export: Dreiecke -> indizierte, quantisierte Arrays ----------
dg = bpy.context.evaluated_depsgraph_get()

def shade_color(pos, nrm, kind):
    x, y, z = pos
    if kind == 'teeth': return (214, 206, 182)
    if kind == 'mouth': return (36, 6, 6)
    if kind == 'fin': return (14, 19, 22)
    t = max(0.0, min(1.0, -nrm[1] * .5 + .35))              # Bauch etwas heller
    n = random.uniform(-3, 3)
    # blasse Narben an der Flanke
    scar = abs(x) > .45 and -.5 < z < 1.0 and abs((y - .15) - .12 * math.sin(z * 7 + (1 if x > 0 else 3))) < .018
    if scar: return (70, 76, 82)
    base = (11 + 20 * t + n, 16 + 23 * t + n, 20 + 25 * t + n)
    return tuple(int(max(0, min(255, c))) for c in base)

def collect(objs, kinds, smooth_flags, shift_z=0.0):
    verts, idx, cache = [], [], {}
    for ob, kind, smooth in zip(objs, kinds, smooth_flags):
        me = ob.evaluated_get(dg).to_mesh(); me.calc_loop_triangles()
        vn = [v.normal for v in me.vertices]
        for tri in me.loop_triangles:
            for k in tri.loops[::-1]:                                # Wicklung beim Achsentausch spiegeln
                pass
            for li in tri.loops:
                vi = me.loops[li].vertex_index; co = me.vertices[vi].co
                n = vn[vi] if smooth else tri.normal
                pos = (co.x, co.z, -co.y + shift_z); nr = (n.x, n.z, -n.y)
                col = shade_color((pos[0], pos[1], pos[2] - shift_z), nr, kind)
                key = (round(pos[0], 3), round(pos[1], 3), round(pos[2], 3), round(nr[0], 2), round(nr[1], 2), round(nr[2], 2), col)
                if key not in cache:
                    cache[key] = len(verts); verts.append((pos, nr, col))
                idx.append(cache[key])
    return verts, idx

def pack(verts, idx):
    mx = max(max(abs(c) for c in v[0]) for v in verts); s = mx / 32767.0
    P_ = b''.join(struct.pack('<hhh', *[int(round(c / s)) for c in v[0]]) for v in verts)
    N_ = b''.join(struct.pack('<bbb', *[int(round(max(-1, min(1, c)) * 127)) for c in v[1]]) for v in verts)
    C_ = b''.join(struct.pack('<BBB', *v[2]) for v in verts)
    I_ = b''.join(struct.pack('<H', i) for i in idx)
    e = lambda b: base64.b64encode(b).decode()
    return '{s:%.8f,n:%d,p:"%s",nm:"%s",c:"%s",i:"%s"}' % (s, len(verts), e(P_), e(N_), e(C_), e(I_))

# Dreiecks-Wicklung: Blender (x,y,z) -> Three (x,z,-y) ist eine Drehung (keine Spiegelung) -> Wicklung bleibt
bv, bi = collect([body] + fins[:-0 or None] + [mouth, teeth], ['body'] + ['fin'] * len(fins) + ['mouth', 'teeth'], [True] + [False] * len(fins) + [False, False])
tv, ti = collect([tail, caudal], ['body', 'fin'], [True, False], shift_z=-PIVOT)
eyes = [(.60, .16, 2.82), (-.60, .16, 2.82)]
js = '// automatisch erzeugt von tools/make_shark.py (Blender %s)\nwindow.SHARK_MESH = {pivot:%.3f,len:8.6,eyes:%s,\nbody:%s,\ntail:%s};\n' % (
    bpy.app.version_string, PIVOT, str([list(e) for e in eyes]), pack(bv, bi), pack(tv, ti))
open(OUT, 'w').write(js)
print('OK', OUT, 'body verts/tris', len(bv), len(bi) // 3, 'tail', len(tv), len(ti) // 3, 'bytes', len(js))
