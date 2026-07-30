import random
from playwright.sync_api import Page


class Humanizer:

    @staticmethod
    def random_delay(page: Page):
        page.wait_for_timeout(
            random.randint(800, 2200)
        )

    @staticmethod
    def move_mouse(page: Page):

        x = random.randint(100, 1200)
        y = random.randint(100, 700)

        page.mouse.move(
            x,
            y,
            steps=random.randint(15, 35),
        )

    @staticmethod
    def random_scroll(page: Page):

        pixels = random.randint(600, 1400)

        page.mouse.wheel(
            0,
            pixels,
        )

        page.wait_for_timeout(
            random.randint(500, 1500)
        )

    @staticmethod
    def think(page: Page):

        page.wait_for_timeout(
            random.randint(1200, 3000)
        )