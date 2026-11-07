import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


BOOST_FILENAME = 'Boost_Bubble_SF.upk'
STEAM_APP_ID = '252950'
MANIFEST_VERSION = 1


class AlphaBoostError(Exception):
    pass


@dataclass(frozen=True)
class GameInstallation:
    source: str
    cooked_dir: Path


def resource_path(filename):
    resource_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return resource_dir / filename


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def store_modified_file(source, destination):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if source.name.casefold() != BOOST_FILENAME.casefold() or not source.is_file():
        raise AlphaBoostError(f'Choisis un fichier valide nommé {BOOST_FILENAME}.')

    source_hash = sha256_file(source)
    if source == destination:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with source.open('rb') as input_file, tempfile.NamedTemporaryFile(
            mode='wb',
            dir=destination.parent,
            prefix=f'.{destination.name}-',
            suffix='.tmp',
            delete=False,
        ) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            while True:
                chunk = input_file.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != source_hash:
            raise AlphaBoostError('La copie du fichier Alpha Boost n’a pas pu être vérifiée.')
        os.replace(temporary, destination)
        temporary = None
        if sha256_file(destination) != source_hash:
            raise AlphaBoostError('La copie du fichier Alpha Boost n’a pas pu être vérifiée.')
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def resolve_cooked_dir(path):
    selected = Path(path).expanduser().resolve()
    if not selected.is_dir():
        raise AlphaBoostError('Le dossier sélectionné est introuvable.')

    if selected.name.casefold() == 'cookedpcconsole':
        cooked_dir = selected
    else:
        cooked_dir = selected / 'TAGame' / 'CookedPCConsole'

    if not (cooked_dir / BOOST_FILENAME).is_file():
        raise AlphaBoostError(
            f'Le fichier {BOOST_FILENAME} est absent. Choisis le dossier du jeu ou CookedPCConsole.'
        )
    return cooked_dir.resolve()


def _steam_roots_from_registry():
    if os.name != 'nt':
        return []

    import winreg

    roots = []
    key_paths = (
        r'SOFTWARE\Valve\Steam',
        r'SOFTWARE\WOW6432Node\Valve\Steam',
    )
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key_path in key_paths:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    for value_name in ('SteamPath', 'InstallPath'):
                        try:
                            value, _ = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        if value:
                            roots.append(Path(value))
            except OSError:
                continue
    return roots


