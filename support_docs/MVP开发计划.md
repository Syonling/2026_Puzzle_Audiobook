# AI 辅助空间拼贴式有声绘本系统：14 天本地实验版 MVP 开发计划

## 1. 最终目标

14 天内完成一个只在本机运行、可以保存多个本地实验账号作品的 MVP：

1. 用户注册、登录、退出。
2. 登录后进入三栏创作台。
3. 用户切换预设故事并阅读故事步骤。
4. 用户按分类查看素材，把 icon 加入画布。
5. 用户移动、缩放、删除画布对象。
6. 用户试听素材，或根据画布中 icon 的位置与大小试听当前画面。
7. 用户点击 AI 提示，获得文字建议和推荐素材。
8. 用户保存作品，退出或刷新后可以恢复。
9. 每个用户只能查询、修改和删除自己的作品。

14 天是正式开发期，第 15–18 天只作为缓冲，不超过 20 天。

## 2. 必须保留与必须延后的功能

### MVP 必须实现

- 用户注册、登录、退出和登录状态检查。
- 用户之间的作品数据隔离。
- 2 个预设故事，每个故事 3–5 个步骤。
- 10–15 个预设素材，至少 3 个分类。
- 三栏创作台。
- 故事切换、步骤切换和文字高亮。
- icon 添加、移动、缩放、删除。
- icon 绑定声音；横向位置影响左右声道，缩放影响音量。
- AI 文字提示与推荐素材高亮。
- 新建、保存、读取、列出和删除自己的作品。
- 统一的前端加载态、空状态和错误提示。

### 第二阶段再实现

- 完整多轨音频合成与空间音频。
- 复杂时间轴、旋转、图层面板、撤销和重做。
- 用户上传素材和 AI 生成图片。
- 多人实时协作。
- 公开发布、作品广场、社交关注、评论和点赞。
- 支付、订阅、管理员后台、云部署和生产运维。

MVP 实现“试听当前画面”，但不实现导出音频文件、复杂多轨合成和专业时间轴。

## 3. 本地实验为什么仍保留用户系统

如果作品未来属于不同用户，`projects.user_id` 应从第一次建表就存在。这样所有作品接口都可以按照当前登录用户过滤：

```sql
SELECT *
FROM projects
WHERE id = ? AND user_id = ?;
```

这里的用户只用于本地实验：你可以建立用户 A、用户 B，分别登录并验证作品是否正确隔离。本计划不开发公开作品、管理员查看、发布或上线功能。

## 4. 推荐技术方案

### 后端

- FastAPI
- Pydantic
- SQLite + 原生 `sqlite3`
- 密码哈希库：`pwdlib` 或 `passlib[bcrypt]`
- 登录方式：随机 Session Token + HttpOnly Cookie
- LLM API：只生成提示文本与推荐素材 ID
- `logging`：记录启动、登录失败、LLM 异常和数据库异常

### 为什么 MVP 推荐 Session Cookie

- 浏览器自动携带 Cookie，前端不需要手动保存密码或 Token。
- Session 可以在退出时由后端立即删除。
- Cookie 设置 `HttpOnly` 后，前端 JavaScript 不能直接读取 Token。
- 比同时实现 Access Token、Refresh Token 和刷新流程更适合当前学习阶段。

前端静态文件由 FastAPI 在本机提供，让页面和 API 使用同一个地址。这样无需为部署环境设计域名，也能减少 Cookie 与 CORS 配置工作。

### 前端

- HTML、CSS、JavaScript
- Konva.js 或 Fabric.js：处理画布对象、拖拽和缩放
- HTML Audio：试听单个素材
- Web Audio API：根据画布位置调整左右声道和音量
- AI 主要辅助生成布局和局部组件，数据流与接口字段由你确认

## 5. 项目目录

