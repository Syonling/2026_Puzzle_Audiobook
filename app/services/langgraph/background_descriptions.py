"""Background scene descriptions exposed to the canvas-design LLM.

Keep this mapping in sync with background assets.  These descriptions describe
the visual content of each background; they are not user-facing translations.
"""

BACKGROUND_DESCRIPTIONS: dict[str, str] = {
    "farm_background": "a working farmyard with a low wooden fence, a small red-roofed barn in the middle distance, a few crop rows, and an open dirt-and-grass yard in front; no mountains",
    "grassland_background": "a pure wide-open grassland with soft rolling grassy hills under a big open sky; no trees, fence, buildings, or mountains",
    "forest_background": "the inside of a forest with soft tree trunks at the sides, hazy leafy depth, a green canopy, and an open mossy clearing; almost no visible sky and no mountains",
    "river_background": "a riverside dominated by a broad calm river flowing across the scene, with an open grassy bank in the foreground",
    "mountain_background": "a mountain landscape with large layered peaks dominating the upper half and a simple open valley floor below",
    "village_background": "a small village with several visible cottages in the middle distance, a soft path between low garden hedges, and open ground in front; no mountains",
    "seaside_background": "a calm seaside with a wide open sandy beach, gentle flat sea, and soft sky; no boats",
    "room_background": "a cozy child's room with a plain warm wall, a large open wooden floor, a small daylight window, and minimal furniture at the side edges",
    "night_background": "a quiet night scene in muted blues and purples with a soft starry sky, open dark meadow, and hazy hill silhouettes; no moon",
    "blank_paper_background": "an empty warm cream watercolor-paper page with subtle grain and a soft uneven wash; no landscape, ground, sky, horizon, or objects",
    "underwater_background": "a fully submerged blue-green underwater scene with seaweed and rounded rocks at the bottom and sides, faint light rays, and open water in the middle; no fish, creatures, or bubbles",
    "cave_entrance_background": "the outside of a cave with a rocky hillside, a large dark cave mouth in the middle distance, open level ground, and daylight sky",
    "cave_inside_background": "the inside of a cave with rock walls and ceiling framing the sides, a wide open cave floor, and daylight from a small distant opening; no sky or outdoor scenery",
    "village_night_background": "a small village at night with a lane through the middle, cottages at both sides, warm light in their windows, and a night sky",
    "village_crossroad_night_background": "a village crossroad at night with two dirt paths visibly crossing in the open middle ground, a few cottages at the sides, and warm lit windows",
    "dock_night_background": "a quiet fishing dock at night with open wooden pier planks, small moored boats and nets at the side edges, calm dark sea, and night sky",
    "dock_day_background": "a quiet fishing dock in soft daylight with open wooden pier planks, small moored boats and nets at the side edges, calm sea, and daytime sky",
    "closed_market_night_background": "a closed seaside market at night with shuttered stalls at the sides, an empty central walkway, dim lanterns, and a hint of dark sea",
    "open_sea_night_background": "the open sea at night with only gentle dark waves and a calm starry sky; no birds, boats, shore, rocks, or moon",
    "open_sea_day_background": "the open sea in soft daylight with only gentle blue-green waves and calm daytime sky; no birds, boats, shore, or rocks",
    "rocky_coast_night_background": "a rocky sea coast at night with no beach or sand, a dark stone shoreline, calm water, and a simple open bottom-left corner for a breakwater sticker",
    "beach_night_background": "a sandy beach at night with wide open pale sand, calm dark sea, and a starry night-blue sky",
    "old_building_interior_background": "the inside of an old building with a wooden spiral staircase at one side, a bright upper window, aged plaster walls, and a wide open wooden floor",
    "hillside_background": "partway up a grassy hillside with one broad gentle diagonal slope, a hinted valley below, and open usable grass on the slope",
    "orchard_background": "an orchard with rows of small round fruit trees receding into the distance and wide open grassy ground between them; no buildings",
    "lighthouse_interior_background": "a lighthouse on a rocky coast with a tall white tower, a small attached building, a few rocks and low shrubs, and open sea in the distance",
}
