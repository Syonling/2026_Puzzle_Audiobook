const STORAGE_KEY = "puzzleAudiobookLanguage";
const SUPPORTED_LANGUAGES = new Set(["ja", "zh", "en"]);

const messages = {
    zh: {
        "app.title": "有声绘本工作台", "app.description": "AI 辅助空间拼贴式有声绘本创作工作台",
        "app.brand": "有声绘本", "app.home": "返回有声绘本工作台首页", "app.workspace": "有声绘本创作工作台",
        "section.story": "故事", "section.canvas": "画布", "section.library": "素材",
        "project.unnamed": "未命名作品", "account.open": "打开用户菜单", "account.current": "当前用户",
        "account.logout": "退出登录", "account.logoutPending": "正在退出…", "account.loginOrRegister": "登录或注册",
        "account.userMenu": "{username} 的用户菜单", "language.label": "界面语言", "language.ja": "日语", "language.zh": "中文", "language.en": "英语",
        "story.heading": "故事与引导", "story.fallback": "故事", "story.current": "当前故事", "story.loading": "正在加载故事…",
        "story.wait": "请稍候", "story.none": "暂无故事", "story.noneDescription": "书架中还没有可选择的故事",
        "story.steps": "故事步骤", "story.step": "故事步骤 {order}", "story.stepView": "查看故事步骤 {order}",
        "story.stepLoading": "正在加载故事内容…", "story.noSteps": "这个故事暂时没有步骤内容。",
        "story.readFailed": "暂时无法读取故事内容。", "story.contentLoadFailed": "故事内容加载失败",
        "story.listReadFailed": "暂时无法读取故事。", "story.listLoadFailed": "故事列表加载失败",
        "story.choose": "选择故事：{title}", "story.open": "打开这本故事", "story.cover": "{title}封面",
        "story.switchSteps": "切换故事步骤", "bookshelf.title": "选择一个故事", "bookshelf.close": "关闭书架",
        "ai.heading": "AI 创作助手", "ai.placeholder": "问问 AI，这一页可以怎么画？", "ai.submit": "提交", "ai.thinking": "思考中…",
        "ai.presets": "预设 AI 问题", "ai.presetsLoading": "正在加载推荐问题…", "ai.presetsEmpty": "暂无推荐问题",
        "ai.presetsInvalid": "推荐问题格式不正确", "ai.presetsFailed": "推荐问题加载失败", "ai.inputRequired": "请输入想问 AI 的内容",
        "ai.stepRequired": "请先选择一个已经加载完成的故事步骤", "ai.suggestionInvalid": "AI 推荐结果格式不正确",
        "ai.suggestions": "已在右侧素材库中高亮 {count} 个推荐素材", "ai.noSuggestions": "AI 暂时没有找到匹配的素材",
        "ai.generated": "AI 已重新布置当前画布，请确认后保存", "ai.unknownMode": "AI 返回了未知的处理模式",
        "ai.failed": "AI 暂时无法回答，请稍后重试", "ai.answer": "AI 的回答", "ai.error": "AI 请求失败", "ai.retry": "重试", "ai.acceptDesign": "接受设计", "ai.rejectDesign": "拒绝设计", "ai.closeAnswer": "关闭 AI 回答",
        "canvas.heading": "绘本画布", "canvas.save": "保存", "canvas.saving": "保存中…", "canvas.unsaved": "尚未保存",
        "history.controls": "撤销与恢复", "history.undo": "撤销上一步", "history.redo": "恢复上一步",
        "canvas.current": "当前故事步骤的绘本画布", "canvas.noStep": "尚未选择故事步骤", "canvas.area": "画布区域",
        "canvas.chooseStep": "选择故事步骤后，将为它建立独立画布", "canvas.page": "第 {order} / {total} 页",
        "canvas.stepTitle": "{title} · 步骤 {order}", "canvas.dragHint": "从右侧把素材拖到这里", "canvas.loading": "正在加载画布…",
        "canvas.loadingSaved": "正在读取这一故事步骤保存的内容", "canvas.object": "画布对象", "canvas.material": "素材",
        "canvas.editObject": "编辑{label}", "canvas.zoomOut": "缩小", "canvas.zoom": "当前缩放比例", "canvas.zoomIn": "放大",
        "canvas.delete": "删除", "canvas.deleteObject": "删除对象", "canvas.bringForward": "向上一层", "canvas.mirrorHorizontal": "左右镜像", "canvas.removeBackground": "删除背景", "canvas.resize": "拖动缩放", "canvas.rotate": "按住并拖动旋转",
        "canvas.drop": "放到画布中", "canvas.noEditable": "当前没有可编辑的画布", "canvas.aiInvalid": "AI 画布格式不正确",
        "canvas.aiAssetInvalid": "AI 返回了无效的素材对象", "canvas.aiCoordinateInvalid": "AI 返回了无效的画布坐标",
        "audio.timeline": "音频时间轴", "audio.tracks": "音频轨道", "audio.controls": "音频播放控制", "audio.currentStep": "当前步骤 · 0:00", "audio.stepStatus": "第 {order} 页 · {time}",
        "audio.noStep": "未选择步骤 · {time}", "audio.play": "播放", "audio.pause": "暂停", "audio.stop": "停止",
        "audio.narration": "旁白", "audio.narrationFixed": "固定旁白轨道，不接受手动拖入", "audio.background": "背景音频", "audio.effects": "素材音效", "audio.free": "自由轨道", "audio.seek": "拖动播放位置",
        "audio.clip": "音频", "audio.dragClip": "拖动音频块：{name}", "audio.fixedClip": "固定音频：{name}", "audio.trim": "拖动裁剪音频结尾", "audio.seconds": "{value}秒", "audio.clipDetail": "{name} · {duration}秒",
        "audio.effectsControls": "音频效果处理", "audio.selectClip": "选择音频后添加效果", "audio.fadeIn": "淡入", "audio.fadeOut": "淡出", "audio.reverb": "空间", "audio.echo": "回声", "audio.effectUndo": "撤销", "audio.effectReset": "还原", "audio.backgroundVolume": "背景音量", "audio.backgroundVolumeAdjust": "调整背景音量",
        "audio.unsupported": "当前浏览器不支持音频时间轴播放", "audio.fileFailed": "音频文件加载失败",
        "audio.preparing": "正在准备音频…", "audio.playFailed": "音频播放失败", "audio.loading": "正在加载音轨…",
        "audioPicker.eyebrow": "Icon Audio", "audioPicker.heading": "素材声音", "audioPicker.options": "素材音频备选",
        "audioPicker.iconAndAudio": "{icon} · 当前：{audio}", "audioPicker.silent": "无声音", "audioPicker.switching": "正在切换音频…", "audioPicker.failed": "音频切换失败",
        "library.heading": "素材库", "library.search": "搜索素材", "library.categories": "素材分类", "library.all": "全部", "library.pagination": "素材分页", "library.page": "第 {page} 页",
        "library.recommended": "推荐素材", "library.closeRecommended": "关闭 AI 推荐", "library.loading": "正在加载素材…",
        "library.empty": "暂无素材", "library.noMatch": "没有找到匹配的素材", "library.invalid": "素材数据格式不正确",
        "library.failed": "素材加载失败", "library.drag": "拖动“{name}”到画布",
        "category.animal": "动物", "category.nature": "自然", "category.character": "角色", "category.vehicle": "交通",
        "category.furniture": "家具", "category.building": "建筑", "category.emotion": "情绪", "category.action": "动作",
        "category.background": "背景", "category.sound": "声音",
        "auth.close": "关闭登录窗口", "auth.welcome": "欢迎回来", "auth.create": "创建账户",
        "auth.loginIntro": "登录后继续创作你的有声绘本。", "auth.registerIntro": "注册一个账户，开始保存你的创作。",
        "auth.actions": "账户操作", "auth.login": "登录", "auth.register": "注册", "auth.username": "用户名", "auth.password": "密码",
        "auth.required": "请输入用户名和密码", "auth.loggingIn": "正在登录…", "auth.registering": "正在注册…",
        "auth.usernameExists": "用户名已存在", "auth.wrongCredentials": "用户名或密码错误",
        "auth.back": "← 返回工作台", "auth.pageTitle": "账户 · 有声绘本", "auth.description": "登录或注册有声绘本账户",
        "unsaved.title": "保存当前画布？", "unsaved.message": "当前画布有未保存的更改。切换前是否保存？",
        "unsaved.cancel": "取消", "unsaved.discard": "不保存", "unsaved.save": "保存并切换", "unsaved.saving": "正在保存…",
        "request.failed": "请求失败，请稍后重试", "project.finding": "正在查找已有项目…", "project.invalid": "项目查询响应无效",
        "project.found": "已找到项目 #{id}", "project.notCreated": "尚未创建项目", "project.lookupFailed": "项目查询失败",
        "project.loading": "正在加载画布…", "project.loaded": "画布已加载", "project.loadFailed": "画布加载失败",
        "project.notReady": "当前画布尚未准备完成", "project.saving": "正在保存…", "project.createInvalid": "项目创建响应无效",
        "project.createdChanged": "项目已创建（#{id}），有保存后的新更改", "project.created": "项目已创建并保存（#{id}）",
        "project.createdLoading": "项目已创建（#{id}），正在加载当前画布…", "project.saveInvalid": "画布保存响应无效",
        "project.stepSavedChanged": "步骤 {order} 已保存，有保存后的新更改", "project.stepSaved": "步骤 {order} 保存成功",
        "project.saveFailed": "保存失败，请稍后重试", "project.changed": "有未保存的更改"
    },
    ja: {},
    en: {}
};

