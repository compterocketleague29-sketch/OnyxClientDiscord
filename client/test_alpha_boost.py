import json
import tempfile
import unittest
from pathlib import Path

from alpha_boost import (
    AlphaBoostError,
    AlphaBoostManager,
    BOOST_FILENAME,
    detect_installations,
    resolve_cooked_dir,
    sha256_file,
    store_modified_file,
)


class AlphaBoostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'Rocket League test with spaces'
        self.cooked = self.root / 'TAGame' / 'CookedPCConsole'
        self.cooked.mkdir(parents=True)
        self.target = self.cooked / BOOST_FILENAME
        self.target.write_bytes(b'original game boost')
        self.modified = Path(self.temporary.name) / BOOST_FILENAME
        self.modified.write_bytes(b'modified alpha boost')
        self.backups = Path(self.temporary.name) / 'user settings' / 'backups'
        self.manager = AlphaBoostManager(self.modified, self.backups, process_check=lambda: False)

    def tearDown(self):
        self.temporary.cleanup()

    def test_resolves_game_root_and_cooked_directory_with_spaces(self):
        self.assertEqual(resolve_cooked_dir(self.root), self.cooked.resolve())
        self.assertEqual(resolve_cooked_dir(self.cooked), self.cooked.resolve())

    def test_selected_file_is_stored_for_later_sessions(self):
        stored = Path(self.temporary.name) / 'user data with spaces' / 'Alpha Boost' / BOOST_FILENAME
        store_modified_file(self.modified, stored)
        expected_hash = sha256_file(self.modified)
        self.assertEqual(sha256_file(stored), expected_hash)

        self.modified.unlink()
        manager = AlphaBoostManager(stored, self.backups, process_check=lambda: False)
        manager.activate(self.root)
        self.assertEqual(sha256_file(self.target), expected_hash)
        self.assertEqual(manager.status(self.root), 'activé')

    def test_invalid_selected_file_is_not_stored(self):
        invalid = Path(self.temporary.name) / 'other-file.upk'
        invalid.write_bytes(b'not the selected resource')
        destination = Path(self.temporary.name) / 'stored' / BOOST_FILENAME
        with self.assertRaises(AlphaBoostError):
            store_modified_file(invalid, destination)
        self.assertFalse(destination.exists())

    def test_missing_installation_is_rejected(self):
        with self.assertRaises(AlphaBoostError):
            resolve_cooked_dir(Path(self.temporary.name) / 'not installed')

        self.target.unlink()
        with self.assertRaises(AlphaBoostError):
            resolve_cooked_dir(self.root)

    def test_activation_preserves_backup_and_restore_returns_original(self):
        original_hash = sha256_file(self.target)
        self.manager.activate(self.root)
        self.assertEqual(self.manager.status(self.root), 'activé')
        self.assertEqual(sha256_file(self.target), sha256_file(self.modified))

        backups = list(self.backups.rglob('original-*.upk'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(sha256_file(backups[0]), original_hash)

        self.manager.restore(self.root)
        self.assertEqual(self.manager.status(self.root), 'désactivé')
        self.assertEqual(sha256_file(self.target), original_hash)
        self.assertEqual(len(list(self.backups.rglob('original-*.upk'))), 1)
        self.manager.activate(self.root)
        backups = list(self.backups.rglob('original-*.upk'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(sha256_file(backups[0]), original_hash)

    def test_modified_file_without_backup_is_indeterminate_and_not_overwritten(self):
        self.target.write_bytes(self.modified.read_bytes())
        self.assertEqual(self.manager.status(self.root), 'indéterminé')
        with self.assertRaises(AlphaBoostError):
            self.manager.activate(self.root)
        with self.assertRaises(AlphaBoostError):
            self.manager.restore(self.root)
        self.assertEqual(sha256_file(self.target), sha256_file(self.modified))

    def test_updated_unknown_file_cannot_be_restored_from_old_backup(self):
        old_original_hash = sha256_file(self.target)
        self.manager.activate(self.root)
        self.target.write_bytes(b'new game version')

        with self.assertRaises(AlphaBoostError):
            self.manager.restore(self.root)
        self.assertNotEqual(sha256_file(self.target), old_original_hash)

        self.manager.activate(self.root)
        self.manager.restore(self.root)
        self.assertEqual(self.target.read_bytes(), b'new game version')
        self.assertEqual(len(list(self.backups.rglob('original-*.upk'))), 2)

    def test_running_game_prevents_replacement(self):
        manager = AlphaBoostManager(self.modified, self.backups, process_check=lambda: True)
        with self.assertRaisesRegex(AlphaBoostError, 'Ferme Rocket League'):
            manager.activate(self.root)
        self.assertEqual(self.target.read_bytes(), b'original game boost')

    def test_running_game_prevents_restoration(self):
        self.manager.activate(self.root)
        manager = AlphaBoostManager(self.modified, self.backups, process_check=lambda: True)
        with self.assertRaisesRegex(AlphaBoostError, 'Ferme Rocket League'):
            manager.restore(self.root)
        self.assertEqual(sha256_file(self.target), sha256_file(self.modified))

    def test_detects_multiple_steam_and_epic_installations(self):
        steam_root = Path(self.temporary.name) / 'Steam root'
        steam_library = Path(self.temporary.name) / 'Steam library with spaces'
        epic_game = Path(self.temporary.name) / 'Epic Rocket League'
        self._create_game(steam_library / 'steamapps' / 'common' / 'Rocket League')
        self._create_game(epic_game)
        (steam_root / 'steamapps').mkdir(parents=True)
        (steam_root / 'steamapps' / 'libraryfolders.vdf').write_text(
            '"libraryfolders" { "0" { "path" "' + str(steam_root).replace('\\', '\\\\')
            + '" } "1" { "path" "' + str(steam_library).replace('\\', '\\\\') + '" } }',
            encoding='utf-8',
        )
        (steam_library / 'steamapps' / f'appmanifest_252950.acf').write_text(
            '"AppState" { "installdir" "Rocket League" }', encoding='utf-8'
        )
        epic_manifests = Path(self.temporary.name) / 'Epic manifests'
        epic_manifests.mkdir()
        (epic_manifests / 'rocket-league.item').write_text(
            json.dumps({'InstallLocation': str(epic_game)}), encoding='utf-8'
        )

        installations = detect_installations(
            steam_roots=[steam_root],
            epic_manifest_dirs=[epic_manifests],
        )
        self.assertEqual(len(installations), 2)
        self.assertEqual({installation.source for installation in installations}, {'Steam', 'Epic Games'})

    def test_detection_returns_empty_when_no_installations_exist(self):
        installations = detect_installations(
            steam_roots=[],
            epic_manifest_dirs=[Path(self.temporary.name) / 'missing manifests'],
        )
        self.assertEqual(installations, [])

    def _create_game(self, game_root):
        cooked_dir = game_root / 'TAGame' / 'CookedPCConsole'
        cooked_dir.mkdir(parents=True)
        (cooked_dir / BOOST_FILENAME).write_bytes(b'game file')


if __name__ == '__main__':
    unittest.main()
