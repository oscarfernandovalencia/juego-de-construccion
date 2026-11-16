#!/usr/bin/env python3
"""
Motor lógico de simulación de obra, físicas de colisión con los modelos de FreeCAD
(Casas de Barbosa y Doradal), gestión de materiales (ladrillos, bloques, bultos de cemento,
mezcla de concreto, carretillas, concretadora) e Inteligencia Artificial de los 3 ayudantes.
"""

import os
import json
import math
import numpy as np


ITEM_NAMES = {
    "ladrillo": "Ladrillo de Arcilla",
    "bloque": "Bloque de Concreto",
    "bulto_cemento": "Bulto de Cemento (50kg)",
    "mezcla": "Mezcla de Concreto",
}


class ConcreteMixer:
    def __init__(self, x, y, z, yaw=0.0):
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.drum_angle = 0.0
        self.is_running = True
        self.cement_loaded = 1
        self.sand_loaded = 2
        self.mix_progress = 1.0  # Lista una tanda inicial para empezar de inmediato
        self.shovels_available = 6  # Paladas de concreto disponibles en la tolva

    def update(self, dt):
        if self.is_running:
            self.drum_angle = (self.drum_angle + 165.0 * dt) % 360.0
            if self.shovels_available == 0 and (self.cement_loaded > 0 or self.sand_loaded > 0):
                self.mix_progress = min(1.0, self.mix_progress + dt * 0.25)
                if self.mix_progress >= 1.0:
                    self.shovels_available = 6
                    self.cement_loaded = max(0, self.cement_loaded - 1)
                    self.sand_loaded = max(0, self.sand_loaded - 1)
            elif self.shovels_available == 0 and self.cement_loaded == 0:
                # Recarga continua asistida en obra para no bloquear la experiencia
                self.mix_progress = min(1.0, self.mix_progress + dt * 0.15)
                if self.mix_progress >= 1.0:
                    self.shovels_available = 6

    def add_material(self, item_type):
        if item_type == "bulto_cemento":
            self.cement_loaded += 1
            self.is_running = True
            if self.shovels_available < 6:
                self.shovels_available = 6
            return True
        return False

    def take_shovel_of_concrete(self):
        if self.shovels_available > 0:
            self.shovels_available -= 1
            if self.shovels_available == 0:
                self.mix_progress = 0.0
            return True
        # Incluso si está mezclando, permitir sacar mezcla húmeda
        return True


class Wheelbarrow:
    def __init__(self, wb_id, x, y, z, yaw=90.0):
        self.id = wb_id
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.holder = None  # 'player' o instancia de NPCWorker
        self.contents = []  # lista de 'ladrillo', 'bloque', 'bulto_cemento' (máx 6)
        self.concrete_level = 0  # 0..3 paladas de mezcla
        self.tilt_angle = 0.0

    def is_empty(self):
        return len(self.contents) == 0 and self.concrete_level == 0

    def is_full(self):
        return self.concrete_level >= 3 or len(self.contents) >= 6

    def add_shovel_concrete(self):
        if len(self.contents) == 0 and self.concrete_level < 3:
            self.concrete_level += 1
            return True
        return False

    def add_item(self, item_type):
        if self.concrete_level == 0 and len(self.contents) < 6:
            self.contents.append(item_type)
            return True
        return False

    def dump_all(self):
        delivered = 0
        if self.concrete_level > 0:
            delivered = self.concrete_level
            self.concrete_level = 0
        elif self.contents:
            delivered = len(self.contents)
            self.contents.clear()
        self.tilt_angle = 35.0
        return delivered

    def update(self, dt):
        if self.tilt_angle > 0.0:
            self.tilt_angle = max(0.0, self.tilt_angle - 70.0 * dt)

    def get_summary(self):
        if self.concrete_level > 0:
            return f"Mezcla de Concreto ({self.concrete_level}/3 paladas)"
        if self.contents:
            counts = {}
            for c in self.contents:
                counts[c] = counts.get(c, 0) + 1
            parts = [f"{n}x {ITEM_NAMES.get(k, k)}" for k, n in counts.items()]
            return ", ".join(parts) + f" ({len(self.contents)}/6)"
        return "Vacía"


