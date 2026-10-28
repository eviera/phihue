# PhiHue

Aplicación en Python + PySide6 para dos focos, con simulación local y conexión opcional a un Hue Bridge mediante la API local v2. La conexión real está implementada y probada con respuestas simuladas; falta validarla con un Bridge físico.

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

El engranaje de la esquina superior derecha abre Configuración. El selector Español / English cambia el idioma al instante y lo guarda en el campo `language` del mismo `data/state.json`. Los archivos anteriores usan español por defecto. Los nombres de los ambientes se conservan tal como los escribiste.

Desde Configuración también podés restaurar los valores iniciales: se pide confirmación antes de reemplazar los ajustes guardados por los cinco ambientes originales. Se conservan el idioma y la vinculación del Bridge. «Volver» regresa a los ambientes sin cambiar sus ajustes.

## Conectar un Hue Bridge

1. En casa, conectá la computadora a la misma red que el Bridge y abrí Configuración.
2. Elegí **Buscar Bridge** (usa el servicio HTTPS de descubrimiento de Hue). Si no aparece, ingresá su IPv4 local manualmente. Si aparecen varios, elegí el correspondiente.
3. Presioná el botón físico del Bridge y enseguida elegí **Vincular**. Si todavía no lo presionaste, se muestra un aviso y podés volver a intentar.
4. Elegí dos focos diferentes de la lista. Solo aparecen focos que admiten color y brillo. **Actualizar focos** vuelve a consultar el Bridge.
5. Cambiá el modo a **Focos reales** para aplicar el ambiente actual. Los siguientes cambios de color, brillo y encendido se envían en segundo plano. **Aplicar ambiente** permite reintentar después de una desconexión.

En **Simulación** no se envían cambios a los focos. Al iniciar la app no se hacen solicitudes ni se aplica un ambiente automáticamente, incluso si el modo guardado es Focos reales. Los errores no borran los esquemas ni la vinculación. Un fallo entre las dos solicitudes puede dejar un solo foco actualizado; usá Aplicar ambiente para reintentar.

La sección `bridge` de `data/state.json` guarda IP, clave local, huella del certificado, focos seleccionados y modo. El JSON continúa excluido de Git y se escribe con permisos privados donde el sistema lo permite. No compartas ese archivo: contiene la clave del Bridge. La conexión usa HTTPS, confía en el certificado inicial durante la vinculación con el botón físico y verifica su huella en conexiones posteriores. Si el certificado cambia, hace falta volver a vincular. No se usa acceso remoto ni una cuenta Hue.

**Desvincular Bridge** pide confirmación, borra la conexión de esta app y vuelve a simulación conservando ambientes e idioma. Funciona sin estar en casa y cancela los cambios pendientes. Si hay una solicitud en curso, el botón espera a que termine. Esto elimina la clave local; no revoca la autorización en el propio Bridge.

Referencias: [inicio y vinculación de Hue](https://developers.meethue.com/develop/get-started-2/), [API v2](https://developers.meethue.com/new-hue-api/).

## Verificar

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```
