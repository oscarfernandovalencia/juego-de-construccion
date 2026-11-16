# Project Objective — `juego-de-construccion`

> **Source of Truth**: Mirror of [`README.md`](file:///home/v1rr3eor/IAs/projects/juego-de-construccion/README.md) and [`rules/objetivo.md`](file:///home/v1rr3eor/IAs/projects/juego-de-construccion/rules/objetivo.md) (Spanish).

## 1. Objective
Maintain and evolve the Python + FreeCAD 3D interactive construction simulator (`pygame-ce`, `PyOpenGL`, `numpy`) enabling first/third-person walkthroughs and crew-assisted construction tasks inside the **Barbosa** (`ArquitectonicoBarbosa.FCStd`) and **Doradal** (`ArquitectonicoDoradal.FCStd`) residential architectural and structural models (including X-Ray rebar mode).

## 2. Rules & Guidelines
1. **Keep Virtual Environments Out of Git**: Always ignore `venv/` and `__pycache__/` in `.gitignore`.
2. **Preserve FreeCAD Source Models**: Maintain `.FCStd`, `.step`, `.glb`, and extracted 3D mesh assets alongside `extract_models.py`, `game_world.py`, `models_3d.py`, and `main.py`.
