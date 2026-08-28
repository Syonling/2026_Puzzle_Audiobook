"""Background scene descriptions exposed to the canvas-design LLM.

Keep this mapping in sync with background assets.  These descriptions describe
the visual content of each background; they are not user-facing translations.
"""

BACKGROUND_DESCRIPTIONS: dict[str, str] = {
    "beach_night_background": "a beach at night, with sand in the bottom-left corner, the sea on the right, and a starry sky filling more than half of the image",
    "blank_paper_background": "a completely blank background with no scenery or objects",
    "cave_entrance_background": "an exterior daytime view looking toward a cave entrance on the right that opens toward the left, with blue sky behind it",
    "cave_inside_background": "the inside of a cave, with the cave opening positioned slightly right of center",
    "closed_market_night_background": "a market at night, with closed shops on both sides, the sea straight ahead, and a night sky with the moon across the upper half",
    "dock_day_background": "a harbor in daylight, with the dock in the center and fishing nets on both sides",
    "dock_night_background": "a harbor at night, with the dock in the center and fishing nets on both sides",
    "farm_background": "a farm in daylight, with farmland filling the lower two-thirds, a fence around the one-third height, and a farmhouse slightly right of center",
    "forest_background": "a forest in daylight, with an open grassy area in the center and groups of trees on both sides",
    "grassland_background": "a grassland in daylight, with grassland below the midpoint and open sky filling more than half of the image; no mountains or buildings",
    "hillside_background": "a hillside in daylight, with a slope running from the bottom-left toward the upper-right and distant mountains and sky filling the other half",
    "lighthouse_interior_background": "a sealed circular tower interior surrounded by brick walls, with only one hanging lamp and no doors or windows",
    "mountain_background": "a mountain landscape in daylight, with grassland across the lower third and continuous mountain peaks in the background",
    "mountain_plateau_background": "a flat plain in daylight, with level open ground across the lower third and sky above; no dominant peaks or diagonal slope",
    "night_background": "a nighttime landscape of grassland and mountain peaks",
    "old_building_interior_background": "a tower interior with a spiral staircase leading upward on the left, a sunlit upper window, and an open door on the right",
    "open_sea_day_background": "the open sea in daylight, with ocean in the lower half and sky in the upper half; no man-made objects or shore",
    "open_sea_night_background": "the open sea at night, with ocean in the lower half and sky in the upper half; no man-made objects or shore",
    "orchard_background": "an orchard in daylight, with a road in the center and rows of fruit trees bearing red fruit on both sides",
    "river_background": "a river landscape in daylight, with a riverbank across the lower third, the river in the center, and sky above",
    "rocky_coast_night_background": "a coast at night, with a rocky hill on the right, the sea in the center, and the moon in the sky; no sandy beach",
    "room_background": "an interior room in daylight, with a window and low shelf on the left, a bookcase on the right, and an empty floor in the center",
    "seaside_background": "a seaside in daylight, with beach at the bottom, sea in the middle, and sky in the distance",
    "underwater_background": "an underwater scene with aquatic plants and rocks along both sides and open water in the center",
    "village_background": "a village in daylight, with rows of houses across the center",
    "village_crossroad_night_background": "a village at night, with a clearly visible crossroad in the center and small houses on both sides",
    "village_night_background": "a village at night, with an ordinary road in the center and rows of houses with glowing windows on both sides",
}