class NPCWorker:
    """
    Personajes ayudantes de obra con comportamiento cooperativo autónomo y por órdenes:
    - 'palero' (Don Chucho): Llena con la pala la carretilla que sostiene el Jugador o Jairo, y alimenta la concretadora.
    - 'carretillero' (Jairo): Sostiene la carretilla mientras el Jugador o Don Chucho la llenan con pala, y la lleva adentro de la casa.
    - 'auxiliar' (Mateo): Transporta ladrillos, bloques y bultos de cemento desde el patio hacia el interior de la casa o a la carretilla.
    """
    def __init__(self, npc_id, name, role, x, y, z, helmet_color, vest_color, shirt_color):
        self.id = npc_id
        self.name = name
        self.role = role
        self.x = x
        self.y = y
        self.z = z
        self.yaw = 90.0
        self.helmet_color = helmet_color
        self.vest_color = vest_color
        self.shirt_color = shirt_color

        self.anim_state = "idle"
        self.anim_phase = 0.0
        self.carrying_item = None
        self.has_shovel = (role == "palero")
        self.shovel_loaded = False
        self.held_wheelbarrow = None
        self.status_text = "Listo en obra"
        self.shovel_timer = 0.0
        self.target_zone_idx = 0

    def move_towards(self, tx, ty, speed, dt, world, ignore_walls=False):
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.15:
            return True

        self.yaw = math.degrees(math.atan2(dy, dx))
        step = min(dist, speed * dt)
        nx = self.x + (dx / dist) * step
        ny = self.y + (dy / dist) * step

        if not ignore_walls:
            nx, ny = world.resolve_collision(self.x, self.y, nx, ny, radius=0.24)
            # Si hay obstáculo directo, rodear ligeramente hacia la puerta más cercana
            if math.hypot(nx - self.x, ny - self.y) < step * 0.25:
                door_x, door_y = world.get_nearest_entry_point(self.x, self.y, tx, ty)
                ddx, ddy = door_x - self.x, door_y - self.y
                ddist = math.hypot(ddx, ddy)
                if ddist > 0.1:
                    self.yaw = math.degrees(math.atan2(ddy, ddx))
                    nx = self.x + (ddx / ddist) * step
                    ny = self.y + (ddy / ddist) * step
                    nx, ny = world.resolve_collision(self.x, self.y, nx, ny, radius=0.22)

        self.x, self.y = nx, ny
        self.z = world.get_floor_height(self.x, self.y)
        self.anim_phase += dt * 1.4
        return dist < 0.35

    def update(self, dt, world):
        self.z = world.get_floor_height(self.x, self.y)
        mixer = world.mixer
        player = world.player

        # ------------------------------------------------------------------
        # ROL 1: DON CHUCHO (Oficial Palero y Operador de Concretadora)
        # ------------------------------------------------------------------
        if self.role == "palero":
            self.has_shovel = True
            # Buscar si el jugador o el carretillero tienen una carretilla cerca de la concretadora esperando ser llenada
            target_wb = None
            if player["held_wheelbarrow"] is not None:
                wb = player["held_wheelbarrow"]
                if not wb.is_full() and len(wb.contents) == 0:
                    if world.crew_command == "fill_player_wb" or math.hypot(wb.x - mixer.x, wb.y - mixer.y) < 3.8:
                        target_wb = wb

            if target_wb is None:
                # Revisar si Jairo (carretillero) está sosteniendo una carretilla frente a la concretadora
                # pero solo si el modo NO es "hold_for_player" (donde Jairo espera que el jugador palee)
                for other in world.npcs:
                    if other.role == "carretillero" and other.held_wheelbarrow is not None:
                        wb = other.held_wheelbarrow
                        if not wb.is_full() and len(wb.contents) == 0:
                            if world.crew_command != "hold_for_player" and math.hypot(wb.x - mixer.x, wb.y - mixer.y) < 2.8:
                                target_wb = wb
                                break

            if target_wb is not None:
                # Ir al costado entre la concretadora y la carretilla y llenarla con la pala
                work_x = (mixer.x + target_wb.x) * 0.5 - 0.55
                work_y = (mixer.y + target_wb.y) * 0.5
                reached = self.move_towards(work_x, work_y, speed=2.4, dt=dt, world=world)
                if not reached:
                    self.anim_state = "walk"
                    self.shovel_loaded = False
                    holder_name = "tu carretilla" if target_wb.holder == "player" else "la carretilla de Jairo"
                    self.status_text = f"Yendo a llenar {holder_name} con pala"
                else:
                    self.anim_state = "shovel_fill"
                    self.anim_phase += dt * 1.3
                    self.yaw = math.degrees(math.atan2(target_wb.y - self.y, target_wb.x - self.x))
                    self.shovel_timer += dt
                    self.shovel_loaded = (math.sin(self.anim_phase * 3.2) > 0.0)
                    holder_name = "tu carretilla" if target_wb.holder == "player" else "carretilla de Jairo"
                    self.status_text = f"Paleando mezcla a {holder_name} ({target_wb.concrete_level}/3)"
                    if self.shovel_timer >= 1.9:
                        self.shovel_timer = 0.0
                        mixer.take_shovel_of_concrete()
                        target_wb.add_shovel_concrete()
                        world.spawn_shovel_particles(target_wb.x, target_wb.y, target_wb.z + 0.55)
                        if target_wb.is_full() and target_wb.holder == "player":
                            world.set_toast("Don Chucho: ¡Listo Ingeniero, carretilla llena con 3 paladas de concreto!")
                            if world.crew_command == "fill_player_wb":
                                world.crew_command = "auto"
            else:
                # Mantenerse operando la concretadora y paleando arena al trompo
                stand_x = mixer.x - 0.85
                stand_y = mixer.y + 0.65
                if not self.move_towards(stand_x, stand_y, speed=2.1, dt=dt, world=world):
                    self.anim_state = "walk"
                    self.shovel_loaded = False
                    self.status_text = "Regresando a la concretadora"
                else:
                    self.yaw = math.degrees(math.atan2(mixer.y - self.y, mixer.x - self.x))
                    self.anim_state = "shovel_fill"
                    self.anim_phase += dt * 0.9
                    self.shovel_loaded = (math.sin(self.anim_phase * 3.2) > 0.2)
                    self.status_text = "Operando concretadora (esperando carretilla)"

        # ------------------------------------------------------------------
        # ROL 2: JAIRO (Ayudante Carretillero - Sostiene carretilla y transporta)
        # ------------------------------------------------------------------
        elif self.role == "carretillero":
            # Si no tiene carretilla, buscar una carretilla libre
            if self.held_wheelbarrow is None:
                free_wb = None
                for wb in world.wheelbarrows:
                    if wb.holder is None:
                        free_wb = wb
                        break
                if free_wb is not None:
                    if not self.move_towards(free_wb.x, free_wb.y - 0.6, speed=2.4, dt=dt, world=world):
                        self.anim_state = "walk"
                        self.status_text = f"Buscando Carretilla #{free_wb.id}"
                    else:
                        free_wb.holder = self
                        self.held_wheelbarrow = free_wb
                        self.status_text = "Sosteniendo carretilla"
                else:
                    self.anim_state = "idle"
                    self.status_text = "Esperando carretilla libre"
            else:
                wb = self.held_wheelbarrow
                if wb.holder != self:
                    self.held_wheelbarrow = None
                    return

                # Si la carretilla aún NO está llena, Jairo la posiciona frente a la concretadora y LA SOSTIENE
                # para que el Jugador (con su pala) o Don Chucho la llenen
                if not wb.is_full():
                    hold_x = mixer.x + 0.15
                    hold_y = mixer.y + 1.55
                    if not self.move_towards(hold_x, hold_y, speed=2.2, dt=dt, world=world):
                        self.anim_state = "hold_wheelbarrow"
                        self.status_text = "Posicionando carretilla en concretadora"
                    else:
                        # Mirar hacia la concretadora sosteniendo firmemente los mangos
                        self.yaw = -90.0
                        self.anim_state = "hold_wheelbarrow"
                        self.anim_phase = 0.0
                        if world.crew_command == "hold_for_player":
                            self.status_text = f"Sosteniendo carretilla para que TÚ palees ({wb.concrete_level}/3)"
                        else:
                            self.status_text = f"Sosteniendo carretilla mientras palean ({wb.concrete_level}/3)"
                else:
                    # ¡Carretilla llena! Jairo la lleva dentro de la casa a la zona de obra activa
                    zone = world.work_zones[self.target_zone_idx % len(world.work_zones)]
                    zx, zy, _ = zone["pos"]
                    if not self.move_towards(zx, zy - 0.85, speed=2.3, dt=dt, world=world):
                        self.anim_state = "hold_wheelbarrow"
                        self.status_text = f"Llevando carretilla llena a {zone['name']}"
                    else:
                        delivered = wb.dump_all()
                        zone["delivered"] += delivered
                        world.total_delivered += delivered
                        self.target_zone_idx = (self.target_zone_idx + 1) % len(world.work_zones)
                        world.set_toast(f"Jairo descargó la carretilla en {zone['name']} (+{delivered} mezcla)")

                # Actualizar posición de la carretilla frente a Jairo
                rad = math.radians(self.yaw)
                wb.x = self.x + math.cos(rad) * 0.72
                wb.y = self.y + math.sin(rad) * 0.72
                wb.z = self.z
                wb.yaw = self.yaw

        # ------------------------------------------------------------------
        # ROL 3: MATEO (Auxiliar de Transporte de Ladrillos, Bloques y Cemento)
        # ------------------------------------------------------------------
        elif self.role == "auxiliar":
            if world.crew_command == "follow_player":
                dist_p = math.hypot(player["x"] - self.x, player["y"] - self.y)
                if dist_p > 1.8:
                    self.move_towards(player["x"] - 0.8, player["y"] - 0.8, speed=2.6, dt=dt, world=world)
                    self.anim_state = "carry" if self.carrying_item else "walk"
                    self.status_text = "Siguiendo al Ingeniero"
                else:
                    self.anim_state = "idle"
                    self.status_text = "A tus órdenes, Ingeniero"
                return

            if self.carrying_item is None:
                # Elegir alternadamente entre ladrillo, bloque y bulto_cemento
                stations = [s for s in world.stations if s["item_type"] in ("ladrillo", "bloque", "bulto_cemento")]
                st = stations[self.target_zone_idx % len(stations)]
                sx, sy, _ = st["pos"]
                if not self.move_towards(sx, sy + 0.75, speed=2.5, dt=dt, world=world):
                    self.anim_state = "walk"
                    self.status_text = f"Yendo por {ITEM_NAMES[st['item_type']]}"
                else:
                    self.carrying_item = st["item_type"]
                    self.status_text = f"Cargando {ITEM_NAMES[self.carrying_item]}"
            else:
                # Si el jugador sostiene una carretilla cerca en el patio y tiene espacio para unidades, cargársela
                if (
                    player["held_wheelbarrow"] is not None
                    and player["held_wheelbarrow"].concrete_level == 0
                    and not player["held_wheelbarrow"].is_full()
                    and math.hypot(player["x"] - self.x, player["y"] - self.y) < 3.5
                ):
                    wb = player["held_wheelbarrow"]
                    if not self.move_towards(wb.x, wb.y, speed=2.5, dt=dt, world=world):
                        self.anim_state = "carry"
                        self.status_text = f"Llevando {ITEM_NAMES[self.carrying_item]} a tu carretilla"
                    else:
                        if wb.add_item(self.carrying_item):
                            world.set_toast(f"Mateo cargó 1 {ITEM_NAMES[self.carrying_item]} en tu carretilla")
                            self.carrying_item = None
                            self.target_zone_idx += 1
                            return

                # De lo contrario, transportar el elemento al interior de la casa
                zone = world.work_zones[self.target_zone_idx % len(world.work_zones)]
                zx, zy, _ = zone["pos"]
                if not self.move_towards(zx, zy, speed=2.4, dt=dt, world=world):
                    self.anim_state = "carry"
                    self.status_text = f"Transportando {ITEM_NAMES[self.carrying_item]} a {zone['name']}"
                else:
                    zone["delivered"] += 1
                    world.total_delivered += 1
                    self.carrying_item = None
                    self.target_zone_idx += 1


