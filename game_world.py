#!/usr/bin/env python3
"""
Motor lógico de simulación de obra y exploración arquitectónica, físicas de colisión 3D
con los modelos de FreeCAD (Vivienda Tipo 1 y Vivienda Tipo 2), subida por escaleras,
gestión de materiales (ladrillos, bloques, bultos de cemento, mezcla de concreto,
carretillas, concretadora) e Inteligencia Artificial de los 3 ayudantes.
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

HOUSE_ALIASES = {
    "barbosa": "tipo1",
    "doradal": "tipo2",
    "tipo1": "tipo1",
    "tipo2": "tipo2",
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
    - 'auxiliar' (Mateo): Transporta ladrillos, bloques y bultos de cemento desde el patio hacia el interior (incluyendo el 2do piso por escalera).
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

    def move_towards(self, tx, ty, speed, dt, world, ignore_walls=False, tz=None):
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
            nx, ny = world.resolve_collision(self.x, self.y, nx, ny, radius=0.24, cur_z=self.z)
            if math.hypot(nx - self.x, ny - self.y) < step * 0.25:
                door_x, door_y = world.get_nearest_entry_point(self.x, self.y, self.z, tx, ty, tz)
                ddx, ddy = door_x - self.x, door_y - self.y
                ddist = math.hypot(ddx, ddy)
                if ddist > 0.1:
                    self.yaw = math.degrees(math.atan2(ddy, ddx))
                    nx = self.x + (ddx / ddist) * step
                    ny = self.y + (ddy / ddist) * step
                    nx, ny = world.resolve_collision(self.x, self.y, nx, ny, radius=0.22, cur_z=self.z)

        self.x, self.y = nx, ny
        self.z = world.get_floor_height(self.x, self.y, cur_z=self.z)
        self.anim_phase += dt * 1.4
        return dist < 0.35

    def update(self, dt, world):
        self.z = world.get_floor_height(self.x, self.y, cur_z=self.z)
        mixer = world.mixer
        player = world.player

        # ------------------------------------------------------------------
        # ROL 1: DON CHUCHO (Oficial Palero y Operador de Concretadora)
        # ------------------------------------------------------------------
        if self.role == "palero":
            self.has_shovel = True
            target_wb = None
            if player["held_wheelbarrow"] is not None:
                wb = player["held_wheelbarrow"]
                if not wb.is_full() and len(wb.contents) == 0:
                    if world.crew_command == "fill_player_wb" or math.hypot(wb.x - mixer.x, wb.y - mixer.y) < 3.8:
                        target_wb = wb

            if target_wb is None:
                for other in world.npcs:
                    if other.role == "carretillero" and other.held_wheelbarrow is not None:
                        wb = other.held_wheelbarrow
                        if not wb.is_full() and len(wb.contents) == 0:
                            if world.crew_command != "hold_for_player" and math.hypot(wb.x - mixer.x, wb.y - mixer.y) < 2.8:
                                target_wb = wb
                                break

            if target_wb is not None:
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

                if not wb.is_full():
                    hold_x = mixer.x + 0.15
                    hold_y = mixer.y + 1.55
                    if not self.move_towards(hold_x, hold_y, speed=2.2, dt=dt, world=world):
                        self.anim_state = "hold_wheelbarrow"
                        self.status_text = "Posicionando carretilla en concretadora"
                    else:
                        self.yaw = -90.0
                        self.anim_state = "hold_wheelbarrow"
                        self.anim_phase = 0.0
                        if world.crew_command == "hold_for_player":
                            self.status_text = f"Sosteniendo carretilla para que TÚ palees ({wb.concrete_level}/3)"
                        else:
                            self.status_text = f"Sosteniendo carretilla mientras palean ({wb.concrete_level}/3)"
                else:
                    # Jairo entrega en zonas de planta baja / primer piso (sin subir escalera con carretilla)
                    p1_zones = [z for z in world.work_zones if z["pos"][2] < 2.2] or world.work_zones
                    zone = p1_zones[self.target_zone_idx % len(p1_zones)]
                    zx, zy, zz = zone["pos"]
                    if not self.move_towards(zx, zy - 0.85, speed=2.3, dt=dt, world=world, tz=zz):
                        self.anim_state = "hold_wheelbarrow"
                        self.status_text = f"Llevando carretilla llena a {zone['name']}"
                    else:
                        delivered = wb.dump_all()
                        zone["delivered"] += delivered
                        world.total_delivered += delivered
                        self.target_zone_idx = (self.target_zone_idx + 1) % len(p1_zones)
                        world.set_toast(f"Jairo descargó la carretilla en {zone['name']} (+{delivered} mezcla)")

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
                    self.move_towards(player["x"] - 0.8, player["y"] - 0.8, speed=2.6, dt=dt, world=world, tz=player["z"])
                    self.anim_state = "carry" if self.carrying_item else "walk"
                    self.status_text = "Siguiendo al Ingeniero"
                else:
                    self.anim_state = "idle"
                    self.status_text = "A tus órdenes, Ingeniero"
                return

            if self.carrying_item is None:
                stations = [s for s in world.stations if s["item_type"] in ("ladrillo", "bloque", "bulto_cemento")]
                st = stations[self.target_zone_idx % len(stations)]
                sx, sy, sz = st["pos"]
                if not self.move_towards(sx, sy + 0.75, speed=2.5, dt=dt, world=world, tz=sz):
                    self.anim_state = "walk"
                    self.status_text = f"Yendo por {ITEM_NAMES[st['item_type']]}"
                else:
                    self.carrying_item = st["item_type"]
                    self.status_text = f"Cargando {ITEM_NAMES[self.carrying_item]}"
            else:
                if (
                    player["held_wheelbarrow"] is not None
                    and player["held_wheelbarrow"].concrete_level == 0
                    and not player["held_wheelbarrow"].is_full()
                    and math.hypot(player["x"] - self.x, player["y"] - self.y) < 3.5
                    and abs(player["z"] - self.z) < 0.8
                ):
                    wb = player["held_wheelbarrow"]
                    if not self.move_towards(wb.x, wb.y, speed=2.5, dt=dt, world=world, tz=wb.z):
                        self.anim_state = "carry"
                        self.status_text = f"Llevando {ITEM_NAMES[self.carrying_item]} a tu carretilla"
                    else:
                        if wb.add_item(self.carrying_item):
                            world.set_toast(f"Mateo cargó 1 {ITEM_NAMES[self.carrying_item]} en tu carretilla")
                            self.carrying_item = None
                            self.target_zone_idx += 1
                            return

                zone = world.work_zones[self.target_zone_idx % len(world.work_zones)]
                zx, zy, zz = zone["pos"]
                if not self.move_towards(zx, zy, speed=2.4, dt=dt, world=world, tz=zz):
                    self.anim_state = "carry"
                    self.status_text = f"Transportando {ITEM_NAMES[self.carrying_item]} a {zone['name']}"
                else:
                    zone["delivered"] += 1
                    world.total_delivered += 1
                    self.carrying_item = None
                    self.target_zone_idx += 1


class ConstructionWorld:
    def __init__(self, assets_dir, initial_house="tipo1", initial_mode="obra"):
        self.assets_dir = assets_dir
        self.current_house_key = "tipo1"
        self.house_title = ""
        self.meta = {}
        self.meshes = {}
        self.floor_z = 1.32
        self.stairs_steps = []
        self.walkable_slabs = []
        self.stair_bounds = None

        # Modo de simulación: 'obra' (con cuadrilla, carretilla y pala) o 'exploracion' (solo observar)
        self.mode = initial_mode if initial_mode in ("obra", "exploracion") else "obra"

        # Visibilidad de capas arquitectónicas/estructurales
        self.show_roof = True
        self.show_rebar = False
        self.show_walls = True
        self.collision_enabled = True

        # Estado del jugador
        self.player = {
            "x": 3.8,
            "y": -2.2,
            "z": 1.32,
            "smooth_z": 1.32,
            "vz": 0.0,
            "yaw": 90.0,
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

        self.crew_command = "auto"
        self.total_delivered = 0
        self.toast_message = "¡Bienvenido! Usa WASD para moverte, [M] para Modo Exploración."
        self.toast_timer = 6.0

        self.load_house(initial_house)

    def set_toast(self, msg, duration=4.5):
        self.toast_message = msg
        self.toast_timer = duration

    def set_mode(self, mode):
        if mode not in ("obra", "exploracion"):
            return
        self.mode = mode
        p = self.player
        if mode == "exploracion":
            if p["held_wheelbarrow"] is not None:
                p["held_wheelbarrow"].holder = None
                p["held_wheelbarrow"] = None
            p["carrying_item"] = None
            p["has_shovel"] = False
            p["shovel_loaded"] = False
            p["shovel_anim_timer"] = 0.0
            self.set_toast(
                "Modo Exploración activo: recorre y observa la vivienda libremente (sin carretilla ni pala)."
            )
        else:
            self.set_toast("Modo Obra activo: interactúa con carretillas [E], pala [F] y cuadrilla [1-4].")

    def toggle_mode(self):
        next_mode = "exploracion" if self.mode == "obra" else "obra"
        self.set_mode(next_mode)

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
        house_key = HOUSE_ALIASES.get(house_key, "tipo1")
        self.current_house_key = house_key
        npz_path = os.path.join(self.assets_dir, f"{house_key}_scene.npz")
        meta_path = os.path.join(self.assets_dir, f"{house_key}_meta.json")

        with open(meta_path, "r", encoding="utf-8") as f:
            self.meta = json.load(f)
        npz_data = np.load(npz_path)
        self.meshes = {k: npz_data[k] for k in npz_data.files}
        self.floor_z = float(self.meta["floor_z"])
        self.stairs_steps = self.meta.get("stairs_steps", [])
        self.walkable_slabs = self.meta.get("walkable_slabs", [])

        if self.stairs_steps:
            xs0 = [s["box"][0] for s in self.stairs_steps]
            xs1 = [s["box"][1] for s in self.stairs_steps]
            ys0 = [s["box"][2] for s in self.stairs_steps]
            ys1 = [s["box"][3] for s in self.stairs_steps]
            zs1 = [s["z_top"] for s in self.stairs_steps]
            self.stair_bounds = (min(xs0), max(xs1), min(ys0), max(ys1), max(zs1))
        else:
            self.stair_bounds = None

        self.loose_items.clear()
        self.particles.clear()

        if house_key == "tipo1":
            self.house_title = "Vivienda Tipo 1 — Estructura Metálica en Ladera"
            fz = self.floor_z  # 1.32 m
            self.player.update({
                "x": 3.8, "y": -2.2, "z": fz, "smooth_z": fz, "vz": 0.0, "yaw": 90.0,
                "carrying_item": None, "held_wheelbarrow": None,
                "has_shovel": False, "shovel_loaded": False, "shovel_anim_timer": 0.0,
            })
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
            self.loose_items = [
                {"type": "ladrillo", "x": 3.6, "y": 1.4, "z": fz, "yaw": 15.0},
                {"type": "ladrillo", "x": 3.9, "y": 1.5, "z": fz, "yaw": -20.0},
                {"type": "bloque", "x": 2.2, "y": 2.2, "z": fz, "yaw": 0.0},
                {"type": "bulto_cemento", "x": 4.8, "y": 1.8, "z": fz, "yaw": 45.0},
            ]
            self.work_zones = [
                {"name": "Sala Principal (Acceso)", "pos": (4.4, 2.1, fz), "delivered": 0, "target": 10},
                {"name": "Habitación Central", "pos": (2.2, 5.2, fz), "delivered": 0, "target": 10},
                {"name": "Balcón / Terraza Mirador", "pos": (4.2, 11.8, fz), "delivered": 0, "target": 10},
            ]
            self.npcs = [
                NPCWorker(1, "Don Chucho (Palero)", "palero", 1.1, -2.8, fz,
                          helmet_color=(0.95, 0.82, 0.10), vest_color=(0.92, 0.48, 0.10), shirt_color=(0.16, 0.34, 0.62)),
                NPCWorker(2, "Jairo (Carretillero)", "carretillero", 2.15, -1.2, fz,
                          helmet_color=(0.95, 0.42, 0.08), vest_color=(0.45, 0.85, 0.15), shirt_color=(0.22, 0.26, 0.34)),
                NPCWorker(3, "Mateo (Auxiliar)", "auxiliar", 5.4, -2.2, fz,
                          helmet_color=(0.15, 0.55, 0.92), vest_color=(0.92, 0.78, 0.12), shirt_color=(0.25, 0.48, 0.32)),
            ]

        else:
            self.house_title = "Vivienda Tipo 2 — Aporticada + Ampliación (2 Pisos con Escalera)"
            fz = self.floor_z  # 0.10 m en losa Piso 1, 0.00 m en terreno/acceso escalera
            self.player.update({
                "x": 14.2, "y": -2.6, "z": 0.0, "smooth_z": 0.0, "vz": 0.0, "yaw": 90.0,
                "carrying_item": None, "held_wheelbarrow": None,
                "has_shovel": False, "shovel_loaded": False, "shovel_anim_timer": 0.0,
            })
            self.mixer = ConcreteMixer(x=14.2, y=-3.7, z=0.0, yaw=0.0)
            self.stations = [
                {"name": "Pila de Arena, Grava y Agua", "item_type": "arena", "pos": (12.2, -3.7, 0.0), "stock": 99},
                {"name": "Estiba de Ladrillos Tolete", "item_type": "ladrillo", "pos": (10.5, -2.0, 0.0), "stock": 16},
                {"name": "Estiba de Bloques #4", "item_type": "bloque", "pos": (16.8, -2.0, 0.0), "stock": 16},
                {"name": "Estiba de Bultos de Cemento", "item_type": "bulto_cemento", "pos": (18.4, -3.5, 0.0), "stock": 16},
            ]
            self.wheelbarrows = [
                Wheelbarrow(1, x=14.35, y=-2.05, z=0.0, yaw=-90.0),
                Wheelbarrow(2, x=12.50, y=-1.95, z=0.0, yaw=90.0),
            ]
            self.loose_items = [
                {"type": "ladrillo", "x": 13.5, "y": 1.8, "z": fz, "yaw": 10.0},
                {"type": "bloque", "x": 16.7, "y": 3.0, "z": 0.0, "yaw": -15.0},
                {"type": "bulto_cemento", "x": 15.0, "y": 6.2, "z": fz, "yaw": 30.0},
            ]
            self.work_zones = [
                {"name": "Local / Restaurante (Piso 1)", "pos": (14.2, 3.0, fz), "delivered": 0, "target": 10},
                {"name": "Apartamento (Piso 1)", "pos": (14.2, 7.2, fz), "delivered": 0, "target": 10},
                {"name": "Ampliación / Terraza (Piso 2)", "pos": (15.2, 12.2, 3.20), "delivered": 0, "target": 10},
            ]
            self.npcs = [
                NPCWorker(1, "Don Chucho (Palero)", "palero", 13.3, -3.0, 0.0,
                          helmet_color=(0.95, 0.82, 0.10), vest_color=(0.92, 0.48, 0.10), shirt_color=(0.16, 0.34, 0.62)),
                NPCWorker(2, "Jairo (Carretillero)", "carretillero", 14.35, -1.35, 0.0,
                          helmet_color=(0.95, 0.42, 0.08), vest_color=(0.45, 0.85, 0.15), shirt_color=(0.22, 0.26, 0.34)),
                NPCWorker(3, "Mateo (Auxiliar)", "auxiliar", 17.2, -2.2, 0.0,
                          helmet_color=(0.15, 0.55, 0.92), vest_color=(0.92, 0.78, 0.12), shirt_color=(0.25, 0.48, 0.32)),
            ]

        mode_lbl = "Exploración" if self.mode == "exploracion" else "Obra"
        self.set_toast(f"Cargado ({mode_lbl}): {self.house_title}")

    def _base_ground_z(self, x, y):
        if self.current_house_key == "tipo1":
            if -3.0 <= x <= 9.0 and -7.0 <= y <= 14.2:
                return self.floor_z
            if y > 0.0:
                return max(-8.2, -0.5 * y)
            return self.floor_z
        return 0.0

    def get_floor_height(self, x, y, cur_z=None):
        """
        Calcula la cota Z transitable bajo (x, y) considerando el terreno,
        las losas de FreeCAD (Piso 1 y Piso 2) y los peldaños reales de la escalera.
        """
        if cur_z is None:
            cur_z = self.player["z"]

        candidates = [self._base_ground_z(x, y)]

        # 1. Losas transitables (con margen de 12 cm para cruzar juntas sobre vigas)
        pad_slab = 0.12
        for slab in self.walkable_slabs:
            b = slab["box"]
            if (b[0] - pad_slab) <= x <= (b[1] + pad_slab) and (b[2] - pad_slab) <= y <= (b[3] + pad_slab):
                if b[5] <= cur_z + 0.38:
                    candidates.append(b[5])

        # 2. Peldaños de escalera extraídos de FreeCAD
        for step in self.stairs_steps:
            b = step["box"]
            if (b[0] - 0.04) <= x <= (b[1] + 0.04) and (b[2] - 0.08) <= y <= (b[3] + 0.08):
                if step["z_top"] <= cur_z + 0.38:
                    candidates.append(step["z_top"])

        return max(candidates)

    def get_current_zone_label(self):
        p = self.player
        x, y, z = p["x"], p["y"], p["z"]
        if self.current_house_key == "tipo2":
            if self.stair_bounds is not None:
                sx0, sx1, sy0, sy1, _ = self.stair_bounds
                if (sx0 - 0.15) <= x <= (sx1 + 0.15) and (sy0 - 0.1) <= y <= (sy1 + 0.1) and 0.15 < z < 2.95:
                    return f"Escalera (Z={z:.2f}m)"
            if z >= 2.75:
                return f"Segundo Piso (Z={z:.2f}m)"
            if 9.8 <= x <= 17.5 and 0.0 <= y <= 10.0:
                return f"Primer Piso - Interior (Z={z:.2f}m)"
            return f"Planta Baja / Exterior (Z={z:.2f}m)"
        else:
            if -0.1 <= x <= 6.1 and 10.5 <= y <= 14.1:
                return f"Balcón / Terraza Mirador (Z={z:.2f}m)"
            if -0.1 <= x <= 6.1 and 0.0 <= y < 10.5:
                return f"Interior Vivienda Tipo 1 (Z={z:.2f}m)"
            return f"Patio / Exterior (Z={z:.2f}m)"

    def get_nearest_entry_point(self, x, y, cur_z, tx, ty, tz=None):
        """Auxiliar de navegación para que los NPC entren por puertas y suban la escalera."""
        if self.current_house_key == "tipo1":
            waypoints = [(4.4, -0.4), (4.4, 1.2), (2.3, 3.5), (4.4, 3.5), (2.5, 7.0), (2.5, 10.5), (4.4, 10.5)]
        else:
            if tz is not None and tz > 2.2 and cur_z < 2.2:
                # Rutas hacia la base de la escalera y subida por la misma
                if x < 17.2 or y < 9.5:
                    return (17.7, max(y, 10.5))
                return (12.6, 10.5)
            if cur_z > 2.2 and (tz is None or tz < 1.5):
                # Bajar por la escalera desde el 2do piso
                if x > 12.7 and y > 11.0:
                    return (12.6, 10.5)
                return (17.6, 10.5)
            waypoints = [
                (13.5, -0.5), (13.5, 1.0),
                (16.6, -0.5), (16.6, 5.4), (15.2, 5.4),
                (17.7, 5.4), (17.7, 10.5),
                (12.6, 10.5), (14.5, 11.8),
            ]

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

    def resolve_collision(self, old_x, old_y, new_x, new_y, radius=0.26, cur_z=None):
        if not self.collision_enabled:
            return new_x, new_y
        if cur_z is None:
            cur_z = self.player["z"]

        body_min_z = cur_z + 0.35
        body_max_z = cur_z + 1.65

        raw_colliders = (
            self.meta.get("wall_colliders", [])
            + self.meta.get("column_colliders", [])
            + self.meta.get("railing_colliders", [])
        )
        active_boxes = []
        for c in raw_colliders:
            b = c["box"]
            if b[4] < body_max_z and b[5] > body_min_z:
                active_boxes.append(b)

        # Bloqueadores laterales de los peldaños altos de escalera (no atravesar de lado el cuerpo macizo)
        for step in self.stairs_steps:
            b = step["box"]
            if step["z_top"] > cur_z + 0.38 and b[4] < cur_z + 1.55:
                active_boxes.append(b)

        # Barandillas laterales y tope de desembarco mientras el personaje está en la escalera
        if self.stair_bounds is not None:
            sx0, sx1, sy0, sy1, sz_max = self.stair_bounds
            if 0.20 < cur_z < (sz_max - 0.12):
                active_boxes.append([sx0 + 0.15, sx1 - 0.10, sy0 - 0.10, sy0 + 0.02, 0.0, sz_max + 1.5])
                active_boxes.append([sx0 + 0.15, sx1 - 0.10, sy1 - 0.02, sy1 + 0.10, 0.0, sz_max + 1.5])
            if cur_z >= (sz_max - 0.25):
                # Evitar caer por el borde trasero del escalón superior al llegar al 2do piso
                active_boxes.append([sx0 - 0.36, sx0 - 0.18, sy0 - 0.05, sy1 + 0.05, sz_max - 0.5, sz_max + 1.5])

        res_x = new_x
        for b in active_boxes:
            if self._circle_intersects_box(res_x, old_y, radius, b):
                res_x = old_x
                break

        res_y = new_y
        for b in active_boxes:
            if self._circle_intersects_box(res_x, res_y, radius, b):
                res_y = old_y
                break

        return res_x, res_y

    def player_interact_e(self):
        """Tecla [E]: Agarrar/Soltar Carretilla, o Recoger/Soltar Ladrillos, Bloques y Bultos de Cemento."""
        if self.mode == "exploracion":
            self.set_toast("Modo Exploración: solo observación (presiona [M] para volver a Modo Obra).")
            return

        p = self.player

        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            wb.holder = None
            p["held_wheelbarrow"] = None
            self.set_toast(f"Soltaste la Carretilla #{wb.id} ({wb.get_summary()})")
            return

        for wb in self.wheelbarrows:
            if math.hypot(wb.x - p["x"], wb.y - p["y"]) < 1.55 and abs(wb.z - p["z"]) < 1.0:
                if p["carrying_item"] is not None:
                    if wb.add_item(p["carrying_item"]):
                        self.set_toast(f"Cargaste 1 {ITEM_NAMES[p['carrying_item']]} en la Carretilla #{wb.id}")
                        p["carrying_item"] = None
                    else:
                        self.set_toast("La carretilla ya está llena o tiene mezcla húmeda.")
                    return

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

        if p["carrying_item"] is not None:
            item = p["carrying_item"]
            if math.hypot(self.mixer.x - p["x"], self.mixer.y - p["y"]) < 1.8 and item == "bulto_cemento":
                self.mixer.add_material(item)
                p["carrying_item"] = None
                self.set_toast("Vaciaste 1 Bulto de Cemento dentro de la Concretadora.")
                return

            for zone in self.work_zones:
                zx, zy, zz = zone["pos"]
                if math.hypot(zx - p["x"], zy - p["y"]) < 1.65 and abs(zz - p["z"]) < 1.2:
                    zone["delivered"] += 1
                    self.total_delivered += 1
                    p["carrying_item"] = None
                    self.set_toast(f"Entregaste {ITEM_NAMES[item]} en {zone['name']}!")
                    return

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

        for idx, it in enumerate(self.loose_items):
            if math.hypot(it["x"] - p["x"], it["y"] - p["y"]) < 1.35 and abs(it["z"] - p["z"]) < 1.0:
                p["carrying_item"] = it["type"]
                p["has_shovel"] = False
                self.loose_items.pop(idx)
                self.set_toast(f"Recogiste {ITEM_NAMES[p['carrying_item']]}. Llévalo a la carretilla o dentro de la casa.")
                return

        for st in self.stations:
            sx, sy, sz = st["pos"]
            if math.hypot(sx - p["x"], sy - p["y"]) < 1.65 and abs(sz - p["z"]) < 1.0:
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
        - Si estás junto a la concretadora y una carretilla -> Dar una palada para llenar la carretilla.
        """
        if self.mode == "exploracion":
            self.set_toast("Modo Exploración: solo observación (presiona [M] para volver a Modo Obra).")
            return

        p = self.player

        if p["held_wheelbarrow"] is not None:
            wb = p["held_wheelbarrow"]
            if wb.is_empty():
                if math.hypot(wb.x - self.mixer.x, wb.y - self.mixer.y) < 3.5:
                    self.crew_command = "fill_player_wb"
                    self.set_toast("¡Don Chucho viene con la pala a llenar tu carretilla mientras tú la sostienes!")
                else:
                    self.set_toast("La carretilla está vacía. Llévala junto a la concretadora o cárgale materiales.")
                return

            for zone in self.work_zones:
                zx, zy, zz = zone["pos"]
                if math.hypot(zx - wb.x, zy - wb.y) < 2.2 and abs(zz - wb.z) < 1.2:
                    count = wb.dump_all()
                    zone["delivered"] += count
                    self.total_delivered += count
                    self.set_toast(f"¡Descargaste la carretilla en {zone['name']} (+{count} unidades de obra)!")
                    return

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

        nearest_wb = None
        for wb in self.wheelbarrows:
            if math.hypot(wb.x - p["x"], wb.y - p["y"]) < 2.3 and abs(wb.z - p["z"]) < 1.0:
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

        if math.hypot(self.mixer.x - p["x"], self.mixer.y - p["y"]) < 2.2:
            self.mixer.is_running = not self.mixer.is_running
            estado = "ENCENDIDA" if self.mixer.is_running else "PAUSADA"
            self.set_toast(f"Concretadora {estado}.")
            return

        self.set_toast("Acércate a la carretilla que sostiene Jairo para palear mezcla con [F], o vacía tu carretilla.")

    def toggle_shovel(self):
        if self.mode == "exploracion":
            self.set_toast("Modo Exploración activo: sin herramientas de obra. Presiona [M] para Modo Obra.")
            return

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
        if self.mode == "exploracion":
            self.set_toast("Modo Exploración activo: sin cuadrilla. Presiona [M] para Modo Obra.")
            return

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
            self.set_toast("Orden a Cuadrilla [4]: ¡Mateo te sigue por la vivienda!")

    def update(self, dt, move_forward, move_right, sprint=False):
        if self.toast_timer > 0.0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        # Actualizar partículas de mezcla
        if self.mode == "obra" and self.particles:
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
        if p["shovel_anim_timer"] > 0.0 and self.mode == "obra":
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
                spd = p["speed"]
                if p["held_wheelbarrow"] is not None:
                    spd *= 0.82
                elif sprint:
                    spd *= 1.65
                nx = p["x"] + vx * spd * dt
                ny = p["y"] + vy * spd * dt
                nx, ny = self.resolve_collision(p["x"], p["y"], nx, ny, radius=0.26, cur_z=p["z"])
                p["x"], p["y"] = nx, ny
                p["anim_phase"] += dt * (2.2 if sprint else 1.6)
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

        # Físicas verticales: escalones de escalera, losas de 2do piso y gravedad suave
        target_z = self.get_floor_height(p["x"], p["y"], cur_z=p["z"])
        if target_z >= p["z"] - 0.45:
            p["z"] = target_z
            p["vz"] = 0.0
        else:
            p["vz"] -= 14.0 * dt
            p["z"] += p["vz"] * dt
            if p["z"] <= target_z:
                p["z"] = target_z
                p["vz"] = 0.0

        # Suavizado visual para subir/bajar los 17 escalones sin saltos bruscos de cámara
        z_diff = p["z"] - p["smooth_z"]
        if abs(z_diff) < 0.002:
            p["smooth_z"] = p["z"]
        else:
            p["smooth_z"] += z_diff * min(1.0, 16.0 * dt)

        if self.mode == "obra":
            if p["held_wheelbarrow"] is not None:
                wb = p["held_wheelbarrow"]
                rad = math.radians(p["yaw"])
                wb_x = p["x"] + math.cos(rad) * 0.75
                wb_y = p["y"] + math.sin(rad) * 0.75
                wb_x, wb_y = self.resolve_collision(wb.x, wb.y, wb_x, wb_y, radius=0.28, cur_z=p["z"])
                wb.x, wb.y = wb_x, wb_y
                wb.z = p["z"]
                wb.yaw = p["yaw"]

            self.mixer.update(dt)
            for wb in self.wheelbarrows:
                wb.update(dt)
            for npc in self.npcs:
                npc.update(dt, self)
