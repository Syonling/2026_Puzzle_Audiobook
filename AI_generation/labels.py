"""拼贴画素材标签表 —— 独立维护,image_generation.py 从这里导入。

规则:
- 每个标签必须是「能独立画出来的具体主体」。声音是主体的属性,不能反过来
  把声音当标签(反例: footsteps 脚步——应该画人物,脚步声由 app 按人物配)。
  天气类允许用绘本通用图标形式(雨 = 云朵加雨滴),prompt 模板里有对应规则。
- 标签之间不能太相似,除非形象差异明显:
  允许: bull/cow(公牛/奶牛)、rooster/hen/chick、ship/sailboat
  排除: grasshopper(似 cricket)、pigeon(似 sparrow)、pine_tree(似 tree)
- category 键用英文小写(作为 images/ 下的子文件夹名,避免路径含中文);
  给用户看的中文名放在 CATEGORY_NAMES 里。
- 标签名全局不可重复(跨 category 也不行),用英文小写 + 下划线,
  同时用作图片文件名: images/<category>/<label>.png

当前共 126 组(第三批: 61 组基础上扩充,新增 buildings 分类)。
"""

# category 英文键 -> 中文显示名
CATEGORY_NAMES: dict[str, str] = {
    "animals": "动物",
    "birds": "鸟类",
    "insects": "昆虫",
    "aquatic": "水生动物",
    "characters": "人物",
    "weather": "天气",
    "scenery": "风景",
    "buildings": "建筑",
    "plants": "植物",
    "vehicles": "交通工具",
    "instruments": "乐器",
    "daily_life": "生活",
    "effects": "特效",
    "background": "背景",
}