Object.assign(messages.ja, {
    "ai.acceptDesign":"デザインを採用","ai.rejectDesign":"元に戻す",
    "ai.error":"AIリクエストに失敗しました","ai.retry":"再試行",
    "canvas.removeBackground":"背景を削除",
    "audio.clipDetail":"{name}・{duration}秒",
    "audioPicker.eyebrow":"Icon Audio","audioPicker.heading":"素材サウンド","audioPicker.options":"素材音声の候補","audioPicker.iconAndAudio":"{icon}・現在：{audio}","audioPicker.silent":"無音","audioPicker.switching":"音声を切り替えています…","audioPicker.failed":"音声の切り替えに失敗しました",
    "auth.usernameExists":"ユーザー名はすでに存在します","auth.wrongCredentials":"ユーザー名またはパスワードが正しくありません",
    "section.story":"ストーリー","section.canvas":"キャンバス","section.library":"素材","audio.controls":"オーディオ再生コントロール",
    "app.title":"オーディオ絵本ワークスペース","app.description":"AI支援コラージュ式オーディオ絵本制作ワークスペース","app.brand":"オーディオ絵本","app.home":"ワークスペースのホームへ戻る","app.workspace":"オーディオ絵本制作ワークスペース","project.unnamed":"無題の作品","account.open":"ユーザーメニューを開く","account.current":"現在のユーザー","account.logout":"ログアウト","account.logoutPending":"ログアウト中…","account.loginOrRegister":"ログインまたは登録","account.userMenu":"{username} のユーザーメニュー","language.label":"表示言語","language.ja":"日本語","language.zh":"中国語","language.en":"英語",
    "story.heading":"物語とガイド","story.fallback":"物語","story.current":"現在の物語","story.loading":"物語を読み込み中…","story.wait":"しばらくお待ちください","story.none":"物語がありません","story.noneDescription":"本棚に選べる物語がありません","story.steps":"物語のステップ","story.step":"物語のステップ {order}","story.stepView":"物語のステップ {order} を表示","story.stepLoading":"物語を読み込み中…","story.noSteps":"この物語にはまだステップがありません。","story.readFailed":"物語を読み込めません。","story.contentLoadFailed":"物語の読み込みに失敗しました","story.listReadFailed":"物語を読み込めません。","story.listLoadFailed":"物語一覧の読み込みに失敗しました","story.choose":"物語を選択：{title}","story.open":"この物語を開く","story.cover":"{title}の表紙","story.switchSteps":"物語のステップを切り替える","bookshelf.title":"物語を選ぶ","bookshelf.close":"本棚を閉じる",
    "ai.heading":"AI制作アシスタント","ai.placeholder":"このページの描き方をAIに聞く","ai.submit":"送信","ai.thinking":"考え中…","ai.presets":"AI質問例","ai.presetsLoading":"おすすめ質問を読み込み中…","ai.presetsEmpty":"おすすめ質問はありません","ai.presetsInvalid":"おすすめ質問の形式が正しくありません","ai.presetsFailed":"おすすめ質問の読み込みに失敗しました","ai.inputRequired":"AIへの質問を入力してください","ai.stepRequired":"読み込み済みの物語ステップを選択してください","ai.suggestionInvalid":"AIのおすすめ形式が正しくありません","ai.suggestions":"右側の素材ライブラリで {count} 件をおすすめ表示しました","ai.noSuggestions":"一致する素材が見つかりませんでした","ai.generated":"AIが現在のキャンバスを再配置しました。確認して保存してください","ai.unknownMode":"AIから不明な処理モードが返されました","ai.failed":"AIが応答できません。後でもう一度お試しください","ai.answer":"AIの回答","ai.closeAnswer":"AIの回答を閉じる",
    "canvas.heading":"絵本キャンバス","canvas.save":"保存","canvas.saving":"保存中…","canvas.unsaved":"未保存","history.controls":"元に戻す・やり直す","history.undo":"一つ前に戻す","history.redo":"一つ先に進む","canvas.current":"現在の物語ステップのキャンバス","canvas.noStep":"物語ステップが未選択です","canvas.area":"キャンバス領域","canvas.chooseStep":"物語ステップを選ぶと個別のキャンバスが作成されます","canvas.page":"{order} / {total} ページ","canvas.stepTitle":"{title}・ステップ {order}","canvas.dragHint":"右側から素材をドラッグしてください","canvas.loading":"キャンバスを読み込み中…","canvas.loadingSaved":"保存済みキャンバスを読み込んでいます","canvas.object":"キャンバスオブジェクト","canvas.material":"素材","canvas.editObject":"{label}を編集","canvas.zoomOut":"縮小","canvas.zoom":"現在の拡大率","canvas.zoomIn":"拡大","canvas.delete":"削除","canvas.deleteObject":"オブジェクトを削除","canvas.bringForward":"一つ前面へ","canvas.mirrorHorizontal":"左右反転","canvas.resize":"ドラッグして拡大縮小","canvas.rotate":"押したままドラッグして回転","canvas.drop":"キャンバスに配置","canvas.noEditable":"編集可能なキャンバスがありません","canvas.aiInvalid":"AIキャンバスの形式が正しくありません","canvas.aiAssetInvalid":"AIから無効な素材が返されました","canvas.aiCoordinateInvalid":"AIから無効な座標が返されました",
    "audio.timeline":"オーディオタイムライン","audio.tracks":"オーディオトラック","audio.currentStep":"現在のステップ・0:00","audio.stepStatus":"{order}ページ・{time}","audio.noStep":"ステップ未選択・{time}","audio.play":"再生","audio.pause":"一時停止","audio.stop":"停止","audio.narration":"ナレーション","audio.narrationFixed":"固定ナレーショントラックには手動で追加できません","audio.background":"背景音声","audio.effects":"素材効果音","audio.free":"フリートラック","audio.seek":"再生位置をドラッグ","audio.clip":"オーディオ","audio.dragClip":"オーディオクリップをドラッグ：{name}","audio.fixedClip":"固定オーディオ：{name}","audio.trim":"末尾をドラッグしてトリミング","audio.seconds":"{value}秒","audio.effectsControls":"音声エフェクト処理","audio.selectClip":"音声を選択してエフェクトを追加","audio.fadeIn":"フェードイン","audio.fadeOut":"フェードアウト","audio.reverb":"空間","audio.echo":"エコー","audio.effectUndo":"元に戻す","audio.effectReset":"リセット","audio.backgroundVolume":"背景音量","audio.backgroundVolumeAdjust":"背景音量を調整","audio.unsupported":"このブラウザはオーディオタイムライン再生に対応していません","audio.fileFailed":"音声ファイルの読み込みに失敗しました","audio.preparing":"音声を準備中…","audio.playFailed":"音声の再生に失敗しました","audio.loading":"トラックを読み込み中…",
    "library.heading":"素材ライブラリ","library.search":"素材を検索","library.categories":"素材カテゴリー","library.all":"すべて","library.pagination":"素材ページ","library.page":"{page}ページ目","library.recommended":"おすすめ素材","library.closeRecommended":"AIおすすめを閉じる","library.loading":"素材を読み込み中…","library.empty":"素材がありません","library.noMatch":"一致する素材がありません","library.invalid":"素材データの形式が正しくありません","library.failed":"素材の読み込みに失敗しました","library.drag":"「{name}」をキャンバスへドラッグ","category.animal":"動物","category.nature":"自然","category.character":"キャラクター","category.vehicle":"乗り物","category.furniture":"家具","category.building":"建物","category.emotion":"感情","category.action":"動作","category.background":"背景","category.sound":"音",
    "auth.close":"ログイン画面を閉じる","auth.welcome":"おかえりなさい","auth.create":"アカウント作成","auth.loginIntro":"ログインしてオーディオ絵本の制作を続けましょう。","auth.registerIntro":"アカウントを作成して作品を保存しましょう。","auth.actions":"アカウント操作","auth.login":"ログイン","auth.register":"登録","auth.username":"ユーザー名","auth.password":"パスワード","auth.required":"ユーザー名とパスワードを入力してください","auth.loggingIn":"ログイン中…","auth.registering":"登録中…","auth.back":"← ワークスペースへ戻る","auth.pageTitle":"アカウント・オーディオ絵本","auth.description":"オーディオ絵本アカウントにログインまたは登録",
    "unsaved.title":"現在のキャンバスを保存しますか？","unsaved.message":"未保存の変更があります。切り替える前に保存しますか？","unsaved.cancel":"キャンセル","unsaved.discard":"保存しない","unsaved.save":"保存して切り替え","unsaved.saving":"保存中…","request.failed":"リクエストに失敗しました。後でもう一度お試しください","project.finding":"既存プロジェクトを検索中…","project.invalid":"プロジェクト応答が正しくありません","project.found":"プロジェクト #{id} が見つかりました","project.notCreated":"プロジェクトは未作成です","project.lookupFailed":"プロジェクト検索に失敗しました","project.loading":"キャンバスを読み込み中…","project.loaded":"キャンバスを読み込みました","project.loadFailed":"キャンバスの読み込みに失敗しました","project.notReady":"キャンバスの準備が完了していません","project.saving":"保存中…","project.createInvalid":"プロジェクト作成応答が正しくありません","project.createdChanged":"プロジェクト #{id} を作成しました。保存後の変更があります","project.created":"プロジェクト #{id} を作成して保存しました","project.createdLoading":"プロジェクト #{id} を作成しました。現在のキャンバスを読み込み中…","project.saveInvalid":"キャンバス保存応答が正しくありません","project.stepSavedChanged":"ステップ {order} を保存しました。新しい変更があります","project.stepSaved":"ステップ {order} を保存しました","project.saveFailed":"保存に失敗しました。後でもう一度お試しください","project.changed":"未保存の変更があります"
});