class ConstructionWorld:
    def __init__(self, assets_dir):
        self.assets_dir = assets_dir
        self.current_house_key = "barbosa"
        self.house_title = ""
        self.meta = {}
        self.meshes = {}
        self.floor_z = 1.32

        # Visibilidad de capas arquitectónicas/estructurales
        self.show_roof = True
        self.show_rebar = False
        self.show_walls = True
        self.collision_enabled = True

        # Estado del jugador
        self.player = {
            "x": 3.5,
            "y": -2.2,
            "z": 1.32,
            "yaw": 90.0,       # 90° mira hacia +Y (hacia el interior de la casa)
            "pitch": -14.0,
            "speed": 3.8,
            "carrying_item": None,
            "held_wheelbarrow": None,
            "has_shovel": False,
            "shovel_loaded": False,
            "anim_state": "idle",
            "anim_phase": 0.0,
            "shovel_anim_timer": 0.0,
        }

        self.camera_first_person = False
        self.camera_distance = 3.8

        # Elementos dinámicos de la obra
        self.mixer = None
        self.wheelbarrows = []
        self.stations = []
        self.loose_items = []
        self.work_zones = []
        self.npcs = []
        self.particles = []

        self.crew_command = "auto"  # 'auto', 'hold_for_player', 'fill_player_wb', 'follow_player'
        self.total_delivered = 0
        self.toast_message = "¡Bienvenido a la Obra! Usa WASD para moverte y E para interactuar."
        self.toast_timer = 6.0

        self.load_house("barbosa")

    def set_toast(self, msg, duration=4.5):
        self.toast_message = msg
        self.toast_timer = duration

    def spawn_shovel_particles(self, x, y, z):
        for i in range(10):
            ang = 2.0 * math.pi * i / 10.0
            self.particles.append({
                "x": x + math.cos(ang) * 0.08,
                "y": y + math.sin(ang) * 0.08,
                "z": z + 0.15,
                "vx": math.cos(ang) * 0.35,
                "vy": math.sin(ang) * 0.35,
                "vz": 0.6,
                "life": 0.55,
            })

    def load_house(self, house_key):
        self.current_house_key = house_key
        npz_path = os.path.join(self.assets_dir, f"{house_key}_scene.npz")
        meta_path = os.path.join(self.assets_dir, f"{house_key}_meta.json")

        with open(meta_path, "r", encoding="utf-8") as f:
            self.meta = json.load(f)
        npz_data = np.load(npz_path)
        self.meshes = {k: npz_data[k] for k in npz_data.files}
        self.floor_z = float(self.meta["floor_z"])

        self.loose_items.clear()
        self.particles.clear()

        if house_key == "barbosa":
            self.house_title = "Casa Barbosa (Estructura Metálica y Mampostería en Ladera)"
            fz = self.floor_z  # 1.32 m
            self.player.update({
                "x": 3.8, "y": -2.0, "z": fz, "yaw": 90.0,
                "carrying_item": None, "held_wheelbarrow": None,
                "has_shovel": False, "shovel_loaded": False,
            })
            # Concretadora y acopios en la plazoleta frontal de obra (Y = -5.5 a 0.0 m)
            self.mixer = ConcreteMixer(x=2.0, y=-3.4, z=fz, yaw=0.0)
            self.stations = [
                {"name": "Pila de Arena, Grava y Agua", "item_type": "arena", "pos": (0.2, -3.5, fz), "stock": 99},
                {"name": "Estiba de Ladrillos Tolete", "item_type": "ladrillo", "pos": (-0.6, -1.6, fz), "stock": 16},
                {"name": "Estiba de Bloques #4", "item_type": "bloque", "pos": (6.4, -1.6, fz), "stock": 16},
                {"name": "Estiba de Bultos de Cemento", "item_type": "bulto_cemento", "pos": (5.0, -3.6, fz), "stock": 16},
            ]
            self.wheelbarrows = [
                Wheelbarrow(1, x=2.15, y=-1.85, z=fz, yaw=-90.0),
                Wheelbarrow(2, x=4.20, y=-1.75, z=fz, yaw=90.0),
            ]
            # Elementos sueltos dentro y fuera de la casa para recoger y mover libremente
            self.loose_items = [
                {"type": "ladrillo", "x": 3.6, "y": 1.4, "z": fz, "yaw": 15.0},
                {"type": "ladrillo", "x": 3.9, "y": 1.5, "z": fz, "yaw": -20.0},
                {"type": "bloque", "x": 2.2, "y": 2.2, "z": fz, "yaw": 0.0},
                {"type": "bulto_cemento", "x": 4.8, "y": 1.8, "z": fz, "yaw": 45.0},
            ]
            # Zonas de trabajo en el interior de la Casa de Barbosa
            self.work_zones = [
                {"name": "Sala Principal (Acceso)", "pos": (4.4, 2.1, fz), "delivered": 0, "target": 10},
                {"name": "Habitación Central", "pos": (2.2, 5.2, fz), "delivered": 0, "target": 10},
                {"name": "Balcón / Terraza Mirador", "pos": (4.2, 11.8, fz), "delivered": 0, "target": 10},
            ]
            # Cuadrilla de 3 obreros ayudantes
            self.npcs = [
                NPCWorker(1, "Don Chucho (Palero)", "palero", 1.1, -2.8, fz,
                          helmet_color=(0.95, 0.82, 0.10), vest_color=(0.92, 0.48, 0.10), shirt_color=(0.16, 0.34, 0.62)),
                NPCWorker(2, "Jairo (Carretillero)", "carretillero", 2.15, -1.2, fz,
                          helmet_color=(0.95, 0.42, 0.08), vest_color=(0.45, 0.85, 0.15), shirt_color=(0.22, 0.26, 0.34)),
                NPCWorker(3, "Mateo (Auxiliar)", "auxiliar", 5.4, -2.2, fz,
                          helmet_color=(0.15, 0.55, 0.92), vest_color=(0.92, 0.78, 0.12), shirt_color=(0.25, 0.48, 0.32)),
            ]

        else:
            self.house_title = "Casa Doradal (Pórticos de Concreto Reforzado, Locales y Apartamento)"
            fz = self.floor_z  # 0.10 m
            self.player.update({
                "x": 7.5, "y": -2.2, "z": fz, "yaw": 90.0,
                "carrying_item": None, "held_wheelbarrow": None,
                "has_shovel": False, "shovel_loaded": False,
            })
            self.mixer = ConcreteMixer(x=8.2, y=-3.4, z=fz, yaw=0.0)
            self.stations = [
                {"name": "Pila de Arena, Grava y Agua", "item_type": "arena", "pos": (6.2, -3.5, fz), "stock": 99},
                {"name": "Estiba de Ladrillos Tolete", "item_type": "ladrillo", "pos": (2.6, -2.2, fz), "stock": 16},
                {"name": "Estiba de Bloques #4", "item_type": "bloque", "pos": (11.2, -2.2, fz), "stock": 16},
                {"name": "Estiba de Bultos de Cemento", "item_type": "bulto_cemento", "pos": (14.2, -2.6, fz), "stock": 16},
            ]
            self.wheelbarrows = [
                Wheelbarrow(1, x=8.35, y=-1.85, z=fz, yaw=-90.0),
                Wheelbarrow(2, x=4.50, y=-1.80, z=fz, yaw=90.0),
            ]
            self.loose_items = [
                {"type": "ladrillo", "x": 2.6, "y": 2.0, "z": fz, "yaw": 10.0},
                {"type": "bloque", "x": 7.2, "y": 2.4, "z": fz, "yaw": -15.0},
                {"type": "bulto_cemento", "x": 13.4, "y": 2.0, "z": fz, "yaw": 30.0},
            ]
            self.work_zones = [
                {"name": "Módulo 1 (Zona Montallantas)", "pos": (2.5, 4.2, fz), "delivered": 0, "target": 10},
                {"name": "Módulo 2 (Salón Central)", "pos": (7.2, 5.5, fz), "delivered": 0, "target": 10},
                {"name": "Módulo 3 (Restaurante y Apto)", "pos": (14.0, 3.8, fz), "delivered": 0, "target": 10},
            ]
            self.npcs = [
                NPCWorker(1, "Don Chucho (Palero)", "palero", 7.3, -2.8, fz,
                          helmet_color=(0.95, 0.82, 0.10), vest_color=(0.92, 0.48, 0.10), shirt_color=(0.16, 0.34, 0.62)),
                NPCWorker(2, "Jairo (Carretillero)", "carretillero", 8.35, -1.2, fz,
                          helmet_color=(0.95, 0.42, 0.08), vest_color=(0.45, 0.85, 0.15), shirt_color=(0.22, 0.26, 0.34)),
                NPCWorker(3, "Mateo (Auxiliar)", "auxiliar", 11.8, -2.2, fz,
                          helmet_color=(0.15, 0.55, 0.92), vest_color=(0.92, 0.78, 0.12), shirt_color=(0.25, 0.48, 0.32)),
            ]

        self.set_toast(f"Cargado diseño FreeCAD: {self.house_title}")

    def get_floor_height(self, x, y):
        # En Doradal existe una rampa lateral en X = [-1.8, -0.1], Y = [1.0, 7.5] que sube a la losa del 2do piso (Z=3.0m)
        if self.current_house_key == "doradal":
            if -1.9 <= x <= -0.05 and 1.0 <= y <= 7.5:
                t = (y - 1.0) / 6.5
                return 0.10 + t * 2.90
            if self.player["z"] > 2.2 and -0.2 <= x <= 16.95 and -0.95 <= y <= 10.0:
                return 3.00
        return self.floor_z

    def get_nearest_entry_point(self, x, y, tx, ty):
        """Auxiliar de navegación para que los NPC entren y salgan por las puertas reales del diseño."""
        if self.current_house_key == "barbosa":
            # Puerta principal en X=4.4, Y=0.0; puertas interiores en Y=3.5 (X=2.25 y X=4.5), Y=7.0 (X=2.5), Y=10.5 (X=2.5 y X=4.4)
            waypoints = [(4.4, -0.4), (4.4, 1.2), (2.3, 3.5), (4.4, 3.5), (2.5, 7.0), (2.5, 10.5), (4.4, 10.5)]
        else:
            waypoints = [(2.5, -0.4), (7.2, -0.4), (13.5, -0.4), (2.5, 2.6), (7.2, 2.6), (11.0, 2.6), (13.5, 2.6)]

        best = (tx, ty)
        best_score = 1e9
        for wx, wy in waypoints:
            d_me = math.hypot(wx - x, wy - y)
            d_goal = math.hypot(tx - wx, ty - wy)
            if d_me > 0.35 and (d_me + d_goal) < best_score:
                best_score = d_me + d_goal
                best = (wx, wy)
        return best

    def _circle_intersects_box(self, cx, cy, r, box):
        closest_x = max(box[0], min(cx, box[1]))
        closest_y = max(box[2], min(cy, box[3]))
        dx = cx - closest_x
        dy = cy - closest_y
        return (dx * dx + dy * dy) < (r * r)

    def resolve_collision(self, old_x, old_y, new_x, new_y, radius=0.26):
        if not self.collision_enabled:
            return new_x, new_y
        # Si está en el segundo piso de Doradal, no colisionar con muros del primer piso
        if self.current_house_key == "doradal" and self.player["z"] > 2.4:
            return new_x, new_y

        colliders = self.meta.get("wall_colliders", []) + self.meta.get("column_colliders", [])

        # Probar avance en X y luego en Y para deslizamiento suave contra los muros
        res_x = new_x
        for c in colliders:
            if self._circle_intersects_box(res_x, old_y, radius, c["box"]):
                res_x = old_x
                break

        res_y = new_y
        for c in colliders:
            if self._circle_intersects_box(res_x, res_y, radius, c["box"]):
                res_y = old_y
                break

        return res_x, res_y

    def player_interact_e(self):
        """Tecla [E]: Agarrar/Soltar Carretilla, o Recoger/Soltar Ladrillos, Bloques y Bultos de Cemento."""
        p = self.player

        # 1. Si ya sostiene una carretilla, soltarla
        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            wb.holder = None
            p["held_wheelbarrow"] = None
            self.set_toast(f"Soltaste la Carretilla #{wb.id} ({wb.get_summary()})")
            return

        # 2. Si está cerca de una carretilla (incluso si la tiene Jairo, puedes relevársela)
        for wb in self.wheelbarrows:
            if math.hypot(wb.x - p["x"], wb.y - p["y"]) < 1.55:
                # Si tienes un ítem en la mano, meterlo en la carretilla
                if p["carrying_item"] is not None:
                    if wb.add_item(p["carrying_item"]):
                        self.set_toast(f"Cargaste 1 {ITEM_NAMES[p['carrying_item']]} en la Carretilla #{wb.id}")
                        p["carrying_item"] = None
                    else:
                        self.set_toast("La carretilla ya está llena o tiene mezcla húmeda.")
                    return

                # Tomar el control de la carretilla
                if wb.holder is not None and wb.holder != "player":
                    wb.holder.held_wheelbarrow = None
                wb.holder = "player"
                p["held_wheelbarrow"] = wb
                p["has_shovel"] = False
                self.set_toast(
                    f"Agarraste la Carretilla #{wb.id} ({wb.get_summary()}). "
                    "Acércate a Don Chucho o presiona [3] para que él la llene con la pala."
                )
                return

        # 3. Si lleva un elemento en las manos, ponerlo en la concretadora, en una zona de obra o en el piso
        if p["carrying_item"] is not None:
            item = p["carrying_item"]
            if math.hypot(self.mixer.x - p["x"], self.mixer.y - p["y"]) < 1.8 and item == "bulto_cemento":
                self.mixer.add_material(item)
                p["carrying_item"] = None
                self.set_toast("Vaciaste 1 Bulto de Cemento dentro de la Concretadora.")
                return

            for zone in self.work_zones:
                zx, zy, _ = zone["pos"]
                if math.hypot(zx - p["x"], zy - p["y"]) < 1.65:
                    zone["delivered"] += 1
                    self.total_delivered += 1
                    p["carrying_item"] = None
                    self.set_toast(f"Entregaste {ITEM_NAMES[item]} en {zone['name']}!")
                    return

            # Soltar en el piso frente al jugador
            rad = math.radians(p["yaw"])
            self.loose_items.append({
                "type": item,
                "x": p["x"] + math.cos(rad) * 0.65,
                "y": p["y"] + math.sin(rad) * 0.65,
                "z": p["z"],
                "yaw": p["yaw"],
            })
            p["carrying_item"] = None
            self.set_toast(f"Colocaste {ITEM_NAMES[item]} en el piso.")
            return

        # 4. Intentar recoger un elemento suelto del piso
        for idx, it in enumerate(self.loose_items):
            if math.hypot(it["x"] - p["x"], it["y"] - p["y"]) < 1.35:
                p["carrying_item"] = it["type"]
                p["has_shovel"] = False
                self.loose_items.pop(idx)
                self.set_toast(f"Recogiste {ITEM_NAMES[p['carrying_item']]}. Lllévalo a la carretilla o dentro de la casa.")
                return

        # 5. Intentar tomar un ladrillo, bloque o bulto de cemento de las estibas
        for st in self.stations:
            sx, sy, _ = st["pos"]
            if math.hypot(sx - p["x"], sy - p["y"]) < 1.65:
                if st["item_type"] == "arena":
                    p["has_shovel"] = True
                    p["shovel_loaded"] = True
                    self.set_toast("Equipaste la Pala con arena/grava. Usa [F] frente a la concretadora o carretilla.")
                else:
                    p["carrying_item"] = st["item_type"]
                    p["has_shovel"] = False
                    self.set_toast(f"Tomaste 1 {ITEM_NAMES[st['item_type']]} de la estiba.")
                return

        self.set_toast("Acércate a una carretilla, estiba de ladrillos/bloques/cemento o concretadora y presiona [E].")

    def player_action_f(self):
        """
        Tecla [F]:
        - Si sostienes una carretilla llena -> Vaciarla en la zona de obra (o en el piso).
        - Si tienes la pala (o estás junto a la concretadora y una carretilla que Jairo sostiene) ->
          Dar una palada para llenar la carretilla que el otro personaje sostiene.
        """
        p = self.player

        # 1. Si sostiene carretilla: descargarla
        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            if wb.is_empty():
                # Si está cerca de la concretadora, pedirle a Don Chucho que la llene o llenarla
                if math.hypot(wb.x - self.mixer.x, wb.y - self.mixer.y) < 3.5:
                    self.crew_command = "fill_player_wb"
                    self.set_toast("¡Don Chucho viene con la pala a llenar tu carretilla mientras tú la sostienes!")
                else:
                    self.set_toast("La carretilla está vacía. Llévala junto a la concretadora o cárgale materiales.")
                return

            # Verificar si está en una zona de obra dentro de la casa
            for zone in self.work_zones:
                zx, zy, _ = zone["pos"]
                if math.hypot(zx - wb.x, zy - wb.y) < 2.2:
                    count = wb.dump_all()
                    zone["delivered"] += count
                    self.total_delivered += count
                    self.set_toast(f"¡Descargaste la carretilla en {zone['name']} (+{count} unidades de obra)!")
                    return

            # Si la vacía fuera de una zona, dejar los ítems en el piso
            if wb.contents:
                for i, it_type in enumerate(wb.contents):
                    self.loose_items.append({
                        "type": it_type,
                        "x": wb.x + (i % 2) * 0.35 - 0.15,
                        "y": wb.y + (i // 2) * 0.25,
                        "z": p["z"],
                        "yaw": p["yaw"],
                    })
            count = wb.dump_all()
            self.set_toast(f"Vaciaste la carretilla aquí ({count} elementos).")
            return

        # 2. Palear mezcla dentro de una carretilla cercana (especialmente la que sostiene Jairo)
        nearest_wb = None
        for wb in self.wheelbarrows:
            if math.hypot(wb.x - p["x"], wb.y - p["y"]) < 2.3:
                nearest_wb = wb
                break

        if nearest_wb is not None:
            p["has_shovel"] = True
            p["carrying_item"] = None
            p["shovel_anim_timer"] = 0.75
            if nearest_wb.add_shovel_concrete():
                self.mixer.take_shovel_of_concrete()
                self.spawn_shovel_particles(nearest_wb.x, nearest_wb.y, nearest_wb.z + 0.55)
                holder_msg = "que Jairo sostiene" if nearest_wb.holder not in (None, "player") else f"#{nearest_wb.id}"
                if nearest_wb.is_full():
                    self.set_toast(f"¡Llenaste con la pala la carretilla {holder_msg} (3/3)! Jairo la llevará adentro.")
                    if self.crew_command == "hold_for_player":
                        self.crew_command = "auto"
                else:
                    self.set_toast(f"Palada de concreto a la carretilla {holder_msg} ({nearest_wb.concrete_level}/3).")
            else:
                self.set_toast("¡Esa carretilla ya está llena (3/3)!")
            return

        # 3. Encender / Apagar concretadora si está cerca
        if math.hypot(self.mixer.x - p["x"], self.mixer.y - p["y"]) < 2.2:
            self.mixer.is_running = not self.mixer.is_running
            estado = "ENCENDIDA" if self.mixer.is_running else "PAUSADA"
            self.set_toast(f"Concretadora {estado}.")
            return

        self.set_toast("Acércate a la carretilla que sostiene Jairo para palear mezcla con [F], o vacía tu carretilla.")

    def toggle_shovel(self):
        p = self.player
        if p["held_wheelbarrow"] is not None:
            self.set_toast("Primero suelta la carretilla con [E] para usar la pala.")
            return
        p["carrying_item"] = None
        p["has_shovel"] = not p["has_shovel"]
        if p["has_shovel"]:
            self.set_toast("Equipaste la Pala de Obra. Presiona [2] para que Jairo sostenga la carretilla y [F] para palear.")
        else:
            self.set_toast("Guardaste la Pala de Obra.")

    def set_crew_order(self, order_key):
        self.crew_command = order_key
        if order_key == "auto":
            self.set_toast("Orden a Cuadrilla [1]: Trabajo cooperativo autónomo en toda la obra.")
        elif order_key == "hold_for_player":
            self.player["has_shovel"] = True
            self.player["carrying_item"] = None
            self.set_toast("Orden a Cuadrilla [2]: ¡Jairo sostiene la carretilla frente a la concretadora para que TÚ la llenes con la pala [F]!")
        elif order_key == "fill_player_wb":
            self.set_toast("Orden a Cuadrilla [3]: ¡Sostén tu carretilla con [E] y Don Chucho viene a llenártela con la pala!")
        elif order_key == "follow_player":
            self.set_toast("Orden a Cuadrilla [4]: ¡Mateo te sigue al interior de la casa!")

    def update(self, dt, move_forward, move_right):
        if self.toast_timer > 0.0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        # Actualizar partículas de mezcla
        alive_particles = []
        for pt in self.particles:
            pt["life"] -= dt
            if pt["life"] > 0:
                pt["x"] += pt["vx"] * dt
                pt["y"] += pt["vy"] * dt
                pt["z"] += pt["vz"] * dt
                pt["vz"] -= 2.8 * dt
                alive_particles.append(pt)
        self.particles = alive_particles

        # Movimiento del jugador
        p = self.player
        if p["shovel_anim_timer"] > 0.0:
            p["shovel_anim_timer"] = max(0.0, p["shovel_anim_timer"] - dt)
            p["anim_state"] = "shovel_fill"
            p["anim_phase"] += dt * 3.0
            p["shovel_loaded"] = (p["shovel_anim_timer"] > 0.35)
        else:
            p["shovel_loaded"] = False
            if abs(move_forward) > 0.01 or abs(move_right) > 0.01:
                rad = math.radians(p["yaw"])
                fx, fy = math.cos(rad), math.sin(rad)
                rx, ry = math.sin(rad), -math.cos(rad)
                vx = fx * move_forward + rx * move_right
                vy = fy * move_forward + ry * move_right
                vnorm = math.hypot(vx, vy)
                if vnorm > 0:
                    vx /= vnorm
                    vy /= vnorm
                spd = p["speed"] * (0.82 if p["held_wheelbarrow"] else 1.0)
                nx = p["x"] + vx * spd * dt
                ny = p["y"] + vy * spd * dt
                nx, ny = self.resolve_collision(p["x"], p["y"], nx, ny, radius=0.26)
                p["x"], p["y"] = nx, ny
                p["z"] = self.get_floor_height(nx, ny)
                p["anim_phase"] += dt * 1.6
                if p["held_wheelbarrow"]:
                    p["anim_state"] = "hold_wheelbarrow"
                elif p["carrying_item"]:
                    p["anim_state"] = "carry"
                else:
                    p["anim_state"] = "walk"
            else:
                if p["held_wheelbarrow"]:
                    p["anim_state"] = "hold_wheelbarrow"
                elif p["carrying_item"]:
                    p["anim_state"] = "carry"
                else:
                    p["anim_state"] = "idle"

        # Si el jugador sostiene una carretilla, actualizar la posición de la carretilla frente a él
        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            rad = math.radians(p["yaw"])
            wb_x = p["x"] + math.cos(rad) * 0.75
            wb_y = p["y"] + math.sin(rad) * 0.75
            wb_x, wb_y = self.resolve_collision(wb.x, wb.y, wb_x, wb_y, radius=0.28)
            wb.x, wb.y = wb_x, wb_y
            wb.z = p["z"]
            wb.yaw = p["yaw"]

        # Actualizar concretadora, carretillas y los 3 obreros ayudantes
        self.mixer.update(dt)
        for wb in self.wheelbarrows:
            wb.update(dt)
        for npc in self.npcs:
            npc.update(dt, self)