# 按标签覆盖 prompt 里的主体描述(默认是标签名本身,下划线转空格)。
# 用途: 某个标签出图有系统性问题时,在这里写更精确的英文描述来纠正,
# 不影响其他标签。key 必须是 LABELS 里存在的标签名。
SUBJECT_OVERRIDES: dict[str, str] = {
    # "cow" 会触发模型画乳房且经常错位;绘本画法是圆润身体+黑白斑,不画乳房
    "cow": (
        "a gentle dairy cow with a simple rounded body, "
        "black-and-white patches, four legs, and no udder"
    ),
    # 与 ocean_wave(单个浪头)区分: 开阔海面,天然横长构图
    "ocean": (
        "a wide horizontal stretch of calm ocean water surface "
        "with gentle rolling waves, seen from the side, no sky, no shore"
    ),
    # "grassland" 容易被画成带地平线的风景; 约束为一块独立的草甸剪贴块面
    "grassland": (
        "a single wide rounded patch of soft grassy meadow with a few tiny "
        "wildflowers, as one isolated cutout piece, no horizon, no sky"
    ),
    # 与 weather 的 rain(云朵+雨滴)区分: 只有连绵落下的雨滴,不带云
    # "raindrops": (
    #     "a continuous curtain of many falling watercolor raindrops, "
    #     "without any cloud, evenly spread as one cohesive cutout group"
    # ),
    # --- effects 特效: 全部需要特制描述 ---------------------------------
    # 它们是"漫画情绪符号图形"而非具体物体,统一用 "comic-style emotive
    # symbol drawn as a graphic shape (the symbol IS the subject)" 句式,
    # 配合模板里"主体本身是符号时不算违禁文字"的例外条款。
    "sweat_drop": (
        "a single large comic-style sweat drop symbol, a plump teardrop "
        "shape tilted slightly, drawn as a graphic emotive shape "
        "(the symbol is the subject itself)"
    ),
    "exclamation_mark": (
        "a single large playful exclamation mark drawn as a comic-style "
        "graphic symbol shape with a rounded dot "
        "(this one punctuation glyph is the subject itself, not forbidden text)"
    ),
    "question_mark": (
        "a single large playful question mark drawn as a comic-style "
        "graphic symbol shape with a rounded dot "
        "(this one punctuation glyph is the subject itself, not forbidden text)"
    ),
    "heart": (
        "a single plump rounded heart shape, drawn as a comic-style "
        "emotive symbol (the symbol is the subject itself)"
    ),
    "sparkles": (
        "a small tight cluster of three or four twinkling four-pointed "
        "sparkle stars, drawn as one cohesive comic-style emotive symbol "
        "group (the symbols are the subject itself)"
    ),
    "music_note": (
        "a single large eighth note drawn as a comic-style graphic music "
        "symbol shape (the symbol is the subject itself)"
    ),
    "zzz": (
        "three letter-Z shapes floating in a diagonal row from small to "
        "large, the classic comic sleep symbol, drawn as one cohesive "
        "graphic shape (these glyphs are the subject itself, not forbidden text)"
    ),
    "speech_bubble": (
        "a single empty rounded speech bubble with a small tail, drawn as "
        "a comic-style graphic shape, completely blank inside with no text "
        "(the empty bubble is the subject itself)"
    ),
    "bubbles": (
        "a loose rising column of five or six round transparent water "
        "bubbles of varying sizes, drawn as one cohesive comic-style group "
        "(the bubbles are the subject; this is NOT a speech bubble)"
    ),
    # --- 群组图标: 整群作为一个剪贴块,共用一圈白边 -----------------------
    "horses_running": (
        "a small herd of three galloping horses running together in the "
        "same direction, side by side and slightly overlapping, composed "
        "as ONE cohesive group inside a single shared cutout outline"
    ),
    "chicken_flock": (
        "a small group of two hens and three chicks gathered on the ground "
        "in front of a small wooden chicken coop, composed as ONE cohesive "
        "group inside a single shared cutout outline"
    ),
    "sparrow_flock": (
        "a small group of five sparrows perched close together on the "
        "ground, all standing (none flying), composed as ONE cohesive "
        "group inside a single shared cutout outline"
    ),
    "sparrow_flock_flying": (
        "a small flock of five sparrows flying together in a loose "
        "formation with wings spread (all airborne, none perched), "
        "composed as ONE cohesive group inside a single shared cutout outline"
    ),
    # 多肢体高危主体: 明确肢体数量和连接方式
    "octopus": (
        "a friendly round-headed octopus with exactly eight simple curling "
        "arms all clearly attached to its body"
    ),
    # 两只海鸥: 群组但要求拉开间距(与其他群组的"紧凑"要求相反)
    "seagulls_flying": (
        "exactly two seagulls gliding in the air in the same direction, "
        "with comfortable open space between them — do NOT squeeze them "
        "together; they are still one cutout group sharing one outline "
        "that follows both birds"
    ),
    # 慌乱人群: 群组,按躲雨方向描述,保持儿童友好
    "fleeing_crowd": (
        "a small group of four people hurrying together in the same "
        "direction to find shelter from sudden rain, holding bags or "
        "newspapers over their heads, mildly flustered but not scary, "
        "composed as ONE cohesive group inside a single shared cutout outline"
    ),
    # 无表情人影: 与"生物要有温和表情"规则相反,明确无面部
    "dark_silhouette": (
        "a single completely dark, softly blurred human silhouette standing "
        "still, painted as one flat dark watercolor shape with NO facial "
        "features, no eyes, and no expression at all — a mysterious but "
        "not frightening storybook shadow figure"
    ),
    # 防波堤: 左下角为直角,便于卡进画面左下角
    "breakwater": (
        "a stone breakwater pier: its left edge is perfectly vertical and "
        "its bottom edge perfectly horizontal, meeting in a clean right "
        "angle at the bottom-left corner of the shape so it can dock into "
        "the bottom-left corner of a scene; the top and right sides have a "
        "natural stacked-stone profile"
    ),
    # 木门一对: 用开合状态硬性区分
    "closed_wooden_door": (
        "a single old wooden door in its frame, completely CLOSED shut, "
        "seen straight on"
    ),
    "half_open_wooden_door": (
        "a single old wooden door in its frame, clearly HALF-OPEN at an "
        "angle, with a dark gap visible in the doorway"
    ),
    # 散落系列: 松散铺开但整体仍是一个剪贴块
    "scattered_letters": (
        "five or six paper envelopes loosely scattered and partly "
        "overlapping on the ground, as if dropped, still composed as ONE "
        "cohesive cutout group with one shared outline"
    ),
    "scattered_parcels": (
        "four or five small brown paper parcels tied with string, loosely "
        "scattered and partly overlapping, as if dropped, still composed "
        "as ONE cohesive cutout group with one shared outline"
    ),
    "scattered_farm_tools": (
        "a few simple farm tools (a rake, a shovel, a watering can) lying "
        "loosely crossed on the ground, still composed as ONE cohesive "
        "cutout group with one shared outline"
    ),
    # 种子三阶段: 三张图必须能一眼区分
    "seed": (
        "a single plump intact seed with a smooth unbroken shell, "
        "no crack and no sprout"
    ),
    "seed_cracked": (
        "a single seed with its shell clearly split half-open by a large "
        "crack, but with NO sprout emerging yet"
    ),
    "seed_sprouting": (
        "a single half-cracked seed with a small bright-green sprout with "
        "two tiny leaves clearly emerging from the crack"
    ),
    # 铃铛: 与教堂钟(大吊钟)区分
    "bell": (
        "a single small golden jingle bell with a round body, a slit, and "
        "a little loop on top, hand-held size — not a large church bell"
    ),
    "tangled_vines": (
        "a loose pile of green vines curling and intertwining with each "
        "other with a few small leaves, composed as ONE cohesive cutout piece"
    ),
    # 思考气泡: 与对话气泡区分(云朵形+圆点尾迹)
    "thought_bubble": (
        "a single empty cloud-shaped thought bubble with a trail of two "
        "small circles at its lower corner, drawn as a comic-style graphic "
        "shape, completely blank inside with no text "
        "(the empty thought bubble is the subject itself)"
    ),
    # 足迹一对: 鞋印 vs 爪印硬性区分
    "human_footprints": (
        "a walking trail of five or six human shoe prints in alternating "
        "left-right steps, drawn as comic-style graphic marks, composed as "
        "ONE cohesive cutout group (the footprint symbols are the subject)"
    ),
    "animal_footprints": (
        "a walking trail of five or six small animal paw prints with toe "
        "pads in alternating steps, drawn as comic-style graphic marks, "
        "composed as ONE cohesive cutout group (the paw print symbols are "
        "the subject; clearly paw pads, not human shoes)"
    ),
}

