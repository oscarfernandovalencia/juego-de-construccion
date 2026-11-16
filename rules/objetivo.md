## Objetivo y Reglas — `juego-de-construccion`

- **Objetivo**: Desarrollar y mantener un simulador interactivo en 3D (`pygame-ce` + `PyOpenGL` + `numpy` + `FreeCAD`) que permita recorrer e interactuar dentro de los modelos arquitectónicos y estructurales reales de las viviendas de **Barbosa** (`ArquitectonicoBarbosa.FCStd`) y **Doradal** (`ArquitectonicoDoradal.FCStd`), incluyendo cuadrilla de obra, maquinaria (concretadora, carretillas, pala) y visualización de acero de refuerzo (`Rebar`).
- **Reglas de Repositorio**:
  - Excluir del control de versiones (`venv/`, `__pycache__/`) mediante `.gitignore`.
  - Mantener sincronizados los scripts de inicio (`iniciar_juego.sh`, `activar_entorno.sh`) y la documentación en `README.md`.
