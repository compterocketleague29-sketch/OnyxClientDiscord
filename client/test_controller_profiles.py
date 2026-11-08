import unittest
from types import SimpleNamespace

import pygame

from controller_profiles import ps5, xbox


class ControllerProfileTests(unittest.TestCase):
    def test_xbox_dpad_down_triggers_stall_from_hat(self):
        event = SimpleNamespace(type=pygame.JOYHATMOTION, value=(0, -1))
        self.assertTrue(xbox.read_event(event)['stall'])

    def test_ps5_dpad_down_triggers_stall_from_hat(self):
        event = SimpleNamespace(type=pygame.JOYHATMOTION, value=(0, -1))
        self.assertTrue(ps5.read_event(event)['stall'])

    def test_xbox_and_ps5_dpad_button_mappings_trigger_stall(self):
        for profile in (xbox, ps5):
            with self.subTest(profile=profile.__name__):
                down = SimpleNamespace(type=pygame.JOYBUTTONDOWN, button=12)
                up = SimpleNamespace(type=pygame.JOYBUTTONUP, button=12)
                self.assertEqual(profile.read_event(down), {'stall': True})
                self.assertEqual(profile.read_event(up), {'stall': False})

    def test_unrelated_buttons_do_not_trigger_stall(self):
        for profile in (xbox, ps5):
            with self.subTest(profile=profile.__name__):
                event = SimpleNamespace(type=pygame.JOYBUTTONDOWN, button=0)
                self.assertEqual(profile.read_event(event), {})


if __name__ == '__main__':
    unittest.main()