```text
puzzle_audiobook/
├── app/
│   ├── main.py
│   ├── api.py
│   ├── auth.py
│   ├── schemas.py
│   ├── database.py
│   ├── config.py
│   ├── llm.py
│   ├── logging_config.py
│   └── seed_data.py
├── static/
│   ├── login.html
│   ├── index.html
│   ├── css/
│   ├── js/
│   │   ├── api.js
│   │   ├── auth.js
│   │   ├── stories.js
│   │   ├── canvas.js
│   │   └── projects.js
│   ├── images/
│   └── audio/
├── .env
├── .gitignore
└── audiobook.db
```

不要一开始拆更多层。`api.py` 超过约 250 行后，再按 `auth_routes.py`、`story_routes.py`、`project_routes.py` 拆分。

`static/images` 和 `static/audio` 仍然属于本地项目文件，并不是部署到外部网站：

- 数据库保存素材名称、分类以及文件路径。
- `static/images` 保存真正的 PNG、JPG、SVG 文件。
- `static/audio` 保存真正的 MP3、WAV 文件。
- FastAPI 从本机读取这些文件并提供给本机浏览器。

不建议把图片和音频二进制直接塞进 SQLite。数据库负责描述和关联文件，静态目录负责保存文件本体。

### 当前前后端如何运行

当前属于“同一个项目、同一个服务器提供页面和 API”，但前端与后端代码职责仍然分开：

```text
浏览器访问 http://127.0.0.1:8000/static/index.html
        ↓
FastAPI 返回 static/index.html
        ↓
浏览器执行 static/js/*.js
        ↓ fetch('/stories')
FastAPI API 查询 SQLite 并返回 JSON
```

FastAPI 中使用 `StaticFiles` 提供本地静态文件，例如：

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

这通常称为前后端未独立部署，或同源部署；不代表 HTML、JavaScript 和 Python 混写在一起。

### 以后如何前后端分离

数据库和后端接口无需推翻。主要变化是：

1. 把 `static` 中的页面代码移动到独立的 `frontend` 项目。
2. 前端由自己的开发服务器运行，例如 `http://localhost:5173`。
3. FastAPI 只提供 API，例如 `http://127.0.0.1:8000/api/stories`。
4. 前端把 `fetch('/stories')` 改为读取配置中的 API 地址。
5. FastAPI CORS 只允许前端地址。
6. 图片和音频可继续由 FastAPI 提供，也可移动到前端公共资源目录。

为了方便以后拆分，现在就应遵守：

- 前端只通过 HTTP API 获取业务数据，不直接读取 SQLite。
- API 请求统一写在 `static/js/api.js`。
- 不在 HTML 中重复硬编码故事和素材数据。
- 后端响应结构由 Pydantic 模型固定。

## 6. 数据库设计

六张表全部存放在同一个 `audiobook.db` 文件中。SQLite 的一个数据库文件可以包含很多张表，它们通过 ID 和外键产生关系：

| 表 | 代表什么 | 为什么单独一张表 |
|---|---|---|
| `users` | 本地实验账号 | 一个用户可以拥有多个作品 |
| `sessions` | 当前登录会话 | 让后端知道这次请求属于哪个用户 |
| `stories` | 故事标题、简介和缩略图 | 一个故事可以包含多个步骤 |
| `story_steps` | 每个故事按顺序拆分的句子 | 避免把数量不固定的步骤塞进故事单列 |
| `assets` | icon、分类、图片路径和音频路径 | 同一个素材可以被多个作品复用 |
| `projects` | 某个用户创作的作品和画布 JSON | 同时关联用户与所选故事 |

设计思路是先找系统中的主要“对象”：用户、登录会话、故事、步骤、素材、作品；再判断它们之间是一对一还是一对多。例如一个故事有多个步骤，因此 `stories` 与 `story_steps` 分开。

### 6.1 `users`

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

只保存密码哈希，绝不能保存明文密码。

### 6.2 `sessions`

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

浏览器保存原始 Session Token；数据库只保存 Token 哈希。

### 6.3 `stories`

```sql
CREATE TABLE stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    age_label TEXT NOT NULL DEFAULT '',
    thumbnail_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 6.4 `story_steps`

```sql
CREATE TABLE story_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
    UNIQUE (story_id, step_order)
);
```

### 6.5 `assets`

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    image_url TEXT NOT NULL,
    audio_url TEXT
);
```

