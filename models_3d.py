#!/usr/bin/env python3
"""
Diseño y renderizado 3D en OpenGL de:
- Personajes articulados (Jugador Ingeniero/Maestro y 3 Obreros Ayudantes con cascos y chalecos)
- Concretadora (Mezcladora de trompo rotatorio e inclinable)
- Carretillas de obra (con carga dinámica de concreto, ladrillos, bloques o bultos)
- Ladrillos de arcilla, Bloques de concreto con celdas, Bultos de cemento de 50kg, Palas, Estibas y Pilas de Arena.
"""

import math
from OpenGL.GL import *


def draw_box(cx, cy, cz, dx, dy, dz, color):
    """Dibuja un paralelepípedo centrado en (cx, cy, cz) con dimensiones (dx, dy, dz)."""
    hx, hy, hz = dx * 0.5, dy * 0.5, dz * 0.5
    glColor4f(color[0], color[1], color[2], color[3] if len(color) > 3 else 1.0)
    glBegin(GL_QUADS)
    # +Z (Arriba)
    glNormal3f(0, 0, 1)
    glVertex3f(cx - hx, cy - hy, cz + hz)
    glVertex3f(cx + hx, cy - hy, cz + hz)
    glVertex3f(cx + hx, cy + hy, cz + hz)
    glVertex3f(cx - hx, cy + hy, cz + hz)
    # -Z (Abajo)
    glNormal3f(0, 0, -1)
    glVertex3f(cx - hx, cy + hy, cz - hz)
    glVertex3f(cx + hx, cy + hy, cz - hz)
    glVertex3f(cx + hx, cy - hy, cz - hz)
    glVertex3f(cx - hx, cy - hy, cz - hz)
    # +Y (Frente)
    glNormal3f(0, 1, 0)
    glVertex3f(cx - hx, cy + hy, cz - hz)
    glVertex3f(cx - hx, cy + hy, cz + hz)
    glVertex3f(cx + hx, cy + hy, cz + hz)
    glVertex3f(cx + hx, cy + hy, cz - hz)
    # -Y (Atrás)
    glNormal3f(0, -1, 0)
    glVertex3f(cx + hx, cy - hy, cz - hz)
    glVertex3f(cx + hx, cy - hy, cz + hz)
    glVertex3f(cx - hx, cy - hy, cz + hz)
    glVertex3f(cx - hx, cy - hy, cz - hz)
    # +X (Derecha)
    glNormal3f(1, 0, 0)
    glVertex3f(cx + hx, cy - hy, cz - hz)
    glVertex3f(cx + hx, cy + hy, cz - hz)
    glVertex3f(cx + hx, cy + hy, cz + hz)
    glVertex3f(cx + hx, cy - hy, cz + hz)
    # -X (Izquierda)
    glNormal3f(-1, 0, 0)
    glVertex3f(cx - hx, cy + hy, cz - hz)
    glVertex3f(cx - hx, cy - hy, cz - hz)
    glVertex3f(cx - hx, cy - hy, cz + hz)
    glVertex3f(cx - hx, cy + hy, cz + hz)
    glEnd()


def draw_cylinder_z(cx, cy, z0, z1, r0, r1, slices, color, cap_top=True, cap_bottom=True):
    """Dibuja un cilindro o cono truncado vertical a lo largo del eje Z."""
    glColor4f(color[0], color[1], color[2], color[3] if len(color) > 3 else 1.0)
    glBegin(GL_QUAD_STRIP)
    for i in range(slices + 1):
        ang = 2.0 * math.pi * i / slices
        ca, sa = math.cos(ang), math.sin(ang)
        glNormal3f(ca, sa, 0.2)
        glVertex3f(cx + r1 * ca, cy + r1 * sa, z1)
        glVertex3f(cx + r0 * ca, cy + r0 * sa, z0)
    glEnd()
    if cap_top and r1 > 0.001:
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(0, 0, 1)
        glVertex3f(cx, cy, z1)
        for i in range(slices + 1):
            ang = 2.0 * math.pi * i / slices
            glVertex3f(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang), z1)
        glEnd()
    if cap_bottom and r0 > 0.001:
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(0, 0, -1)
        glVertex3f(cx, cy, z0)
        for i in range(slices, -1, -1):
            ang = 2.0 * math.pi * i / slices
            glVertex3f(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), z0)
        glEnd()