Object.assign(messages.en, {
    "ai.acceptDesign":"Accept Design","ai.rejectDesign":"Reject Design",
    "ai.error":"AI request failed","ai.retry":"Retry",
    "canvas.removeBackground":"Remove Background",
    "audio.clipDetail":"{name} · {duration}s",
    "audioPicker.eyebrow":"Icon Audio","audioPicker.heading":"Asset Sound","audioPicker.options":"Alternative asset audio","audioPicker.iconAndAudio":"{icon} · Current: {audio}","audioPicker.silent":"No Sound","audioPicker.switching":"Switching audio…","audioPicker.failed":"Failed to switch audio",
    "auth.usernameExists":"Username already exists","auth.wrongCredentials":"Wrong username or password",
    "section.story":"Story","section.canvas":"Canvas","section.library":"Library","audio.controls":"Audio playback controls",
    "app.title":"Audiobook Studio","app.description":"AI-assisted spatial collage audiobook studio","app.brand":"Audiobook","app.home":"Return to the audiobook studio home","app.workspace":"Audiobook creation workspace","project.unnamed":"Untitled Project","account.open":"Open user menu","account.current":"Current user","account.logout":"Log out","account.logoutPending":"Logging out…","account.loginOrRegister":"Log in or register","account.userMenu":"User menu for {username}","language.label":"Interface language","language.ja":"Japanese","language.zh":"Chinese","language.en":"English",
    "story.heading":"Story & Guidance","story.fallback":"Story","story.current":"Current story","story.loading":"Loading stories…","story.wait":"Please wait","story.none":"No stories","story.noneDescription":"There are no stories to choose from","story.steps":"Story steps","story.step":"Story step {order}","story.stepView":"View story step {order}","story.stepLoading":"Loading story content…","story.noSteps":"This story has no steps yet.","story.readFailed":"Unable to read the story content.","story.contentLoadFailed":"Failed to load story content","story.listReadFailed":"Unable to read stories.","story.listLoadFailed":"Failed to load the story list","story.choose":"Choose story: {title}","story.open":"Open this story","story.cover":"Cover of {title}","story.switchSteps":"Switch story steps","bookshelf.title":"Choose a Story","bookshelf.close":"Close bookshelf",
    "ai.heading":"AI Creative Assistant","ai.placeholder":"Ask AI how to illustrate this page","ai.submit":"Submit","ai.thinking":"Thinking…","ai.presets":"Preset AI questions","ai.presetsLoading":"Loading suggested questions…","ai.presetsEmpty":"No suggested questions","ai.presetsInvalid":"Invalid suggested-question format","ai.presetsFailed":"Failed to load suggested questions","ai.inputRequired":"Enter a question for AI","ai.stepRequired":"Select a fully loaded story step first","ai.suggestionInvalid":"Invalid AI suggestion format","ai.suggestions":"Highlighted {count} suggested assets in the library","ai.noSuggestions":"AI could not find matching assets","ai.generated":"AI rearranged the current canvas. Review and save it","ai.unknownMode":"AI returned an unknown mode","ai.failed":"AI cannot answer right now. Please try again later","ai.answer":"AI answer","ai.closeAnswer":"Close AI answer",
    "canvas.heading":"Picture-book Canvas","canvas.save":"Save","canvas.saving":"Saving…","canvas.unsaved":"Not saved","history.controls":"Undo and redo","history.undo":"Undo last change","history.redo":"Redo last change","canvas.current":"Canvas for the current story step","canvas.noStep":"No story step selected","canvas.area":"Canvas area","canvas.chooseStep":"Select a story step to create its individual canvas","canvas.page":"Page {order} / {total}","canvas.stepTitle":"{title} · Step {order}","canvas.dragHint":"Drag assets here from the right","canvas.loading":"Loading canvas…","canvas.loadingSaved":"Reading the saved canvas for this story step","canvas.object":"canvas object","canvas.material":"asset","canvas.editObject":"Edit {label}","canvas.zoomOut":"Zoom out","canvas.zoom":"Current scale","canvas.zoomIn":"Zoom in","canvas.delete":"Delete","canvas.deleteObject":"Delete object","canvas.bringForward":"Bring forward one layer","canvas.mirrorHorizontal":"Flip horizontally","canvas.resize":"Drag to resize","canvas.rotate":"Hold and drag to rotate","canvas.drop":"Drop onto canvas","canvas.noEditable":"There is no editable canvas","canvas.aiInvalid":"Invalid AI canvas format","canvas.aiAssetInvalid":"AI returned an invalid asset","canvas.aiCoordinateInvalid":"AI returned invalid canvas coordinates",
    "audio.timeline":"Audio timeline","audio.tracks":"Audio Tracks","audio.currentStep":"Current step · 0:00","audio.stepStatus":"Page {order} · {time}","audio.noStep":"No step selected · {time}","audio.play":"Play","audio.pause":"Pause","audio.stop":"Stop","audio.narration":"Narration","audio.narrationFixed":"The fixed narration track does not accept manual drops","audio.background":"Background Audio","audio.effects":"Asset Audio","audio.free":"Free Track","audio.seek":"Drag playback position","audio.clip":"Audio","audio.dragClip":"Drag audio clip: {name}","audio.fixedClip":"Fixed audio: {name}","audio.trim":"Drag to trim the audio ending","audio.seconds":"{value}s","audio.effectsControls":"Audio effects","audio.selectClip":"Select audio to add effects","audio.fadeIn":"Fade In","audio.fadeOut":"Fade Out","audio.reverb":"Space","audio.echo":"Echo","audio.effectUndo":"Undo","audio.effectReset":"Reset","audio.backgroundVolume":"Background Volume","audio.backgroundVolumeAdjust":"Adjust background volume","audio.unsupported":"This browser does not support timeline audio playback","audio.fileFailed":"Failed to load the audio file","audio.preparing":"Preparing audio…","audio.playFailed":"Audio playback failed","audio.loading":"Loading tracks…",
    "library.heading":"Asset Library","library.search":"Search assets","library.categories":"Asset categories","library.all":"All","library.pagination":"Asset pages","library.page":"Page {page}","library.recommended":"Suggested Assets","library.closeRecommended":"Close AI suggestions","library.loading":"Loading assets…","library.empty":"No assets","library.noMatch":"No matching assets","library.invalid":"Invalid asset data format","library.failed":"Failed to load assets","library.drag":"Drag “{name}” onto the canvas","category.animal":"Animals","category.nature":"Nature","category.character":"Characters","category.vehicle":"Vehicles","category.furniture":"Furniture","category.building":"Buildings","category.emotion":"Emotions","category.action":"Actions","category.background":"Backgrounds","category.sound":"Sounds",
    "auth.close":"Close login dialog","auth.welcome":"Welcome Back","auth.create":"Create Account","auth.loginIntro":"Log in to continue creating your audiobook.","auth.registerIntro":"Create an account and start saving your work.","auth.actions":"Account actions","auth.login":"Log In","auth.register":"Register","auth.username":"Username","auth.password":"Password","auth.required":"Enter your username and password","auth.loggingIn":"Logging in…","auth.registering":"Registering…","auth.back":"← Back to Studio","auth.pageTitle":"Account · Audiobook","auth.description":"Log in or register an audiobook account",
    "unsaved.title":"Save the current canvas?","unsaved.message":"The current canvas has unsaved changes. Save before switching?","unsaved.cancel":"Cancel","unsaved.discard":"Don't Save","unsaved.save":"Save and Switch","unsaved.saving":"Saving…","request.failed":"Request failed. Please try again later","project.finding":"Looking for an existing project…","project.invalid":"Invalid project response","project.found":"Found project #{id}","project.notCreated":"Project not created yet","project.lookupFailed":"Project lookup failed","project.loading":"Loading canvas…","project.loaded":"Canvas loaded","project.loadFailed":"Failed to load canvas","project.notReady":"The current canvas is not ready","project.saving":"Saving…","project.createInvalid":"Invalid project creation response","project.createdChanged":"Created project #{id}; there are newer changes","project.created":"Created and saved project #{id}","project.createdLoading":"Created project #{id}; loading the current canvas…","project.saveInvalid":"Invalid canvas save response","project.stepSavedChanged":"Saved step {order}; there are newer changes","project.stepSaved":"Step {order} saved","project.saveFailed":"Save failed. Please try again later","project.changed":"Unsaved changes"
});