LABELS: dict[str, list[str]] = {
    "animals": [         # 动物(走兽、两栖、海洋哺乳等)
        "cow",           # 奶牛
        "bull",          # 公牛(与奶牛形象差异明显: 牛角、体格)
        "sheep",         # 绵羊
        "goat",          # 山羊
        "horse",         # 马
        "donkey",        # 驴
        "pig",           # 猪
        "dog",           # 狗
        "cat",           # 猫
        "mouse",         # 老鼠
        "rabbit",        # 兔子
        "squirrel",      # 松鼠
        "deer",          # 鹿
        "bear",          # 熊
        "wolf",          # 狼
        "fox",           # 狐狸
        "elephant",      # 大象
        "lion",          # 狮子
        "tiger",         # 老虎
        "monkey",        # 猴子
        "snake",         # 蛇
        "frog",          # 青蛙
        "whale",         # 鲸鱼(历史原因留在 animals,勿挪到 aquatic——挪分类会被误判为未生成)
        "dolphin",       # 海豚(同上)
        "horses_running", # 奔跑的马群(群组图标,SUBJECT_OVERRIDES 有特制描述)
    ],
    "birds": [           # 鸟类
        "crow",          # 乌鸦
        "sparrow",       # 麻雀
        "swallow",       # 燕子(剪刀尾,与麻雀形象区分明显)
        "magpie",        # 喜鹊
        "owl",           # 猫头鹰
        "eagle",         # 老鹰
        "rooster",       # 公鸡
        "hen",           # 母鸡(与公鸡形象差异明显: 鸡冠、尾羽)
        "chick",         # 小鸡(黄色绒毛)
        "duck",          # 鸭子
        "goose",         # 鹅
        "swan",          # 天鹅(曲颈浮水,与鹅的直立形象区分)
        "seagull",       # 海鸥
        "woodpecker",    # 啄木鸟
        "parrot",        # 鹦鹉
        "peacock",       # 孔雀
        "penguin",       # 企鹅
        # 群组图标(均有 SUBJECT_OVERRIDES 特制描述,整群共用一圈白边)
        "chicken_flock",        # 鸡群与鸡舍(母鸡小鸡聚在鸡舍前)
        "sparrow_flock",        # 麻雀群(停落地面,与飞翔版区分)
        "sparrow_flock_flying", # 飞翔的麻雀群(展翅飞行,与停落版区分)
        "seagulls_flying",      # 飞翔的两只海鸥(拉开间距,不挤在一起)
    ],
    "insects": [         # 昆虫与小虫(含无声但拼贴常用的)
        "cricket",       # 蟋蟀(=蛐蛐)
        "bee",           # 蜜蜂
        "cicada",        # 蝉
        "butterfly",     # 蝴蝶
        "ladybug",       # 瓢虫
        "dragonfly",     # 蜻蜓
        "firefly",       # 萤火虫(发光尾部)
        "ant",           # 蚂蚁
        "snail",         # 蜗牛
        "caterpillar",   # 毛毛虫(与蝴蝶形象完全不同)
    ],
    "aquatic": [         # 水生动物(鱼类及伙伴;whale/dolphin 因历史原因在 animals)
        "goldfish",      # 金鱼(橙红飘尾)
        "clownfish",     # 小丑鱼(橙白条纹,与金鱼区分明显)
        "pufferfish",    # 河豚(圆滚带刺,形象独特)
        "shark",         # 鲨鱼
        "seahorse",      # 海马
        "octopus",       # 章鱼(SUBJECT_OVERRIDES 有防多肢画错的特制描述)
        "crab",          # 螃蟹
        "sea_turtle",    # 海龟
    ],
    "characters": [      # 人物(脚步声、说笑声、劳作声等由 app 按人物配)
        "man",                  # 男人
        "woman",                # 女人
        "boy",                  # 男孩
        "girl",                 # 女孩
        "baby",                 # 婴儿
        "grandpa",              # 爷爷
        "grandma",              # 奶奶
        "farmer",               # 农民
        "construction_worker",  # 工人(建筑工人形象,比笼统的 worker 好出图)
        "teacher",              # 老师
        "doctor",               # 医生
        "police_officer",       # 警察
        "firefighter",          # 消防员
        "chef",                 # 厨师
        "fisherman",            # 渔夫
        "postman",              # 邮递员
        "astronaut",            # 宇航员
        "sailor",               # 水手(条纹衫,与渔夫的雨帽渔具形象区分)
        "clown",                # 小丑
        "fleeing_crowd",        # 慌乱的人群(躲雨奔跑,群组图标)
        "dark_silhouette",      # 漆黑模糊的人影(无表情无面部)
    ],
    "weather": [         # 天气与天空(绘本图标形式: 雨=云+雨滴, 雷=云+闪电)
        "rain",          # 雨
        "thunder",       # 雷
        "wind",          # 风(卷起落叶的风旋)
        "snow",          # 雪
        "cloud",         # 云(单朵白云,与"雨"的雨滴云区分)
        "sun",           # 太阳
        "moon",          # 月亮
        "rainbow",       # 彩虹
    ],
    "scenery": [         # 风景
        "stream",        # 溪流
        "ocean_wave",    # 海浪(单个浪头,与 ocean 的开阔海面区分)
        "ocean",         # 海洋(开阔海面,横长构图)
        "waterfall",     # 瀑布
        "campfire",      # 篝火
        "mountain",      # 山
        "volcano",       # 火山(喷发冒烟,与普通山区分)
        "grassland",     # 草地(横长的草甸块面)
        # "raindrops",     # 连绵的雨滴(不带云朵,与 weather 的 rain 云朵雨滴区分)
    ],
    "buildings": [       # 建筑
        "house",         # 房子
        "church",        # 教堂(建筑整体,与生活类的 church_bell 吊钟区分)
        "lighthouse",    # 灯塔
        "windmill",      # 风车磨坊
        "castle",        # 城堡
        "tent",          # 帐篷
        "barn",          # 谷仓
        "bridge",        # 桥
        "breakwater",    # 防波堤(左下为直角,卡画面左下角用)
        "closed_wooden_door",    # 关闭的木门(与半开版区分)
        "half_open_wooden_door", # 半开的木门(与关闭版区分)
    ],
    "plants": [          # 植物
        "tree",          # 大树
        "bamboo",        # 竹子
        "fallen_leaves", # 落叶
        "sunflower",     # 向日葵
        "mushroom",      # 蘑菇
        "cactus",        # 仙人掌
        "palm_tree",     # 棕榈树(轮廓与大树差异明显)
        "pumpkin",       # 南瓜
        "rose",          # 玫瑰(红色单支,与向日葵区分明显)
        # 种子三阶段(生长故事线,三张必须能明确区分)
        "seed",          # 完整的种子
        "seed_cracked",  # 半裂开的种子(未发芽)
        "seed_sprouting",# 半裂开且发芽的种子(带绿芽)
        "tangled_vines", # 一堆交错的藤蔓
    ],
    "vehicles": [        # 交通工具
        "train",            # 火车
        "car",              # 汽车
        "bus",              # 公交车
        "bicycle",          # 自行车
        "motorcycle",       # 摩托车
        "tractor",          # 拖拉机
        "excavator",        # 挖掘机
        "fire_truck",       # 消防车
        "ambulance",        # 救护车(白色厢式车,与红色消防车区分)
        "airplane",         # 飞机
        "helicopter",       # 直升机
        "hot_air_balloon",  # 热气球
        "ship",             # 轮船
        "sailboat",         # 帆船(与轮船形象差异明显: 风帆)
        "mail_truck",       # 邮差车(邮政涂装小货车)
        "old_fishing_boat", # 破旧的渔船(木质旧渔船,与轮船/帆船区分)
    ],
    "instruments": [     # 乐器
        "drum",          # 鼓
        "guitar",        # 吉他
        "violin",        # 小提琴(琴弓,与吉他区分)
        "piano",         # 钢琴
        "flute",         # 长笛
        "trumpet",       # 小号
        "xylophone",     # 木琴
        "accordion",     # 手风琴
    ],
    "daily_life": [      # 生活物品
        "church_bell",   # 教堂钟(吊钟本体)
        "wind_chime",    # 风铃
        "clock",         # 时钟(滴答声)
        "telephone",     # 电话(复古造型)
        "radio",         # 收音机(复古造型)
        "kettle",        # 水壶(鸣笛声)
        "music_box",     # 八音盒
        "umbrella",      # 雨伞(雨打伞面声,与天气类的雨搭配)
        "mailbag",       # 邮包(邮差的邮袋)
        "bell",          # 铃铛(手持小铃,与教堂钟区分)
        # 散落系列(松散铺开但仍是一个剪贴块,有特制描述)
        "scattered_letters",    # 散落的信件
        "scattered_parcels",    # 散落的包裹
        "scattered_farm_tools", # 散落的农具
    ],
    # 特效: 漫画式情绪/氛围符号,贴在其他素材旁用。走图标管线(透明底+白边),
    # 但每个标签都必须在 SUBJECT_OVERRIDES 里写特制描述——它们是"符号图形"
    # 而非具体物体,且感叹号/问号/Zzz 会触碰模板的"禁止文字"条款(模板已加例外)。
    "effects": [
        "sweat_drop",          # 汗滴(漫画式紧张/费力符号)
        "exclamation_mark",    # 感叹号
        "question_mark",       # 问号
        "heart",               # 爱心
        "sparkles",            # 闪光(星星亮晶晶)
        "music_note",          # 音符
        "zzz",                 # 瞌睡符号(三个 Z)
        "speech_bubble",       # 对话气泡(空白的,用户自由使用)
        "bubbles",             # 气泡(上升的水泡群,与对话气泡完全不同)
        "thought_bubble",      # 思考气泡(云朵形+小圆点尾迹,与对话气泡区分)
        "human_footprints",    # 一串人类足迹(鞋印)
        "animal_footprints",   # 一串动物足迹(爪印,与鞋印区分)
    ],
    # 背景是特殊分类: 8:5 横幅、不透明、走独立的 prompt 模板和模型
    # (见 image_generation.py 的 BACKGROUND_* 配置和下面的 BACKGROUND_SCENES)。
    # 系统按「分类是否为 background」区分背景和图标,assets 数据格式完全一致。
    "background": [
        "farm_background",         # 农场背景
        "grassland_background",    # 草原背景
        "forest_background",       # 森林背景
        "river_background",        # 河流背景
        "mountain_background",     # 山景背景
        "village_background",      # 村庄背景
        "seaside_background",      # 海边背景
        "room_background",         # 房间背景
        "night_background",        # 夜晚背景
        "blank_paper_background",  # 空白纸张背景
        "underwater_background",   # 水下背景(水草岩石,无鱼)
        "cave_entrance_background", # 山洞口背景(从外看洞口,与洞内区分)
        "cave_inside_background",  # 山洞内背景(洞穴内部视角,与洞口区分)
        "village_night_background",       # 夜晚的村庄内(村中小巷,窗内暖光)
        "village_crossroad_night_background", # 夜晚村庄的路口(小路交叉口)
        "dock_night_background",          # 夜晚码头(渔船渔网,夜色)
        "dock_day_background",            # 白天码头(渔船渔网,白昼)
        "closed_market_night_background", # 夜晚打烊的海边集市
        "open_sea_night_background",      # 夜晚海面(只有海面,无鸟无船)
        "open_sea_day_background",        # 白天海面(只有海面)
        "rocky_coast_night_background",   # 夜晚海边·无沙滩(岩岸,左下留位卡防波堤)
        "beach_night_background",         # 夜晚海边·带沙滩
        "old_building_interior_background", # 古旧楼内部(旋转楼梯+二楼窗)
        "hillside_background",            # 半山坡
        "orchard_background",             # 果园(无房屋)
    ],
}

