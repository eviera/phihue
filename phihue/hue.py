"""Local Hue API v2 client. No requests happen until explicitly invoked.

The bridge uses a local certificate. Pairing trusts its first certificate and
pins its SHA-256 fingerprint; subsequent connections must match that pin.
"""
import hashlib
import http.client
import ipaddress
import json
import ssl
from urllib.request import urlopen
from uuid import UUID


class HueError(Exception):
    pass


def validate_address(address):
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        raise HueError('Ingresá una dirección IPv4 local válida.') from None
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        raise HueError('Ingresá una dirección IPv4 local válida.')
    return str(ip)


def discover():
    try:
        with urlopen('https://discovery.meethue.com/', timeout=5) as response:
            data = json.load(response)
        if not isinstance(data, list):
            raise ValueError()
        addresses = []
        for item in data:
            address = validate_address(item['internalipaddress'])
            if address not in addresses:
                addresses.append(address)
        return addresses
    except (OSError, ValueError, KeyError, TypeError, HueError):
        raise HueError('No se pudo buscar el Bridge. Podés ingresar su IP manualmente.') from None


class HueClient:
    def __init__(self, address, key='', fingerprint=''):
        self.address = validate_address(address)
        self.key = key
        self.fingerprint = fingerprint

    def request(self, method, path, body=None, pairing=False):
        if not pairing and (not self.key or not self.fingerprint):
            raise HueError('Primero vinculá el Bridge.')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Local bridge certificates are pinned after physical-button pairing.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection(self.address, timeout=4, context=context)
        try:
            connection.connect()
            fingerprint = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if self.fingerprint and fingerprint != self.fingerprint:
                raise HueError('Cambió el certificado del Bridge. Volvé a vincularlo.')
            headers = {'Content-Type': 'application/json'}
            if self.key:
                headers['hue-application-key'] = self.key
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            if response.status in (401, 403):
                raise HueError('La vinculación venció. Volvé a vincular el Bridge.')
            if response.status >= 400:
                raise HueError('El Bridge rechazó la solicitud. Actualizá los focos e intentá de nuevo.')
            data = json.loads(response.read())
            if pairing:
                if not isinstance(data, list) or not data:
                    raise ValueError()
                for item in data:
                    if 'error' in item:
                        if item['error'].get('type') == 101:
                            raise HueError('Presioná el botón físico del Bridge y volvé a intentar.')
                        raise HueError('No se pudo vincular el Bridge.')
                key = data[0]['success']['username']
                if not isinstance(key, str) or not key:
                    raise ValueError()
                return key, fingerprint
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                raise ValueError()
            if any(error.get('error_code') == 'communication_error' for error in data.get('errors', [])):
                raise HueError('El Bridge está conectado, pero un foco no responde. Revisá su alimentación y conexión en la app Hue; luego reintentá el cambio.')
            if data.get('errors'):
                raise HueError('El Bridge rechazó la solicitud. Actualizá los focos e intentá de nuevo.')
            return data['data']
        except HueError:
            raise
        except (OSError, http.client.HTTPException):
            raise HueError('No se pudo contactar al Bridge. Revisá que estés en la misma red.') from None
        except (ValueError, KeyError, TypeError):
            raise HueError('El Bridge devolvió una respuesta inesperada.') from None
        finally:
            connection.close()

    def pair(self):
        return self.request('POST', '/api', {'devicetype': 'phihue#desktop'}, pairing=True)

    def lights(self):
        result = []
        try:
            for light in self.request('GET', '/clip/v2/resource/light'):
                # PhiHue's two slots require color-capable lights.
                if 'color' not in light or 'dimming' not in light:
                    continue
                light_id = str(UUID(light['id']))
                name = light['metadata']['name']
                if not isinstance(name, str):
                    raise ValueError()
                result.append({'id': light_id, 'name': name})
        except (KeyError, TypeError, ValueError):
            raise HueError('El Bridge devolvió una respuesta inesperada.') from None
        return result

    def light_states(self, light_ids):
        lights = self.request('GET', '/clip/v2/resource/light')
        try:
            by_id = {light['id']: light for light in lights}
            result = []
            for light_id in light_ids:
                light = by_id[light_id]
                on = light['on']['on']
                brightness = light['dimming']['brightness']
                xy = light['color']['xy']
                if type(on) is not bool or not 0 <= brightness <= 100:
                    raise ValueError()
                result.append({'on': on, 'brightness': brightness,
                               'color': xy_to_rgb(xy['x'], xy['y'])})
            if len(result) != 2:
                raise ValueError()
            return result
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            raise HueError('No se pudo consultar el estado de los dos focos. Actualizá los focos en Configuración.') from None

    def power_states(self, light_ids):
        return [light['on'] for light in self.light_states(light_ids)]

    def set_power(self, light_ids, powered):
        for light_id in light_ids:
            self.request('PUT', '/clip/v2/resource/light/' + str(UUID(light_id)), {'on': {'on': powered}})

    def apply(self, light_ids, colors, brightness, powered):
        if len(light_ids) != 2 or len(set(light_ids)) != 2:
            raise HueError('Elegí dos focos distintos.')
        for index, (light_id, color) in enumerate(zip(light_ids, colors)):
            light_id = str(UUID(light_id))
            level = brightness[index] if isinstance(brightness, list) else brightness
            power = powered[index] if isinstance(powered, list) else powered
            on = power and level > 0 and color.lower() != '#000000'
            payload = {'on': {'on': on}}
            if on:
                x, y = rgb_to_xy(color)
                payload.update(dimming={'brightness': float(level)}, color={'xy': {'x': x, 'y': y}})
            self.request('PUT', '/clip/v2/resource/light/' + light_id, payload)


def rgb_to_xy(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [((v + .055) / 1.055) ** 2.4 if v > .04045 else v / 12.92 for v in values]
    x = r * .664511 + g * .154324 + b * .162028
    y = r * .283881 + g * .668433 + b * .047685
    z = r * .000088 + g * .072310 + b * .986039
    total = x + y + z
    return (x / total, y / total) if total else (0, 0)


def xy_to_rgb(x, y):
    """Approximate a Hue xy chromaticity at full brightness for display."""
    if not (0 <= x <= 1 and 0 < y <= 1 and x + y <= 1.00001):
        raise ValueError('Invalid xy')
    X, Y, Z = x / y, 1.0, (1 - x - y) / y
    values = [max(0, X * 1.656492 - Y * .354851 - Z * .255038),
              max(0, -X * .707196 + Y * 1.655397 + Z * .036152),
              max(0, X * .051713 - Y * .121364 + Z * 1.011530)]
    scale = max(1, *values)
    values = [v / scale for v in values]
    values = [12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055 for v in values]
    return '#' + ''.join(f'{round(min(1, max(0, v)) * 255):02x}' for v in values)
