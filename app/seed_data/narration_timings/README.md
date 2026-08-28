# Narration timing data

The future offline alignment script should write one file per story and language:

```text
story_{story_id}_{language}.json
```

Example:

```json
{
  "story_id": 1,
  "language": "zh",
  "steps": [
    {
      "step_order": 1,
      "duration_seconds": 28.4,
      "cues": [
        {
          "text": "两只小牛",
          "start_seconds": 2.85,
          "end_seconds": 4.26
        }
      ]
    }
  ]
}
```

Free-creation steps and steps without narration may be omitted or use an empty `cues` list.
