#!/usr/bin/env python3
"""
Extractor de geometría 3D y metadatos arquitectónicos/estructurales desde FreeCAD (.FCStd)
para las casas de Barbosa (ArquitectonicoBarbosa.FCStd) y Doradal (ArquitectonicoDoradal.FCStd).
Convierte las formas BREP y mallas de FreeCAD a mallas triangulares optimizadas (.npz + .json)
con normales por cara, colores por categoría constructiva y cajas de colisión con vanos de puertas.
"""

import os
import sys
import json
import numpy as np

# Asegurar acceso a las librerías de FreeCAD en Arch Linux
for p in ["/usr/lib/freecad/lib", "/usr/lib/freecad/Mod"]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.append(p)

import FreeCAD

CATEGORY_STYLES = {
    "slab":      {"color": [0.76, 0.75, 0.72, 1.0], "name": "Losas y Pisos de Concreto"},
    "column":    {"color": [0.42, 0.46, 0.52, 1.0], "name": "Columnas Estructurales"},
    "beam":      {"color": [0.48, 0.52, 0.58, 1.0], "name": "Vigas y Correas"},
    "wall":      {"color": [0.86, 0.52, 0.34, 1.0], "name": "Muros de Mampostería / Bloque"},
    "door":      {"color": [0.55, 0.36, 0.20, 1.0], "name": "Puertas y Carpintería"},
    "window":    {"color": [0.55, 0.80, 0.92, 0.55], "name": "Ventanas y Vidrios"},
    "roof":      {"color": [0.30, 0.36, 0.42, 1.0], "name": "Estructura de Cubierta / Cerchas"},
    "railing":   {"color": [0.22, 0.25, 0.28, 1.0], "name": "Barandas y Pasamanos"},
    "sanitary":  {"color": [0.95, 0.96, 0.98, 1.0], "name": "Aparatos Sanitarios"},
    "rebar":     {"color": [0.72, 0.32, 0.18, 1.0], "name": "Acero de Refuerzo (Figuraciones)"},
    "other":     {"color": [0.70, 0.70, 0.70, 1.0], "name": "Otros Elementos"},
}


def classify_object(obj):
    name = obj.Name.lower()
    label = obj.Label.lower()
    ifc = getattr(obj, "IfcType", "").lower()

    if "rebar" in name or "rebar" in label or "stirrup" in label or "reinforcement" in label or "reinforcing" in ifc:
        return "rebar"
    if obj.TypeId == "Mesh::Feature" or "sanitary" in name or "sanitary" in label:
        return "sanitary"
    if name.startswith("window"):
        if "puerta" in label or "door" in ifc:
            return "door"
        return "window"
    if name.startswith("wall") or "muro" in label or "wall" in ifc:
        return "wall"
    if "losa" in label or "piso" in label or "slab" in ifc:
        return "slab"
    if "pasamanos" in label or "poste" in label or "baranda" in label:
        return "railing"
    if "celos" in label or "cercha" in label or "correatecho" in label or ("vigac" in label and "vigacim" not in label):
        return "roof"
    if "columna" in label or ("column" in ifc and "viga" not in label and "correa" not in label):
        return "column"
    if "viga" in label or "correa" in label or "beam" in ifc:
        return "beam"
    return "other"


def should_include_object(obj):
    # Ignorar grupos y contenedores
    if hasattr(obj, "Group") or obj.Name == "Site":
        return False
    # Ignorar uniones booleanas auxiliares de losas en Doradal para evitar Z-fighting
    if obj.TypeId == "Part::MultiFuse":
        return False
    if obj.TypeId in ("Sketcher::SketchObject", "Part::Part2DObjectPython", "App::MaterialObjectPython"):
        return False
    if obj.Name.startswith("Axis") or obj.Name.startswith("Profile") or obj.Name.startswith("Rectangle") or obj.Name.startswith("Wire"):
        return False

    if obj.TypeId == "Mesh::Feature":
        return hasattr(obj, "Mesh") and obj.Mesh and obj.Mesh.CountFacets > 0

    if not hasattr(obj, "Shape") or not obj.Shape or obj.Shape.isNull():
        return False

    bb = obj.Shape.BoundBox
    if not bb.isValid():
        return False

    min_dim = min(bb.XLength, bb.YLength, bb.ZLength)
    if min_dim < 1.0 or len(obj.Shape.Faces) <= 1:
        return False

    return True