def _epic_manifest_dirs():
    program_data = os.environ.get('PROGRAMDATA')
    if not program_data:
        return []
    return [Path(program_data) / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests']


def _steam_library_paths(steam_root):
    libraries = [Path(steam_root)]
    vdf = Path(steam_root) / 'steamapps' / 'libraryfolders.vdf'
    try:
        contents = vdf.read_text(encoding='utf-8-sig')
    except OSError:
        return libraries

    for match in re.finditer(r'"path"\s+"((?:[^"\\]|\\.)*)"', contents):
        value = match.group(1).replace(r'\\', '\\').replace(r'\"', '"')
        library = Path(value)
        if library not in libraries:
            libraries.append(library)
    return libraries


def _steam_installations(steam_roots):
    installations = []
    seen = set()
    for steam_root in steam_roots:
        for library in _steam_library_paths(steam_root):
            manifest = library / 'steamapps' / f'appmanifest_{STEAM_APP_ID}.acf'
            try:
                contents = manifest.read_text(encoding='utf-8-sig')
            except OSError:
                continue
            match = re.search(r'"installdir"\s+"([^"]+)"', contents, re.IGNORECASE)
            if not match:
                continue
            game_dir = library / 'steamapps' / 'common' / match.group(1)
            try:
                cooked_dir = resolve_cooked_dir(game_dir)
            except (OSError, AlphaBoostError):
                continue
            identity = os.path.normcase(str(cooked_dir))
            if identity not in seen:
                seen.add(identity)
                installations.append(GameInstallation('Steam', cooked_dir))
    return installations


def _epic_installations(manifest_dirs):
    installations = []
    seen = set()
    for manifest_dir in manifest_dirs:
        try:
            manifests = manifest_dir.glob('*.item')
        except OSError:
            continue
        for manifest in manifests:
            try:
                data = json.loads(manifest.read_text(encoding='utf-8-sig'))
                install_location = data.get('InstallLocation')
                if not install_location:
                    continue
                cooked_dir = resolve_cooked_dir(install_location)
            except (OSError, ValueError, TypeError, AlphaBoostError):
                continue
            identity = os.path.normcase(str(cooked_dir))
            if identity not in seen:
                seen.add(identity)
                installations.append(GameInstallation('Epic Games', cooked_dir))
    return installations


def detect_installations(steam_roots=None, epic_manifest_dirs=None):
    if steam_roots is None:
        steam_roots = _steam_roots_from_registry()
    if epic_manifest_dirs is None:
        epic_manifest_dirs = _epic_manifest_dirs()

    installations = _steam_installations(steam_roots)
    installations.extend(_epic_installations(epic_manifest_dirs))

    unique = {}
    for installation in installations:
        unique.setdefault(os.path.normcase(str(installation.cooked_dir)), installation)
    return sorted(unique.values(), key=lambda item: (item.source, str(item.cooked_dir).casefold()))


def is_rocket_league_running():
    if os.name != 'nt':
        return False
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq RocketLeague.exe', '/NH'],
            capture_output=True,
            text=True,
            check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AlphaBoostError(
            'Impossible de vérifier si Rocket League est ouvert. Réessaie après avoir fermé le jeu.'
        ) from error
    return any(
        line.lstrip().casefold().startswith('rocketleague.exe ')
        for line in result.stdout.splitlines()
    )


class AlphaBoostManager:
    def __init__(self, modified_file, backup_root, process_check=None):
        self.modified_file = Path(modified_file)
        self.backup_root = Path(backup_root)
        self.process_check = process_check or is_rocket_league_running

    def _modified_hash(self):
        try:
            return sha256_file(self.modified_file)
        except OSError as error:
            raise AlphaBoostError(
                'Le fichier Alpha Boost sélectionné est introuvable ou inaccessible.'
            ) from error

    def _installation_storage(self, cooked_dir):
        identity = self._installation_identity(cooked_dir)
        directory_hash = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        directory = self.backup_root / directory_hash
        return directory, directory / 'manifest.json'

    @staticmethod
    def _installation_identity(cooked_dir):
        return os.path.normcase(str(cooked_dir.resolve()))

    def _load_manifest(self, cooked_dir):
        _, manifest_path = self._installation_storage(cooked_dir)
        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            raise AlphaBoostError(
                'Les informations de sauvegarde sont illisibles. Aucun fichier n’a été modifié.'
            ) from error
        if (
            not isinstance(data, dict)
            or data.get('version') != MANIFEST_VERSION
            or data.get('installation') != self._installation_identity(cooked_dir)
            or not isinstance(data.get('backups'), list)
        ):
            raise AlphaBoostError(
                'Les informations de sauvegarde ne correspondent pas à cette installation.'
            )
        for record in data['backups']:
            if (
                not isinstance(record, dict)
                or not isinstance(record.get('sha256'), str)
                or re.fullmatch(r'[0-9a-f]{64}', record['sha256']) is None
                or record.get('file') != f"original-{record['sha256']}.upk"
            ):
                raise AlphaBoostError(
                    'Les informations de sauvegarde sont invalides. Aucun fichier n’a été modifié.'
                )
        active_hash = data.get('active_original_sha256')
        if active_hash is not None and (
            not isinstance(active_hash, str) or re.fullmatch(r'[0-9a-f]{64}', active_hash) is None
        ):
            raise AlphaBoostError(
                'Les informations de sauvegarde sont invalides. Aucun fichier n’a été modifié.'
            )
        return data

    def _write_manifest(self, cooked_dir, data):
        directory, manifest_path = self._installation_storage(cooked_dir)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=directory,
                prefix='.manifest-',
                suffix='.tmp',
                delete=False,
            ) as output:
                temporary = Path(output.name)
                json.dump(data, output, ensure_ascii=True, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, manifest_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _backup_file(self, cooked_dir, target, original_hash):
        directory, _ = self._installation_storage(cooked_dir)
        directory.mkdir(parents=True, exist_ok=True)
        backup_path = directory / f'original-{original_hash}.upk'
        if backup_path.exists():
            if sha256_file(backup_path) != original_hash:
                raise AlphaBoostError(
                    'Une sauvegarde existante est invalide. Elle a été conservée sans modification.'
                )
            return backup_path

        created = False
        try:
            with target.open('rb') as source, backup_path.open('xb') as backup:
                created = True
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    backup.write(chunk)
                backup.flush()
                os.fsync(backup.fileno())
        except FileExistsError:
            if sha256_file(backup_path) != original_hash:
                raise AlphaBoostError(
                    'Une sauvegarde existante est invalide. Elle a été conservée sans modification.'
                )
        except OSError:
            if created:
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            raise

        try:
            copied_hash = sha256_file(backup_path)
        except OSError as error:
            if created:
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            raise AlphaBoostError('La copie de sauvegarde n’a pas pu être vérifiée.') from error
        if copied_hash != original_hash:
            if created:
                backup_path.unlink(missing_ok=True)
            raise AlphaBoostError('La copie de sauvegarde n’a pas pu être vérifiée.')
        return backup_path

    @staticmethod
    def _atomic_replace(target, source, expected_hash, before_replace):
        temporary = None
        try:
            with Path(source).open('rb') as input_file, tempfile.NamedTemporaryFile(
                mode='wb',
                dir=target.parent,
                prefix=f'.{target.name}-',
                suffix='.tmp',
                delete=False,
            ) as output:
                temporary = Path(output.name)
                digest = hashlib.sha256()
                while True:
                    chunk = input_file.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != expected_hash:
                raise AlphaBoostError('La copie préparée ne correspond pas au fichier attendu.')
            before_replace()
            os.replace(temporary, target)
            temporary = None
            if sha256_file(target) != expected_hash:
                raise AlphaBoostError('La vérification du fichier installé a échoué.')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _require_game_closed(self):
        if self.process_check():
            raise AlphaBoostError('Ferme Rocket League avant de modifier ce fichier.')

    @staticmethod
    def _find_backup(manifest, original_hash):
        for record in manifest.get('backups', []):
            if isinstance(record, dict) and record.get('sha256') == original_hash:
                return record
        return None

    def status(self, path):
        cooked_dir = resolve_cooked_dir(path)
        target = cooked_dir / BOOST_FILENAME
        current_hash = sha256_file(target)
        modified_hash = self._modified_hash()

        try:
            manifest = self._load_manifest(cooked_dir)
        except AlphaBoostError:
            return 'indéterminé'
        if current_hash == modified_hash:
            if manifest is None:
                return 'indéterminé'
            active_hash = manifest.get('active_original_sha256')
            record = self._find_backup(manifest, active_hash)
            if not record or record.get('file') != f'original-{active_hash}.upk':
                return 'indéterminé'
            backup = self._installation_storage(cooked_dir)[0] / record['file']
            try:
                return 'activé' if sha256_file(backup) == active_hash else 'indéterminé'
            except OSError:
                return 'indéterminé'

        if manifest is None:
            return 'désactivé'
        for record in manifest['backups']:
            if isinstance(record, dict) and record.get('sha256') == current_hash:
                backup_name = record.get('file')
                if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
                    return 'indéterminé'
                try:
                    if sha256_file(self._installation_storage(cooked_dir)[0] / backup_name) == current_hash:
                        return 'désactivé'
                except OSError:
                    return 'indéterminé'
        return 'indéterminé'

    def activate(self, path):
        cooked_dir = resolve_cooked_dir(path)
        target = cooked_dir / BOOST_FILENAME
        modified_hash = self._modified_hash()
        self._require_game_closed()
        original_hash = sha256_file(target)
        manifest = self._load_manifest(cooked_dir)

        if original_hash == modified_hash:
            if manifest and manifest.get('active_original_sha256'):
                active_hash = manifest['active_original_sha256']
                record = self._find_backup(manifest, active_hash)
                if record and record.get('file') == f'original-{active_hash}.upk':
                    backup = self._installation_storage(cooked_dir)[0] / record['file']
                    if sha256_file(backup) == active_hash:
                        return
            raise AlphaBoostError(
                'Le fichier Alpha Boost est déjà présent sans sauvegarde vérifiable. '
                'Impossible de retrouver l’original.'
            )

        backup_path = self._backup_file(cooked_dir, target, original_hash)
        if manifest is None:
            manifest = {
                'version': MANIFEST_VERSION,
                'installation': self._installation_identity(cooked_dir),
                'backups': [],
            }
        record = self._find_backup(manifest, original_hash)
        if record is None:
            manifest['backups'].append({
                'sha256': original_hash,
                'file': backup_path.name,
            })
        else:
            record['file'] = backup_path.name
        manifest['active_original_sha256'] = original_hash
        self._write_manifest(cooked_dir, manifest)

        def verify_unchanged():
            self._require_game_closed()
            if sha256_file(target) != original_hash:
                raise AlphaBoostError(
                    'Le fichier du jeu a changé pendant l’opération. Aucun remplacement n’a été effectué.'
                )

        self._atomic_replace(target, self.modified_file, modified_hash, verify_unchanged)

    def restore(self, path):
        cooked_dir = resolve_cooked_dir(path)
        target = cooked_dir / BOOST_FILENAME
        modified_hash = self._modified_hash()
        self._require_game_closed()
        if sha256_file(target) != modified_hash:
            raise AlphaBoostError(
                'Le fichier actuel n’est pas celui d’Alpha Boost. La sauvegarde n’a pas été restaurée.'
            )

        manifest = self._load_manifest(cooked_dir)
        active_hash = manifest.get('active_original_sha256') if manifest else None
        record = self._find_backup(manifest, active_hash) if manifest else None
        if not record or record.get('file') != f'original-{active_hash}.upk':
            raise AlphaBoostError(
                'Aucune sauvegarde vérifiable ne correspond à cette installation.'
            )

        backup_path = self._installation_storage(cooked_dir)[0] / record['file']
        try:
            backup_hash = sha256_file(backup_path)
        except OSError as error:
            raise AlphaBoostError('La sauvegarde est introuvable. Aucun fichier n’a été modifié.') from error
        if backup_hash != active_hash:
            raise AlphaBoostError(
                'La sauvegarde ne correspond pas au fichier attendu. Aucun fichier n’a été modifié.'
            )

        def verify_unchanged():
            self._require_game_closed()
            if sha256_file(target) != modified_hash:
                raise AlphaBoostError(
                    'Le fichier du jeu a changé pendant l’opération. Aucun remplacement n’a été effectué.'
                )

        self._atomic_replace(target, backup_path, active_hash, verify_unchanged)
        manifest['active_original_sha256'] = None
        self._write_manifest(cooked_dir, manifest)