# ---------------------------------------------------------------------------
# 背景场景描述({scene} 填入背景 prompt 模板)。
# 只描述环境要素——地面/天空/远景/两侧收边;绝不出现可拖拽主体
# (动物、人物、车辆、显眼道具),那些留给用户从图标里拖。
# key 必须与 LABELS["background"] 一一对应,_validate 会检查。
# ---------------------------------------------------------------------------
# 每条场景描述必须: ① 点名标志性元素(必须显眼) ② 明确排除容易混淆的默认构图。
# 教训: 描述太笼统时,所有户外背景都会被模板收敛成"草地+两侧树+远山"一个样。
BACKGROUND_SCENES: dict[str, str] = {
    "farm_background": (
        "a working farmyard that must clearly read as a FARM, not a plain "
        "meadow: a low wooden fence running across the scene, a small "
        "red-roofed barn clearly visible in the middle distance, a few strips "
        "of plowed field or crop rows, and an open dirt-and-grass yard in "
        "front; no mountains"
    ),
    "grassland_background": (
        "a pure wide-open GRASSLAND: nothing but soft rolling grassy hills "
        "fading into the distance under a big open sky; strictly no trees, "
        "no fence, no buildings, and no mountains — openness itself is the "
        "defining feature"
    ),
    "forest_background": (
        "the INSIDE of a forest: tall soft tree trunks on both sides and "
        "continuing into a hazy leafy depth, a green canopy closing off most "
        "of the top, dappled light falling on an open mossy clearing floor; "
        "almost no visible sky, no horizon line, and no mountains"
    ),
    "river_background": (
        "a riverside where a broad calm RIVER is the dominant feature, its "
        "wide water surface flowing across the whole scene from one side to "
        "the other, with an open grassy bank in the foreground; the water "
        "must be unmistakably the main element, not a thin distant stripe"
    ),
    "mountain_background": (
        "a MOUNTAIN landscape where large layered peaks dominate the upper "
        "half of the picture, close and grand rather than tiny distant "
        "bumps, with a simple open valley floor below; the mountains are "
        "the defining feature"
    ),
    "village_background": (
        "a small VILLAGE: several simple cottages with clearly visible "
        "rooftops and warm walls in the middle distance, a soft path "
        "leading toward them between low garden hedges, open ground in "
        "front; the cottages must be prominent, not tiny dots; no mountains"
    ),
    "seaside_background": (
        "a calm seaside: wide open sandy beach in the foreground, gentle flat "
        "sea in the middle distance, soft sky, no boats"
    ),
    "room_background": (
        "a cozy child's room interior: one plain warm wall, a large open "
        "wooden floor area, a small window with soft daylight, and only "
        "minimal simple furniture pushed to the side edges"
    ),
    "night_background": (
        "a quiet NIGHT scene where the entire palette is dark muted night "
        "blues and purples: a soft starry sky covering most of the picture, "
        "an open dark meadow below, hazy hill silhouettes; it must "
        "unmistakably look like nighttime, never daylight; no moon (users "
        "may add their own moon sticker)"
    ),
    "blank_paper_background": (
        "an EMPTY page: nothing but warm cream watercolor paper with a "
        "subtle grain texture and a soft uneven wash; absolutely no "
        "landscape, no ground, no sky, no horizon, no trees, no mountains, "
        "and no objects of any kind — just blank paper for free play"
    ),
    "underwater_background": (
        "an UNDERWATER scene, fully submerged with no water surface and "
        "no sky: soft blue-green water filling the whole picture, gentle "
        "swaying seaweed and smooth rounded rocks along the bottom and "
        "side edges, faint light rays from above, a wide open water area "
        "in the middle; strictly no fish, no sea creatures, and no bubbles "
        "(users will add their own sea-life stickers)"
    ),
    "cave_entrance_background": (
        "the OUTSIDE of a cave, clearly viewed from outdoors: a soft rocky "
        "hillside with a large dark cave mouth in the middle distance, "
        "open level ground in front of the entrance, daylight sky above; "
        "this must be an exterior view, never the cave interior"
    ),
    "cave_inside_background": (
        "the INSIDE of a cave, clearly an interior view: soft rock walls "
        "and a rocky ceiling framing the top and sides, a wide open level "
        "cave floor, a gentle glow of daylight coming from a small opening "
        "in the distance; no outdoor scenery, no sky, no horizon"
    ),
    "village_night_background": (
        "the INSIDE of a small village at NIGHT, palette of dark muted "
        "night blues: a soft village lane running through the middle with "
        "a few cottages along both sides, warm yellow light glowing from "
        "their windows, night sky above the rooftops; unmistakably "
        "nighttime, never daylight"
    ),
    "village_crossroad_night_background": (
        "a village CROSSROAD at NIGHT, palette of dark muted night blues: "
        "two soft dirt paths clearly CROSSING in the open middle ground, "
        "one or two cottages with warm lit windows set back at the sides, "
        "night sky above; the path crossing itself is the defining "
        "feature, distinct from a plain village lane"
    ),
    "dock_night_background": (
        "a quiet fishing DOCK at NIGHT, palette of dark muted night "
        "blues: wooden pier planks as the open foreground, a couple of "
        "small moored fishing boats and hanging fishing nets at the side "
        "edges as quiet background scenery, calm dark sea beyond, night "
        "sky; unmistakably nighttime"
    ),
    "dock_day_background": (
        "a quiet fishing DOCK in soft DAYLIGHT: wooden pier planks as the "
        "open foreground, a couple of small moored fishing boats and "
        "hanging fishing nets at the side edges as quiet background "
        "scenery, calm sea beyond, gentle daytime sky; clearly daytime, "
        "the daytime twin of the night dock"
    ),
    "closed_market_night_background": (
        "a small seaside market street at NIGHT with every stall CLOSED: "
        "shuttered wooden stalls with folded awnings lining the sides, an "
        "empty open walkway through the middle, one or two dim lanterns, "
        "a hint of dark sea in the distance, night-blue palette; clearly "
        "closed and deserted, calm rather than spooky"
    ),
    "open_sea_night_background": (
        "the open SEA at NIGHT, water and sky only: gentle dark waves "
        "filling the lower part of the picture, calm starry night sky "
        "above, night-blue palette; strictly nothing else — no birds, no "
        "boats, no shore, no rocks, no moon"
    ),
    "open_sea_day_background": (
        "the open SEA in soft DAYLIGHT, water and sky only: gentle "
        "blue-green waves filling the lower part of the picture, calm "
        "daytime sky above; strictly nothing else — no birds, no boats, "
        "no shore, no rocks"
    ),
    "rocky_coast_night_background": (
        "a rocky SEA COAST at NIGHT with strictly NO beach and NO sand: "
        "a dark stone shoreline meeting calm night water, night-blue "
        "palette; keep the BOTTOM-LEFT corner of the picture simple, "
        "level and open, so a separate breakwater sticker can later be "
        "docked into that corner"
    ),
    "beach_night_background": (
        "a sandy BEACH at NIGHT: wide open pale sand in the foreground, "
        "calm dark sea in the middle distance, starry night-blue sky; "
        "the nighttime twin of a calm seaside — unmistakably dark, "
        "with sand clearly visible"
    ),
    "old_building_interior_background": (
        "the INSIDE of an old vintage building: a wooden SPIRAL STAIRCASE "
        "winding up along one side, a small bright second-floor window "
        "above letting in soft light, aged warm plaster walls, and a wide "
        "open wooden floor as the foreground; an interior view with no "
        "sky and no outdoor scenery"
    ),
    "hillside_background": (
        "partway up a grassy HILLSIDE: one broad gentle slope crossing "
        "the picture diagonally, the crest continuing past the upper "
        "corner and a soft valley hinted below, open usable grass on the "
        "slope itself; the slope must stay gentle so stickers placed on "
        "it still look naturally seated, and it must clearly read as a "
        "hillside rather than flat ground"
    ),
    "orchard_background": (
        "an ORCHARD: neat rows of small round fruit trees with a few red "
        "fruits receding into the distance, wide open grassy ground "
        "between the rows as the foreground; strictly no house, no barn, "
        "and no buildings of any kind"
    ),
}


