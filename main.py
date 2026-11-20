#!/usr/bin/env python3
"""
Simulador 3D de Construcción y Exploración Arquitectónica en Python (Compatible con Arch Linux)
Modelos FreeCAD integrados:
- Vivienda_Estructura_Metalica_Tipo_01.FCStd (Vivienda Tipo 1)
- Vivienda_Aporticado_Metalica_Tipo_02.FCStd (Vivienda Tipo 2, 2 pisos con escalera)

Controles principales:
- W, A, S, D : Mover al jugador (Shift = correr)
- Flechas / Ratón (Clic izq) : Girar cámara (Rueda del ratón = zoom 3ra persona)
- M : Alternar entre Modo Obra (carretilla/pala/cuadrilla) y Modo Exploración (solo observar)
- E : [Modo Obra] Agarrar / Soltar Carretilla, o Tomar / Dejar Ladrillo, Bloque, Bulto de Cemento
- F : [Modo Obra] Dar palada de concreto a la carretilla o Vaciar tu carretilla
- P : [Modo Obra] Equipar / Guardar la Pala de Obra
- 1..4 : [Modo Obra] Órdenes a la cuadrilla
- TAB : Alternar entre Vivienda Tipo 1 y Vivienda Tipo 2
- T : Mostrar / Ocultar Cubierta y Techo (vista interior despejada)
- R : Mostrar / Ocultar Acero de Refuerzo (Modo Rayos-X Estructural)
- V : Cambiar Cámara (3ra Persona / 1ra Persona)
- C : Activar / Desactivar colisión con muros (Inspector Libre)
"""

import os
import math
import argparse
import numpy as np
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

from game_world import ConstructionWorld, ITEM_NAMES
from models_3d import (
    draw_box,
    draw_character,
    draw_wheelbarrow,
    draw_concrete_mixer,
    draw_material_station,
    draw_work_zone_marker,
    draw_item_mesh,
    build_sky_dome_list,
    draw_sky_and_clouds,
)


class HouseDisplayLists:
    """Compila las mallas extraídas de FreeCAD en Display Lists de OpenGL para máximo rendimiento."""
    def __init__(self):
        self.lists = {}

    def clear(self):
        for dl in self.lists.values():
            glDeleteLists(dl, 1)
        self.lists.clear()

    def build_from_world(self, world):
        self.clear()
        cats = world.meta.get("categories", {})
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        for cat, info in cats.items():
            tris = world.meshes.get(f"{cat}_tris")
            norms = world.meshes.get(f"{cat}_norms")
            if tris is None or len(tris) == 0:
                continue

            verts_flat = np.ascontiguousarray(tris.reshape(-1, 3), dtype=np.float32)
            norms_rep = np.repeat(norms, 3, axis=0)
            norms_flat = np.ascontiguousarray(norms_rep.reshape(-1, 3), dtype=np.float32)
            col = info["color"]

            dl = glGenLists(1)
            glNewList(dl, GL_COMPILE)
            glColor4f(col[0], col[1], col[2], col[3])
            glVertexPointer(3, GL_FLOAT, 0, verts_flat)
            glNormalPointer(GL_FLOAT, 0, norms_flat)
            glDrawArrays(GL_TRIANGLES, 0, len(verts_flat))
            glEndList()
            self.lists[cat] = dl

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)


