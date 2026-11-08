import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import device_identity
from device_identity import get_device_directory, get_device_id


class DeviceIdentityTests(unittest.TestCase):
    def test_device_id_is_persisted_and_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            device_file = Path(temporary) / 'MacroClientV6' / 'device_id.txt'

            first_id = get_device_id(device_file)
            second_id = get_device_id(device_file)

            self.assertEqual(first_id, second_id)
            self.assertEqual(str(uuid.UUID(first_id)), first_id)

    def test_invalid_saved_id_is_replaced(self):
        for invalid_content in ('invalid', '', b'\xff'):
            with self.subTest(invalid_content=invalid_content):
                with tempfile.TemporaryDirectory() as temporary:
                    device_file = Path(temporary) / 'device_id.txt'
                    if isinstance(invalid_content, bytes):
                        device_file.write_bytes(invalid_content)
                    else:
                        device_file.write_text(invalid_content, encoding='utf-8')

                    device_id = get_device_id(device_file)

                    self.assertEqual(str(uuid.UUID(device_id)), device_id)
                    self.assertEqual(device_file.read_text(encoding='utf-8'), device_id)

    def test_empty_local_app_data_uses_a_stable_home_directory(self):
        with patch.dict('os.environ', {'LOCALAPPDATA': ''}):
            expected_base = (
                Path.home() / 'AppData' / 'Local'
                if device_identity.os.name == 'nt'
                else Path.home()
            )
            self.assertEqual(get_device_directory(), expected_base / 'MacroClientV6')

    def test_filesystem_failure_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            device_file = Path(temporary) / 'device_id.txt'
            with patch.object(Path, 'mkdir', side_effect=PermissionError('Access denied')):
                with self.assertRaisesRegex(PermissionError, 'Access denied'):
                    get_device_id(device_file)


if __name__ == '__main__':
    unittest.main()
