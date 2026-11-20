## Objetivo y Reglas — `juego-de-construccion`

- **Objetivo**: Desarrollar y mantener un simulador interactivo en 3D (`pygame-ce` + `PyOpenGL` + `numpy` + `FreeCAD`) que permita recorrer e interactuar dentro de los modelos arquitectónicos y estructurales reales de las viviendas **Tipo 1** (`Vivienda_Estructura_Metalica_Tipo_01.FCStd`) y **Tipo 2** (`Vivienda_Aporticado_Metalica_Tipo_02.FCStd`), incluyendo subida/bajada por escalera al 2do piso, **Modo Exploración** (solo observar sin carretilla ni pala), cuadrilla de obra, maquinaria y visualización de acero de refuerzo (`Rebar`).
- **Reglas de Repositorio**:
  - Excluir del control de versiones (`venv/`, `__pycache__/`) mediante `.gitignore`.
  - Mantener sincronizados los scripts de inicio (`iniciar_juego.sh`, `activar_entorno.sh`) y la documentación en `README.md`.