def tessellate_object(obj, tolerance=15.0):
    """Extrae triángulos (N, 3, 3) en metros y normales (N, 3) desde un objeto de FreeCAD."""
    if obj.TypeId == "Mesh::Feature":
        mesh = obj.Mesh
        pts = np.array([[p.x, p.y, p.z] for p in mesh.Points], dtype=np.float32) * 0.001
        facets = np.array(mesh.Topology[1], dtype=np.int32)
        if len(facets) == 0:
            return np.zeros((0, 3, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
        tris = pts[facets]
    else:
        verts, faces = obj.Shape.tessellate(tolerance)
        if not verts or not faces:
            return np.zeros((0, 3, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
        pts = np.array([[v.x, v.y, v.z] for v in verts], dtype=np.float32) * 0.001
        facets = np.array(faces, dtype=np.int32)
        tris = pts[facets]

    v0 = tris[:, 0, :]
    v1 = tris[:, 1, :]
    v2 = tris[:, 2, :]
    normals = np.cross(v1 - v0, v2 - v0)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms[norms < 1e-8] = 1.0
    normals = normals / norms
    return tris.astype(np.float32), normals.astype(np.float32)


def subtract_openings_from_wall(wall_bb, openings):
    """
    Divide la caja de colisión 2D de un muro [xmin, xmax, ymin, ymax, zmin, zmax]
    restando los vanos de puertas o ventanales de piso que intersecten el muro.
    """
    segments = [wall_bb]
    dx = wall_bb[1] - wall_bb[0]
    dy = wall_bb[3] - wall_bb[2]
    horizontal_along_x = dx >= dy

    for op in openings:
        new_segments = []
        for seg in segments:
            # Verificar intersección 2D con margen de 0.18 m para el espesor del muro
            ix_min = max(seg[0] - 0.18, op[0])
            ix_max = min(seg[1] + 0.18, op[1])
            iy_min = max(seg[2] - 0.18, op[2])
            iy_max = min(seg[3] + 0.18, op[3])
            if ix_max > ix_min and iy_max > iy_min:
                if horizontal_along_x:
                    # Recortar a lo largo de X
                    cut_min = op[0] - 0.05
                    cut_max = op[1] + 0.05
                    if cut_min > seg[0] + 0.08:
                        new_segments.append([seg[0], min(seg[1], cut_min), seg[2], seg[3], seg[4], seg[5]])
                    if cut_max < seg[1] - 0.08:
                        new_segments.append([max(seg[0], cut_max), seg[1], seg[2], seg[3], seg[4], seg[5]])
                else:
                    # Recortar a lo largo de Y
                    cut_min = op[2] - 0.05
                    cut_max = op[3] + 0.05
                    if cut_min > seg[2] + 0.08:
                        new_segments.append([seg[0], seg[1], seg[2], min(seg[3], cut_min), seg[4], seg[5]])
                    if cut_max < seg[3] - 0.08:
                        new_segments.append([seg[0], seg[1], max(seg[2], cut_max), seg[3], seg[4], seg[5]])
            else:
                new_segments.append(seg)
        segments = new_segments
    return segments


def extract_fcstd(fcstd_path, out_prefix, floor_z_m, extra_openings=None):
    print(f"Extrayendo modelo FreeCAD: {fcstd_path} ...")
    doc = FreeCAD.openDocument(fcstd_path)

    buckets = {cat: {"tris": [], "norms": []} for cat in CATEGORY_STYLES}
    raw_walls = []
    columns_coll = []
    walkable_slabs = []
    openings = list(extra_openings or [])
    object_counts = {cat: 0 for cat in CATEGORY_STYLES}

    # Primero recolectar todas las puertas y ventanales a nivel de piso como vanos transitables
    for obj in doc.Objects:
        if obj.Name.startswith("Window") and hasattr(obj, "Shape") and obj.Shape:
            bb = obj.Shape.BoundBox
            if bb.isValid():
                zmin = bb.ZMin * 0.001
                zmax = bb.ZMax * 0.001
                # Si la base de la puerta/ventanal llega cerca del nivel del piso (+0.35 m), es un vano de paso
                if zmin <= floor_z_m + 0.35 and zmax >= floor_z_m + 1.8:
                    openings.append([
                        bb.XMin * 0.001, bb.XMax * 0.001,
                        bb.YMin * 0.001, bb.YMax * 0.001,
                        zmin, zmax, obj.Label
                    ])

    for obj in doc.Objects:
        if not should_include_object(obj):
            continue

        cat = classify_object(obj)
        # Usar tolerancia más gruesa en barras de refuerzo para mantener altos FPS
        tol = 45.0 if cat == "rebar" else 15.0
        tris, norms = tessellate_object(obj, tolerance=tol)
        if len(tris) == 0:
            continue

        buckets[cat]["tris"].append(tris)
        buckets[cat]["norms"].append(norms)
        object_counts[cat] += 1

        if obj.TypeId != "Mesh::Feature":
            bb = obj.Shape.BoundBox
            box_m = [
                bb.XMin * 0.001, bb.XMax * 0.001,
                bb.YMin * 0.001, bb.YMax * 0.001,
                bb.ZMin * 0.001, bb.ZMax * 0.001,
            ]
            if cat == "wall":
                # Solo colisionar muros que estén a altura de persona (no dinteles altos)
                if box_m[4] < floor_z_m + 1.7 and box_m[5] > floor_z_m + 0.3:
                    raw_walls.append((obj.Label, box_m))
            elif cat == "column":
                if box_m[4] < floor_z_m + 1.8 and box_m[5] > floor_z_m + 0.2:
                    columns_coll.append({"label": obj.Label, "box": box_m})
            elif cat == "slab":
                walkable_slabs.append({"label": obj.Label, "box": box_m})

    # Procesar segmentos de colisión de muros descontando puertas/vanos
    wall_colliders = []
    for label, wbox in raw_walls:
        segs = subtract_openings_from_wall(wbox, openings)
        for s in segs:
            wall_colliders.append({"label": label, "box": s})

    npz_dict = {}
    summary_cats = {}
    total_tris = 0
    for cat, data in buckets.items():
        if data["tris"]:
            t_arr = np.concatenate(data["tris"], axis=0)
            n_arr = np.concatenate(data["norms"], axis=0)
            if cat == "rebar" and len(t_arr) > 18000:
                step = max(1, len(t_arr) // 18000)
                t_arr = t_arr[::step]
                n_arr = n_arr[::step]
        else:
            t_arr = np.zeros((0, 3, 3), dtype=np.float32)
            n_arr = np.zeros((0, 3), dtype=np.float32)
        npz_dict[f"{cat}_tris"] = t_arr
        npz_dict[f"{cat}_norms"] = n_arr
        summary_cats[cat] = {
            "objects": object_counts[cat],
            "triangles": int(len(t_arr)),
            "color": CATEGORY_STYLES[cat]["color"],
            "display_name": CATEGORY_STYLES[cat]["name"],
        }
        total_tris += int(len(t_arr))

    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    np.savez_compressed(f"{out_prefix}_scene.npz", **npz_dict)

    meta = {
        "source_file": os.path.basename(fcstd_path),
        "floor_z": floor_z_m,
        "total_triangles": total_tris,
        "categories": summary_cats,
        "wall_colliders": wall_colliders,
        "column_colliders": columns_coll,
        "walkable_slabs": walkable_slabs,
        "openings": [
            {"label": op[6], "box": op[:6]} for op in openings
        ],
    }
    with open(f"{out_prefix}_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    FreeCAD.closeDocument(doc.Name)
    print(f"  -> Guardado {out_prefix}_scene.npz ({total_tris} triángulos) y {out_prefix}_meta.json ({len(wall_colliders)} segmentos de muro, {len(openings)} vanos).")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # 1. Casa Barbosa: Piso principal sobre losa nivel Z = 1.32 m
    barbosa_fc = os.path.join(base_dir, "ArquitectonicoBarbosa.FCStd")
    if os.path.exists(barbosa_fc):
        extract_fcstd(
            barbosa_fc,
            os.path.join(assets_dir, "barbosa"),
            floor_z_m=1.32,
            extra_openings=[],
        )

    # 2. Casa Doradal: Piso principal sobre losa nivel Z = 0.10 m
    # Agregamos vanos de paso de obra en muros internos aún sin puerta modelada para permitir recorrer todos los salones
    doradal_fc = os.path.join(base_dir, "ArquitectonicoDoradal.FCStd")
    if os.path.exists(doradal_fc):
        doradal_extra_openings = [
            # Paso frontal al módulo central (MuroP1009)
            [6.60, 7.80, -0.05, 0.15, 0.10, 2.30, "VanoObraCentralFrente"],
            # Paso interior entre módulo 1 (Montallantas) y módulo 2 (MuroP1007)
            [4.60, 4.82, 2.10, 3.20, 0.10, 2.30, "VanoObraMod1Mod2"],
            # Paso interior entre módulo 2 y módulo 3 (MuroP1010)
            [9.74, 9.95, 2.10, 3.20, 0.10, 2.30, "VanoObraMod2Mod3"],
            # Paso interior en MuroSucesion hacia zona restaurante/apartamento
            [12.35, 12.55, 2.10, 3.20, 0.10, 2.30, "VanoObraSucesion1"],
            [12.35, 12.55, 5.30, 6.30, 0.10, 2.30, "VanoObraSucesion2"],
        ]
        extract_fcstd(
            doradal_fc,
            os.path.join(assets_dir, "doradal"),
            floor_z_m=0.10,
            extra_openings=doradal_extra_openings,
        )


if __name__ == "__main__":
    main()
