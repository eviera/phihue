# PhiHue

Prototipo local en Python + PySide6 para dos focos simulados. No utiliza red, credenciales ni Bridge.

## Ejecutar en macOS / Linux

```sh
cd ~/workspace/phihue
.venv/bin/python -m phihue
```

Para reconstruir el entorno (la instalación inicial necesita acceso a PyPI):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Windows: `py -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt` y `.venv\Scripts\python -m phihue`.

## Uso

Cinco tarjetas seleccionan ambientes con dos colores independientes. Los botones `1 → 2` y `1 ← 2` copian el color una sola vez; no vinculan ediciones futuras.

El selector de color aplica cada cambio en vivo, sin confirmar. El brillo común se refleja en ambas luces y muestras de color. El botón circular de encendido controla ambos focos simulados.

Cada cambio de color, brillo, nombre válido, ambiente seleccionado o encendido se escribe inmediatamente en `data/state.json`. Al abrir se recupera el último estado. Los esquemas antiguos se abren con colores independientes. No se muestra texto de guardado exitoso; los errores sí se avisan.

Pendiente para una futura pantalla de setup: acción explícita para borrar la configuración de luces y restaurar defaults razonables. No implementar aún.

## Verificar

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```
