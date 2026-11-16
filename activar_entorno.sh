#!/usr/bin/env bash
# Script en Bash que inicia automáticamente el entorno virtual de Python en esta carpeta.
# Funciona tanto si lo ejecutas con:
#   source ./activar_entorno.sh
# como si lo ejecutas directamente con:
#   ./activar_entorno.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creando entorno virtual de Python..."
    python3 -m venv --system-site-packages "$SCRIPT_DIR/venv"
    "$SCRIPT_DIR/venv/bin/pip" install pygame-ce PyOpenGL trimesh pygltflib
fi

export PYTHONPATH="/usr/lib/freecad/lib:/usr/lib/freecad/Mod:${PYTHONPATH}"

# Detectar si el script fue llamado con 'source' o ejecutado directamente
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "Entorno virtual activado en la sesión actual: $(which python)"
    echo "Ejecuta 'python main.py' o './iniciar_juego.sh' para abrir el juego 3D."
else
    echo "Abriendo sesión de Bash con el entorno virtual (venv) activado automáticamente..."
    echo "Escribe 'python main.py' para iniciar el juego, o 'exit' para salir del entorno."
    exec bash --rcfile <(echo "if [ -f ~/.bashrc ]; then source ~/.bashrc; fi; source '$SCRIPT_DIR/venv/bin/activate'; export PYTHONPATH='/usr/lib/freecad/lib:/usr/lib/freecad/Mod:${PYTHONPATH}'")
fi