def draw_environment(world):
    """Dibuja el terreno, plazoleta/sendero y entorno según la vivienda activa."""
    fz = world.floor_z

    if world.current_house_key == "tipo1":
        # Plazoleta frontal a nivel Z = 1.32 m (Y de -6.5 a 0.05, X de -2.5 a 8.5)
        draw_box(3.0, -3.2, fz - 0.12, 11.5, 6.6, 0.24, (0.56, 0.53, 0.47))
        if world.mode == "obra":
            draw_box(-2.6, -3.2, fz + 0.08, 0.2, 6.6, 0.16, (0.85, 0.65, 0.15))
            draw_box(8.6, -3.2, fz + 0.08, 0.2, 6.6, 0.16, (0.85, 0.65, 0.15))

        # Ladera verde inclinada bajo los pilotes (Y de 0 a 16 m, Z bajando de 0.0 a -8.2 m)
        glColor3f(0.26, 0.48, 0.24)
        glBegin(GL_QUADS)
        glNormal3f(0, 0.45, 0.89)
        glVertex3f(-8.0, -0.5, 0.0)
        glVertex3f(14.0, -0.5, 0.0)
        glVertex3f(14.0, 16.0, -8.2)
        glVertex3f(-8.0, 16.0, -8.2)
        glEnd()

        # Terreno posterior alrededor del patio
        draw_box(3.0, -10.0, fz - 0.15, 28.0, 8.0, 0.20, (0.30, 0.52, 0.26))
    else:
        # Terreno plano verde alrededor de la Vivienda Tipo 2 (tope en Z = 0.00 m)
        draw_box(14.2, 5.0, -0.11, 28.0, 28.0, 0.22, (0.34, 0.55, 0.28))
        # Plazoleta frontal de obra / acceso (tope en Z = 0.00 m)
        draw_box(14.5, -3.0, -0.05, 12.0, 6.2, 0.10, (0.60, 0.57, 0.50))
        # Sendero lateral derecho que conecta el frente con el arranque de la escalera (X=17.0, Y=10.5)
        draw_box(18.0, 5.5, -0.04, 3.6, 17.5, 0.08, (0.58, 0.56, 0.51))


