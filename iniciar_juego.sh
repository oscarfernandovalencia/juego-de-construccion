#!/usr/bin/env bash
# Script para activar automáticamente el entorno virtual e iniciar el Juego de Construcción 3D
# Compatible con ejecución directa (./iniciar_juego.sh) o source (source iniciar_juego.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creando entorno virtual de Python..."
    python3 -m venv --system-site-packages "$SCRIPT_DIR/venv"
    "$SCRIPT_DIR/venv/bin/pip" install pygame-ce PyOpenGL trimesh pygltflib
fi

# Activar entorno virtual
source "$SCRIPT_DIR/venv/bin/activate"
export PYTHONPATH="/usr/lib/freecad/lib:/usr/lib/freecad/Mod:${PYTHONPATH}"

echo "=========================================================="
echo "  Entorno virtual activado: $(which python)"
echo "  Proyecto: Simulador de Obra 3D - Casas Barbosa y Doradal"
echo "=========================================================="

# Si aún no se han extraído las mallas optimizadas de FreeCAD, extraerlas
if [ ! -f "$SCRIPT_DIR/assets/barbosa_scene.npz" ] || [ ! -f "$SCRIPT_DIR/assets/doradal_scene.npz" ]; then
    echo "Procesando modelos de FreeCAD (Barbosa y Doradal)..."
    python "$SCRIPT_DIR/extract_models.py"
fi

# Si no se pasa el argumento --solo-entorno, iniciar el juego automáticamente
if [ "$1" != "--solo-entorno" ]; then
    echo "Iniciando el juego de construcción 3D..."
    python "$SCRIPT_DIR/main.py" "$@"
else
    echo "Modo solo entorno activo. Ejecuta 'python main.py' cuando quieras iniciar."
fi