### 6.6 `projects`

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    story_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '未命名作品',
    current_step INTEGER NOT NULL DEFAULT 1,
    canvas_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
```

核心索引：

```sql
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_story_steps_story_id ON story_steps(story_id);
```

画布暂时整体保存为 JSON：

```json
[
  {
    "instance_id": "obj_001",
    "asset_id": 3,
    "x": 520,
    "y": 180,
    "scale": 0.8,
    "rotation": 0
  }
]
```

MVP 不拆 `canvas_objects` 表。以后需要对象级搜索、版本历史或多人协作时再拆。

### 6.7 预设故事和素材放在哪里

建议把预设数据写在后端的 `app/seed_data.py`，不要写死在 HTML，也不要每次手工执行 SQL。

最小示例：

```python
STORIES = [
    {
        "slug": "farm_day",
        "title": "农场的一天",
        "description": "认识农场中的动物",
        "age_label": "4-7岁",
        "thumbnail_url": "/static/images/farm.jpg",
        "steps": [
            "农场里住着两只小牛。",
            "小鸟每天在树上歌唱。",
            "风轻轻吹过草地。",
        ],
    }
]

ASSETS = [
    {
        "asset_key": "bird",
        "name": "小鸟",
        "category": "animal",
        "image_url": "/static/images/bird.png",
        "audio_url": "/static/audio/bird.wav",
    },
    {
        "asset_key": "cow",
        "name": "小牛",
        "category": "animal",
        "image_url": "/static/images/cow.png",
        "audio_url": "/static/audio/cow.wav",
    },
]
```

数据分为两部分：

```text
app/seed_data.py
    保存故事文字、步骤、素材名称和文件路径

static/images、static/audio
    保存真正的图片和声音文件
```

在 `database.py` 的 `init_db()` 完成建表后调用 `seed_database(connect)`。插入故事时先用 `slug` 防止重复，再查询故事 ID，最后插入步骤：

```python
def seed_database(connect):
    for story in STORIES:
        connect.execute(
            """
            INSERT OR IGNORE INTO stories (
                slug, title, description, age_label, thumbnail_url
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                story["slug"],
                story["title"],
                story["description"],
                story["age_label"],
                story["thumbnail_url"],
            ),
        )

        story_row = connect.execute(
            "SELECT id FROM stories WHERE slug = ?",
            (story["slug"],),
        ).fetchone()

        for index, sentence in enumerate(story["steps"], start=1):
            connect.execute(
                """
                INSERT OR IGNORE INTO story_steps (
                    story_id, step_order, sentence
                )
                VALUES (?, ?, ?)
                """,
                (story_row[0], index, sentence),
            )

    for asset in ASSETS:
        connect.execute(
            """
            INSERT OR IGNORE INTO assets (
                asset_key, name, category, image_url, audio_url
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                asset["asset_key"],
                asset["name"],
                asset["category"],
                asset["image_url"],
                asset["audio_url"],
            ),
        )

    connect.commit()
