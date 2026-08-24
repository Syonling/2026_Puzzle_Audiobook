# AI 请求体

```python
    # 后端整理后，传给llm
ai_input = 
{
"language": x_language
"question": "用户输入的AI问题"
"sentence": "对应语言的当前故事句子"
"canvas": {
  "objects": [
    {
      "asset_key": "cow",
      "x": 430,
      "y": 405,
      "scale": 1.55,
      "rotation": 0
      "flip_x": true
    }
  ],
  "background_id": "farm"
}
}
```

```python
# 建议输出
{
    'icon_keys': ['tree'], 

    'background_key': 'farm_background', 

    'reasoning': '建议增加 tree，作为中景主体，让小鸟有明确的栖息位置，并表现树洞的场景关系。现有 bird 可放在树冠附近，树干和树洞位于其下方、略偏前景。建议使用 farm_background 补充户外环境，作为远景背景。句子中的大雨和树洞没有对应的可用图标，因此暂不增加其他图标。音频顺序可先播放 bird 的鸣叫，再表现鸟儿躲进树洞的动作；当前没有可用的雨声图标。'
}

# 画布输出

{
    'objects': 
    [
        {'asset_key': 'tree', 
        'x': 175.0, 
        'y': 455.0, 
        'scale': 2.2, 
        'rotation': 0.0, 
        'start_offset_seconds': None
        }, 
        ……
    ], 
    'background_key': 'farm_background', #需要补充audio_url

    'reasoning': '使用 farm_background 作为朦胧灰天空与乡野环境的整体背景。左侧较大的树位于前景，右侧较小的树退后形成中景和空间纵深。小鸟置于画面上方偏中间，远离树冠，突出清亮歌声在天空与微风中飘荡的感觉。画面没有可用的雨滴图标，因此借助灰色背景氛围暗示细雨降临。可播放的小鸟声音从0秒开始。'
}

```


```python
    # 前端传入
    {
    "user_request": "用户输入的AI问题",
    "story_id": 1,
    "step_order": 1,
    "canvas": {
        "objects": [],
        "background_id": null
    }
    }

    # Canve 字典
    {
    "objects": [
        {
        "instance_id": "73f54b4d-...",
        "asset_id": 3,
        "object_id": "bird",
        "asset_key": "bird",
        "label": "小鸟",
        "image_url": "/static/images/bird.png",
        "audio_url": "/static/audio/bird.mp3",
        "x": 285,
        "y": 145,
        "scale": 0.65,
        "rotation": 0
        }
    ],
    "background_id": "farm"
    }
```