def draw_wheel_x(cx, cy, cz, radius, width, color_tire=(0.15, 0.15, 0.16), color_rim=(0.85, 0.72, 0.15)):
    """Dibuja una rueda con eje paralelo a X."""
    hw = width * 0.5
    slices = 14
    glColor3f(*color_tire)
    glBegin(GL_QUAD_STRIP)
    for i in range(slices + 1):
        ang = 2.0 * math.pi * i / slices
        ca, sa = math.cos(ang), math.sin(ang)
        glNormal3f(0, ca, sa)
        glVertex3f(cx - hw, cy + radius * ca, cz + radius * sa)
        glVertex3f(cx + hw, cy + radius * ca, cz + radius * sa)
    glEnd()
    for sign in (-1, 1):
        glColor3f(*color_tire)
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(sign, 0, 0)
        glVertex3f(cx + sign * hw, cy, cz)
        for i in range(slices + 1):
            ang = 2.0 * math.pi * i / slices
            glVertex3f(cx + sign * hw, cy + radius * math.cos(ang), cz + radius * math.sin(ang))
        glEnd()
        glColor3f(*color_rim)
        r_rim = radius * 0.55
        glBegin(GL_TRIANGLE_FAN)
        glNormal3f(sign, 0, 0)
        glVertex3f(cx + sign * (hw + 0.004), cy, cz)
        for i in range(slices + 1):
            ang = 2.0 * math.pi * i / slices
            glVertex3f(cx + sign * (hw + 0.004), cy + r_rim * math.cos(ang), cz + r_rim * math.sin(ang))
        glEnd()


def draw_item_mesh(item_type, x=0.0, y=0.0, z=0.0, yaw_deg=0.0):
    """Dibuja un elemento de construcción (ladrillo, bloque, bulto_cemento, balde_mezcla)."""
    glPushMatrix()
    glTranslatef(x, y, z)
    if yaw_deg != 0.0:
        glRotatef(yaw_deg, 0, 0, 1)

    if item_type == "ladrillo":
        # Ladrillo tolete/farol de arcilla cocida con perforaciones superiores
        draw_box(0, 0, 0.055, 0.28, 0.14, 0.11, (0.78, 0.31, 0.16))
        for hx in (-0.08, 0.0, 0.08):
            draw_box(hx, 0, 0.111, 0.045, 0.07, 0.005, (0.35, 0.12, 0.06))

    elif item_type == "bloque":
        # Bloque estructural de concreto abujardado con 2 celdas huecas
        draw_box(0, 0, 0.095, 0.38, 0.19, 0.19, (0.64, 0.66, 0.68))
        draw_box(-0.09, 0, 0.191, 0.13, 0.12, 0.006, (0.28, 0.30, 0.32))
        draw_box(0.09, 0, 0.191, 0.13, 0.12, 0.006, (0.28, 0.30, 0.32))

    elif item_type == "bulto_cemento":
        # Saco de cemento de 50 kg (papel kraft con franja verde/roja)
        draw_box(0, 0, 0.075, 0.50, 0.34, 0.15, (0.76, 0.67, 0.52))
        draw_box(0, 0, 0.135, 0.44, 0.28, 0.04, (0.80, 0.71, 0.56))
        # Banda impresa del saco de cemento
        draw_box(0, 0, 0.156, 0.30, 0.18, 0.005, (0.16, 0.48, 0.26))
        draw_box(0, 0, 0.159, 0.18, 0.06, 0.004, (0.85, 0.22, 0.18))

    elif item_type == "mezcla":
        # Porción de mezcla de concreto húmedo
        draw_cylinder_z(0, 0, 0.0, 0.12, 0.18, 0.12, 10, (0.52, 0.56, 0.58))

    glPopMatrix()


