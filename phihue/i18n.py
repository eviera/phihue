"""Interface translations. Scheme names remain user-owned data."""

ENGLISH = {
    'PhiHue · Simulador': 'PhiHue · Simulator',
    '●  Simulación local': '●  Local simulation',
    'TUS AMBIENTES': 'YOUR SCENES',
    'Personalizá tu ambiente': 'Customize your scene',
    'Nombre del esquema': 'Scene name',
    'Copiar color del foco {source} al foco {target}': 'Copy color from light {source} to light {target}',
    'Brillo común de los dos focos': 'Shared brightness for both lights',
    'Configuración': 'Settings',
    'Abrir configuración': 'Open settings',
    'Encender o apagar ambos focos': 'Turn both lights on or off',
    'No se pudo leer el guardado. Se cargaron los valores iniciales.': 'Could not read saved settings. Defaults have been loaded.',
    '← Volver': '← Back',
    'Idioma': 'Language',
    'Restaurar valores iniciales': 'Restore defaults',
    'Restaurá los cinco ambientes originales: nombres, colores, brillo y encendido. Se conserva el idioma elegido.': 'Restore the five original scenes: names, colors, brightness and power. Your chosen language is kept.',
    '¿Querés borrar tu configuración guardada?': 'Reset your saved scene settings?',
    'Se perderán los nombres, colores y ajustes personalizados de todos los ambientes. Esta acción no se puede deshacer.': 'Custom names, colors and settings for all scenes will be lost. This cannot be undone.',
    'Restaurar': 'Restore',
    'Cancelar': 'Cancel',
    'No se pudo restaurar': 'Could not restore defaults',
    'No se pudo guardar': 'Could not save',
    'No se pudo guardar: {error}': 'Could not save: {error}',
    'Foco {number}': 'Light {number}',
    'Brillo común · {value}%': 'Shared brightness · {value}%',
    'Apagar': 'Turn off',
    'Encender': 'Turn on',
    'Color del foco {number}': 'Light {number} color',
}


def translate(language, text, **values):
    template = ENGLISH.get(text, text) if language == 'en' else text
    return template.format(**values)