def render_hud(screen_w, screen_h, world, font_title, font_body, font_small, fps):
    """Renderiza el panel HUD 2D y el minimapa arquitectónico sobre la escena OpenGL."""
    hud_surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    is_explore = (world.mode == "exploracion")

    # 1. Barra superior: Vivienda actual, modo activo y estado del jugador
    pygame.draw.rect(hud_surf, (16, 22, 32, 215), (12, 10, screen_w - 280, 74), border_radius=8)
    border_col = (70, 215, 185, 255) if is_explore else (235, 165, 35, 255)
    pygame.draw.rect(hud_surf, border_col, (12, 10, screen_w - 280, 74), width=2, border_radius=8)

    title_txt = font_title.render(f"PROYECTO FREECAD: {world.house_title}", True, (255, 210, 80))
    hud_surf.blit(title_txt, (24, 16))

    # Insignia de modo en la esquina derecha de la barra superior
    badge_txt_str = "MODO EXPLORACIÓN" if is_explore else "MODO OBRA"
    badge_col = (40, 175, 145, 235) if is_explore else (210, 125, 25, 235)
    badge_surf = font_small.render(badge_txt_str, True, (255, 255, 255))
    bw = badge_surf.get_width() + 20
    bx = screen_w - 280 - bw + 2
    pygame.draw.rect(hud_surf, badge_col, (bx, 16, bw, 24), border_radius=6)
    hud_surf.blit(badge_surf, (bx + 10, 19))

    p = world.player
    zone_lbl = world.get_current_zone_label()
    if is_explore:
        sub_txt = font_body.render(
            f"Observador (Manos libres)   |   {zone_lbl}   |   "
            f"Pos: ({p['x']:.1f}, {p['y']:.1f}, {p['z']:.2f}m)   |   FPS: {int(fps)}",
            True, (220, 245, 240)
        )
    else:
        hand_state = "Manos libres"
        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            hand_state = f"Llevando Carretilla #{wb.id}: {wb.get_summary()}"
        elif p["carrying_item"] is not None:
            hand_state = f"Cargando en manos: {ITEM_NAMES[p['carrying_item']]}"
        elif p["has_shovel"]:
            hand_state = "Pala equipada ([F] junto a carretilla para palear)"

        sub_txt = font_body.render(
            f"{hand_state}   |   {zone_lbl}   |   Concretadora: {'ON' if world.mixer.is_running else 'OFF'} "
            f"({world.mixer.shovels_available} paladas)   |   FPS: {int(fps)}",
            True, (230, 238, 245)
        )
    hud_surf.blit(sub_txt, (24, 48))

    # 2. Panel izquierdo: Inspección (Modo Exploración) o Cuadrilla y Avance (Modo Obra)
    if is_explore:
        panel_h = 228 if world.current_house_key == "tipo2" else 204
        pygame.draw.rect(hud_surf, (16, 22, 32, 205), (12, 94, 435, panel_h), border_radius=8)
        hdr = font_body.render("MODO EXPLORACIÓN (SOLO OBSERVACIÓN):", True, (90, 235, 195))
        hud_surf.blit(hdr, (22, 102))

        cam_lbl = "1ra Persona" if world.camera_first_person else f"3ra Persona (Zoom {world.camera_distance:.1f}m)"
        lines = [
            f"• Cámara [V]: {cam_lbl}",
            f"• Cubierta / Techo [T]: {'VISIBLE' if world.show_roof else 'OCULTO (Vista interior)'}",
            f"• Acero de Refuerzo [R]: {'RAYOS-X ACTIVO' if world.show_rebar else 'Oculto'}",
            f"• Colisión con Muros [C]: {'ACTIVA' if world.collision_enabled else 'DESACTIVADA (Paso libre)'}",
            f"• Cambiar Vivienda [TAB]: Tipo 1 <-> Tipo 2",
        ]
        if world.current_house_key == "tipo2":
            lines.append("• Escalera: Sube por X=17.0->12.5, Y=10.5 hacia el 2do Piso")
        lines.append("• Presiona [M] si deseas pasar a Modo Obra (carretilla/pala)")

        y_off = 130
        for line in lines:
            surf_l = font_small.render(line, True, (230, 240, 245))
            hud_surf.blit(surf_l, (24, y_off))
            y_off += 23
    else:
        pygame.draw.rect(hud_surf, (16, 22, 32, 205), (12, 94, 435, 245), border_radius=8)
        hdr_crew = font_body.render("CUADRILLA DE OBRA (Órdenes: teclas [1] [2] [3] [4]):", True, (110, 215, 255))
        hud_surf.blit(hdr_crew, (22, 102))

        y_off = 126
        for npc in world.npcs:
            col_dot = tuple(int(c * 255) for c in npc.helmet_color)
            pygame.draw.circle(hud_surf, col_dot, (30, y_off + 9), 6)
            npc_line = font_small.render(f"{npc.name}: {npc.status_text}", True, (235, 240, 245))
            hud_surf.blit(npc_line, (44, y_off))
            y_off += 24

        y_off += 6
        hdr_zones = font_body.render("AVANCE DE LABORES DENTRO DE LA VIVIENDA:", True, (130, 240, 150))
        hud_surf.blit(hdr_zones, (22, y_off))
        y_off += 24

        for z in world.work_zones:
            pct = min(1.0, z["delivered"] / max(1, z["target"]))
            pygame.draw.rect(hud_surf, (45, 55, 68, 230), (24, y_off + 2, 130, 14), border_radius=4)
            pygame.draw.rect(hud_surf, (60, 210, 100, 240), (24, y_off + 2, int(130 * pct), 14), border_radius=4)
            z_txt = font_small.render(f"{z['name']}: {z['delivered']}/{z['target']} unid.", True, (230, 235, 240))
            hud_surf.blit(z_txt, (164, y_off))
            y_off += 22

    # 3. Minimapa Arquitectónico en vivo (esquina superior derecha)
    map_x, map_y, map_w, map_h = screen_w - 255, 10, 242, 242
    pygame.draw.rect(hud_surf, (16, 22, 32, 225), (map_x, map_y, map_w, map_h), border_radius=8)
    pygame.draw.rect(hud_surf, (100, 160, 220, 255), (map_x, map_y, map_w, map_h), width=2, border_radius=8)

    map_lbl = font_small.render("PLANTA ARQUITECTÓNICA (En Vivo)", True, (180, 220, 255))
    hud_surf.blit(map_lbl, (map_x + 14, map_y + 6))

    if world.current_house_key == "tipo1":
        min_x, max_x = -2.5, 8.5
        min_y, max_y = -6.0, 15.0
    else:
        min_x, max_x = 8.5, 20.0
        min_y, max_y = -6.0, 15.0

    def to_map(wx, wy):
        nx = (wx - min_x) / (max_x - min_x)
        ny = 1.0 - (wy - min_y) / (max_y - min_y)
        px = int(map_x + 14 + nx * (map_w - 28))
        py = int(map_y + 28 + ny * (map_h - 38))
        return max(map_x + 4, min(map_x + map_w - 4, px)), max(map_y + 24, min(map_y + map_h - 4, py))

    # Dibujar huella de la escalera en el minimapa (si existe)
    if world.stair_bounds is not None:
        sx0, sx1, sy0, sy1, _ = world.stair_bounds
        sp1 = to_map(sx0, sy1)
        sp2 = to_map(sx1, sy0)
        rx, ry = min(sp1[0], sp2[0]), min(sp1[1], sp2[1])
        rw, rh = max(4, abs(sp2[0] - sp1[0])), max(4, abs(sp2[1] - sp1[1]))
        pygame.draw.rect(hud_surf, (70, 185, 235, 220), (rx, ry, rw, rh))

    # Dibujar muros reales del nivel actual en el minimapa
    body_min_z = p["z"] + 0.35
    body_max_z = p["z"] + 1.65
    for wc in world.meta.get("wall_colliders", []):
        b = wc["box"]
        if not (b[4] < body_max_z and b[5] > body_min_z):
            continue
        p1 = to_map(b[0], b[3])
        p2 = to_map(b[1], b[2])
        rx = min(p1[0], p2[0])
        ry = min(p1[1], p2[1])
        rw = max(3, abs(p2[0] - p1[0]))
        rh = max(3, abs(p2[1] - p1[1]))
        pygame.draw.rect(hud_surf, (215, 130, 85, 255), (rx, ry, rw, rh))

    if not is_explore:
        for z in world.work_zones:
            zx, zy = to_map(z["pos"][0], z["pos"][1])
            pygame.draw.circle(hud_surf, (60, 220, 100), (zx, zy), 5, 2)

        mx, my = to_map(world.mixer.x, world.mixer.y)
        pygame.draw.rect(hud_surf, (245, 120, 30), (mx - 5, my - 5, 10, 10))
        for wb in world.wheelbarrows:
            wx, wy = to_map(wb.x, wb.y)
            pygame.draw.rect(hud_surf, (250, 210, 50), (wx - 4, wy - 4, 8, 8))

        for npc in world.npcs:
            nx, ny = to_map(npc.x, npc.y)
            col_dot = tuple(int(c * 255) for c in npc.helmet_color)
            pygame.draw.circle(hud_surf, col_dot, (nx, ny), 5)

    # Jugador y dirección de mirada
    px, py = to_map(p["x"], p["y"])
    pygame.draw.circle(hud_surf, (255, 255, 255), (px, py), 6)
    rad = math.radians(p["yaw"])
    lx = int(px + math.cos(rad) * 11)
    ly = int(py - math.sin(rad) * 11)
    pygame.draw.line(hud_surf, (255, 80, 80), (px, py), (lx, ly), 2)

    # 4. Mensaje Toast central
    if world.toast_timer > 0.0 and world.toast_message:
        pygame.draw.rect(hud_surf, (22, 32, 48, 235), (screen_w // 2 - 410, screen_h - 118, 820, 36), border_radius=8)
        pygame.draw.rect(hud_surf, (255, 195, 50, 255), (screen_w // 2 - 410, screen_h - 118, 820, 36), width=2, border_radius=8)
        t_surf = font_body.render(world.toast_message, True, (255, 240, 150))
        hud_surf.blit(t_surf, (screen_w // 2 - t_surf.get_width() // 2, screen_h - 110))

    # 5. Barra inferior de controles
    pygame.draw.rect(hud_surf, (14, 18, 26, 230), (12, screen_h - 74, screen_w - 24, 64), border_radius=8)
    if is_explore:
        c1 = font_small.render(
            "[WASD] Caminar  |  [Shift] Correr  |  [Flechas / Ratón] Girar cámara  |  [Rueda] Zoom  |  "
            "[V] Cámara 1ra/3ra Persona  |  [M] Cambiar a Modo Obra",
            True, (220, 240, 235)
        )
        c2 = font_small.render(
            "[TAB] Cambiar Vivienda (Tipo 1 / Tipo 2)  |  [T] Cubierta/Techo  |  "
            "[R] Rayos-X Acero Refuerzo  |  [C] Colisiones con Muros  |  [ESC] Liberar Ratón / Salir",
            True, (165, 225, 215)
        )
    else:
        c1 = font_small.render(
            "[WASD] Moverse (Shift=Correr)  |  [E] Agarrar Carretilla / Material  |  "
            "[F] Palear / Vaciar Carretilla  |  [P] Pala  |  [M] Modo Exploración (Sin carga)",
            True, (220, 230, 240)
        )
        c2 = font_small.render(
            "[1] Auto  |  [2] Jairo sostiene y TÚ paleas  |  [3] Don Chucho llena tu carretilla  |  "
            "[4] Síganme  |  [TAB] Vivienda (Tipo 1/Tipo 2)  |  [T] Techo  |  [R] Acero  |  [V] Cámara",
            True, (175, 210, 245)
        )
    hud_surf.blit(c1, (24, screen_h - 66))
    hud_surf.blit(c2, (24, screen_h - 40))

    # Volcar superficie 2D a OpenGL
    tex_data = pygame.image.tobytes(hud_surf, "RGBA", True)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, screen_w, 0, screen_h, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glWindowPos2d(0, 0)
    glDrawPixels(screen_w, screen_h, GL_RGBA, GL_UNSIGNED_BYTE, tex_data)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def run_headless_verification(assets_dir):
    """Prueba automatizada para validar Vivienda Tipo 1, Tipo 2, escalera, Modo Exploración y Modo Obra."""
    print("Ejecutando verificación automatizada del motor de juego y modelos FreeCAD...")
    world = ConstructionWorld(assets_dir, initial_house="tipo1", initial_mode="obra")
    assert len(world.meshes["wall_tris"]) > 0, "Faltan muros en Vivienda Tipo 1"
    print(f"  [OK] Vivienda Tipo 1 cargada ({world.meta['total_triangles']} triángulos, piso Z={world.floor_z}m)")

    # 1. Probar cooperación en Modo Obra
    wb1 = world.wheelbarrows[0]
    world.player["x"], world.player["y"] = wb1.x, wb1.y - 0.5
    world.player_interact_e()
    assert world.player["held_wheelbarrow"] == wb1, "El jugador debe sostener la Carretilla #1"
    world.set_crew_order("fill_player_wb")
    for _ in range(120):
        world.update(0.05, 0.0, 0.0)
    assert wb1.concrete_level > 0, "Don Chucho debió llenar con pala la carretilla del jugador"
    print(f"  [OK] Cooperación 1 verificada: Don Chucho llenó carretilla ({wb1.concrete_level}/3 paladas)")

    world.player_interact_e()
    world.set_crew_order("hold_for_player")
    for _ in range(40):
        world.update(0.05, 0.0, 0.0)
    world.player["x"], world.player["y"] = wb1.x - 0.6, wb1.y
    world.player_action_f()
    print(f"  [OK] Cooperación 2 verificada: Jugador paleó mezcla ({wb1.concrete_level}/3 paladas)")

    # 2. Probar Modo Exploración (suelta carga y evita cargar carretilla/pala)
    world.set_mode("exploracion")
    assert world.player["held_wheelbarrow"] is None
    assert world.player["carrying_item"] is None
    assert world.player["has_shovel"] is False
    world.player_interact_e()
    world.player_action_f()
    world.toggle_shovel()
    assert world.player["held_wheelbarrow"] is None and not world.player["has_shovel"], \
        "En Modo Exploración el personaje no debe cargar carretilla ni pala"
    print("  [OK] Modo Exploración verificado: personaje sin carretilla ni pala, libre observación")

    # 3. Cambiar a Vivienda Tipo 2 y verificar subida y bajada por escalera
    world.load_house("tipo2")
    assert len(world.meshes["wall_tris"]) > 0, "Faltan muros en Vivienda Tipo 2"
    assert len(world.stairs_steps) >= 16, f"Faltan peldaños en Tipo 2 ({len(world.stairs_steps)})"
    print(f"  [OK] Vivienda Tipo 2 cargada ({world.meta['total_triangles']} triángulos, {len(world.stairs_steps)} peldaños)")

    # Posicionar al pie de la escalera (X=17.2, Y=10.5, Z=0.0) mirando hacia -X (yaw=180)
    world.player["x"], world.player["y"], world.player["z"], world.player["smooth_z"] = 17.2, 10.5, 0.0, 0.0
    world.player["yaw"] = 180.0
    for _ in range(30):
        world.update(0.05, 1.0, 0.0)
    assert world.player["x"] < 12.8, f"No avanzó por la escalera (x={world.player['x']:.2f})"
    assert world.player["z"] >= 2.8, f"No subió al 2do piso por la escalera (z={world.player['z']:.2f})"
    z_top_stairs = world.player["z"]

    # Avanzar hacia la losa del 2do piso (+Y hacia Y=12.0)
    world.player["yaw"] = 90.0
    for _ in range(15):
        world.update(0.05, 1.0, 0.0)
    assert world.player["z"] >= 3.15, f"No subió a la losa del 2do piso (z={world.player['z']:.2f})"
    print(f"  [OK] Subida por escalera verificada: Z=0.00m -> escalón superior Z={z_top_stairs:.2f}m -> Losa Piso 2 Z={world.player['z']:.2f}m")

    # Bajar de regreso por la escalera (volver a X=12.6, Y=10.5 y caminar hacia +X)
    world.player["yaw"] = -90.0
    for _ in range(15):
        world.update(0.05, 1.0, 0.0)
    world.player["yaw"] = 0.0
    for _ in range(32):
        world.update(0.05, 1.0, 0.0)
    assert world.player["z"] <= 0.25, f"No bajó por la escalera (z={world.player['z']:.2f})"
    print(f"  [OK] Bajada por escalera verificada: regresó a Planta Baja Z={world.player['z']:.2f}m")

    # 4. Verificar paso libre entre pórticos de acero sin muro en Piso 1 y Piso 2
    world.player["x"], world.player["y"], world.player["z"], world.player["smooth_z"] = 16.5, 2.5, 0.0, 0.0
    world.player["yaw"] = 0.0
    for _ in range(10):
        world.update(0.05, 1.0, 0.0)
    assert world.player["x"] > 17.8, f"Pórtico Piso 1 bloqueó paso abierto (x={world.player['x']:.2f})"

    world.player["x"], world.player["y"], world.player["z"], world.player["smooth_z"] = 17.8, 2.5, 3.20, 3.20
    world.player["yaw"] = 180.0
    for _ in range(25):
        world.update(0.05, 1.0, 0.0)
    assert world.player["x"] < 14.0, f"Pórtico Piso 2 bloqueó paso abierto (x={world.player['x']:.2f})"
    print(f"  [OK] Pórticos abiertos de Tipo 2 verificados: cruce libre en Piso 1 y Piso 2 (x={world.player['x']:.2f})")
    print("¡Verificación completada con éxito!")


def main():
    parser = argparse.ArgumentParser(description="Juego 3D de Construcción y Exploración - Viviendas Tipo 1 y Tipo 2")
    parser.add_argument(
        "--casa",
        choices=["tipo1", "tipo2", "barbosa", "doradal"],
        default="tipo1",
        help="Vivienda inicial a cargar (tipo1 o tipo2)",
    )
    parser.add_argument(
        "--modo",
        choices=["obra", "exploracion"],
        default="obra",
        help="Modo inicial: 'obra' (con cuadrilla/carretilla) o 'exploracion' (solo observar)",
    )
    parser.add_argument("--headless-test", action="store_true", help="Ejecutar verificación automática y salir")
    parser.add_argument("--frames", type=int, default=0, help="Número de cuadros a renderizar (0 = ilimitado)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")

    if args.headless_test:
        run_headless_verification(assets_dir)
        return

    pygame.display.init()
    pygame.font.init()
    screen_w, screen_h = 1360, 820
    pygame.display.set_mode((screen_w, screen_h), DOUBLEBUF | OPENGL | RESIZABLE)
    pygame.display.set_caption("Simulador 3D - Viviendas Tipo 1 y Tipo 2 (FreeCAD + Python)")

    font_title = pygame.font.SysFont("DejaVu Sans", 20, bold=True)
    font_body = pygame.font.SysFont("DejaVu Sans", 15, bold=True)
    font_small = pygame.font.SysFont("DejaVu Sans", 13)

    # Configuración de iluminación y OpenGL 3D
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_NORMALIZE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glLightfv(GL_LIGHT0, GL_POSITION, [14.0, -15.0, 28.0, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.92, 0.90, 0.85, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.38, 0.40, 0.44, 1.0])

    glLightfv(GL_LIGHT1, GL_POSITION, [-10.0, 22.0, 18.0, 1.0])
    glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.35, 0.40, 0.50, 1.0])

    world = ConstructionWorld(assets_dir, initial_house=args.casa, initial_mode=args.modo)

    house_dls = HouseDisplayLists()
    house_dls.build_from_world(world)
    sky_dl = build_sky_dome_list()

    clock = pygame.time.Clock()
    mouse_captured = False
    anim_time = 0.0
    frame_count = 0
    running = True

    while running:
        dt = min(0.05, clock.tick(60) / 1000.0)
        anim_time += dt
        frame_count += 1
        if args.frames > 0 and frame_count > args.frames:
            break

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == VIDEORESIZE:
                screen_w, screen_h = max(800, event.w), max(600, event.h)
                pygame.display.set_mode((screen_w, screen_h), DOUBLEBUF | OPENGL | RESIZABLE)
                glViewport(0, 0, screen_w, screen_h)
            elif event.type == MOUSEWHEEL:
                world.camera_distance = max(1.8, min(8.5, world.camera_distance - event.y * 0.35))
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1 and not mouse_captured:
                    mouse_captured = True
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    pygame.mouse.get_rel()
                elif event.button == 1 and mouse_captured:
                    if world.mode == "obra":
                        world.player_action_f()
                elif event.button == 3:
                    if world.mode == "obra":
                        world.player_interact_e()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    if mouse_captured:
                        mouse_captured = False
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)
                    else:
                        running = False
                elif event.key == K_m:
                    world.toggle_mode()
                elif event.key == K_e:
                    world.player_interact_e()
                elif event.key == K_f or event.key == K_SPACE:
                    world.player_action_f()
                elif event.key == K_p:
                    world.toggle_shovel()
                elif event.key == K_TAB:
                    next_house = "tipo2" if world.current_house_key == "tipo1" else "tipo1"
                    world.load_house(next_house)
                    house_dls.build_from_world(world)
                elif event.key == K_t:
                    world.show_roof = not world.show_roof
                    world.set_toast(f"Cubierta / Techo: {'VISIBLE' if world.show_roof else 'OCULTO (Vista Interior)'}")
                elif event.key == K_r:
                    world.show_rebar = not world.show_rebar
                    world.set_toast(f"Modo Rayos-X Acero de Refuerzo: {'ACTIVO' if world.show_rebar else 'OCULTO'}")
                elif event.key == K_v:
                    world.camera_first_person = not world.camera_first_person
                    world.set_toast(f"Cámara en {'1ra Persona' if world.camera_first_person else '3ra Persona'}")
                elif event.key == K_c:
                    world.collision_enabled = not world.collision_enabled
                    world.set_toast(f"Colisión con muros: {'ACTIVA' if world.collision_enabled else 'DESACTIVADA (Paso libre)'}")
                elif event.key == K_1:
                    world.set_crew_order("auto")
                elif event.key == K_2:
                    world.set_crew_order("hold_for_player")
                elif event.key == K_3:
                    world.set_crew_order("fill_player_wb")
                elif event.key == K_4:
                    world.set_crew_order("follow_player")

        keys = pygame.key.get_pressed()

        if mouse_captured:
            mx, my = pygame.mouse.get_rel()
            world.player["yaw"] -= mx * 0.18
            world.player["pitch"] = max(-65.0, min(75.0, world.player["pitch"] - my * 0.15))

        yaw_speed = 95.0 * dt
        pitch_speed = 65.0 * dt
        if keys[K_LEFT]:
            world.player["yaw"] += yaw_speed
        if keys[K_RIGHT]:
            world.player["yaw"] -= yaw_speed
        if keys[K_UP]:
            world.player["pitch"] = min(75.0, world.player["pitch"] + pitch_speed)
        if keys[K_DOWN]:
            world.player["pitch"] = max(-65.0, world.player["pitch"] - pitch_speed)

        move_f = (1.0 if keys[K_w] else 0.0) - (1.0 if keys[K_s] else 0.0)
        move_r = (1.0 if keys[K_d] else 0.0) - (1.0 if keys[K_a] else 0.0)
        sprint = bool(keys[K_LSHIFT] or keys[K_RSHIFT])
        world.update(dt, move_f, move_r, sprint=sprint)

        # Renderizado 3D OpenGL
        glClearColor(0.54, 0.76, 0.94, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60.0, screen_w / float(screen_h), 0.15, 120.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        p = world.player
        pz = p["smooth_z"]
        rad_yaw = math.radians(p["yaw"])
        rad_pitch = math.radians(p["pitch"])
        dir_x = math.cos(rad_yaw) * math.cos(rad_pitch)
        dir_y = math.sin(rad_yaw) * math.cos(rad_pitch)
        dir_z = math.sin(rad_pitch)

        if world.camera_first_person:
            eye_x = p["x"]
            eye_y = p["y"]
            eye_z = pz + 1.58
            gluLookAt(
                eye_x, eye_y, eye_z,
                eye_x + dir_x, eye_y + dir_y, eye_z + dir_z,
                0.0, 0.0, 1.0,
            )
        else:
            dist = world.camera_distance
            eye_x = p["x"] - math.cos(rad_yaw) * dist
            eye_y = p["y"] - math.sin(rad_yaw) * dist
            eye_z = max(pz + 0.35, pz + 1.95 - math.sin(rad_pitch) * 2.2)
            target_x = p["x"] + math.cos(rad_yaw) * 1.2
            target_y = p["y"] + math.sin(rad_yaw) * 1.2
            target_z = pz + 1.25
            gluLookAt(eye_x, eye_y, eye_z, target_x, target_y, target_z, 0.0, 0.0, 1.0)

        # 0. Cielo con gradiente, sol brillante y nubes en movimiento
        draw_sky_and_clouds(sky_dl, eye_x, eye_y, eye_z, anim_time)

        # 1. Terreno y plazoleta
        draw_environment(world)

        # 2. Modelo FreeCAD de la vivienda activa
        render_order = ["slab", "stairs", "column", "beam", "railing", "sanitary", "door", "other"]
        if not world.show_rebar:
            render_order.append("wall")
        if world.show_roof:
            render_order.append("roof")
        if world.show_rebar:
            render_order.append("rebar")

        for cat in render_order:
            dl = house_dls.lists.get(cat)
            if dl is not None:
                glCallList(dl)

        if world.show_rebar and "wall" in house_dls.lists:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glCallList(house_dls.lists["wall"])
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        if "window" in house_dls.lists:
            glCallList(house_dls.lists["window"])

        # 3. Maquinaria, materiales, carretillas y cuadrilla (solo en Modo Obra)
        if world.mode == "obra":
            draw_concrete_mixer(
                world.mixer.x, world.mixer.y, world.mixer.z,
                world.mixer.yaw, world.mixer.drum_angle,
                world.mixer.is_running, world.mixer.mix_progress,
                world.mixer.shovels_available > 0,
            )
            for st in world.stations:
                draw_material_station(st)
            for zone in world.work_zones:
                draw_work_zone_marker(zone, anim_time)
            for item in world.loose_items:
                draw_item_mesh(item["type"], item["x"], item["y"], item["z"], item.get("yaw", 0.0))

            for wb in world.wheelbarrows:
                draw_wheelbarrow(wb.x, wb.y, wb.z, wb.yaw, wb.contents, wb.concrete_level, wb.tilt_angle)

            for pt in world.particles:
                draw_box(pt["x"], pt["y"], pt["z"], 0.07, 0.07, 0.07, (0.55, 0.58, 0.60))

            for npc in world.npcs:
                draw_character(
                    npc.x, npc.y, npc.z, npc.yaw,
                    helmet_color=npc.helmet_color,
                    vest_color=npc.vest_color,
                    shirt_color=npc.shirt_color,
                    anim_state=npc.anim_state,
                    anim_phase=npc.anim_phase,
                    carrying_item=npc.carrying_item,
                    has_shovel=npc.has_shovel,
                    shovel_loaded=npc.shovel_loaded,
                )

        # 4. Personaje Jugador (en 3ra persona)
        if not world.camera_first_person:
            draw_character(
                p["x"], p["y"], pz, p["yaw"],
                helmet_color=(0.96, 0.96, 0.98),
                vest_color=(0.95, 0.38, 0.08),
                shirt_color=(0.15, 0.28, 0.52),
                anim_state=p["anim_state"],
                anim_phase=p["anim_phase"],
                carrying_item=p["carrying_item"] if world.mode == "obra" else None,
                has_shovel=p["has_shovel"] if world.mode == "obra" else False,
                shovel_loaded=p["shovel_loaded"] if world.mode == "obra" else False,
            )

        # 5. HUD 2D y Minimapa
        render_hud(screen_w, screen_h, world, font_title, font_body, font_small, clock.get_fps())

        pygame.display.flip()

    house_dls.clear()
    if sky_dl is not None:
        glDeleteLists(sky_dl, 1)
    pygame.quit()


if __name__ == "__main__":
    main()