def draw_shovel(has_load=False):
    """Dibuja una pala de construcción en el sistema local de la mano del personaje."""
    # Mango de madera
    draw_box(0, 0.25, 0.0, 0.032, 0.75, 0.032, (0.68, 0.48, 0.24))
    # Empuñadura trasera en D
    draw_box(0, -0.14, 0.0, 0.11, 0.04, 0.035, (0.20, 0.20, 0.22))
    # Hoja metálica cóncava en el extremo (+Y)
    draw_box(0, 0.68, -0.01, 0.24, 0.28, 0.018, (0.38, 0.41, 0.45))
    draw_box(-0.11, 0.68, 0.01, 0.02, 0.26, 0.03, (0.34, 0.37, 0.40))
    draw_box(0.11, 0.68, 0.01, 0.02, 0.26, 0.03, (0.34, 0.37, 0.40))
    if has_load:
        # Montículo de concreto/arena en la cuchara de la pala
        draw_cylinder_z(0, 0.68, 0.0, 0.09, 0.11, 0.04, 8, (0.54, 0.57, 0.59))


def draw_wheelbarrow(x, y, z, yaw_deg, contents=None, concrete_level=0, tilted=0.0):
    """
    Dibuja una carretilla de obra completa en (x, y, z) orientada hacia yaw_deg (0° = +Y).
    - contents: lista de tipos de ítems ('ladrillo', 'bloque', 'bulto_cemento')
    - concrete_level: 0..3 paladas de mezcla de concreto fresco
    """
    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(yaw_deg - 90.0, 0, 0, 1)  # Alinear eje local +Y con yaw_deg
    if tilted != 0.0:
        glRotatef(tilted, 1, 0, 0)

    # 1. Rueda neumática delantera en Y = +0.52 m, Z = 0.18 m
    draw_wheel_x(0.0, 0.52, 0.18, radius=0.18, width=0.09)

    # 2. Chasis tubular y mangos de caucho (de Y = -0.58 a Y = +0.54)
    frame_col = (0.18, 0.22, 0.26)
    for sx in (-0.22, 0.22):
        glPushMatrix()
        glTranslatef(sx, -0.02, 0.27)
        glRotatef(-8.0, 1, 0, 0)
        draw_box(0, 0, 0, 0.035, 1.15, 0.035, frame_col)
        # Empuñaduras rojas de caucho en los extremos traseros
        draw_box(0, -0.54, 0, 0.046, 0.18, 0.046, (0.82, 0.18, 0.15))
        glPopMatrix()

        # Patas de apoyo traseras (llegan a Z=0)
        draw_box(sx, -0.25, 0.14, 0.03, 0.03, 0.28, frame_col)
        draw_box(sx, -0.18, 0.02, 0.03, 0.16, 0.03, frame_col)

    # Travesaño frontal junto a la rueda
    draw_box(0, 0.34, 0.22, 0.46, 0.04, 0.04, frame_col)

    # 3. Platón metálico (Tolva de la carretilla: color amarillo/naranja o azul obra)
    tray_col = (0.92, 0.62, 0.10)
    tray_dark = (0.76, 0.50, 0.08)
    # Fondo del platón
    draw_box(0, 0.08, 0.30, 0.52, 0.62, 0.03, tray_dark)
    # Paredes laterales
    draw_box(-0.27, 0.08, 0.44, 0.03, 0.68, 0.26, tray_col)
    draw_box(0.27, 0.08, 0.44, 0.03, 0.68, 0.26, tray_col)
    # Pared trasera e inclinada delantera
    draw_box(0, -0.25, 0.44, 0.56, 0.03, 0.26, tray_col)
    glPushMatrix()
    glTranslatef(0, 0.41, 0.43)
    glRotatef(-25.0, 1, 0, 0)
    draw_box(0, 0, 0, 0.56, 0.03, 0.30, tray_col)
    glPopMatrix()
    # Borde superior reforzado
    draw_box(0, 0.08, 0.57, 0.59, 0.72, 0.025, (0.25, 0.25, 0.28))

    # 4. Contenido dinámico dentro de la carretilla
    if concrete_level > 0:
        fill_ratio = min(1.0, concrete_level / 3.0)
        z_fill = 0.33 + 0.19 * fill_ratio
        # Superficie de concreto fresco gris húmedo
        draw_box(0, 0.08, (0.31 + z_fill) * 0.5, 0.50, 0.60, z_fill - 0.31, (0.53, 0.57, 0.60))
        # Relieve superior de mezcla
        draw_cylinder_z(0, 0.08, z_fill, z_fill + 0.04 * fill_ratio, 0.22, 0.08, 10, (0.58, 0.62, 0.65))

    if contents:
        for idx, it in enumerate(contents[:6]):
            row = idx // 2
            col = idx % 2
            ix = -0.11 + col * 0.22 if len(contents) > 1 else 0.0
            iy = -0.06 + row * 0.18
            iz = 0.33 + (idx // 4) * 0.13
            draw_item_mesh(it, ix, iy, iz, yaw_deg=90.0 if it == "bulto_cemento" else 0.0)

    glPopMatrix()


def draw_concrete_mixer(x, y, z, yaw_deg, drum_angle_deg, is_running, mix_progress, has_batch_ready):
    """
    Dibuja la Concretadora (Mezcladora de Trompo de 1.5 bultos) en 3D con tambor giratorio.
    """
    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(yaw_deg, 0, 0, 1)

    frame_col = (0.20, 0.22, 0.25)
    orange_col = (0.92, 0.42, 0.08)
    orange_dark = (0.78, 0.33, 0.05)

    # 1. Ruedas y eje
    draw_wheel_x(-0.58, 0.0, 0.22, radius=0.22, width=0.10)
    draw_wheel_x(0.58, 0.0, 0.22, radius=0.22, width=0.10)
    draw_box(0, 0, 0.22, 1.16, 0.06, 0.06, frame_col)

    # 2. Bastidor y patas estabilizadoras
    draw_box(0, 0, 0.36, 1.05, 0.90, 0.07, frame_col)
    draw_box(0, -0.55, 0.18, 0.10, 0.08, 0.36, frame_col)
    draw_box(0, 0.55, 0.18, 0.10, 0.08, 0.36, frame_col)
    # Parales verticales del yugo del trompo
    draw_box(-0.48, 0.0, 0.78, 0.08, 0.10, 0.84, frame_col)
    draw_box(0.48, 0.0, 0.78, 0.08, 0.10, 0.84, frame_col)

    # 3. Cabina del motor lateral (en -X)
    draw_box(-0.72, 0.0, 0.62, 0.42, 0.56, 0.52, orange_dark)
    draw_box(-0.94, 0.0, 0.62, 0.02, 0.40, 0.34, (0.15, 0.15, 0.18))  # Rejilla de ventilación

    # 4. Volante lateral de volteo (en +X)
    draw_wheel_x(0.60, 0.0, 1.05, radius=0.26, width=0.03, color_tire=(0.15, 0.15, 0.18), color_rim=orange_col)

    # 5. Trompo / Tambor rotatorio inclinado hacia el frente (+Y)
    glPushMatrix()
    glTranslatef(0.0, 0.05, 1.08)
    # Inclinación de trabajo hacia adelante (+Y)
    tilt = 32.0 if not has_batch_ready else 38.0
    glRotatef(-tilt, 1, 0, 0)
    # Rotación continua del tambor alrededor de su propio eje Z local
    glRotatef(drum_angle_deg, 0, 0, 1)

    # Cono inferior del trompo
    draw_cylinder_z(0, 0, -0.38, 0.0, 0.24, 0.48, 16, orange_dark, cap_top=False, cap_bottom=True)
    # Anillo central (corona dentada)
    draw_cylinder_z(0, 0, -0.03, 0.05, 0.50, 0.50, 16, (0.25, 0.26, 0.28), cap_top=False, cap_bottom=False)
    # Cono superior hacia la boca
    draw_cylinder_z(0, 0, 0.0, 0.42, 0.48, 0.32, 16, orange_col, cap_top=False, cap_bottom=False)
    # Interior oscuro o con concreto fresco girando
    inner_col = (0.50, 0.55, 0.58) if (is_running or has_batch_ready or mix_progress > 0) else (0.18, 0.18, 0.20)
    draw_cylinder_z(0, 0, 0.28, 0.38, 0.34, 0.30, 14, inner_col, cap_top=True, cap_bottom=False)

    # Aletas batidoras en la boca para que se note el giro claramente
    for b_ang in (0, 90, 180, 270):
        glPushMatrix()
        glRotatef(b_ang, 0, 0, 1)
        draw_box(0.24, 0.0, 0.32, 0.14, 0.025, 0.16, (0.30, 0.32, 0.35))
        glPopMatrix()

    glPopMatrix()
    glPopMatrix()


def draw_material_station(station):
    """Dibuja una estiba/acopio de materiales (ladrillos, bloques, bultos, arena/grava) en el patio."""
    sx, sy, sz = station["pos"]
    stype = station["item_type"]

    glPushMatrix()
    glTranslatef(sx, sy, sz)

    if stype == "arena":
        # Gran montículo de arena y triturado junto a la concretadora + caneca de agua azul
        draw_cylinder_z(0, 0, 0.0, 0.48, 1.05, 0.22, 16, (0.76, 0.66, 0.44))
        draw_cylinder_z(0.95, 0.35, 0.0, 0.72, 0.28, 0.28, 14, (0.12, 0.42, 0.82))  # Caneca de agua
        draw_cylinder_z(0.95, 0.35, 0.68, 0.73, 0.26, 0.26, 14, (0.25, 0.68, 0.95))
    else:
        # Estiba de madera (Pallet)
        draw_box(0, 0, 0.05, 1.15, 1.15, 0.10, (0.58, 0.40, 0.22))
        count = station.get("stock", 12)
        for i in range(min(count, 16)):
            layer = i // 4
            rem = i % 4
            rx = -0.26 + (rem % 2) * 0.52
            ry = -0.26 + (rem // 2) * 0.52
            rz = 0.10 + layer * (0.12 if stype == "ladrillo" else (0.19 if stype == "bloque" else 0.15))
            draw_item_mesh(stype, rx, ry, rz)

    glPopMatrix()


def draw_work_zone_marker(zone, anim_time):
    """Dibuja la zona de entrega/obra dentro de la casa con avance visual de mampostería/piso."""
    zx, zy, zz = zone["pos"]
    progress = zone["delivered"] / max(1, zone["target"])
    pulse = 0.5 + 0.5 * math.sin(anim_time * 4.0)

    glPushMatrix()
    glTranslatef(zx, zy, zz)

    # Marco luminoso en el piso indicando área de trabajo en obra
    col = (0.15, 0.85, 0.35) if progress >= 1.0 else (0.95, 0.75 + 0.2 * pulse, 0.12)
    draw_box(0, 0, 0.015, 1.30, 1.30, 0.02, col)
    draw_box(0, 0, 0.022, 1.12, 1.12, 0.015, (0.32, 0.34, 0.36))

    # Mostrar obra ejecutada según lo entregado (murete de ladrillo/bloque y losa de mortero)
    built_items = zone["delivered"]
    for i in range(min(built_items, 18)):
        row = i // 3
        col_i = i % 3
        bx = -0.35 + col_i * 0.35
        by = 0.35
        bz = 0.03 + row * 0.15
        if i % 2 == 0:
            draw_item_mesh("ladrillo", bx, by, bz)
        else:
            draw_item_mesh("bloque", bx, by, bz)

    glPopMatrix()


def draw_character(
    x, y, z, yaw_deg,
    helmet_color=(0.95, 0.80, 0.10),
    vest_color=(0.95, 0.45, 0.08),
    shirt_color=(0.18, 0.36, 0.65),
    pants_color=(0.16, 0.22, 0.34),
    anim_state="idle",
    anim_phase=0.0,
    carrying_item=None,
    has_shovel=False,
    shovel_loaded=False,
):
    """
    Dibuja un personaje 3D articulado (Jugador o Ayudante de Obra):
    - anim_state: 'idle', 'walk', 'hold_wheelbarrow', 'shovel_fill', 'carry'
    """
    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(yaw_deg - 90.0, 0, 0, 1)  # +Y local apunta hacia yaw_deg

    leg_swing = 0.0
    arm_l_pitch = 0.0
    arm_r_pitch = 0.0
    torso_pitch = 0.0
    torso_yaw = 0.0

    if anim_state == "walk":
        leg_swing = math.sin(anim_phase * 8.0) * 28.0
        arm_l_pitch = -leg_swing * 0.8
        arm_r_pitch = leg_swing * 0.8
    elif anim_state == "hold_wheelbarrow":
        if abs(math.sin(anim_phase * 4.0)) > 0.01:
            leg_swing = math.sin(anim_phase * 7.0) * 18.0
        arm_l_pitch = 52.0
        arm_r_pitch = 52.0
        torso_pitch = 8.0
    elif anim_state == "carry":
        leg_swing = math.sin(anim_phase * 7.0) * 22.0
        arm_l_pitch = 65.0
        arm_r_pitch = 65.0
    elif anim_state == "shovel_fill":
        # Ciclo de palear hacia la carretilla:
        # 0..pi: agacharse y recoger mezcla; pi..2pi: girar y descargar en la carretilla
        s = math.sin(anim_phase * 3.2)
        torso_pitch = 18.0 - 14.0 * s
        torso_yaw = 28.0 * math.cos(anim_phase * 3.2)
        arm_l_pitch = 55.0 + 25.0 * s
        arm_r_pitch = 45.0 + 30.0 * s

    # 1. Piernas y botas de seguridad (Z = 0.0 a 0.74 m)
    for sign, swing in ((-1, leg_swing), (1, -leg_swing)):
        glPushMatrix()
        glTranslatef(sign * 0.11, 0.0, 0.72)
        glRotatef(swing, 1, 0, 0)
        # Pantalón jean/dotación
        draw_box(0, 0, -0.28, 0.13, 0.14, 0.56, pants_color)
        # Bota pantanera / punta de acero
        draw_box(0, 0.03, -0.64, 0.14, 0.21, 0.16, (0.14, 0.14, 0.15))
        glPopMatrix()

    # 2. Torso con camisa de dotación y chaleco reflectivo (Z = 0.72 a 1.32 m)
    glPushMatrix()
    glTranslatef(0, 0, 0.74)
    glRotatef(torso_yaw, 0, 0, 1)
    glRotatef(torso_pitch, 1, 0, 0)

    # Camisa base y chaleco reflectivo
    draw_box(0, 0, 0.28, 0.36, 0.22, 0.56, shirt_color)
    draw_box(0, 0, 0.29, 0.38, 0.24, 0.48, vest_color)
    # Franjas reflectivas grises/plateadas en el chaleco
    draw_box(0, 0, 0.18, 0.39, 0.25, 0.04, (0.85, 0.88, 0.90))
    draw_box(0, 0, 0.36, 0.39, 0.25, 0.04, (0.85, 0.88, 0.90))

    # 3. Cabeza y Casco de Seguridad (Z local = 0.58 a 0.92 m -> altura total ~1.70 m)
    # Cuello y Rostro
    draw_box(0, 0, 0.68, 0.21, 0.21, 0.22, (0.88, 0.68, 0.54))
    # Ojos mirando hacia +Y
    draw_box(-0.05, 0.106, 0.70, 0.03, 0.01, 0.03, (0.12, 0.12, 0.14))
    draw_box(0.05, 0.106, 0.70, 0.03, 0.01, 0.03, (0.12, 0.12, 0.14))
    # Casco de obra con visera frontal y nervadura superior
    draw_box(0, 0.01, 0.81, 0.26, 0.27, 0.11, helmet_color)
    draw_box(0, 0.15, 0.77, 0.24, 0.09, 0.03, helmet_color)  # Visera
    draw_box(0, 0.0, 0.87, 0.06, 0.24, 0.04, helmet_color)   # Cresta del casco

    # 4. Brazos articulados
    for sign, pitch in ((-1, arm_l_pitch), (1, arm_r_pitch)):
        glPushMatrix()
        glTranslatef(sign * 0.24, 0.0, 0.50)
        glRotatef(-pitch, 1, 0, 0)
        # Brazo y antebrazo
        draw_box(0, 0, -0.22, 0.10, 0.10, 0.46, shirt_color)
        # Guante de carnaza/obra
        draw_box(0, 0, -0.47, 0.11, 0.11, 0.10, (0.78, 0.62, 0.32))

        # Si este es el brazo derecho y tiene pala, dibujar la pala
        if sign == 1 and (has_shovel or anim_state == "shovel_fill"):
            glPushMatrix()
            glTranslatef(-0.12, 0.05, -0.46)
            glRotatef(65.0, 1, 0, 0)
            draw_shovel(has_load=shovel_loaded)
            glPopMatrix()
        glPopMatrix()

    # 5. Si lleva un elemento cargado en las manos (ladrillo, bloque, bulto de cemento)
    if carrying_item:
        draw_item_mesh(carrying_item, 0.0, 0.34, 0.24)

    glPopMatrix()
    glPopMatrix()


# Nubes suaves en el cielo: (x_base, y_base, z_altura, escala, velocidad_viento)
_CLOUD_PRESETS = [
    (-35.0, -28.0, 26.0, 1.20, 0.45),
    (-12.0, -34.0, 29.0, 0.95, 0.35),
    (18.0,  -30.0, 25.0, 1.35, 0.40),
    (42.0,  -20.0, 28.0, 1.10, 0.50),
    (-40.0,  -2.0, 30.0, 1.25, 0.38),
    (-18.0,   6.0, 24.5, 1.05, 0.48),
    (12.0,   14.0, 27.5, 1.40, 0.36),
    (36.0,    8.0, 25.5, 1.15, 0.44),
    (-32.0,  26.0, 28.0, 1.30, 0.42),
    (-4.0,   32.0, 25.0, 1.00, 0.52),
    (26.0,   34.0, 29.5, 1.25, 0.34),
    (46.0,   28.0, 26.5, 1.10, 0.46),
    (-46.0,  42.0, 27.0, 1.20, 0.39),
    (6.0,   -10.0, 31.0, 0.90, 0.41),
    (28.0,  -12.0, 27.0, 1.05, 0.47),
]


def build_sky_dome_list(radius=68.0):
    """Compila una cúpula celeste con gradiente suave desde el horizonte hasta el cenit."""
    rings = [
        (-0.25, (0.56, 0.72, 0.84)),
        (0.00,  (0.76, 0.89, 0.98)),
        (0.12,  (0.60, 0.80, 0.96)),
        (0.32,  (0.42, 0.69, 0.94)),
        (0.60,  (0.26, 0.55, 0.88)),
        (0.88,  (0.18, 0.45, 0.82)),
        (1.00,  (0.15, 0.40, 0.78)),
    ]
    slices = 28
    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)
    for idx in range(len(rings) - 1):
        s0, c0 = rings[idx]
        s1, c1 = rings[idx + 1]
        z0 = radius * s0
        r0 = radius * math.sqrt(max(0.0, 1.0 - s0 * s0))
        z1 = radius * s1
        r1 = radius * math.sqrt(max(0.0, 1.0 - s1 * s1))

        glBegin(GL_QUAD_STRIP)
        for i in range(slices + 1):
            ang = 2.0 * math.pi * i / slices
            ca, sa = math.cos(ang), math.sin(ang)
            glColor3f(*c1)
            glVertex3f(r1 * ca, r1 * sa, z1)
            glColor3f(*c0)
            glVertex3f(r0 * ca, r0 * sa, z0)
        glEnd()
    glEndList()
    return dl


def _draw_sun_disc(cx, cy, cz, rx, ry, rz, ux, uy, uz, radius, center_col, edge_col, slices=24):
    """Dibuja un disco radial (sol o halo) orientado hacia la cámara."""
    glBegin(GL_TRIANGLE_FAN)
    glColor4f(*center_col)
    glVertex3f(cx, cy, cz)
    glColor4f(*edge_col)
    for i in range(slices + 1):
        ang = 2.0 * math.pi * i / slices
        ca, sa = math.cos(ang) * radius, math.sin(ang) * radius
        glVertex3f(cx + rx * ca + ux * sa, cy + ry * ca + uy * sa, cz + rz * ca + uz * sa)
    glEnd()


def _draw_cloud_puff(cx, cy, cz, rx, ry, rz):
    """Dibuja un volumen de nube suave con parte superior luminosa e inferior sombreada."""
    lat_steps = 5
    lon_steps = 10
    for j in range(lat_steps):
        p0 = -0.5 * math.pi + math.pi * j / lat_steps
        p1 = -0.5 * math.pi + math.pi * (j + 1) / lat_steps
        cp0, sp0 = math.cos(p0), math.sin(p0)
        cp1, sp1 = math.cos(p1), math.sin(p1)

        # Tinte suave: blanco cálido arriba, azulado suave debajo
        t0 = 0.5 + 0.5 * sp0
        t1 = 0.5 + 0.5 * sp1
        col0 = (0.85 + 0.14 * t0, 0.90 + 0.09 * t0, 0.96 + 0.04 * t0, 0.88)
        col1 = (0.85 + 0.14 * t1, 0.90 + 0.09 * t1, 0.96 + 0.04 * t1, 0.88)

        glBegin(GL_QUAD_STRIP)
        for i in range(lon_steps + 1):
            ang = 2.0 * math.pi * i / lon_steps
            ca, sa = math.cos(ang), math.sin(ang)
            glColor4f(*col1)
            glVertex3f(cx + rx * cp1 * ca, cy + ry * cp1 * sa, cz + rz * sp1)
            glColor4f(*col0)
            glVertex3f(cx + rx * cp0 * ca, cy + ry * cp0 * sa, cz + rz * sp0)
        glEnd()


def draw_sky_and_clouds(sky_dl, eye_x, eye_y, eye_z, anim_time):
    """Dibuja el cielo degradado, el sol con halo atmosférico y las nubes en movimiento."""
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glDepthMask(GL_FALSE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # 1. Cúpula de cielo centrada en la cámara
    glPushMatrix()
    glTranslatef(eye_x, eye_y, eye_z)
    if sky_dl is not None:
        glCallList(sky_dl)

    # 2. Sol alineado con la luz principal en lo alto del cielo
    sx, sy, sz = 0.40, -0.48, 0.78
    norm = math.sqrt(sx * sx + sy * sy + sz * sz)
    sx, sy, sz = sx / norm, sy / norm, sz / norm
    sun_dist = 56.0
    scx, scy, scz = sx * sun_dist, sy * sun_dist, sz * sun_dist

    # Base ortogonal perpendicular a la dirección del sol
    rx, ry, rz = sy, -sx, 0.0
    rnorm = math.hypot(rx, ry)
    rx, ry = rx / rnorm, ry / rnorm
    ux = sy * rz - sz * ry
    uy = sz * rx - sx * rz
    uz = sx * ry - sy * rx

    _draw_sun_disc(scx, scy, scz, rx, ry, rz, ux, uy, uz, 13.0, (1.0, 0.96, 0.80, 0.34), (0.45, 0.72, 0.94, 0.0))
    _draw_sun_disc(scx, scy, scz, rx, ry, rz, ux, uy, uz, 5.4, (1.0, 0.98, 0.88, 0.72), (1.0, 0.92, 0.68, 0.0))
    _draw_sun_disc(scx, scy, scz, rx, ry, rz, ux, uy, uz, 2.3, (1.0, 0.99, 0.92, 1.0), (1.0, 0.96, 0.80, 0.98))
    glPopMatrix()

    # 3. Nubes 3D desplazándose suavemente por el cielo
    for x0, y0, z0, sc, spd in _CLOUD_PRESETS:
        cx = ((x0 + anim_time * spd + 55.0) % 110.0) - 55.0 + 10.0
        cy = y0 + 5.0
        cz = z0
        _draw_cloud_puff(cx, cy, cz, 3.6 * sc, 2.2 * sc, 1.15 * sc)
        _draw_cloud_puff(cx - 2.3 * sc, cy + 0.4 * sc, cz - 0.15 * sc, 2.4 * sc, 1.7 * sc, 0.90 * sc)
        _draw_cloud_puff(cx + 2.4 * sc, cy - 0.3 * sc, cz - 0.10 * sc, 2.6 * sc, 1.8 * sc, 0.95 * sc)
        _draw_cloud_puff(cx + 0.5 * sc, cy + 0.9 * sc, cz + 0.45 * sc, 2.1 * sc, 1.5 * sc, 0.85 * sc)

    glDepthMask(GL_TRUE)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)