```

故事完整文本不重复存入 `stories`。后端读取有序步骤后，可以按需要组合：

```python
story_text = "".join(step["sentence"] for step in steps)
```

AI 操作提示不属于预设数据。用户点击“AI 提示”时，后端才把当前句子、画布对象和可用素材交给 LLM。

### 6.8 “SQLite 外键开启”的最小解释

外键表示一条数据引用另一张表中真实存在的数据。例如 `projects.user_id = 2` 表示这个作品属于 `users.id = 2` 的用户。

如果外键检查没有开启，用户 999 不存在时，SQLite 仍可能允许写入：

```sql
INSERT INTO projects (user_id, story_id, title)
VALUES (999, 1, '错误作品');
```

每次建立 SQLite 连接后执行：

```python
connect.execute("PRAGMA foreign_keys = ON")
```

开启后，上面的错误数据会被拒绝并产生 `sqlite3.IntegrityError`。最简单的记法是：

> 外键负责防止作品引用一个不存在的用户或故事。

### 6.9 第一天如何验收六张表

方法一：在终端进入项目目录后执行：

```bash
sqlite3 audiobook.db ".tables"
```

预期看到：

```text
assets  projects  sessions  stories  story_steps  users
```

方法二：进入 SQLite 后查询系统表：

```sql
SELECT name
FROM sqlite_master
WHERE type = 'table'
ORDER BY name;
```

检查外键是否开启：

```sql
PRAGMA foreign_keys;
```

当前连接返回 `1` 表示开启，返回 `0` 表示未开启。注意该设置针对每一个连接，因此 `get_db()` 和 `init_db()` 创建连接后都要设置。

检查预设数据是否重复：先记录数量，重启应用后再次执行，数量应保持不变：

```sql
SELECT COUNT(*) FROM stories;
SELECT COUNT(*) FROM story_steps;
SELECT COUNT(*) FROM assets;
```

## 7. Pydantic 模型清单

必须定义并区分请求与响应：

- `UserRegister`：邮箱、显示名、密码。
- `UserLogin`：邮箱、密码。
- `UserResponse`：用户 ID、邮箱、显示名，不包含密码哈希。
- `StorySummary`：书架卡片数据。
- `StoryDetail`：故事全文和步骤列表。
- `AssetResponse`：素材信息。
- `CanvasObject`：画布单个对象。
- `ProjectCreate`：故事 ID、作品标题。
- `ProjectUpdate`：标题、当前步骤、画布对象列表。
- `ProjectResponse`：作品完整响应。
- `HintResponse`：提示文字、推荐素材 ID。

模型中要验证：

- 邮箱格式。
- 密码最小长度。
- `scale` 合理范围，例如 `0.2–3.0`。
- `rotation` 合理范围。
- `current_step >= 1`。
- 画布对象数量设置上限，例如最多 100 个。

## 8. API 清单与权限

| 方法与路径 | 功能 | 是否登录 |
|---|---|---|
| `POST /auth/register` | 注册并创建会话 | 否 |
| `POST /auth/login` | 登录并创建会话 | 否 |
| `POST /auth/logout` | 删除当前会话 | 是 |
| `GET /auth/me` | 获取当前用户 | 是 |
| `GET /stories` | 获取故事书架 | 是 |
| `GET /stories/{story_id}` | 获取故事和步骤 | 是 |
| `GET /assets` | 获取素材，可按分类筛选 | 是 |
| `POST /projects` | 新建自己的作品 | 是 |
| `GET /projects` | 获取自己的作品列表 | 是 |
| `GET /projects/{id}` | 获取自己的单个作品 | 是 |
| `PUT /projects/{id}` | 更新自己的作品 | 是 |
| `DELETE /projects/{id}` | 删除自己的作品 | 是 |
| `POST /projects/{id}/hint` | 获取当前作品的 AI 提示 | 是 |

所有带 `{id}` 的作品 SQL 必须同时判断用户：

```sql
WHERE id = ? AND user_id = ?
```

不能先按 ID 查出作品，再忘记检查所有者。

## 9. 14 天详细执行计划

### 第 1 天：冻结需求、项目骨架和数据库

后端：

- 创建项目目录和最小 FastAPI 应用。
- 配置 `.env`、日志、lifespan 和 SQLite 外键开启。
- 创建 `users`、`sessions`、`stories`、`story_steps`、`assets`、`projects`。
- 编写可重复执行的初始化函数和预设数据函数。

数据：

- 准备 2 个故事标题和完整正文。
- 每个故事拆成 3–5 个步骤。
- 准备 10–15 个素材的名称、分类、图片路径和音频路径。
- 把故事、步骤和素材说明作为预设数据写入数据库。
- 把对应图片放入 `static/images`，音频放入 `static/audio`。

前端：

- 只建立 `login.html` 与 `index.html` 空骨架。

验收：

- 执行 `sqlite3 audiobook.db ".tables"` 能看到六张业务表。
- 重启应用不会重复插入预设数据。
- 在应用创建的数据库连接中，`PRAGMA foreign_keys` 返回 `1`。
- `.env` 和数据库文件不进入 Git。

### 第 2 天：注册、密码哈希和 Session

后端：

- 学习密码哈希，完成 `UserRegister`。
- 实现 `POST /auth/register`。
- 邮箱重复返回 409。
- 生成高强度随机 Session Token，数据库只保存哈希。
- 使用 HttpOnly Cookie 返回会话。

前端：

- 创建注册表单：邮箱、显示名、密码、确认密码。
- 显示字段校验和后端错误。

验收：

- 数据库中没有明文密码和原始 Token。
- 重复邮箱无法注册。
- 注册成功后浏览器获得 Cookie。
- 非法邮箱和短密码不能提交。

### 第 3 天：登录、退出和权限依赖

后端：

- 实现 `POST /auth/login`、`POST /auth/logout`、`GET /auth/me`。
- 编写 `get_current_user` 依赖。
- Session 设置过期时间，过期会话返回 401。

前端：

- 创建登录表单。
- 页面启动时请求 `/auth/me`。
- 未登录留在登录页；已登录进入创作台。
- 添加退出按钮。

验收：

- 正确账号可以登录。
- 错误密码只返回统一提示，不暴露邮箱是否存在。
- 退出后原 Session 失效。
- 未登录访问受保护接口得到 401。

### 第 4 天：故事数据与切换功能

后端：

- 实现 `GET /stories`，返回书架卡片列表。
- 实现 `GET /stories/{id}`，返回全文和有序步骤。
- 不存在的故事返回 404。

前端：

- 完成左侧故事书架卡片。
- 页面加载时请求 `/stories`。
- 默认选择第一篇故事，并请求 `/stories/{id}`。
- 点击其他故事卡片时重新请求详情。
- 更新标题、全文、步骤和选中高亮。

验收：

- 登录后可以看到 2 个真实数据库故事。
- 点击第二个故事时，标题、正文和步骤全部切换。
- 当前选中的故事卡片有明确高亮。
- 错误或空故事列表有提示，不出现空白页面。

### 第 5 天：三栏创作台与故事步骤

前端：

- 建立左侧故事区、中间画布区、右侧素材区。
- 左侧加入上一条、下一条和当前步骤编号。
- 切换步骤时高亮对应句子。
- 全文由有序的 `story_steps.sentence` 组合显示。

后端：

- 只修正故事响应字段，不增加新业务功能。

验收：

- 三栏在常见桌面宽度下不重叠。
- 每个故事都能从第一步切换到最后一步。
- 当前步骤句子在全文中正确高亮。
- 切换故事后步骤自动回到第一步。

### 第 6 天：素材接口与素材库

后端：

- 实现 `GET /assets`。
- 支持 `?category=animal` 筛选。
- 空分类返回 `[]`。

前端：

- 右侧显示分类按钮和素材卡片。
- 素材卡片显示图片、名称和试听按钮。
- 切换分类后更新素材列表。
- 图片加载失败时显示占位图。

验收：

- 至少 3 个分类、10 个素材来自真实 API。
- 分类切换结果正确。
- 有音频的素材可以试听，无音频时按钮禁用。

### 第 7 天：画布添加、移动、缩放和删除

前端：

- 接入 Konva.js 或 Fabric.js，二选一。
- 点击或拖拽素材到画布。
- 支持选中、移动、缩放和删除。
- 给每个实例生成唯一 `instance_id`。
- 每个实例保留对应的 `asset_id`，以便找到绑定音频。
- 提供清空画布按钮和确认提示。

数据：

- 实时生成统一的 `canvas_objects` 数组。
- 坐标保存为画布坐标，不能保存页面绝对坐标。

验收：

- 同一素材可以添加多个实例。
- 10 个对象同时存在时仍可操作。
- 移动和缩放后 JSON 正确更新。
- 删除对象后 JSON 中对应实例消失。

### 第 8 天：画布声音映射与试听

前端：

- 素材卡片试听时播放 `assets.audio_url` 的原始声音。
- 画布对象试听时，根据 `x` 计算左右声道。
- 根据 `scale` 计算简单音量，不实现真实物理声学。
- 添加“试听当前画面”按钮，播放画布中有音频的对象。
- 播放前由用户主动点击按钮，避免浏览器自动播放限制。

最小映射规则：

```text
pan = (对象中心 x / 画布宽度) × 2 - 1
volume = 限制在 0.2 到 1.0 之间的 scale
```

验收：

- 小鸟放在左侧时声音明显偏左，放在右侧时明显偏右。
- icon 变大后声音更响，变小后声音更轻。
- 没有 `audio_url` 的素材不会导致整个试听失败。
- 故事步骤本身不绑定声音，也不会自动生成 AI 提示。

### 第 9 天：创建作品与用户作品列表

后端：

- 实现 `POST /projects` 和 `GET /projects`。
- 新建作品自动写入当前 `user_id`。
- 作品列表只查询当前用户。

前端：

- 登录后先显示“我的作品”和“新建作品”。
- 新建时选择故事并输入标题。
- 创建成功后进入创作台并保存 `project_id`。

验收：

- 用户 A 和用户 B 分别只能看到自己的作品。
- 新建作品与当前用户、故事正确关联。
- 不允许创建不存在故事的作品。

### 第 10 天：保存与恢复画布

后端：

- 实现 `GET /projects/{id}` 和 `PUT /projects/{id}`。
- 保存标题、当前步骤和画布 JSON。
- 更新 `updated_at`。
- 所有查询包含 `id` 与当前 `user_id`。

前端：

- 点击保存时提交当前步骤与画布对象。
- 增加“保存中、保存成功、保存失败”状态。
- 从作品列表进入时恢复故事、步骤和画布。
- 保存过程中禁用重复提交。

验收：

- 保存后刷新页面，画布对象的位置和大小完全恢复。
- 恢复后的 `asset_id` 仍能找到正确图片和音频。
- 用户 B 即使知道用户 A 的作品 ID，也无法读取或修改。
- 非法画布 JSON 得到 422，不写入数据库。

### 第 11 天：按需生成 AI 提示

后端：

- 只有用户点击按钮时才调用 LLM。
- 输入当前故事句子、现有画布素材 ID 和可用素材列表。
- 要求 LLM 返回固定 JSON：`hint` 和 `recommended_asset_ids`。
- 使用 Pydantic 校验 LLM 输出。
- 超时或服务错误转换为 503。
- 推荐 ID 必须存在于 `assets`。

前端：

- 添加“AI 提示”按钮。
- 请求期间显示加载状态并禁用按钮。
- 显示提示气泡。
- 高亮右侧推荐素材并显示推荐标记。

验收：

- 不点击按钮时不会调用 LLM。
- 连续测试 5 次都能得到可解析响应。
- 推荐素材一定来自当前素材库。
- LLM 失败时已有画布不丢失，用户可以继续手动创作。

### 第 12 天：删除作品、完整导航和错误状态

后端：

- 实现 `DELETE /projects/{id}`，只允许所有者删除。
- 检查注册冲突、401、404、422、数据库 500、LLM 503。
- 写操作确认 `commit/rollback`。
- 日志不记录密码、Cookie、Session Token、API Key。

前端：

- 完成“登录页 → 我的作品 → 新建/继续编辑 → 返回列表 → 退出”的导航。
- 删除前二次确认，删除成功后立即更新列表。
- 所有请求统一处理 401。
- 为加载、空列表、网络失败和服务器失败提供不同状态。
- 有未保存修改时离开页面给出提醒。

验收：

- 完整导航不依赖手工修改 URL。
- 删除操作不会影响其他用户作品。
- 前端不会只显示“Load failed”。
- 日志能定位错误，但不含敏感值。

### 第 13 天：自动测试和集成修复

后端：

- 使用 FastAPI `TestClient`。
- 覆盖注册、登录、未授权访问、用户隔离、创建作品、保存恢复和删除作品。
- 对 LLM 使用假的测试响应，不调用真实收费 API。

前端：

- 使用两个本地测试账号完成全流程。
- 测试空画布、多对象、快速切换故事、重复保存和无音频素材。
- 测试声音左右位置和大小映射。

验收：

- 核心后端测试全部通过。
- 用户隔离测试必须通过。
- 画布恢复后图像与声音映射仍正确。
- 演示主流程没有阻塞性错误。

### 第 14 天：演示版本和文档

- 冻结功能，不再增加需求。
- 清理演示数据，保留 2 个完整故事和清晰素材。
- 编写 README：安装、环境变量、初始化、启动和测试。
- 准备 2–3 分钟演示脚本。
- 完整演示：注册 → 登录 → 新建作品 → 切换故事步骤 → 拼贴 → 试听画面 → AI 提示 → 保存 → 退出 → 再登录恢复。

验收：

- 删除本地测试数据库后，按 README 可以重新初始化并启动。
- 演示流程连续完成 3 次。
- 数据在刷新、退出和重新登录后仍正确。

## 10. 第 15–18 天缓冲安排

只有第 14 天仍有阻塞问题时使用：

- 第 15 天：修复本地认证或 Cookie 问题。
- 第 16 天：修复画布序列化和恢复问题。
- 第 17 天：修复 LLM 结构化输出与异常降级。
- 第 18 天：界面可用性、README 和最终演示修复。

缓冲期禁止加入完整音频合成、社交功能或多人协作。

## 11. 学习顺序

### 开始前必须理解

1. SQLite 外键、一对多、唯一约束和索引。
2. 密码哈希与“不能解密密码”的概念。
3. Cookie、Session、401 和当前用户依赖。
4. Pydantic 请求模型与响应模型分离。

### 开发到对应日期再学习

- 第 4–6 天：`fetch`、DOM 更新、HTML Audio。
- 第 7 天：Konva.js 或 Fabric.js 的对象事件与 JSON 序列化。
- 第 8 天：Web Audio API 的 `StereoPannerNode` 和 `GainNode`。
- 第 10 天：JSON `dumps/loads` 与坐标恢复。
- 第 11 天：LLM 结构化输出和 Pydantic 二次验证。
- 第 13 天：FastAPI `TestClient`、测试数据库和依赖替换。

### 暂时不要学习

- OAuth 第三方登录。
- JWT Refresh Token 体系。
- React 全家桶和复杂状态管理。
- Redis、消息队列、微服务和 WebSocket。
- 向量数据库、RAG 和模型微调。
- 专业音频时间轴与实时多人协作。

## 12. AI 辅助开发规则

- 一次只让 AI 完成一个接口或一个前端组件。
- 提问时附上真实的 Schema、请求 JSON、响应 JSON。
- 要求 AI 明确修改的文件和行，不允许它顺带重构无关模块。
- 前端优先让 AI 辅助布局、空状态、加载态和错误态。
- 后端代码必须人工检查 SQL 参数化、用户权限条件、事务和敏感日志。
- 不把 `.env`、真实 API Key、密码、Cookie 和完整日志发给外部 AI。
- 每完成一天的验收后做一次 Git 提交。

## 13. 最终验收清单

- [ ] 用户可注册、登录和退出。
- [ ] 密码和 Session Token 不以明文存储。
- [ ] 未登录用户不能访问创作数据。
- [ ] 不同用户的作品完全隔离。
- [ ] 2 个故事可以真实切换，任务与验收一致。
- [ ] 每个故事有有序步骤和当前句子高亮。
- [ ] 至少 3 个分类、10 个素材来自数据库。
- [ ] icon 可添加、移动、缩放和删除。
- [ ] icon 声音与素材绑定，左右位置和缩放影响试听效果。
- [ ] AI 返回固定结构的提示与推荐素材。
- [ ] 作品可创建、保存、恢复、列出和删除。
- [ ] 刷新和重新登录后仍可恢复画布。
- [ ] 关键后端接口有自动测试。
- [ ] API Key、密码和会话信息未进入 Git 和日志。

首个版本要证明的核心不是“功能数量多”，而是：**用户身份明确、作品归属可靠、故事能够切换、拼贴能够保存、AI 提示确实帮助创作。**
