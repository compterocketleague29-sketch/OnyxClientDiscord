import os
import uuid
from pathlib import Path


def get_device_directory():
    local_app_data = os.environ.get('LOCALAPPDATA', '').strip()
    if local_app_data:
        base_directory = Path(local_app_data)
    elif os.name == 'nt':
        base_directory = Path.home() / 'AppData' / 'Local'
    else:
        base_directory = Path.home()
    return base_directory / 'MacroClientV6'


def get_device_id(device_file):
    device_file.parent.mkdir(parents=True, exist_ok=True)

    for _ in range(2):
        try:
            existing = device_file.read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            existing = None
        except UnicodeDecodeError:
            device_file.unlink()
            existing = None

        if existing is not None:
            try:
                return str(uuid.UUID(existing))
            except ValueError:
                device_file.unlink()

        device_id = str(uuid.uuid4())
        try:
            with device_file.open('x', encoding='utf-8') as file:
                file.write(device_id)
            return device_id
        except FileExistsError:
            continue

    raise OSError(f'Impossible de créer un identifiant stable dans {device_file}.')
