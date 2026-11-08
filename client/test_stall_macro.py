import unittest
from unittest.mock import patch

from main import MacroEngine


class StallMacroTests(unittest.TestCase):
    def test_stall_taps_air_roll_then_second_key_then_jump_for_each_profile(self):
        expected = [
            ('key_down', 'q'),
            ('key_up', 'q'),
            ('key_down', 'e'),
            ('key_up', 'e'),
            ('mouse_down', 'right'),
            ('mouse_up', 'right'),
        ]

        for platform in ('PS5', 'Xbox'):
            with self.subTest(platform=platform):
                events = []
                engine = MacroEngine(controller_platform=platform)
                engine.set_enabled('Stall', True)

                with (
                    patch('main.keyboard.press', side_effect=lambda key: events.append(('key_down', key))),
                    patch('main.keyboard.release', side_effect=lambda key: events.append(('key_up', key))),
                    patch('main.mouse.press', side_effect=lambda button: events.append(('mouse_down', button))),
                    patch('main.mouse.release', side_effect=lambda button: events.append(('mouse_up', button))),
                ):
                    engine.stall()

                self.assertEqual(events, expected)


if __name__ == '__main__':
    unittest.main()
