"""Poolrooms-Requisiten in Blender (bpy) modelliert -> props_mesh.js

Aufruf:  python make_props.py ../props_mesh.js        (Blender als Python-Modul: pip install bpy)

Modelliert werden: riesige Quietscheente, Schwimmring, Wasserball, Liege, Whirlpool,
Bademeisterstuhl, Poolnudeln und eine Wasserrutsche mit Turm. In Blender entstehen die
Meshes (bmesh + Bevel-Modifier); beim Export wird pro Vertex ein Ambient-Occlusion-Wert per
Raycast (BVH) berechnet und in die Vertexfarbe eingebacken -> weiche Kontaktschatten ohne
Texturen. Koordinaten im Spiel (Three.js): x rechts, y oben, z vorwaerts; y = 0 ist der Boden.
"""
import sys, os, math, random, base64, struct
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

random.seed(5)
OUT = sys.argv[-1] if sys.argv[-1].endswith('.js') else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'props_mesh.js')
bpy.ops.wm.read_factory_settings(use_empty=True)

def to_b(x, y, z): return Vector((x, -z, y))                 # Three -> Blender (Drehung, keine Spiegelung)
def rotm(r): return Matrix.Rotation(r[2], 3, 'Z') @ Matrix.Rotation(r[1], 3, 'Y') @ Matrix.Rotation(r[0], 3, 'X')

# ---------------------------------------------------------------- Bausteine
def new_bm():
    bm = bmesh.new(); bm.loops.layers.float_color.new('col'); return bm

def paint(bm, fn):
    lay = bm.loops.layers.float_color['col']
    for f in bm.faces:
        for l in f.loops:
            v = l.vert.co; c = fn((v.x, v.z, -v.y)); l[lay] = (c[0], c[1], c[2], 1.0)

def ellipsoid(c, r, rot=(0, 0, 0), us=28, vs=20):
    bm = new_bm(); bmesh.ops.create_uvsphere(bm, u_segments=us, v_segments=vs, radius=1.0)
    M = rotm(rot)
    for v in bm.verts:
        p = M @ Vector((v.co.x * r[0], v.co.y * r[1], v.co.z * r[2])) + Vector(c); v.co = to_b(*p)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def box(c, s, rot=(0, 0, 0)):
    bm = new_bm(); bmesh.ops.create_cube(bm, size=1.0); M = rotm(rot)
    for v in bm.verts:
        p = M @ Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2])) + Vector(c); v.co = to_b(*p)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def tube(pts, radius, seg=16, caps=True, facecol=None):
    """Roehre entlang einer Polylinie (parallel transport). facecol(i) -> Farbe des Abschnitts i."""
    bm = new_bm(); n = len(pts); rings = []
    P = [Vector(p) for p in pts]; a = None
    for i, p in enumerate(P):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        if a is None:
            up = Vector((0, 1, 0)) if abs(t.y) < 0.95 else Vector((1, 0, 0)); a = t.cross(up).normalized()
        else: a = (a - t * a.dot(t)).normalized()
        b = a.cross(t).normalized(); rad = radius[i] if isinstance(radius, (list, tuple)) else radius
        rings.append([bm.verts.new(to_b(*(p + (a * math.cos(2 * math.pi * s / seg) + b * math.sin(2 * math.pi * s / seg)) * rad))) for s in range(seg)])
    faces = []
    for i in range(n - 1):
        for s in range(seg):
            faces.append((i, bm.faces.new((rings[i][s], rings[i][(s + 1) % seg], rings[i + 1][(s + 1) % seg], rings[i + 1][s]))))
    if caps: bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    mid = P[n // 2]; f0 = faces[len(faces) // 2][1]
    if (f0.calc_center_median() - to_b(*mid)).dot(f0.normal) < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces)
    if facecol:
        lay = bm.loops.layers.float_color['col']
        for i, f in faces:
            c = facecol(i)
            for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)
    return bm

