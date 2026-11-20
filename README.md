# Simulador 3D de Construcción y Exploración — Viviendas Tipo 1 y Tipo 2 (FreeCAD + Python)

Simulador interactivo en 3D desarrollado en Python para Arch Linux (`pygame-ce` + `PyOpenGL` + `numpy` + `FreeCAD`) donde puedes recorrer, inspeccionar e interactuar dentro de tus diseños arquitectónicos y estructurales de **Vivienda Tipo 1** (`Vivienda_Estructura_Metalica_Tipo_01.FCStd`) y **Vivienda Tipo 2** (`Vivienda_Aporticado_Metalica_Tipo_02.FCStd`, con 2 pisos y escalera real transitable).

## Inicio Rápido (Entorno Virtual Automático en Bash)

Para activar automáticamente el entorno virtual e iniciar el simulador 3D:

```bash
./iniciar_juego.sh
```

Para iniciar directamente en la **Vivienda Tipo 2** (con escalera al 2do piso) o en **Modo Exploración** (solo observar, sin carretilla ni pala):

```bash
./iniciar_juego.sh --casa tipo2 --modo exploracion
```

Si deseas únicamente activar el entorno virtual en tu terminal Bash:

```bash
./activar_entorno.sh
# o también:
source ./activar_entorno.sh
```

Si modificas los archivos `.FCStd`, vuelve a extraer las mallas 3D con:

```bash
python extract_models.py
```

## Modos del Simulador

1. **Modo Exploración (`[M]` o `--modo exploracion`)**:
   - Recorrido arquitectónico y estructural limpio, **sin cargar carretilla, materiales ni pala**, ideal para simplemente observar la vivienda.
   - Permite caminar y correr (`Shift`), subir y bajar por la **escalera real** de la Vivienda Tipo 2 hacia el 2do piso, activar vista en 1ra/3ra persona (`[V]`), ocultar el techo (`[T]`) y activar Rayos-X de acero de refuerzo (`[R]`).
2. **Modo Obra (`[M]` o `--modo obra`)**:
   - **Jugador (Ingeniero / Maestro de Obra)**: Casco blanco, chaleco naranja, puede empujar carretillas, usar la pala y cargar ladrillos, bloques y bultos de cemento.
   - **Don Chucho (Palero - Casco Amarillo)**, **Jairo (Carretillero - Casco Naranja)** y **Mateo (Auxiliar - Casco Azul)**: Cuadrilla cooperativa que opera la concretadora y transporta materiales (Mateo incluso sube por la escalera al 2do piso en Tipo 2).

## Controles del Juego

| Tecla / Control | Acción |
| :--- | :--- |
| `W`, `A`, `S`, `D` | Mover al personaje (mantén `Shift` para correr) |
| `Flechas` o `Ratón` | Girar cámara (Clic izquierdo captura el ratón, `ESC` lo libera) |
| `Rueda del Ratón` | Acercar / Alejar zoom de cámara en 3ra Persona |
| `M` | Alternar entre **Modo Exploración** (solo observar) y **Modo Obra** |
| `TAB` | Alternar entre **Vivienda Tipo 1** y **Vivienda Tipo 2** |
| `V` | Alternar Cámara entre **3ra Persona** y **1ra Persona** |
| `T` | Mostrar / Ocultar **Cubierta y Tejas** (para ver el interior desde arriba) |
| `R` | Modo Rayos-X: Mostrar / Ocultar el **Acero de Refuerzo (`Rebar`)** de FreeCAD |
| `C` | Activar / Desactivar colisión con muros |
| `E` | *[Modo Obra]* Agarrar / Soltar **Carretilla**, o recoger / colocar **Ladrillo, Bloque, Cemento** |
| `F` o `Espacio` | *[Modo Obra]* **Dar palada de mezcla** a la carretilla o **Vaciar tu carretilla** |
| `P` | *[Modo Obra]* Equipar / Guardar la **Pala de Obra** |
| `1` .. `4` | *[Modo Obra]* Órdenes a la cuadrilla (Auto / Jairo sostiene / Don Chucho llena / Mateo sígueme) |
