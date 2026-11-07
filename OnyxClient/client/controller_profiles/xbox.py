import pygame


XBOX_DPAD_BUTTON_CONTROLS = {
    11: 'horse_dash',
    12: 'stall',
    13: 'dash_left',
    14: 'dash_right',
}


def read_event(event):
    if event.type == pygame.JOYHATMOTION:
        x, y = event.value
        return {
            'horse_dash': y == 1,
            'stall': y == -1,
            'dash_left': x == -1,
            'dash_right': x == 1,
        }

    if event.type not in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
        return {}

    control = XBOX_DPAD_BUTTON_CONTROLS.get(event.button)
    if control is None:
        return {}
    return {control: event.type == pygame.JOYBUTTONDOWN}