# ---------------------------------------------------------------------------
# 多语言翻译表(copy.py 生成 assets 数据时使用)
# en 名不需要维护: 由标签名自动生成(下划线转空格 + 首字母大写)
# ---------------------------------------------------------------------------

# category 英文键 -> 日文显示名(中文在上面的 CATEGORY_NAMES)
CATEGORY_NAMES_JA: dict[str, str] = {
    "animals": "動物",
    "birds": "鳥",
    "insects": "昆虫",
    "aquatic": "水の生き物",
    "characters": "人物",
    "weather": "天気",
    "scenery": "風景",
    "buildings": "建物",
    "plants": "植物",
    "vehicles": "乗り物",
    "instruments": "楽器",
    "daily_life": "生活",
    "effects": "エフェクト",
    "background": "背景",
}

# 标签 -> {"zh": 中文名, "ja": 日文名}
LABEL_TRANSLATIONS: dict[str, dict[str, str]] = {
    # animals
    "cow": {"zh": "奶牛", "ja": "乳牛"},
    "bull": {"zh": "公牛", "ja": "雄牛"},
    "sheep": {"zh": "绵羊", "ja": "羊"},
    "goat": {"zh": "山羊", "ja": "ヤギ"},
    "horse": {"zh": "马", "ja": "馬"},
    "donkey": {"zh": "驴", "ja": "ロバ"},
    "pig": {"zh": "猪", "ja": "豚"},
    "dog": {"zh": "狗", "ja": "犬"},
    "cat": {"zh": "猫", "ja": "猫"},
    "mouse": {"zh": "老鼠", "ja": "ネズミ"},
    "rabbit": {"zh": "兔子", "ja": "ウサギ"},
    "squirrel": {"zh": "松鼠", "ja": "リス"},
    "deer": {"zh": "鹿", "ja": "鹿"},
    "bear": {"zh": "熊", "ja": "クマ"},
    "wolf": {"zh": "狼", "ja": "オオカミ"},
    "fox": {"zh": "狐狸", "ja": "キツネ"},
    "elephant": {"zh": "大象", "ja": "ゾウ"},
    "lion": {"zh": "狮子", "ja": "ライオン"},
    "tiger": {"zh": "老虎", "ja": "トラ"},
    "monkey": {"zh": "猴子", "ja": "サル"},
    "snake": {"zh": "蛇", "ja": "ヘビ"},
    "frog": {"zh": "青蛙", "ja": "カエル"},
    "whale": {"zh": "鲸鱼", "ja": "クジラ"},
    "dolphin": {"zh": "海豚", "ja": "イルカ"},
    "horses_running": {"zh": "奔跑的马群", "ja": "走る馬の群れ"},
    # birds
    "crow": {"zh": "乌鸦", "ja": "カラス"},
    "sparrow": {"zh": "麻雀", "ja": "スズメ"},
    "swallow": {"zh": "燕子", "ja": "ツバメ"},
    "magpie": {"zh": "喜鹊", "ja": "カササギ"},
    "owl": {"zh": "猫头鹰", "ja": "フクロウ"},
    "eagle": {"zh": "老鹰", "ja": "ワシ"},
    "rooster": {"zh": "公鸡", "ja": "オンドリ"},
    "hen": {"zh": "母鸡", "ja": "メンドリ"},
    "chick": {"zh": "小鸡", "ja": "ヒヨコ"},
    "duck": {"zh": "鸭子", "ja": "アヒル"},
    "goose": {"zh": "鹅", "ja": "ガチョウ"},
    "swan": {"zh": "天鹅", "ja": "白鳥"},
    "seagull": {"zh": "海鸥", "ja": "カモメ"},
    "woodpecker": {"zh": "啄木鸟", "ja": "キツツキ"},
    "parrot": {"zh": "鹦鹉", "ja": "オウム"},
    "peacock": {"zh": "孔雀", "ja": "クジャク"},
    "penguin": {"zh": "企鹅", "ja": "ペンギン"},
    "chicken_flock": {"zh": "鸡群与鸡舍", "ja": "ニワトリの群れ"},
    "sparrow_flock": {"zh": "麻雀群", "ja": "スズメの群れ"},
    "sparrow_flock_flying": {"zh": "飞翔的麻雀群", "ja": "飛んでいるスズメの群れ"},
    "seagulls_flying": {"zh": "飞翔的两只海鸥", "ja": "飛んでいる2羽のカモメ"},
    # insects
    "cricket": {"zh": "蟋蟀", "ja": "コオロギ"},
    "bee": {"zh": "蜜蜂", "ja": "ミツバチ"},
    "cicada": {"zh": "蝉", "ja": "セミ"},
    "butterfly": {"zh": "蝴蝶", "ja": "チョウ"},
    "ladybug": {"zh": "瓢虫", "ja": "テントウムシ"},
    "dragonfly": {"zh": "蜻蜓", "ja": "トンボ"},
    "firefly": {"zh": "萤火虫", "ja": "ホタル"},
    "ant": {"zh": "蚂蚁", "ja": "アリ"},
    "snail": {"zh": "蜗牛", "ja": "カタツムリ"},
    "caterpillar": {"zh": "毛毛虫", "ja": "イモムシ"},
    # aquatic
    "goldfish": {"zh": "金鱼", "ja": "金魚"},
    "clownfish": {"zh": "小丑鱼", "ja": "クマノミ"},
    "pufferfish": {"zh": "河豚", "ja": "フグ"},
    "shark": {"zh": "鲨鱼", "ja": "サメ"},
    "seahorse": {"zh": "海马", "ja": "タツノオトシゴ"},
    "octopus": {"zh": "章鱼", "ja": "タコ"},
    "crab": {"zh": "螃蟹", "ja": "カニ"},
    "sea_turtle": {"zh": "海龟", "ja": "ウミガメ"},
    # characters
    "man": {"zh": "男人", "ja": "男の人"},
    "woman": {"zh": "女人", "ja": "女の人"},
    "boy": {"zh": "男孩", "ja": "男の子"},
    "girl": {"zh": "女孩", "ja": "女の子"},
    "baby": {"zh": "婴儿", "ja": "赤ちゃん"},
    "grandpa": {"zh": "爷爷", "ja": "おじいさん"},
    "grandma": {"zh": "奶奶", "ja": "おばあさん"},
    "farmer": {"zh": "农民", "ja": "農家の人"},
    "construction_worker": {"zh": "工人", "ja": "建設作業員"},
    "teacher": {"zh": "老师", "ja": "先生"},
    "doctor": {"zh": "医生", "ja": "お医者さん"},
    "police_officer": {"zh": "警察", "ja": "警察官"},
    "firefighter": {"zh": "消防员", "ja": "消防士"},
    "chef": {"zh": "厨师", "ja": "シェフ"},
    "fisherman": {"zh": "渔夫", "ja": "漁師"},
    "postman": {"zh": "邮递员", "ja": "郵便屋さん"},
    "astronaut": {"zh": "宇航员", "ja": "宇宙飛行士"},
    "sailor": {"zh": "水手", "ja": "船乗り"},
    "clown": {"zh": "小丑", "ja": "ピエロ"},
    "fleeing_crowd": {"zh": "慌乱的人群", "ja": "あわてる人々"},
    "dark_silhouette": {"zh": "漆黑的人影", "ja": "黒い人影"},
    # weather
    "rain": {"zh": "雨", "ja": "雨"},
    "thunder": {"zh": "雷", "ja": "雷"},
    "wind": {"zh": "风", "ja": "風"},
    "snow": {"zh": "雪", "ja": "雪"},
    "cloud": {"zh": "云", "ja": "雲"},
    "sun": {"zh": "太阳", "ja": "太陽"},
    "moon": {"zh": "月亮", "ja": "月"},
    "rainbow": {"zh": "彩虹", "ja": "虹"},
    # scenery
    "stream": {"zh": "溪流", "ja": "小川"},
    "ocean_wave": {"zh": "海浪", "ja": "波"},
    "ocean": {"zh": "海洋", "ja": "海"},
    "grassland": {"zh": "草地", "ja": "草原"},
    # "raindrops": {"zh": "雨滴", "ja": "雨粒"},
    "waterfall": {"zh": "瀑布", "ja": "滝"},
    "campfire": {"zh": "篝火", "ja": "たき火"},
    "mountain": {"zh": "山", "ja": "山"},
    "volcano": {"zh": "火山", "ja": "火山"},
    # buildings
    "house": {"zh": "房子", "ja": "家"},
    "church": {"zh": "教堂", "ja": "教会"},
    "lighthouse": {"zh": "灯塔", "ja": "灯台"},
    "windmill": {"zh": "风车磨坊", "ja": "風車"},
    "castle": {"zh": "城堡", "ja": "お城"},
    "tent": {"zh": "帐篷", "ja": "テント"},
    "barn": {"zh": "谷仓", "ja": "納屋"},
    "bridge": {"zh": "桥", "ja": "橋"},
    "breakwater": {"zh": "防波堤", "ja": "防波堤"},
    "closed_wooden_door": {"zh": "关闭的木门", "ja": "閉じた木のドア"},
    "half_open_wooden_door": {"zh": "半开的木门", "ja": "半開きの木のドア"},
    # plants
    "tree": {"zh": "大树", "ja": "木"},
    "bamboo": {"zh": "竹子", "ja": "竹"},
    "fallen_leaves": {"zh": "落叶", "ja": "落ち葉"},
    "sunflower": {"zh": "向日葵", "ja": "ひまわり"},
    "mushroom": {"zh": "蘑菇", "ja": "キノコ"},
    "cactus": {"zh": "仙人掌", "ja": "サボテン"},
    "palm_tree": {"zh": "棕榈树", "ja": "ヤシの木"},
    "pumpkin": {"zh": "南瓜", "ja": "カボチャ"},
    "rose": {"zh": "玫瑰", "ja": "バラ"},
    "seed": {"zh": "种子", "ja": "タネ"},
    "seed_cracked": {"zh": "裂开的种子", "ja": "割れたタネ"},
    "seed_sprouting": {"zh": "发芽的种子", "ja": "芽が出たタネ"},
    "tangled_vines": {"zh": "交错的藤蔓", "ja": "絡み合ったツル"},
    # vehicles
    "train": {"zh": "火车", "ja": "電車"},
    "car": {"zh": "汽车", "ja": "車"},
    "bus": {"zh": "公交车", "ja": "バス"},
    "bicycle": {"zh": "自行车", "ja": "自転車"},
    "motorcycle": {"zh": "摩托车", "ja": "バイク"},
    "tractor": {"zh": "拖拉机", "ja": "トラクター"},
    "excavator": {"zh": "挖掘机", "ja": "ショベルカー"},
    "fire_truck": {"zh": "消防车", "ja": "消防車"},
    "ambulance": {"zh": "救护车", "ja": "救急車"},
    "airplane": {"zh": "飞机", "ja": "飛行機"},
    "helicopter": {"zh": "直升机", "ja": "ヘリコプター"},
    "hot_air_balloon": {"zh": "热气球", "ja": "気球"},
    "ship": {"zh": "轮船", "ja": "船"},
    "sailboat": {"zh": "帆船", "ja": "ヨット"},
    "mail_truck": {"zh": "邮差车", "ja": "郵便車"},
    "old_fishing_boat": {"zh": "破旧的渔船", "ja": "古い漁船"},
    # instruments
    "drum": {"zh": "鼓", "ja": "ドラム"},
    "guitar": {"zh": "吉他", "ja": "ギター"},
    "violin": {"zh": "小提琴", "ja": "バイオリン"},
    "piano": {"zh": "钢琴", "ja": "ピアノ"},
    "flute": {"zh": "长笛", "ja": "フルート"},
    "trumpet": {"zh": "小号", "ja": "トランペット"},
    "xylophone": {"zh": "木琴", "ja": "木琴"},
    "accordion": {"zh": "手风琴", "ja": "アコーディオン"},
    # daily_life
    "church_bell": {"zh": "教堂钟", "ja": "教会の鐘"},
    "wind_chime": {"zh": "风铃", "ja": "風鈴"},
    "clock": {"zh": "时钟", "ja": "時計"},
    "telephone": {"zh": "电话", "ja": "電話"},
    "radio": {"zh": "收音机", "ja": "ラジオ"},
    "kettle": {"zh": "水壶", "ja": "やかん"},
    "music_box": {"zh": "八音盒", "ja": "オルゴール"},
    "umbrella": {"zh": "雨伞", "ja": "傘"},
    "mailbag": {"zh": "邮包", "ja": "郵便カバン"},
    "bell": {"zh": "铃铛", "ja": "鈴"},
    "scattered_letters": {"zh": "散落的信件", "ja": "散らばった手紙"},
    "scattered_parcels": {"zh": "散落的包裹", "ja": "散らばった小包"},
    "scattered_farm_tools": {"zh": "散落的农具", "ja": "散らばった農具"},
    # effects
    "sweat_drop": {"zh": "汗滴", "ja": "汗マーク"},
    "exclamation_mark": {"zh": "感叹号", "ja": "びっくりマーク"},
    "question_mark": {"zh": "问号", "ja": "はてなマーク"},
    "heart": {"zh": "爱心", "ja": "ハート"},
    "sparkles": {"zh": "闪光", "ja": "キラキラ"},
    "music_note": {"zh": "音符", "ja": "音符"},
    "zzz": {"zh": "瞌睡符号", "ja": "眠りマーク"},
    "speech_bubble": {"zh": "对话气泡", "ja": "吹き出し"},
    "bubbles": {"zh": "气泡", "ja": "泡"},
    "thought_bubble": {"zh": "思考气泡", "ja": "考えの吹き出し"},
    "human_footprints": {"zh": "人类足迹", "ja": "人の足あと"},
    "animal_footprints": {"zh": "动物足迹", "ja": "動物の足あと"},
    # background
    "farm_background": {"zh": "农场背景", "ja": "農場の背景"},
    "grassland_background": {"zh": "草原背景", "ja": "草原の背景"},
    "forest_background": {"zh": "森林背景", "ja": "森の背景"},
    "river_background": {"zh": "河流背景", "ja": "川の背景"},
    "mountain_background": {"zh": "山景背景", "ja": "山の背景"},
    "village_background": {"zh": "村庄背景", "ja": "村の背景"},
    "seaside_background": {"zh": "海边背景", "ja": "海辺の背景"},
    "room_background": {"zh": "房间背景", "ja": "部屋の背景"},
    "night_background": {"zh": "夜晚背景", "ja": "夜の背景"},
    "blank_paper_background": {"zh": "空白纸张背景", "ja": "白紙の背景"},
    "underwater_background": {"zh": "水下背景", "ja": "水中の背景"},
    "cave_entrance_background": {"zh": "山洞口背景", "ja": "洞窟の入り口の背景"},
    "cave_inside_background": {"zh": "山洞内背景", "ja": "洞窟の中の背景"},
    "village_night_background": {"zh": "夜晚村庄背景", "ja": "夜の村の背景"},
    "village_crossroad_night_background": {"zh": "夜晚村庄路口背景", "ja": "夜の村の交差点の背景"},
    "dock_night_background": {"zh": "夜晚码头背景", "ja": "夜の波止場の背景"},
    "dock_day_background": {"zh": "白天码头背景", "ja": "昼の波止場の背景"},
    "closed_market_night_background": {"zh": "夜晚打烊集市背景", "ja": "夜の閉まった市場の背景"},
    "open_sea_night_background": {"zh": "夜晚海面背景", "ja": "夜の海の背景"},
    "open_sea_day_background": {"zh": "白天海面背景", "ja": "昼の海の背景"},
    "rocky_coast_night_background": {"zh": "夜晚岩岸背景", "ja": "夜の岩の海辺の背景"},
    "beach_night_background": {"zh": "夜晚沙滩背景", "ja": "夜の砂浜の背景"},
    "old_building_interior_background": {"zh": "古旧楼内部背景", "ja": "古い建物の中の背景"},
    "hillside_background": {"zh": "半山坡背景", "ja": "山の斜面の背景"},
    "orchard_background": {"zh": "果园背景", "ja": "果樹園の背景"},
}


def _validate() -> None:
    """标签不重复、category/标签的翻译齐全。导入时自动检查。"""
    seen: set[str] = set()
    for category, labels in LABELS.items():
        assert category in CATEGORY_NAMES, f"category '{category}' 缺少中文名"
        assert category in CATEGORY_NAMES_JA, f"category '{category}' 缺少日文名"
        for label in labels:
            assert label not in seen, f"标签重复: {label}"
            seen.add(label)
    for label in SUBJECT_OVERRIDES:
        assert label in seen, f"SUBJECT_OVERRIDES 中的 '{label}' 不在 LABELS 里"
    missing = seen - set(LABEL_TRANSLATIONS)
    assert not missing, f"缺少翻译的标签: {sorted(missing)}"
    extra = set(LABEL_TRANSLATIONS) - seen
    assert not extra, f"LABEL_TRANSLATIONS 中的多余标签: {sorted(extra)}"
    bg = set(LABELS.get("background", []))
    assert bg == set(BACKGROUND_SCENES), (
        f"background 标签与 BACKGROUND_SCENES 不一致: "
        f"缺 {sorted(bg - set(BACKGROUND_SCENES))}, "
        f"多 {sorted(set(BACKGROUND_SCENES) - bg)}"
    )


_validate()