def torus(c, R, r, rot=(0, 0, 0), s1=40, s2=18):
    bm = new_bm(); M = rotm(rot); vs = []
    for i in range(s1):
        th = 2 * math.pi * i / s1; row = []
        for j in range(s2):
            ph = 2 * math.pi * j / s2
            p = M @ Vector(((R + r * math.cos(ph)) * math.cos(th), r * math.sin(ph), (R + r * math.cos(ph)) * math.sin(th))) + Vector(c)
            row.append(bm.verts.new(to_b(*p)))
        vs.append(row)
    for i in range(s1):
        for j in range(s2): bm.faces.new((vs[i][j], vs[(i + 1) % s1][j], vs[(i + 1) % s1][(j + 1) % s2], vs[i][(j + 1) % s2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def lathe(profile, c=(0, 0, 0), seg=40):
    """Drehkoerper um die y-Achse; profile = [(radius, y), ...] (geschlossen, falls Anfang=Ende-Radius 0)."""
    bm = new_bm(); rings = []
    for rad, y in profile:
        rings.append([bm.verts.new(to_b(c[0] + rad * math.cos(2 * math.pi * s / seg), c[1] + y, c[2] + rad * math.sin(2 * math.pi * s / seg))) for s in range(seg)])
    for i in range(len(profile) - 1):
        for s in range(seg): bm.faces.new((rings[i][s], rings[i][(s + 1) % seg], rings[i + 1][(s + 1) % seg], rings[i + 1][s]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

class Model:
    def __init__(self, name): self.name = name; self.parts = []; self.meta = {}
    def add(self, bm, color=None, mods=None, mat=0):
        if color is not None and not mods: paint(bm, lambda p, c=color: c)
        me = bpy.data.meshes.new('m'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('o', me); bpy.context.collection.objects.link(ob)
        for typ, kw in (mods or []):
            m = ob.modifiers.new(typ.lower(), typ)
            for k, v in kw.items(): setattr(m, k, v)
        self.parts.append((ob, mat, color if mods else None))
BEVEL = lambda w=0.02, s=2: [('BEVEL', dict(width=w, segments=s, limit_method='ANGLE', angle_limit=math.radians(40)))]

def catmull(ctrl, per=14):
    P = [Vector(p) for p in ctrl]; out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1]); return out

models = []
GRAY, STEEL, WHITE = (0.62, 0.66, 0.68), (0.55, 0.6, 0.64), (0.92, 0.93, 0.94)

# ---------------------------------------------------------------- Quietscheente
def make_duck():
    m = Model('duck'); Y = (0.93, 0.74, 0.17); Yd = (0.88, 0.67, 0.13); O = (0.88, 0.42, 0.12); K = (0.02, 0.02, 0.02)
    m.add(ellipsoid((0, 1.0, 0), (1.0, 0.85, 1.45), (-0.10, 0, 0), 32, 24), Y)                 # Koerper
    m.add(ellipsoid((0, 1.50, -1.28), (0.34, 0.34, 0.62), (0.75, 0, 0)), Y)                    # Schwanz
    m.add(ellipsoid((0, 2.12, 0.82), (0.66, 0.62, 0.66), (0, 0, 0), 28, 20), Y)                # Kopf
    m.add(ellipsoid((0, 2.05, 1.46), (0.38, 0.11, 0.48), (0.05, 0, 0)), O)                     # Oberschnabel
    m.add(ellipsoid((0, 1.94, 1.42), (0.31, 0.07, 0.40), (0.05, 0, 0)), (0.80, 0.34, 0.09))     # Unterschnabel
    for sx in (-1, 1):
        m.add(ellipsoid((sx * 1.04, 1.18, -0.10), (0.24, 0.46, 0.82), (0, 0, sx * 0.20)), Yd)  # Fluegel
        m.add(ellipsoid((sx * 0.40, 2.32, 1.22), (0.12, 0.13, 0.12), (0, 0, 0), 14, 10), K)     # Auge
        m.add(ellipsoid((sx * 0.47, 2.38, 1.31), (0.04, 0.04, 0.04), (0, 0, 0), 8, 6), (1, 1, 1))
    return m

# ---------------------------------------------------------------- Schwimmring, Wasserball
def make_ring():
    m = Model('ring')
    bm = torus((0, 0.34, 0), 1.05, 0.34)
    paint(bm, lambda p: (0.50, 0.66, 0.78) if int((math.atan2(p[2], p[0]) + math.pi) / (2 * math.pi) * 16) % 2 else (0.86, 0.88, 0.89))
    m.add(bm); return m

def make_ball():
    m = Model('ball'); bm = ellipsoid((0, 0.85, 0), (0.85, 0.85, 0.85), (0, 0, 0), 36, 24)
    cols = [(0.70, 0.17, 0.15), (0.88, 0.88, 0.87), (0.17, 0.32, 0.60), (0.88, 0.88, 0.87), (0.80, 0.66, 0.15), (0.88, 0.88, 0.87)]
    paint(bm, lambda p: (0.88, 0.88, 0.87) if abs(p[1] - 0.85) > 0.78 else cols[int((math.atan2(p[2], p[0]) + math.pi) / (2 * math.pi) * 6) % 6])
    m.add(bm); return m

# ---------------------------------------------------------------- Liege
def make_lounger():
    m = Model('lounger'); L = 2.0
    bm = box((0, 0.38, 0), (0.72, 0.12, 1.15)); paint(bm, lambda p: (0.35, 0.50, 0.65) if int((p[2] + 5) / 0.16) % 2 else (0.86, 0.87, 0.88)); m.add(bm, mods=None)
    bm = box((0, 0.74, -0.78), (0.72, 0.12, 0.95), (0.95, 0, 0)); paint(bm, lambda p: (0.35, 0.50, 0.65) if int((p[2] + 5) / 0.16) % 2 else (0.86, 0.87, 0.88)); m.add(bm)
    for sx in (-1, 1):
        for z in (-0.5, 0.45): m.add(tube([(sx * 0.33, 0, z), (sx * 0.33, 0.32, z)], 0.025, 10), STEEL)
        m.add(tube([(sx * 0.35, 0.31, -0.55), (sx * 0.35, 0.31, 0.58)], 0.025, 10), STEEL)
        m.add(tube([(sx * 0.35, 0.31, -0.45), (sx * 0.35, 0.62, -0.95)], 0.022, 10), STEEL)
    return m

# ---------------------------------------------------------------- Whirlpool
def make_hottub():
    m = Model('hottub')
    prof = [(0.0, 0.0), (2.1, 0.0), (2.1, 0.88), (2.0, 0.98), (1.82, 0.98), (1.76, 0.88), (1.74, 0.15), (0.0, 0.15)]
    bm = lathe(prof, seg=44)
    paint(bm, lambda p: (0.20, 0.52, 0.56) if math.hypot(p[0], p[2]) < 1.79 and p[1] < 0.9 else (0.86, 0.89, 0.91))
    m.add(bm)
    for k in range(8):
        a = 2 * math.pi * k / 8 + 0.2
        m.add(tube([(1.72 * math.cos(a), 0.55, 1.72 * math.sin(a)), (1.66 * math.cos(a), 0.55, 1.66 * math.sin(a))], 0.06, 10), (0.75, 0.78, 0.8))
    m.meta['water'] = [1.74, 0.82]; return m

# ---------------------------------------------------------------- Bademeisterstuhl
def make_lifeguard():
    m = Model('lifeguard'); W = (0.93, 0.93, 0.94)
    for sx in (-1, 1):
        for sz in (-1, 1): m.add(tube([(sx * 0.95, 0, sz * 0.85), (sx * 0.6, 2.0, sz * 0.55)], 0.06, 10), W)
    m.add(box((0, 2.05, 0), (1.35, 0.1, 1.2)), (0.85, 0.85, 0.87), BEVEL(0.015, 2))
    m.add(box((0, 2.65, -0.62), (1.3, 1.0, 0.08)), (0.72, 0.28, 0.14), BEVEL(0.015, 2))
    for sx in (-1, 1): m.add(box((sx * 0.62, 2.4, 0), (0.07, 0.07, 1.1)), W)
    for k in range(6): m.add(box((0, 0.3 + k * 0.32, 0.97 - k * 0.07), (0.9, 0.06, 0.12)), W)   # Leiter
    m.add(box((0, 0.3, 0.9), (0.06, 0.06, 0.06)), W)
    bm = lathe([(0, 3.35), (0.5, 3.18), (1.15, 2.92), (1.2, 2.88), (0, 2.88)], c=(0, 0, -0.1), seg=24)
    paint(bm, lambda p: (0.68, 0.17, 0.14) if int((math.atan2(p[2] + 0.1, p[0]) + math.pi) / (2 * math.pi) * 8) % 2 else (0.86, 0.86, 0.85)); m.add(bm)
    m.add(tube([(0, 2.88, -0.1), (0, 2.1, -0.1)], 0.04, 8), W); return m

# ---------------------------------------------------------------- Poolnudeln
def make_noodle(name, col):
    m = Model(name); pts = [(1.0 * math.sin(a), 0.5 * (1 - math.cos(a)) + 0.06, 0.0) for a in [i * math.pi * 0.62 / 22 - math.pi * 0.31 for i in range(23)]]
    m.add(tube(pts, 0.065, 12), col); return m

# ---------------------------------------------------------------- Wasserrutsche mit Turm
SLIDE_CTRL = [(-1.8, 4.75, 0), (-4.0, 4.35, 0.0), (-7.0, 3.60, 1.6), (-9.2, 2.75, 4.3), (-8.6, 1.95, 7.4),
              (-6.0, 1.35, 9.2), (-3.0, 1.05, 9.4), (-0.5, 0.90, 9.0), (1.2, 0.85, 8.7)]
def make_slide():
    m = Model('slide'); path = catmull(SLIDE_CTRL, 16)
    bands = [(0.80, 0.84, 0.86), (0.48, 0.64, 0.74), (0.88, 0.90, 0.91)]
    m.add(tube([tuple(p) for p in path], 0.62, 30, caps=False, facecol=lambda i: bands[(i // 8) % 3]), mat=2)
    m.add(box((0, 4.1, 0), (3.6, 0.2, 3.6)), (0.68, 0.76, 0.80), BEVEL(0.02, 2))                    # Plattform
    for sx in (-1, 1):
        for sz in (-1, 1): m.add(tube([(sx * 1.65, 0, sz * 1.65), (sx * 1.65, 4.05, sz * 1.65)], 0.10, 12), GRAY)
    def rail(p, q):
        m.add(tube([(p[0], 5.15, p[1]), (q[0], 5.15, q[1])], 0.035, 8), STEEL)
        m.add(tube([(p[0], 4.7, p[1]), (q[0], 4.7, q[1])], 0.025, 8), STEEL)
        for e in (p, q): m.add(tube([(e[0], 4.2, e[1]), (e[0], 5.15, e[1])], 0.03, 8), STEEL)
    for a, b in [((1.8, -1.8), (1.8, -0.85)), ((1.8, 0.85), (1.8, 1.8)), ((-1.8, -1.8), (1.8, -1.8)), ((-1.8, 1.8), (1.8, 1.8)),
                 ((-1.8, -1.8), (-1.8, -0.95)), ((-1.8, 0.95), (-1.8, 1.8))]: rail(a, b)
    for k in range(10, len(path) - 6, 15):                                                        # Stuetzen unter der Roehre
        p = path[k]
        if p.x < -3.0: m.add(tube([(p.x, 0, p.z), (p.x, p.y - 0.55, p.z)], 0.09, 10), GRAY); m.add(box((p.x, 0.04, p.z), (0.5, 0.08, 0.5)), GRAY)
    dense = [path[i] for i in range(0, len(path), 2)]
    m.meta['path'] = [[round(p.x, 2), round(p.y, 2), round(p.z, 2)] for p in dense]
    return m


# ---------------------------------------------------------------- Poolrooms-typische Objekte
def make_domelamp():
    """Industrielle Haengelampe; Ursprung = Aufhaengepunkt oben, haengt nach unten. mat 3 = leuchtend, mat 4 = Metall."""
    m = Model('domelamp'); METAL = (0.30, 0.32, 0.34)
    m.add(lathe([(0.04, 0.0), (0.05, -0.05), (0.14, -0.06), (0.30, -0.22), (0.33, -0.27), (0.29, -0.285), (0.04, -0.285)], seg=28), METAL, mat=4)
    m.add(ellipsoid((0, -0.29, 0), (0.17, 0.13, 0.17), (0, 0, 0), 20, 14), (1.0, 0.93, 0.78), mat=3)
    m.add(torus((0, -0.30, 0), 0.30, 0.012), (0.55, 0.57, 0.6), mat=4)
    for k in range(6):
        a = 2 * math.pi * k / 6
        m.add(tube([(0.30 * math.cos(a), -0.30, 0.30 * math.sin(a)), (0.12 * math.cos(a), -0.48, 0.12 * math.sin(a)), (0.0, -0.52, 0.0)], 0.008, 6), (0.55, 0.57, 0.6), mat=4)
    return m

def make_pipe(name, col):
    """Senkrechtes Rohr mit Flanschen und Kruemmer nach -z (in die Wand)."""
    m = Model(name); H = 6.2; R = 0.45; dark = (col[0] * 0.55, col[1] * 0.55, col[2] * 0.55)
    m.add(tube([(0, 0, 0), (0, H, 0)], 0.20, 20), col)
    for y in (0.35, 2.6, 4.6): m.add(tube([(0, y - 0.04, 0), (0, y + 0.04, 0)], 0.27, 20), dark)
    el = [(0, H + R * math.sin(a), -R + R * math.cos(a)) for a in [i * math.pi / 2 / 10 for i in range(11)]]
    m.add(tube(el + [(0, H + R, -R - 0.9)], 0.20, 20), col)
    m.add(tube([(0, H + R, -R - 0.55), (0, H + R, -R - 0.63)], 0.27, 20), dark)
    m.add(tube([(0, 0, 0), (0, 0.05, 0)], 0.30, 20), dark)
    return m

def make_ladder():
    """Verchromte Beckenleiter: Holme biegen sich ueber den Rand ins Wasser (Ursprung am Rand, Abstieg nach +z)."""
    m = Model('ladder'); CH = (0.80, 0.82, 0.85)
    rail = lambda x: [(x, 0.0, -0.15), (x, 0.55, -0.15), (x, 1.02, -0.10), (x, 1.22, 0.08), (x, 1.12, 0.28), (x, 0.55, 0.50), (x, -0.4, 0.58), (x, -1.2, 0.60)]
    for x in (-0.26, 0.26):
        m.add(tube(catmull(rail(x), 5), 0.022, 12), CH, mat=4)
        m.add(tube([(x, 0.0, -0.15), (x, 0.02, -0.15)], 0.05, 14), (0.6, 0.62, 0.65), mat=4)
    for y, z in ((0.32, 0.53), (-0.25, 0.575), (-0.8, 0.595)): m.add(tube([(-0.26, y, z), (0.26, y, z)], 0.018, 10), CH, mat=4)
    return m

def make_stool():
    m = Model('stool'); W = (0.88, 0.88, 0.87)
    m.add(lathe([(0.0, 0.43), (0.21, 0.43), (0.22, 0.41), (0.21, 0.39), (0.0, 0.39)], seg=24), W)
    for sx in (-1, 1): m.add(tube([(sx * 0.15, 0.40, 0.0), (sx * 0.14, 0.0, 0.10), (sx * 0.14, 0.0, -0.10)], 0.018, 8), W)
    m.add(box((0, 0.03, 0), (0.30, 0.025, 0.22)), W)
    return m

# ---------------------------------------------------------------- Export mit Ambient Occlusion
DIRS = []
for i in range(30):
    r = math.sqrt((i + 0.5) / 30); ph = i * 2.39996; DIRS.append((r * math.cos(ph), r * math.sin(ph), math.sqrt(max(0, 1 - r * r))))

def corner_normals(me):
    vp = {}
    for pi, pol in enumerate(me.polygons):
        for v in pol.vertices: vp.setdefault(v, []).append(pi)
    return vp

def export_model(model):
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ev = [(ob.evaluated_get(dg).to_mesh(), mat, cc) for ob, mat, cc in model.parts]
    vs, ps = [], []
    for me, _, _ in ev:
        base = len(vs); vs += [v.co.copy() for v in me.vertices]; me.calc_loop_triangles()
        for t in me.loop_triangles: ps.append(tuple(base + me.loops[l].vertex_index for l in t.loops))
    bvh = BVHTree.FromPolygons(vs, ps)
    out = {}
    for me, mat, cc in ev:
        vp = corner_normals(me); col = None if cc is not None else me.color_attributes.get('col'); cache = {}; verts = []; idx = []
        for t in me.loop_triangles:
            fn = me.polygons[t.polygon_index].normal
            for li in t.loops:
                vi = me.loops[li].vertex_index; co = me.vertices[vi].co
                n = Vector((0, 0, 0))
                for pi in vp[vi]:
                    pn = me.polygons[pi].normal
                    if pn.dot(fn) > 0.75: n += pn * me.polygons[pi].area
                n = n.normalized() if n.length > 1e-9 else fn
                alb = tuple(col.data[li].color[:3]) if col else (cc if cc is not None else (0.8, 0.8, 0.8))
                key = (round(co.x, 3), round(co.y, 3), round(co.z, 3), round(n.x, 2), round(n.y, 2), round(n.z, 2), tuple(round(c, 3) for c in alb))
                if key not in cache:
                    tt = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized(); bb = n.cross(tt); hits = 0
                    for u, v, w in (() if mat == 3 else DIRS):
                        if bvh.ray_cast(co + n * 0.06, tt * u + bb * v + n * w, 1.0)[0] is not None: hits += 1
                    ao = 1.0 if mat == 3 else (1 - hits / len(DIRS)) * 0.6 + 0.4
                    c8 = tuple(int(max(0, min(255, round(255 * c * ao)))) for c in alb)
                    pos = (co.x, co.z, -co.y); nr = (n.x, n.z, -n.y)
                    cache[key] = len(verts); verts.append((pos, nr, c8))
                idx.append(cache[key])
        out.setdefault(mat, []).append((verts, idx))
    return out

def merge(lst):
    verts, idx = [], []
    for v, i in lst: off = len(verts); verts += v; idx += [k + off for k in i]
    return verts, idx

def pack(verts, idx, mat):
    mx = max(max(abs(c) for c in v[0]) for v in verts); s = mx / 32767.0
    P_ = b''.join(struct.pack('<hhh', *[int(round(c / s)) for c in v[0]]) for v in verts)
    N_ = b''.join(struct.pack('<bbb', *[int(round(max(-1, min(1, c)) * 127)) for c in v[1]]) for v in verts)
    C_ = b''.join(struct.pack('<BBB', *v[2]) for v in verts)
    I_ = b''.join(struct.pack('<H', i) for i in idx); e = lambda b: base64.b64encode(b).decode()
    return '{m:%d,s:%.8f,p:"%s",nm:"%s",c:"%s",i:"%s"}' % (mat, s, e(P_), e(N_), e(C_), e(I_))

built = [make_duck(), make_ring(), make_ball(), make_lounger(), make_hottub(), make_lifeguard(),
         make_noodle('noodleB', (0.30, 0.50, 0.75)), make_noodle('noodleP', (0.78, 0.50, 0.62)), make_noodle('noodleG', (0.40, 0.65, 0.50)), make_slide(),
         make_domelamp(), make_pipe('pipeR', (0.62, 0.10, 0.10)), make_pipe('pipeB', (0.10, 0.28, 0.58)), make_pipe('pipeY', (0.78, 0.60, 0.10)), make_ladder(), make_stool()]
js = ['// automatisch erzeugt von tools/make_props.py (Blender %s)' % bpy.app.version_string, 'window.PROPS = {']
total = 0
for md in built:
    parts = export_model(md); packed = []
    for mat, lst in sorted(parts.items()):
        v, i = merge(lst); total += len(v); packed.append(pack(v, i, mat))
    meta = md.meta
    js.append('%s:{meta:%s,parts:[%s]},' % (md.name, str(meta).replace("'", '"'), ','.join(packed)))
    print(md.name, sum(len(merge(l)[0]) for l in parts.values()), 'verts')
js.append('};'); open(OUT, 'w').write('\n'.join(js) + '\n')
print('OK', OUT, 'verts', total, 'bytes', os.path.getsize(OUT))
