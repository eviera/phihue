# PhiHue

Aplicación en Python + PySide6 para dos focos, con conexión a un Hue Bridge mediante la API local v2. La conexión real está implementada y probada con respuestas simuladas; falta validarla con un Bridge físico.

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

## Estado actual

La tarjeta **Actual**, antes de los cinco ambientes, consulta el Bridge sin modificar las luces. Muestra encendido, brillo individual y una aproximación RGB del color informado por cada foco. Se selecciona al iniciar y al regresar de Configuración. Sus valores son una lectura puntual: pulsá Actual para actualizar cambios realizados desde otra app.

En Actual podés pulsar el color de cada foco para editarlo, ajustar su brillo con el deslizador individual debajo de cada botón. Los dos focos se muestran lado a lado, sin botones de copiar. Se envían solo los parámetros modificados y se agrupan los cambios rápidos. Esta vista no modifica los ambientes guardados. El botón de encendido envía solo encendido/apagado, conservando colores y brillos; si hay un foco encendido, permite apagar ambos. Elegir una de las cinco escenas vuelve a sus controles habituales y aplica sus ajustes.

## Conectar un Hue Bridge

1. En Configuración, buscá el Bridge en tu red o ingresá su IP local.
2. Presioná el botón físico del Bridge y luego **Vincular**. La app carga los focos disponibles.
3. Elegí dos focos de color distintos. Volvé a la pantalla principal para controlarlos.

No hay modo simulación. Los controles principales se muestran grises y deshabilitados hasta verificar la conexión y elegir ambos focos; el engranaje permanece disponible. Al abrir la app se verifica el Bridge guardado sin cambiar las luces. Si se pierde la conexión durante un comando, los controles se bloquean: desde Configuración, **Actualizar focos** permite reintentar.

La conexión, el idioma y los ambientes se guardan en el mismo `data/state.json`, excluido de Git. Incluye la clave local del Bridge: no compartas ese archivo. Las solicitudes usan HTTPS con la huella del certificado guardada durante la vinculación. **Desvincular Bridge** elimina la conexión local con confirmación y bloquea los controles, conservando ambientes e idioma; no revoca la autorización en el propio Bridge.

Referencias: [inicio y vinculación de Hue](https://developers.meethue.com/develop/get-started-2/), [API v2](https://developers.meethue.com/new-hue-api/).

## Verificar

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```
