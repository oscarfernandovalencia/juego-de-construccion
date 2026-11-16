# Juego de Construcción 3D - Casas de Barbosa y Doradal (FreeCAD + Python)

Simulador interactivo en 3D desarrollado en Python para Arch Linux (`pygame-ce` + `PyOpenGL` + `numpy` + `FreeCAD`) donde puedes recorrer e interactuar dentro de tus diseños arquitectónicos y estructurales de **Barbosa** (`ArquitectonicoBarbosa.FCStd`) y **Doradal** (`ArquitectonicoDoradal.FCStd`).

## Inicio Rápido (Entorno Virtual Automático en Bash)

Para activar automáticamente el entorno virtual e iniciar el juego 3D:

```bash
./iniciar_juego.sh
```

Si deseas únicamente abrir o activar el entorno virtual en tu terminal Bash:

```bash
./activar_entorno.sh
# o también:
source ./activar_entorno.sh
```

Para iniciar directamente en la **Casa de Doradal**:

```bash
./iniciar_juego.sh --casa doradal
```

## Elementos y Personajes Diseñados

1. **Personajes en Obra**:
   - **Jugador (Ingeniero / Maestro de Obra)**: Casco blanco de seguridad, chaleco reflectivo naranja, puede caminar dentro de las habitaciones de ambas viviendas, empujar carretillas, usar la pala y cargar materiales.
   - **Don Chucho (Oficial Palero - Casco Amarillo)**: Opera la concretadora y **llena con la pala la carretilla mientras tú o Jairo la sostienen**.
   - **Jairo (Ayudante Carretillero - Casco Naranja)**: **Sostiene la carretilla firme frente a la concretadora mientras tú (con la pala) o Don Chucho la llenan**, y luego la lleva por las puertas hacia los salones interiores de la casa.
   - **Mateo (Auxiliar de Materiales - Casco Azul)**: Transporta ladrillos, bloques y bultos de cemento desde las estibas hacia el interior de la obra o los carga en tu carretilla.
2. **Maquinaria y Materiales 3D**:
   - **Concretadora (Mezcladora de trompo)** con tambor rotatorio e inclinable en tiempo real.
   - **Carretillas de Obra** con visualización dinámica de su carga (nivel de mezcla húmeda de 1 a 3 paladas, o pilas de ladrillos, bloques y bultos de cemento).
   - **Ladrillos de arcilla tolete/farol**, **Bloques de concreto estructural**, **Bultos de cemento de 50 kg**, **Pala de obra** y **Acopio de arena, grava y agua**.

## Controles del Juego

| Tecla / Control | Acción |
| :--- | :--- |
| `W`, `A`, `S`, `D` | Mover al jugador por el patio y el interior de las casas |
| `Flechas` o `Ratón` | Girar cámara (Clic izquierdo captura el ratón, `ESC` lo libera) |
| `E` | Agarrar / Soltar **Carretilla**, o recoger / colocar **Ladrillo, Bloque, Bulto de Cemento** |
| `F` o `Espacio` | **Dar palada de mezcla** a la carretilla (que sostiene Jairo) o **Vaciar tu carretilla** |
| `P` | Equipar / Guardar la **Pala de Obra** |
| `1` | Orden a Cuadrilla: **Trabajo cooperativo autónomo** |
| `2` | Orden a Cuadrilla: **Jairo sostiene la carretilla para que TÚ la llenes con la pala (`F`)** |
| `3` | Orden a Cuadrilla: **Don Chucho llena con la pala la carretilla que TÚ sostienes (`E`)** |
| `4` | Orden a Cuadrilla: **Mateo sígueme al interior de la casa** |
| `TAB` | Alternar en vivo entre **Casa Barbosa** y **Casa Doradal** |
| `T` | Mostrar / Ocultar **Cubierta y Techo** (para ver el interior desde arriba) |
| `R` | Modo Rayos-X: Mostrar / Ocultar el **Acero de Refuerzo (`Rebar`)** de FreeCAD |
| `V` | Alternar Cámara entre **3ra Persona** y **1ra Persona** |
| `C` | Activar / Desactivar colisión con muros |