export function getLanguage() {
    const saved = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED_LANGUAGES.has(saved) ? saved : "zh";
}

export function t(key, values = {}) {
    const template = messages[getLanguage()]?.[key] ?? messages.zh[key] ?? key;
    return Object.entries(values).reduce(
        (text, [name, value]) => text.replaceAll("{" + name + "}", String(value)),
        template,
    );
}

export function applyTranslations(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    root.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
        element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
    root.querySelectorAll("[data-i18n-title]").forEach((element) => {
        element.setAttribute("title", t(element.dataset.i18nTitle));
    });
    root.querySelectorAll("[data-i18n-content]").forEach((element) => {
        element.setAttribute("content", t(element.dataset.i18nContent));
    });
    document.documentElement.lang = { zh: "zh-CN", ja: "ja", en: "en" }[getLanguage()];
    document.documentElement.style.setProperty("--canvas-drop-label", '"' + t("canvas.drop") + '"');
    document.title = t(document.body?.dataset.i18nTitle || "app.title");
}

export function setLanguage(language) {
    if (!SUPPORTED_LANGUAGES.has(language) || language === getLanguage()) return;
    localStorage.setItem(STORAGE_KEY, language);
    applyTranslations();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:language-change", {
        detail: { language },
    }));
}

function initializeLanguageSelector() {
    document.querySelectorAll("[data-language]").forEach((button) => {
        const isCurrent = button.dataset.language === getLanguage();
        button.classList.toggle("is-active", isCurrent);
        button.setAttribute("aria-pressed", String(isCurrent));
        button.addEventListener("click", () => setLanguage(button.dataset.language));
    });
    window.addEventListener("puzzle-audiobook:language-change", () => {
        document.querySelectorAll("[data-language]").forEach((button) => {
            const isCurrent = button.dataset.language === getLanguage();
            button.classList.toggle("is-active", isCurrent);
            button.setAttribute("aria-pressed", String(isCurrent));
        });
    });
}

applyTranslations();
initializeLanguageSelector();
