# OpenRouter Models Table

Total models: 458

| Provider | Model ID | Name | Context | Modality | Input | Output | Input $/M | Output $/M | Intel | Coding | Agentic | Reasoning | Created |
|----------|----------|------|---------|----------|------|-------|-----------|------------|-------|--------|---------|-----------|---------|
| aion-labs | aion-labs/aion-3.5 | AionLabs: Aion 3.5 | 262,144 | text->text | text | text | $3.0000 | $6.0000 | - | - | - | Mandatory | 2026-09-23 |
| aion-labs | aion-labs/aion-3.5-mini | AionLabs: Aion 3.5 Mini | 262,144 | text->text | text | text | $0.7000 | $1.4000 | - | - | - | Mandatory | 2026-09-23 |
| aion-labs | aion-labs/aion-2.0 | AionLabs: Aion-2.0 | 131,072 | text->text | text | text | $0.8000 | $1.6000 | - | - | - | Mandatory | 2026-02-24 |
| aion-labs | aion-labs/aion-3.0 | AionLabs: Aion-3.0 | 131,072 | text->text | text | text | $3.0000 | $6.0000 | - | - | - | Mandatory | 2026-07-08 |
| aion-labs | aion-labs/aion-3.0-mini | AionLabs: Aion-3.0-Mini | 131,072 | text->text | text | text | $0.7000 | $1.4000 | - | - | - | Mandatory | 2026-07-08 |
| aion-labs | aion-labs/aion-rp-llama-3.1-8b | AionLabs: Aion-RP 1.0 (8B) | 32,768 | text->text | text | text | $0.8000 | $1.6000 | - | - | - | Optional | 2025-02-05 |
| amazon | amazon/nova-2-lite-v1 | Amazon: Nova 2 Lite | 1,000,000 | text+image+file+video->text | text,image,video,file | text | $0.3000 | $2.5000 | 13.4 | 23 | - | Optional | 2025-12-03 |
| amazon | amazon/nova-lite-v1 | Amazon: Nova Lite 1.0 | 300,000 | text+image->text | text,image | text | $0.0600 | $0.2400 | 6.7 | - | - | Optional | 2024-12-06 |
| amazon | amazon/nova-micro-v1 | Amazon: Nova Micro 1.0 | 128,000 | text->text | text | text | $0.0350 | $0.1400 | 5.9 | - | - | Optional | 2024-12-06 |
| amazon | amazon/nova-premier-v1 | Amazon: Nova Premier 1.0 | 1,000,000 | text+image->text | text,image | text | $2.5000 | $12.5000 | 9.2 | - | - | Optional | 2025-11-01 |
| amazon | amazon/nova-pro-v1 | Amazon: Nova Pro 1.0 | 300,000 | text+image->text | text,image | text | $0.8000 | $3.2000 | 7 | - | - | Optional | 2024-12-06 |
| anthracite-org | anthracite-org/magnum-v4-72b | Magnum v4 72B | 32,768 | text->text | text | text | $2.5000 | $5.0000 | - | - | - | Optional | 2024-10-22 |
| anthropic | anthropic/claude-fable-5 | Anthropic: Claude Fable 5 | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | 49.6 | 76.5 | 50.7 | Mandatory | 2026-06-09 |
| anthropic | anthropic/claude-fable-5:batch | Anthropic: Claude Fable 5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 49.6 | 76.5 | 50.7 | Mandatory | 2026-06-09 |
| anthropic | anthropic/claude-fable-5.1 | Anthropic: Claude Fable 5.1 | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | 53.4 | 81.6 | 57.9 | Mandatory | 2026-09-02 |
| anthropic | anthropic/claude-fable-5.1:batch | Anthropic: Claude Fable 5.1 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 53.4 | 81.6 | 57.9 | Mandatory | 2026-09-02 |
| anthropic | anthropic/claude-haiku-4.5 | Anthropic: Claude Haiku 4.5 | 200,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | 16.9 | 43.9 | 8 | Optional | 2025-10-16 |
| anthropic | anthropic/claude-haiku-4.5:batch | Anthropic: Claude Haiku 4.5 (batch) | 200,000 | text+image+file->text | text,image,file | text | $0.5000 | $2.5000 | 16.9 | 43.9 | 8 | Optional | 2025-10-16 |
| anthropic | anthropic/claude-haiku-5.5 | Anthropic: Claude Haiku 5.5 | 1,000,000 | text+image+file->text | text,image,file | text | $0.1000 | $0.5000 | 43.4 | - | - | Optional | 2026-10-08 |
| anthropic | anthropic/claude-haiku-5.5:batch | Anthropic: Claude Haiku 5.5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $0.0500 | $0.2500 | 43.4 | - | - | Optional | 2026-10-08 |
| anthropic | anthropic/claude-opus-4.1 | Anthropic: Claude Opus 4.1 | 200,000 | text+image+file->text | image,text,file | text | $15.0000 | $75.0000 | 22.8 | - | - | Optional | 2025-08-06 |
| anthropic | anthropic/claude-opus-4.1:batch | Anthropic: Claude Opus 4.1 (batch) | 200,000 | text+image+file->text | image,text,file | text | $7.5000 | $37.5000 | 22.8 | - | - | Optional | 2025-08-06 |
| anthropic | anthropic/claude-opus-4.5 | Anthropic: Claude Opus 4.5 | 200,000 | text+image+file->text | file,image,text | text | $5.0000 | $25.0000 | 29.1 | - | - | Optional | 2025-11-25 |
| anthropic | anthropic/claude-opus-4.5:batch | Anthropic: Claude Opus 4.5 (batch) | 200,000 | text+image+file->text | file,image,text | text | $2.5000 | $12.5000 | 29.1 | - | - | Optional | 2025-11-25 |
| anthropic | anthropic/claude-opus-4.6 | Anthropic: Claude Opus 4.6 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 31.9 | - | - | Optional | 2026-02-04 |
| anthropic | anthropic/claude-opus-4.6:batch | Anthropic: Claude Opus 4.6 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 31.9 | - | - | Optional | 2026-02-04 |
| anthropic | anthropic/claude-opus-4.7 | Anthropic: Claude Opus 4.7 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 40.7 | 73.6 | 38.6 | Optional | 2026-04-16 |
| anthropic | anthropic/claude-opus-4.7:batch | Anthropic: Claude Opus 4.7 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 40.7 | 73.6 | 38.6 | Optional | 2026-04-16 |
| anthropic | anthropic/claude-opus-4.8 | Anthropic: Claude Opus 4.8 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 41.8 | 74.3 | 41.9 | Optional | 2026-05-28 |
| anthropic | anthropic/claude-opus-4.8:batch | Anthropic: Claude Opus 4.8 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 41.8 | 74.3 | 41.9 | Optional | 2026-05-28 |
| anthropic | anthropic/claude-opus-5 | Anthropic: Claude Opus 5 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 50.8 | 78 | 56.5 | Default | 2026-07-25 |
| anthropic | anthropic/claude-opus-5:batch | Anthropic: Claude Opus 5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 50.8 | 78 | 56.5 | Default | 2026-07-25 |
| anthropic | anthropic/claude-opus-5.5 | Anthropic: Claude Opus 5.5 | 1,000,000 | text+image+file->text | text,image,file | text | $4.0000 | $20.0000 | 57.6 | - | - | Mandatory | 2026-09-23 |
| anthropic | anthropic/claude-opus-5.5:batch | Anthropic: Claude Opus 5.5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | 57.6 | - | - | Mandatory | 2026-09-23 |
| anthropic | anthropic/claude-sonnet-4 | Anthropic: Claude Sonnet 4 | 200,000 | text+image+file->text | image,text,file | text | $3.0000 | $15.0000 | 18.9 | 37.6 | - | Optional | 2025-05-23 |
| anthropic | anthropic/claude-sonnet-4.5 | Anthropic: Claude Sonnet 4.5 | 1,000,000 | text+image+file->text | text,image,file | text | $3.0000 | $15.0000 | 20.7 | 52.1 | 15.8 | Optional | 2025-09-30 |
| anthropic | anthropic/claude-sonnet-4.5:batch | Anthropic: Claude Sonnet 4.5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.5000 | $7.5000 | 20.7 | 52.1 | 15.8 | Optional | 2025-09-30 |
| anthropic | anthropic/claude-sonnet-4.6 | Anthropic: Claude Sonnet 4.6 | 1,000,000 | text+image+file->text | text,image,file | text | $3.0000 | $15.0000 | 30.1 | 63 | 31.8 | Optional | 2026-02-17 |
| anthropic | anthropic/claude-sonnet-4.6:batch | Anthropic: Claude Sonnet 4.6 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.5000 | $7.5000 | 30.1 | 63 | 31.8 | Optional | 2026-02-17 |
| anthropic | anthropic/claude-sonnet-5 | Anthropic: Claude Sonnet 5 | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | 38.2 | 71.5 | 43.6 | Default | 2026-07-01 |
| anthropic | anthropic/claude-sonnet-5:batch | Anthropic: Claude Sonnet 5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | 38.2 | 71.5 | 43.6 | Default | 2026-07-01 |
| anthropic | anthropic/claude-sonnet-5.5 | Anthropic: Claude Sonnet 5.5 | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | 56 | - | - | Mandatory | 2026-09-29 |
| anthropic | anthropic/claude-sonnet-5.5:batch | Anthropic: Claude Sonnet 5.5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | 56 | - | - | Mandatory | 2026-09-29 |
| apodex | apodex/apodex-1.1-mini:free | Apodex: Apodex 1.1 Mini (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Optional | 2026-10-02 |
| arcee-ai | arcee-ai/trinity-large-thinking | Arcee AI: Trinity Large Thinking | 262,144 | text->text | text | text | $0.2500 | $0.8000 | 10.8 | 25.8 | 1 | Mandatory | 2026-04-01 |
| bytedance | bytedance/ui-tars-1.5-7b | ByteDance: UI-TARS 7B  | 128,000 | text+image->text | image,text | text | $0.1000 | $0.2000 | - | - | - | Optional | 2025-07-23 |
| bytedance-seed | bytedance-seed/seed-1.6 | ByteDance Seed: Seed 1.6 | 262,144 | text+image+video->text | image,text,video | text | $0.2500 | $2.0000 | - | - | - | Optional | 2025-12-23 |
| bytedance-seed | bytedance-seed/seed-1.6-flash | ByteDance Seed: Seed 1.6 Flash | 262,144 | text+image+video->text | image,text,video | text | $0.0750 | $0.3000 | - | - | - | Optional | 2025-12-23 |
| bytedance-seed | bytedance-seed/seed-2-1-turbo | ByteDance Seed: Seed 2.1 Turbo | 262,144 | text+image+video->text | text,image,video | text | $0.5000 | $2.5000 | - | - | - | Optional | 2026-08-13 |
| bytedance-seed | bytedance-seed/seed-2.0-code | ByteDance Seed: Seed-2.0-Code | 262,144 | text+image+video->text | text,image,video | text | $0.5000 | $3.0000 | - | - | - | Optional | 2026-08-13 |
| bytedance-seed | bytedance-seed/seed-2.0-lite | ByteDance Seed: Seed-2.0-Lite | 262,144 | text+image+video->text | text,image,video | text | $0.2500 | $2.0000 | - | - | - | Optional | 2026-03-10 |
| bytedance-seed | bytedance-seed/seed-2.0-mini | ByteDance Seed: Seed-2.0-Mini | 262,144 | text+image+video->text | text,image,video | text | $0.1000 | $0.4000 | - | - | - | Optional | 2026-02-27 |
| cognitivecomputations | cognitivecomputations/dolphin-mistral-24b-venice-edition | Venice: Uncensored | 128,000 | text->text | text | text | $0.2000 | $0.9000 | - | - | - | Optional | 2025-07-10 |
| cohere | cohere/command-a | Cohere: Command A | 256,000 | text->text | text | text | $2.5000 | $10.0000 | 13.1 | 27.8 | 1 | Optional | 2025-03-14 |
| cohere | cohere/command-a-plus | Cohere: Command A+ | 192,000 | text+image->text | text,image | text | $0.3000 | $1.5000 | - | - | - | Optional | 2026-09-23 |
| cohere | cohere/command-r-08-2024 | Cohere: Command R (08-2024) | 128,000 | text->text | text | text | $0.1500 | $0.6000 | - | - | - | Optional | 2024-08-30 |
| cohere | cohere/command-r-plus-08-2024 | Cohere: Command R+ (08-2024) | 128,000 | text->text | text | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-08-30 |
| cohere | cohere/command-r7b-12-2024 | Cohere: Command R7B (12-2024) | 128,000 | text->text | text | text | $0.0375 | $0.1500 | - | - | - | Optional | 2024-12-14 |
| cohere | cohere/north-mini-code:free | Cohere: North Mini Code (free) | 256,000 | text->text | text | text | $0.0000 | $0.0000 | 9.9 | 36.5 | 1.1 | Optional | 2026-06-18 |
| deepseek | deepseek/deepseek-chat | DeepSeek: DeepSeek V3 | 163,840 | text->text | text | text | $0.3200 | $0.8900 | - | - | - | Optional | 2024-12-27 |
| deepseek | deepseek/deepseek-chat-v3-0324 | DeepSeek: DeepSeek V3 0324 | 163,840 | text->text | text | text | $0.2900 | $1.1400 | 9.7 | 21.2 | 0.8 | Optional | 2025-03-24 |
| deepseek | deepseek/deepseek-chat-v3.1 | DeepSeek: DeepSeek V3.1 | 163,840 | text->text | text | text | $0.2500 | $0.9500 | 13.7 | - | - | Optional | 2025-08-21 |
| deepseek | deepseek/deepseek-v3.1-terminus | DeepSeek: DeepSeek V3.1 Terminus | 163,840 | text->text | text | text | $0.2700 | $1.0000 | 14.8 | 43.5 | 6.8 | Optional | 2025-09-22 |
| deepseek | deepseek/deepseek-v3.2 | DeepSeek: DeepSeek V3.2 | 163,840 | text->text | text | text | $0.2590 | $0.8000 | 21.5 | 44.2 | - | Optional | 2025-12-01 |
| deepseek | deepseek/deepseek-v3.2-exp | DeepSeek: DeepSeek V3.2 Exp | 163,840 | text->text | text | text | $0.2700 | $0.4100 | 16.6 | - | - | Optional | 2025-09-29 |
| deepseek | deepseek/deepseek-v4-flash | DeepSeek: DeepSeek V4 Flash 0423 | 1,048,576 | text->text | text | text | $0.0300 | $1.2800 | 24.4 | 52 | 26.3 | Optional | 2026-04-24 |
| deepseek | deepseek/deepseek-v4-flash-0731 | DeepSeek: DeepSeek V4 Flash 0731 | 1,048,576 | text->text | text | text | $0.0168 | $1.2800 | 34.3 | 69.1 | 41 | Default | 2026-07-31 |
| deepseek | deepseek/deepseek-v4-flash-vision-exp | DeepSeek: DeepSeek V4 Flash Vision Exp | 1,048,576 | text+image->text | text,image | text | $0.2156 | $0.6468 | 34.8 | 65 | 47.5 | Default | 2026-08-21 |
| deepseek | deepseek/deepseek-v4-pro | DeepSeek: DeepSeek V4 Pro 0423 | 1,048,576 | text->text | text | text | $0.2088 | $0.4176 | 30.4 | 59.4 | 26.3 | Optional | 2026-04-24 |
| deepseek | deepseek/deepseek-v4-pro-0813 | DeepSeek: DeepSeek V4 Pro 0813 | 1,048,576 | text->text | text | text | $0.6600 | $1.9800 | 36 | 68.8 | 41.3 | Optional | 2026-08-12 |
| deepseek | deepseek/deepseek-v4.1-flash | DeepSeek: DeepSeek V4.1 Flash | 1,048,576 | text+image->text | text,image | text | $0.3000 | $1.2000 | 39.5 | - | - | Default | 2026-09-10 |
| deepseek | deepseek/deepseek-v4.1-flash:batch | DeepSeek: DeepSeek V4.1 Flash (batch) | 1,048,576 | text+image->text | text,image | text | $0.1120 | $0.3360 | 39.5 | - | - | Default | 2026-09-10 |
| deepseek | deepseek/deepseek-r1 | DeepSeek: R1 | 64,000 | text->text | text | text | $0.7000 | $2.5000 | 11.4 | 24.6 | 1.1 | Mandatory | 2025-01-20 |
| deepseek | deepseek/deepseek-r1-0528 | DeepSeek: R1 0528 | 163,840 | text->text | text | text | $0.5000 | $2.1500 | 13.1 | - | - | Mandatory | 2025-05-29 |
| dots-studio | dots-studio/dots-3-note-preview:free | Dots Studio: Dots3-Note Preview (free) | 512,000 | text+image->text | text,image | text | $0.0000 | $0.0000 | - | - | - | Optional | 2026-08-14 |
| fireworks | fireworks/ember-1 | Fireworks: Ember-1 | 1,048,576 | text+image->text | text,image | text | $3.0000 | $15.0000 | - | - | - | Default | 2026-09-24 |
| google | google/gemini-2.5-flash | Google: Gemini 2.5 Flash | 1,048,576 | text+image+file+audio+video->text | file,image,text,audio,video | text | $0.3000 | $2.5000 | 15.5 | - | - | Optional | 2025-06-17 |
| google | google/gemini-2.5-flash:batch | Google: Gemini 2.5 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | file,image,text,audio,video | text | $0.1500 | $1.2500 | 15.5 | - | - | Optional | 2025-06-17 |
| google | google/gemini-2.5-flash-lite | Google: Gemini 2.5 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.1000 | $0.4000 | 10.4 | - | - | Optional | 2025-07-23 |
| google | google/gemini-2.5-flash-lite:batch | Google: Gemini 2.5 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.0500 | $0.2000 | 10.4 | - | - | Optional | 2025-07-23 |
| google | google/gemini-2.5-pro | Google: Gemini 2.5 Pro | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $1.2500 | $10.0000 | 16.1 | 33.3 | 1.6 | Mandatory | 2025-06-17 |
| google | google/gemini-2.5-pro:batch | Google: Gemini 2.5 Pro (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.6250 | $5.0000 | 16.1 | 33.3 | 1.6 | Mandatory | 2025-06-17 |
| google | google/gemini-2.5-pro-preview | Google: Gemini 2.5 Pro Preview 06-05 | 1,048,576 | text+image+file+audio->text | file,image,text,audio | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-06-05 |
| google | google/gemini-3-flash-preview | Google: Gemini 3 Flash Preview | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.5000 | $3.0000 | 26.3 | - | - | Optional | 2025-12-17 |
| google | google/gemini-3-flash-preview:batch | Google: Gemini 3 Flash Preview (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.2500 | $1.5000 | 26.3 | - | - | Optional | 2025-12-17 |
| google | google/gemini-3.1-flash-lite | Google: Gemini 3.1 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.2500 | $1.5000 | - | - | - | Default | 2026-05-07 |
| google | google/gemini-3.1-flash-lite:batch | Google: Gemini 3.1 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.1250 | $0.7500 | - | - | - | Default | 2026-05-07 |
| google | google/gemini-3.1-flash-lite-preview | Google: Gemini 3.1 Flash Lite Preview | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.2500 | $1.5000 | 15.6 | 34.7 | 1.6 | Default | 2026-03-03 |
| google | google/gemini-3.1-pro-preview | Google: Gemini 3.1 Pro Preview | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $2.0000 | $12.0000 | 29.7 | 68.8 | 8.2 | Mandatory | 2026-02-19 |
| google | google/gemini-3.1-pro-preview:batch | Google: Gemini 3.1 Pro Preview (batch) | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $1.0000 | $6.0000 | 29.7 | 68.8 | 8.2 | Mandatory | 2026-02-19 |
| google | google/gemini-3.1-pro-preview-customtools | Google: Gemini 3.1 Pro Preview Custom Tools | 1,048,576 | text+image+file+audio+video->text | text,audio,image,video,file | text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-02-26 |
| google | google/gemini-3.5-flash | Google: Gemini 3.5 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $1.5000 | $9.0000 | 33.6 | - | - | Mandatory | 2026-05-19 |
| google | google/gemini-3.5-flash:batch | Google: Gemini 3.5 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $4.5000 | 33.6 | - | - | Mandatory | 2026-05-19 |
| google | google/gemini-3.5-flash-lite | Google: Gemini 3.5 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.3000 | $2.5000 | 22.2 | 49.3 | 14.3 | Mandatory | 2026-07-21 |
| google | google/gemini-3.5-flash-lite:batch | Google: Gemini 3.5 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.1500 | $1.2500 | 22.2 | 49.3 | 14.3 | Mandatory | 2026-07-21 |
| google | google/gemini-3.6-flash | Google: Gemini 3.6 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $3.7500 | 34 | 69.2 | 29 | Mandatory | 2026-07-21 |
| google | google/gemini-3.6-flash:batch | Google: Gemini 3.6 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.3750 | $1.8750 | 34 | 69.2 | 29 | Mandatory | 2026-07-21 |
| google | google/gemini-3.7-flash | Google: Gemini 3.7 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $3.7500 | 39.6 | 71.5 | - | Mandatory | 2026-08-14 |
| google | google/gemini-3.7-flash:batch | Google: Gemini 3.7 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.3750 | $1.8750 | 39.6 | 71.5 | - | Mandatory | 2026-08-14 |
| google | google/gemini-3.8-flash | Google: Gemini 3.8 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $3.7500 | 40.9 | 76.3 | 40.2 | Mandatory | 2026-09-02 |
| google | google/gemini-3.8-flash:batch | Google: Gemini 3.8 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.3750 | $1.8750 | 40.9 | 76.3 | 40.2 | Mandatory | 2026-09-02 |
| google | google/gemma-2-27b-it | Google: Gemma 2 27B | 8,192 | text->text | text | text | $0.6500 | $0.6500 | - | - | - | Optional | 2024-07-13 |
| google | google/gemma-3-12b-it | Google: Gemma 3 12B | 131,072 | text+image->text | text,image | text | $0.0500 | $0.1500 | 3.8 | 5.8 | 0.1 | Optional | 2025-03-14 |
| google | google/gemma-3-27b-it | Google: Gemma 3 27B | 131,072 | text+image->text | text,image | text | $0.0800 | $0.4500 | 4.9 | 10.1 | 0.1 | Optional | 2025-03-12 |
| google | google/gemma-3-4b-it | Google: Gemma 3 4B | 131,072 | text+image->text | text,image | text | $0.0500 | $0.1000 | 4.8 | 2.7 | - | Optional | 2025-03-14 |
| google | google/gemma-4-26b-a4b-it | Google: Gemma 4 26B A4B  | 262,144 | text+image+video->text | image,text,video | text | $0.0675 | $0.2250 | 16.7 | 39.3 | 2.9 | Optional | 2026-04-03 |
| google | google/gemma-4-26b-a4b-it:free | Google: Gemma 4 26B A4B  (free) | 262,144 | text+image+video->text | image,text,video | text | $0.0000 | $0.0000 | 16.7 | 39.3 | 2.9 | Optional | 2026-04-03 |
| google | google/gemma-4-31b-it | Google: Gemma 4 31B | 262,144 | text+image+video->text | image,text,video | text | $0.0900 | $0.3400 | 14.7 | 43.4 | 4.2 | Optional | 2026-04-03 |
| google | google/gemma-4-31b-it:free | Google: Gemma 4 31B (free) | 262,144 | text+image+video->text | image,text,video | text | $0.0000 | $0.0000 | 14.7 | 43.4 | 4.2 | Optional | 2026-04-03 |
| google | google/lyria-3-clip-preview | Google: Lyria 3 Clip Preview | 1,048,576 | text+image->text+audio | text,image | text,audio | $0.0000 | $0.0000 | - | - | - | Optional | 2026-03-31 |
| google | google/lyria-3-pro-preview | Google: Lyria 3 Pro Preview | 1,048,576 | text+image->text+audio | text,image | text,audio | $0.0000 | $0.0000 | - | - | - | Optional | 2026-03-31 |
| google | google/gemini-2.5-flash-image | Google: Nano Banana (Gemini 2.5 Flash Image) | 32,768 | text+image->text+image | image,text | image,text | $0.3000 | $2.5000 | - | - | - | Optional | 2025-10-08 |
| google | google/gemini-3.1-flash-image-preview | Google: Nano Banana 2 (Gemini 3.1 Flash Image Preview) | 65,536 | text+image->text+image | image,text | image,text | $0.5000 | $3.0000 | - | - | - | Default | 2026-02-26 |
| google | google/gemini-3.1-flash-image | Google: Nano Banana 2 (Gemini 3.1 Flash Image) | 131,072 | text+image->text+image | image,text | image,text | $0.5000 | $3.0000 | - | - | - | Default | 2026-06-18 |
| google | google/gemini-3.1-flash-lite-image | Google: Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image) | 65,536 | text+image->text+image | image,text | image,text | $0.2500 | $1.5000 | - | - | - | Default | 2026-07-01 |
| google | google/gemini-nano-banana-2.1 | Google: Nano Banana 2.1 | 65,536 | text+image->text+image | image,text | image,text | $1.5000 | $7.5000 | - | - | - | Default | 2026-10-06 |
| google | google/gemini-3-pro-image-preview | Google: Nano Banana Pro (Gemini 3 Pro Image Preview) | 65,536 | text+image->text+image | image,text | image,text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2025-11-20 |
| google | google/gemini-3-pro-image | Google: Nano Banana Pro (Gemini 3 Pro Image) | 131,072 | text+image->text+image | image,text | image,text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-06-18 |
| gryphe | gryphe/mythomax-l2-13b | MythoMax 13B | 8,192 | text->text | text | text | $0.0800 | $0.1100 | - | - | - | Optional | 2023-07-02 |
| ibm-granite | ibm-granite/granite-4.0-h-micro | IBM: Granite 4.0 Micro | 131,000 | text->text | text | text | $0.0170 | $0.1120 | 5.1 | - | - | Optional | 2025-10-20 |
| ibm-granite | ibm-granite/granite-4.2-8b | IBM: Granite 4.2 8B | 131,072 | text->text | text | text | $0.0600 | $0.2500 | 11.1 | 22.4 | 1.3 | Default | 2026-09-01 |
| inception | inception/mercury-2 | Inception: Mercury 2 | 128,000 | text->text | text | text | $0.2500 | $0.7500 | 13.8 | 31.1 | 1.6 | Default | 2026-03-04 |
| inception | inception/mercury-2.5 | Inception: Mercury 2.5 | 260,000 | text->text | text | text | $0.0400 | $0.1500 | 12.3 | - | - | Default | 2026-09-09 |
| inclusionai | inclusionai/ling-3.0-flash | inclusionAI: Ling 3.0 Flash | 262,144 | text->text | text | text | $0.0210 | $0.0630 | 20.1 | 50.6 | 19.3 | Default | 2026-07-23 |
| inclusionai | inclusionai/ling-3.0-flash-fin | inclusionAI: Ling 3.0 Flash Fin | 262,144 | text->text | text | text | $0.0420 | $0.1232 | 22.6 | 55.6 | 27.9 | Default | 2026-08-27 |
| inclusionai | inclusionai/ling-3.0-flash-sante | inclusionAI: Ling 3.0 Flash Sante | 262,144 | text->text | text | text | $0.0420 | $0.1232 | - | - | - | Default | 2026-09-05 |
| inclusionai | inclusionai/ling-3.0-flash-vl | inclusionAI: Ling 3.0 Flash VL | 262,144 | text+image+video->text | text,image,video | text | $0.0210 | $0.0616 | 24.6 | 57 | 28.7 | Default | 2026-09-11 |
| inclusionai | inclusionai/ling-3.1-flash | inclusionAI: Ling 3.1 Flash | 262,144 | text->text | text | text | $0.0000 | $0.0000 | 41.1 | - | - | Default | 2026-10-02 |
| inference-net | inference-net/schematron-v2-small | Inference.net: Schematron V2 Small | 128,000 | text->text | text | text | $0.0500 | $0.2300 | - | - | - | Optional | 2026-09-12 |
| inference-net | inference-net/schematron-v2-turbo | Inference.net: Schematron V2 Turbo | 128,000 | text->text | text | text | $0.0300 | $0.1500 | - | - | - | Optional | 2026-09-12 |
| liquid | liquid/lfm-2.5-2.6b:free | LiquidAI: LFM2.5-2.6B (free) | 65,536 | text->text | text | text | $0.0000 | $0.0000 | 8.4 | 7.7 | - | Mandatory | 2026-08-12 |
| mancer | mancer/weaver | Mancer: Weaver (alpha) | 8,000 | text->text | text | text | $0.4000 | $0.7500 | - | - | - | Optional | 2023-08-02 |
| meituan | meituan/longcat-2.0 | Meituan: LongCat 2.0 | 1,048,756 | text->text | text | text | $0.3000 | $1.2000 | 19.1 | 45.3 | 14 | Default | 2026-07-20 |
| meta | meta/muse-glimmer-30b | Meta: Muse Glimmer 30B | 131,072 | text+image->text | text,image | text | $0.3000 | $1.2000 | 17.5 | 49 | 8.5 | Mandatory | 2026-08-10 |
| meta | meta/muse-spark-1.1 | Meta: Muse Spark 1.1 | 1,048,576 | text+image+file+video->text | text,image,video,file | text | $1.2500 | $4.2500 | 33.7 | 71.3 | 25.8 | Mandatory | 2026-07-16 |
| meta | meta/muse-spark-1.2 | Meta: Muse Spark 1.2 | 1,048,576 | text+image+file+video->text | text,image,video,file | text | $1.2500 | $4.2500 | 39.6 | 72.2 | 43.2 | Mandatory | 2026-08-06 |
| meta | meta/muse-spark-1.2-contributor | Meta: Muse Spark 1.2 Contributor | 1,048,576 | text+image+file+video->text | text,image,video,file | text | $0.1000 | $0.2000 | - | - | - | Mandatory | 2026-08-22 |
| meta | meta/muse-spark-1.3 | Meta: Muse Spark 1.3 | 1,048,576 | text+image+file+video->text | text,image,video,file | text | $1.2500 | $4.2500 | 48.1 | 75.8 | 55.5 | Mandatory | 2026-09-03 |
| meta | meta/muse-spark-1.3-contributor | Meta: Muse Spark 1.3 Contributor | 1,048,576 | text+image+file+video->text | text,image,video,file | text | $0.1000 | $0.2000 | - | - | - | Mandatory | 2026-09-03 |
| meta-llama | meta-llama/llama-3.1-70b-instruct | Meta: Llama 3.1 70B Instruct | 131,072 | text->text | text | text | $0.4000 | $0.4000 | 6.6 | - | - | Optional | 2024-07-23 |
| meta-llama | meta-llama/llama-3.1-8b-instruct | Meta: Llama 3.1 8B Instruct | 131,072 | text->text | text | text | $0.0500 | $0.0800 | 6.9 | 5.4 | - | Optional | 2024-07-23 |
| meta-llama | meta-llama/llama-3.2-1b-instruct | Meta: Llama 3.2 1B Instruct | 60,000 | text->text | text | text | $0.0270 | $0.2010 | 4.8 | - | - | Optional | 2024-09-25 |
| meta-llama | meta-llama/llama-3.2-3b-instruct | Meta: Llama 3.2 3B Instruct | 131,072 | text->text | text | text | $0.0500 | $0.3300 | 5.7 | - | - | Optional | 2024-09-25 |
| meta-llama | meta-llama/llama-3.3-70b-instruct | Meta: Llama 3.3 70B Instruct | 131,072 | text->text | text | text | $0.2200 | $0.5000 | 7.7 | 11.9 | - | Optional | 2024-12-07 |
| meta-llama | meta-llama/llama-4-maverick | Meta: Llama 4 Maverick | 1,048,576 | text+image->text | text,image | text | $0.1875 | $0.6525 | 10 | 16.3 | 0.6 | Optional | 2025-04-06 |
| meta-llama | meta-llama/llama-4-scout | Meta: Llama 4 Scout | 1,310,720 | text+image->text | text,image | text | $0.1000 | $0.3000 | 8.1 | 8.2 | 0.5 | Optional | 2025-04-06 |
| meta-llama | meta-llama/llama-guard-4-12b | Meta: Llama Guard 4 12B | 163,840 | text+image->text | image,text | text | $0.1800 | $0.1800 | - | - | - | Optional | 2025-04-30 |
| microsoft | microsoft/phi-4 | Microsoft: Phi 4 | 16,384 | text->text | text | text | $0.0700 | $0.1400 | 5.9 | - | - | Optional | 2025-01-10 |
| microsoft | microsoft/wizardlm-2-8x22b | WizardLM-2 8x22B | 65,535 | text->text | text | text | $0.6200 | $0.6200 | - | - | - | Optional | 2024-04-16 |
| minimax | minimax/minimax-m1 | MiniMax: MiniMax M1 | 1,000,000 | text->text | text | text | $0.5500 | $2.2000 | 11.7 | - | - | Optional | 2025-06-18 |
| minimax | minimax/minimax-m2 | MiniMax: MiniMax M2 | 204,800 | text->text | text | text | $0.3000 | $1.2000 | 18.6 | - | - | Mandatory | 2025-10-24 |
| minimax | minimax/minimax-m2-her | MiniMax: MiniMax M2-her | 65,536 | text->text | text | text | $0.3000 | $1.2000 | - | - | - | Optional | 2026-01-23 |
| minimax | minimax/minimax-m2.1 | MiniMax: MiniMax M2.1 | 204,800 | text->text | text | text | $0.3000 | $1.2000 | 20.9 | - | - | Mandatory | 2025-12-23 |
| minimax | minimax/minimax-m2.5 | MiniMax: MiniMax M2.5 | 204,800 | text->text | text | text | $0.2700 | $1.0800 | 22.8 | - | - | Mandatory | 2026-02-12 |
| minimax | minimax/minimax-m2.7 | MiniMax: MiniMax M2.7 | 204,800 | text->text | text | text | $0.2100 | $0.8400 | 22.8 | 52.6 | 15.3 | Mandatory | 2026-03-18 |
| minimax | minimax/minimax-m3 | MiniMax: MiniMax M3 | 1,048,576 | text+image+video->text | text,image,video | text | $0.3000 | $1.2000 | 29.2 | 58.6 | 29.5 | Optional | 2026-06-01 |
| minimax | minimax/minimax-01 | MiniMax: MiniMax-01 | 1,000,192 | text+image->text | text,image | text | $0.2000 | $1.1000 | - | - | - | Optional | 2025-01-15 |
| mistralai | mistralai/mistral-large | Mistral Large | 128,000 | text+file->text | text,file | text | $2.0000 | $6.0000 | 5.8 | - | - | Optional | 2024-02-26 |
| mistralai | mistralai/mistral-large-2407 | Mistral Large 2407 | 131,072 | text+file->text | text,file | text | $2.0000 | $6.0000 | 7.6 | - | - | Optional | 2024-11-19 |
| mistralai | mistralai/codestral-2508 | Mistral: Codestral 2508 | 256,000 | text+file->text | text,file | text | $0.3000 | $0.9000 | - | - | - | Optional | 2025-08-02 |
| mistralai | mistralai/codestral-2508:batch | Mistral: Codestral 2508 (batch) | 256,000 | text+file->text | text,file | text | $0.1500 | $0.4500 | - | - | - | Optional | 2025-08-02 |
| mistralai | mistralai/devstral-2512 | Mistral: Devstral 2 2512 | 262,144 | text+file->text | text,file | text | $0.4000 | $2.0000 | 8.6 | 31.3 | 2.3 | Optional | 2025-12-09 |
| mistralai | mistralai/ministral-14b-2512 | Mistral: Ministral 3 14B 2512 | 262,144 | text+image->text | text,image | text | $0.2000 | $0.2000 | 6 | 14.4 | 1.1 | Optional | 2025-12-02 |
| mistralai | mistralai/ministral-3b-2512 | Mistral: Ministral 3 3B 2512 | 131,072 | text+image->text | text,image | text | $0.1000 | $0.1000 | 4.8 | 4.8 | 0.8 | Optional | 2025-12-02 |
| mistralai | mistralai/ministral-8b-2512 | Mistral: Ministral 3 8B 2512 | 262,144 | text+image->text | text,image | text | $0.1500 | $0.1500 | 5.5 | 9.7 | 0.6 | Optional | 2025-12-02 |
| mistralai | mistralai/ministral-8b-2512:batch | Mistral: Ministral 3 8B 2512 (batch) | 262,144 | text+image->text | text,image | text | $0.0750 | $0.0750 | 5.5 | 9.7 | 0.6 | Optional | 2025-12-02 |
| mistralai | mistralai/mistral-large-2512 | Mistral: Mistral Large 3 2512 | 262,144 | text+image+file->text | text,image,file | text | $0.5000 | $1.5000 | 9.3 | 20.1 | 1 | Optional | 2025-12-02 |
| mistralai | mistralai/mistral-large-2512:batch | Mistral: Mistral Large 3 2512 (batch) | 262,144 | text+image+file->text | text,image,file | text | $0.2500 | $0.7500 | 9.3 | 20.1 | 1 | Optional | 2025-12-02 |
| mistralai | mistralai/mistral-large-4-0 | Mistral: Mistral Large 4 | 1,048,576 | text+image->text | text,image | text | $0.6800 | $2.0900 | - | - | - | Default | 2026-10-06 |
| mistralai | mistralai/mistral-medium-3 | Mistral: Mistral Medium 3 | 131,072 | text+image+file->text | text,image,file | text | $0.4000 | $2.0000 | 9 | - | - | Optional | 2025-05-07 |
| mistralai | mistralai/mistral-medium-3.1 | Mistral: Mistral Medium 3.1 | 131,072 | text+image+file->text | text,image,file | text | $0.4000 | $2.0000 | 9.2 | 20.5 | 1.9 | Optional | 2025-08-13 |
| mistralai | mistralai/mistral-medium-3.1:batch | Mistral: Mistral Medium 3.1 (batch) | 131,072 | text+image+file->text | text,image,file | text | $0.2000 | $1.0000 | 9.2 | 20.5 | 1.9 | Optional | 2025-08-13 |
| mistralai | mistralai/mistral-medium-3-5 | Mistral: Mistral Medium 3.5 | 262,144 | text+image+file->text | text,image,file | text | $1.5000 | $7.5000 | 14.2 | 46.9 | 7 | Optional | 2026-05-01 |
| mistralai | mistralai/mistral-medium-3-5:batch | Mistral: Mistral Medium 3.5 (batch) | 262,144 | text+image+file->text | text,image,file | text | $0.7500 | $3.7500 | 14.2 | 46.9 | 7 | Optional | 2026-05-01 |
| mistralai | mistralai/mistral-nemo | Mistral: Mistral Nemo | 131,072 | text->text | text | text | $0.0290 | $0.0300 | - | - | - | Optional | 2024-07-19 |
| mistralai | mistralai/mistral-small-24b-instruct-2501 | Mistral: Mistral Small 3 | 32,768 | text->text | text | text | $0.0500 | $0.0800 | 6.7 | - | - | Optional | 2025-01-31 |
| mistralai | mistralai/mistral-small-3.1-24b-instruct | Mistral: Mistral Small 3.1 24B | 128,000 | text+image->text | text,image | text | $0.3510 | $0.5550 | - | - | - | Optional | 2025-03-18 |
| mistralai | mistralai/mistral-small-3.2-24b-instruct | Mistral: Mistral Small 3.2 24B | 256,000 | text+image->text | image,text | text | $0.0938 | $0.2500 | - | - | - | Optional | 2025-06-21 |
| mistralai | mistralai/mistral-small-2603 | Mistral: Mistral Small 4 | 262,144 | text+image->text | text,image | text | $0.1500 | $0.6000 | 11.3 | 26.6 | 0.8 | Optional | 2026-03-17 |
| mistralai | mistralai/mistral-small-2603:batch | Mistral: Mistral Small 4 (batch) | 262,144 | text+image->text | text,image | text | $0.0750 | $0.3000 | 11.3 | 26.6 | 0.8 | Optional | 2026-03-17 |
| mistralai | mistralai/mixtral-8x22b-instruct | Mistral: Mixtral 8x22B Instruct | 65,536 | text+file->text | text,file | text | $2.0000 | $6.0000 | 5.7 | - | - | Optional | 2024-04-17 |
| mistralai | mistralai/mistral-saba | Mistral: Saba | 32,768 | text+file->text | text,file | text | $0.2000 | $0.6000 | 6.5 | - | - | Optional | 2025-02-17 |
| mistralai | mistralai/voxtral-small-24b-2507 | Mistral: Voxtral Small 24B 2507 | 32,768 | text+file+audio->text | text,audio,file | text | $0.1000 | $0.3000 | - | - | - | Optional | 2025-10-30 |
| moonshotai | moonshotai/kimi-k2 | MoonshotAI: Kimi K2 0711 | 131,072 | text->text | text | text | $0.5700 | $2.3000 | 12.7 | - | - | Optional | 2025-07-12 |
| moonshotai | moonshotai/kimi-k2-0905 | MoonshotAI: Kimi K2 0905 | 262,144 | text->text | text | text | $0.6000 | $2.5000 | 15.3 | - | - | Optional | 2025-09-05 |
| moonshotai | moonshotai/kimi-k2-thinking | MoonshotAI: Kimi K2 Thinking | 262,144 | text->text | text | text | $0.6000 | $2.5000 | 22 | - | - | Mandatory | 2025-11-06 |
| moonshotai | moonshotai/kimi-k2.5 | MoonshotAI: Kimi K2.5 | 262,144 | text+image->text | text,image | text | $0.5000 | $2.5000 | 23.5 | 46.8 | - | Default | 2026-01-27 |
| moonshotai | moonshotai/kimi-k2.6 | MoonshotAI: Kimi K2.6 | 262,144 | text+image->text | text,image | text | $0.4375 | $2.4500 | 27 | 61.8 | 20.5 | Default | 2026-04-20 |
| moonshotai | moonshotai/kimi-k2.7-code | MoonshotAI: Kimi K2.7 Code | 262,144 | text+image->text | text,image | text | $0.6712 | $3.3500 | 25.8 | 60.8 | 21 | Mandatory | 2026-06-12 |
| moonshotai | moonshotai/kimi-k3 | MoonshotAI: Kimi K3 | 1,048,576 | text+image+video->text | text,image,video | text | $0.5000 | $13.5000 | 43.6 | 76.2 | 50 | Default | 2026-07-16 |
| moonshotai | moonshotai/kimi-k3:batch | MoonshotAI: Kimi K3 (batch) | 1,048,576 | text+image+video->text | text,image,video | text | $2.2800 | $11.4000 | 43.6 | 76.2 | 50 | Default | 2026-07-16 |
| morph | morph/morph-v3-fast | Morph: Morph V3 Fast | 81,920 | text->text | text | text | $0.8000 | $1.2000 | - | - | - | Optional | 2025-07-08 |
| morph | morph/morph-v3-large | Morph: Morph V3 Large | 262,144 | text->text | text | text | $0.9000 | $1.9000 | - | - | - | Optional | 2025-07-08 |
| nex-agi | nex-agi/nex-n2.5-mini | Nex AGI: Nex-N2.5-Mini | 262,144 | text+image->text | text,image | text | $0.0250 | $0.1000 | - | - | - | Optional | 2026-09-09 |
| nex-agi | nex-agi/nex-n2.5-pro | Nex AGI: Nex-N2.5-Pro | 262,144 | text+image->text | text,image | text | $0.0750 | $0.2500 | - | - | - | Optional | 2026-09-09 |
| nousresearch | nousresearch/hermes-3-llama-3.1-405b | Nous: Hermes 3 405B Instruct | 131,072 | text->text | text | text | $1.0000 | $1.0000 | 7.4 | - | - | Optional | 2024-08-16 |
| nousresearch | nousresearch/hermes-3-llama-3.1-70b | Nous: Hermes 3 70B Instruct | 131,072 | text->text | text | text | $0.7000 | $0.7000 | 6.7 | - | - | Optional | 2024-08-18 |
| nousresearch | nousresearch/hermes-4-405b | Nous: Hermes 4 405B | 131,072 | text->text | text | text | $1.0000 | $3.0000 | 7.5 | - | - | Optional | 2025-08-27 |
| nvidia | nvidia/nemotron-3-nano-30b-a3b | NVIDIA: Nemotron 3 Nano 30B A3B | 262,144 | text->text | text | text | $0.0600 | $0.2400 | 8.9 | 14.4 | 1 | Optional | 2025-12-15 |
| nvidia | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | NVIDIA: Nemotron 3 Nano Omni (free) | 256,000 | text+image+audio+video->text | text,audio,image,video | text | $0.0000 | $0.0000 | 10.3 | 13.8 | - | Default | 2026-04-29 |
| nvidia | nvidia/nemotron-3-super-120b-a12b | NVIDIA: Nemotron 3 Super | 262,144 | text->text | text | text | $0.0800 | $0.4500 | 12.8 | 37.7 | 1.7 | Default | 2026-03-12 |
| nvidia | nvidia/nemotron-3-super-120b-a12b:free | NVIDIA: Nemotron 3 Super (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | 12.8 | 37.7 | 1.7 | Default | 2026-03-12 |
| nvidia | nvidia/nemotron-3-ultra-550b-a55b | NVIDIA: Nemotron 3 Ultra | 262,144 | text->text | text | text | $0.5000 | $2.2000 | 22.9 | 49.3 | 20.1 | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3-ultra-550b-a55b:free | NVIDIA: Nemotron 3 Ultra (free) | 1,000,000 | text->text | text | text | $0.0000 | $0.0000 | 22.9 | 49.3 | 20.1 | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3.5-content-safety | NVIDIA: Nemotron 3.5 Content Safety | 131,072 | text+image->text | text,image | text | $0.2000 | $0.2000 | - | - | - | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3.5-content-safety:free | NVIDIA: Nemotron 3.5 Content Safety (free) | 128,000 | text+image->text | text,image | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3.5-lightning | NVIDIA: Nemotron 3.5 Lightning | 262,144 | text->text | text | text | $0.0700 | $0.2000 | 12.9 | 26.8 | 3.5 | Optional | 2026-08-11 |
| nvidia | nvidia/nemotron-3.5-lightning:free | NVIDIA: Nemotron 3.5 Lightning (free) | 1,000,000 | text->text | text | text | $0.0000 | $0.0000 | 12.9 | 26.8 | 3.5 | Optional | 2026-08-11 |
| nvidia | nvidia/switchyard | NVIDIA: Switchyard | 1,000,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-09-22 |
| openai | openai/gpt-audio | OpenAI: GPT Audio | 128,000 | text+audio->text+audio | text,audio | text,audio | $2.5000 | $10.0000 | - | - | - | Optional | 2026-01-20 |
| openai | openai/gpt-audio-mini | OpenAI: GPT Audio Mini | 128,000 | text+audio->text+audio | text,audio | text,audio | $0.6000 | $2.4000 | - | - | - | Optional | 2026-01-20 |
| openai | openai/gpt-chat-latest | OpenAI: GPT Chat Latest | 400,000 | text+image+file->text | text,image,file | text | $5.0000 | $30.0000 | - | - | - | Optional | 2026-05-06 |
| openai | openai/gpt-3.5-turbo | OpenAI: GPT-3.5 Turbo | 16,385 | text->text | text | text | $0.5000 | $1.5000 | 5.5 | 10.7 | - | Optional | 2023-05-28 |
| openai | openai/gpt-3.5-turbo:batch | OpenAI: GPT-3.5 Turbo (batch) | 16,385 | text->text | text | text | $0.2500 | $0.7500 | 5.5 | 10.7 | - | Optional | 2023-05-28 |
| openai | openai/gpt-3.5-turbo-0613 | OpenAI: GPT-3.5 Turbo (older v0613) | 4,095 | text->text | text | text | $1.0000 | $2.0000 | - | - | - | Optional | 2024-01-25 |
| openai | openai/gpt-3.5-turbo-16k | OpenAI: GPT-3.5 Turbo 16k | 16,385 | text->text | text | text | $3.0000 | $4.0000 | - | - | - | Optional | 2023-08-28 |
| openai | openai/gpt-3.5-turbo-instruct | OpenAI: GPT-3.5 Turbo Instruct | 4,095 | text->text | text | text | $1.5000 | $2.0000 | - | - | - | Optional | 2023-09-28 |
| openai | openai/gpt-4 | OpenAI: GPT-4 | 8,191 | text->text | text | text | $30.0000 | $60.0000 | 6.7 | 13.1 | - | Optional | 2023-05-28 |
| openai | openai/gpt-4-turbo | OpenAI: GPT-4 Turbo | 128,000 | text+image->text | text,image | text | $10.0000 | $30.0000 | 7 | 21.5 | - | Optional | 2024-04-09 |
| openai | openai/gpt-4-turbo:batch | OpenAI: GPT-4 Turbo (batch) | 128,000 | text+image->text | text,image | text | $5.0000 | $15.0000 | 7 | 21.5 | - | Optional | 2024-04-09 |
| openai | openai/gpt-4.1 | OpenAI: GPT-4.1 | 1,047,576 | text+image+file->text | image,text,file | text | $2.0000 | $8.0000 | 12.7 | - | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1:batch | OpenAI: GPT-4.1 (batch) | 1,047,576 | text+image+file->text | image,text,file | text | $1.0000 | $4.0000 | 12.7 | - | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-mini | OpenAI: GPT-4.1 Mini | 1,047,576 | text+image+file->text | image,text,file | text | $0.4000 | $1.6000 | 10.2 | 20.2 | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-mini:batch | OpenAI: GPT-4.1 Mini (batch) | 1,047,576 | text+image+file->text | image,text,file | text | $0.2000 | $0.8000 | 10.2 | 20.2 | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-nano | OpenAI: GPT-4.1 Nano | 1,047,576 | text+image+file->text | image,text,file | text | $0.1000 | $0.4000 | 7.8 | 11.1 | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-nano:batch | OpenAI: GPT-4.1 Nano (batch) | 1,047,576 | text+image+file->text | image,text,file | text | $0.0500 | $0.2000 | 7.8 | 11.1 | - | Optional | 2025-04-15 |
| openai | openai/gpt-4o | OpenAI: GPT-4o | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-05-13 |
| openai | openai/gpt-4o-2024-05-13 | OpenAI: GPT-4o (2024-05-13) | 128,000 | text+image+file->text | text,image,file | text | $5.0000 | $15.0000 | 7.3 | 24.2 | - | Optional | 2024-05-13 |
| openai | openai/gpt-4o-2024-08-06 | OpenAI: GPT-4o (2024-08-06) | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | 7.7 | - | - | Optional | 2024-08-06 |
| openai | openai/gpt-4o-2024-11-20 | OpenAI: GPT-4o (2024-11-20) | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | 8.4 | - | - | Optional | 2024-11-21 |
| openai | openai/gpt-4o:batch | OpenAI: GPT-4o (batch) | 128,000 | text+image+file->text | text,image,file | text | $1.2500 | $5.0000 | - | - | - | Optional | 2024-05-13 |
| openai | openai/gpt-4o-mini | OpenAI: GPT-4o-mini | 128,000 | text+image+file->text | text,image,file | text | $0.1500 | $0.6000 | 6.7 | 11.4 | - | Optional | 2024-07-18 |
| openai | openai/gpt-4o-mini-2024-07-18 | OpenAI: GPT-4o-mini (2024-07-18) | 128,000 | text+image+file->text | text,image,file | text | $0.1500 | $0.6000 | - | - | - | Optional | 2024-07-18 |
| openai | openai/gpt-4o-mini:batch | OpenAI: GPT-4o-mini (batch) | 128,000 | text+image+file->text | text,image,file | text | $0.0750 | $0.3000 | 6.7 | 11.4 | - | Optional | 2024-07-18 |
| openai | openai/gpt-5 | OpenAI: GPT-5 | 400,000 | text+image+file->text | text,image,file | text | $1.2500 | $10.0000 | 23 | 37.8 | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5:batch | OpenAI: GPT-5 (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.6250 | $5.0000 | 23 | 37.8 | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-image | OpenAI: GPT-5 Image | 400,000 | text+image+file->text+image | image,text,file | image,text | $10.0000 | $10.0000 | - | - | - | Mandatory | 2025-10-14 |
| openai | openai/gpt-5-image-mini | OpenAI: GPT-5 Image Mini | 400,000 | text+image+file->text+image | file,image,text | image,text | $2.5000 | $2.0000 | - | - | - | Mandatory | 2025-10-16 |
| openai | openai/gpt-5-mini | OpenAI: GPT-5 Mini | 400,000 | text+image+file->text | text,image,file | text | $0.2500 | $2.0000 | 20.6 | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-mini:batch | OpenAI: GPT-5 Mini (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.1250 | $1.0000 | 20.6 | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-nano | OpenAI: GPT-5 Nano | 400,000 | text+image+file->text | text,image,file | text | $0.0500 | $0.4000 | 13 | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-nano:batch | OpenAI: GPT-5 Nano (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.0250 | $0.2000 | 13 | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-pro | OpenAI: GPT-5 Pro | 400,000 | text+image+file->text | image,text,file | text | $15.0000 | $120.0000 | - | - | - | Mandatory | 2025-10-07 |
| openai | openai/gpt-5-pro:batch | OpenAI: GPT-5 Pro (batch) | 400,000 | text+image+file->text | image,text,file | text | $7.5000 | $60.0000 | - | - | - | Mandatory | 2025-10-07 |
| openai | openai/gpt-5.1 | OpenAI: GPT-5.1 | 400,000 | text+image+file->text | image,text,file | text | $1.2500 | $10.0000 | 24.7 | 49.4 | - | Default | 2025-11-14 |
| openai | openai/gpt-5.1:batch | OpenAI: GPT-5.1 (batch) | 400,000 | text+image+file->text | image,text,file | text | $0.6250 | $5.0000 | 24.7 | 49.4 | - | Default | 2025-11-14 |
| openai | openai/gpt-5.1-codex | OpenAI: GPT-5.1-Codex | 400,000 | text+image->text | text,image | text | $1.2500 | $10.0000 | 23.7 | - | - | Mandatory | 2025-11-14 |
| openai | openai/gpt-5.1-codex-max | OpenAI: GPT-5.1-Codex-Max | 400,000 | text+image->text | text,image | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-12-05 |
| openai | openai/gpt-5.1-codex-mini | OpenAI: GPT-5.1-Codex-Mini | 400,000 | text+image->text | image,text | text | $0.2500 | $2.0000 | 20.4 | - | - | Optional | 2025-11-14 |
| openai | openai/gpt-5.2 | OpenAI: GPT-5.2 | 400,000 | text+image+file->text | file,image,text | text | $1.7500 | $14.0000 | 30.4 | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2:batch | OpenAI: GPT-5.2 (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.8750 | $7.0000 | 30.4 | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2-chat | OpenAI: GPT-5.2 Chat | 128,000 | text+image+file->text | file,image,text | text | $1.7500 | $14.0000 | - | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2-pro | OpenAI: GPT-5.2 Pro | 400,000 | text+image+file->text | image,text,file | text | $21.0000 | $168.0000 | - | - | - | Mandatory | 2025-12-11 |
| openai | openai/gpt-5.2-pro:batch | OpenAI: GPT-5.2 Pro (batch) | 400,000 | text+image+file->text | image,text,file | text | $10.5000 | $84.0000 | - | - | - | Mandatory | 2025-12-11 |
| openai | openai/gpt-5.2-codex | OpenAI: GPT-5.2-Codex | 400,000 | text+image->text | text,image | text | $1.7500 | $14.0000 | 28.5 | - | - | Mandatory | 2026-01-15 |
| openai | openai/gpt-5.3-codex | OpenAI: GPT-5.3-Codex | 400,000 | text+image+file->text | text,image,file | text | $1.7500 | $14.0000 | 32.5 | - | - | Optional | 2026-02-25 |
| openai | openai/gpt-5.4 | OpenAI: GPT-5.4 | 1,050,000 | text+image+file->text | text,image,file | text | $2.5000 | $15.0000 | 39 | 71.1 | - | Optional | 2026-03-06 |
| openai | openai/gpt-5.4:batch | OpenAI: GPT-5.4 (batch) | 1,050,000 | text+image+file->text | text,image,file | text | $1.2500 | $7.5000 | 39 | 71.1 | - | Optional | 2026-03-06 |
| openai | openai/gpt-5.4-image-2 | OpenAI: GPT-5.4 Image 2 | 272,000 | text+image+file->text+image | image,text,file | image,text | $8.0000 | $15.0000 | - | - | - | Optional | 2026-04-22 |
| openai | openai/gpt-5.4-mini | OpenAI: GPT-5.4 Mini | 400,000 | text+image+file->text | file,image,text | text | $0.7500 | $4.5000 | 24.1 | 56.1 | 17.9 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-mini:batch | OpenAI: GPT-5.4 Mini (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.3750 | $2.2500 | 24.1 | 56.1 | 17.9 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-nano | OpenAI: GPT-5.4 Nano | 400,000 | text+image+file->text | file,image,text | text | $0.2000 | $1.2500 | 20.7 | 56.1 | 16 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-nano:batch | OpenAI: GPT-5.4 Nano (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.6250 | 20.7 | 56.1 | 16 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-pro | OpenAI: GPT-5.4 Pro | 1,050,000 | text+image+file->text | text,image,file | text | $30.0000 | $180.0000 | - | - | - | Mandatory | 2026-03-06 |
| openai | openai/gpt-5.4-pro:batch | OpenAI: GPT-5.4 Pro (batch) | 1,050,000 | text+image+file->text | text,image,file | text | $15.0000 | $90.0000 | - | - | - | Mandatory | 2026-03-06 |
| openai | openai/gpt-5.5 | OpenAI: GPT-5.5 | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $30.0000 | 38.4 | 74.9 | 36.4 | Default | 2026-04-25 |
| openai | openai/gpt-5.5:batch | OpenAI: GPT-5.5 (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $2.5000 | $15.0000 | 38.4 | 74.9 | 36.4 | Default | 2026-04-25 |
| openai | openai/gpt-5.5-pro | OpenAI: GPT-5.5 Pro | 1,050,000 | text+image+file->text | file,image,text | text | $30.0000 | $180.0000 | - | - | - | Mandatory | 2026-04-25 |
| openai | openai/gpt-5.5-pro:batch | OpenAI: GPT-5.5 Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $15.0000 | $90.0000 | - | - | - | Mandatory | 2026-04-25 |
| openai | openai/gpt-5.6-luna | OpenAI: GPT-5.6 Luna | 1,050,000 | text+image+file->text | file,image,text | text | $0.2000 | $1.2000 | 37.3 | 71.4 | 42.1 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-luna:batch | OpenAI: GPT-5.6 Luna (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.6000 | 37.3 | 71.4 | 42.1 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-luna-pro | OpenAI: GPT-5.6 Luna Pro | 1,050,000 | text+image+file->text | file,image,text | text | $0.2000 | $1.2000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-luna-pro:batch | OpenAI: GPT-5.6 Luna Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.6000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol | OpenAI: GPT-5.6 Sol | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | 47 | 77.4 | 50.2 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol:batch | OpenAI: GPT-5.6 Sol (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | 47 | 77.4 | 50.2 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol-pro | OpenAI: GPT-5.6 Sol Pro | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol-pro:batch | OpenAI: GPT-5.6 Sol Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra | OpenAI: GPT-5.6 Terra | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $12.0000 | 42.1 | 76.7 | 43.2 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra:batch | OpenAI: GPT-5.6 Terra (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $6.0000 | 42.1 | 76.7 | 43.2 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra-pro | OpenAI: GPT-5.6 Terra Pro | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $12.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra-pro:batch | OpenAI: GPT-5.6 Terra Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $6.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-6-astra | OpenAI: GPT-6 Astra | 1,050,000 | text+image+file->text | file,image,text | text | $10.0000 | $50.0000 | 52.7 | 76.9 | 51 | Mandatory | 2026-09-05 |
| openai | openai/gpt-6-astra:batch | OpenAI: GPT-6 Astra (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $25.0000 | 52.7 | 76.9 | 51 | Mandatory | 2026-09-05 |
| openai | openai/gpt-6-astra-pro | OpenAI: GPT-6 Astra Pro | 1,050,000 | text+image+file->text | file,image,text | text | $10.0000 | $50.0000 | - | - | - | Mandatory | 2026-09-05 |
| openai | openai/gpt-6-astra-pro:batch | OpenAI: GPT-6 Astra Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $25.0000 | - | - | - | Mandatory | 2026-09-05 |
| openai | openai/gpt-6-luna | OpenAI: GPT-6 Luna | 1,050,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.5000 | 38.1 | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-luna:batch | OpenAI: GPT-6 Luna (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $0.0500 | $0.2500 | 38.1 | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-luna-pro | OpenAI: GPT-6 Luna Pro | 1,050,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.5000 | - | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-luna-pro:batch | OpenAI: GPT-6 Luna Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $0.0500 | $0.2500 | - | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-sol | OpenAI: GPT-6 Sol | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | 47.6 | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-sol:batch | OpenAI: GPT-6 Sol (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | 47.6 | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-sol-pro | OpenAI: GPT-6 Sol Pro | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | - | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6-sol-pro:batch | OpenAI: GPT-6 Sol Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | - | - | - | Default | 2026-09-23 |
| openai | openai/gpt-6.1-sol | OpenAI: GPT-6.1 Sol | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | 51.8 | - | - | Mandatory | 2026-09-30 |
| openai | openai/gpt-6.1-sol:batch | OpenAI: GPT-6.1 Sol (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | 51.8 | - | - | Mandatory | 2026-09-30 |
| openai | openai/gpt-6.1-sol-pro | OpenAI: GPT-6.1 Sol Pro | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | - | - | - | Mandatory | 2026-09-30 |
| openai | openai/gpt-6.1-sol-pro:batch | OpenAI: GPT-6.1 Sol Pro (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $1.0000 | $5.0000 | - | - | - | Mandatory | 2026-09-30 |
| openai | openai/gpt-oss-120b | OpenAI: gpt-oss-120b | 131,072 | text->text | text | text | $0.0370 | $0.1700 | 11.6 | 30.4 | 3.7 | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-120b:batch | OpenAI: gpt-oss-120b (batch) | 131,072 | text->text | text | text | $0.0296 | $0.1360 | 11.6 | 30.4 | 3.7 | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-20b | OpenAI: gpt-oss-20b | 131,072 | text->text | text | text | $0.0180 | $0.0900 | 10 | - | - | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-20b:batch | OpenAI: gpt-oss-20b (batch) | 131,072 | text->text | text | text | $0.0240 | $0.1120 | 10 | - | - | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-safeguard-20b | OpenAI: gpt-oss-safeguard-20b | 131,072 | text->text | text | text | $0.0750 | $0.3000 | - | - | - | Mandatory | 2025-10-29 |
| openai | openai/o1 | OpenAI: o1 | 200,000 | text+image+file->text | text,image,file | text | $15.0000 | $60.0000 | 15.2 | 39.7 | - | Optional | 2024-12-18 |
| openai | openai/o1-pro | OpenAI: o1-pro | 200,000 | text+image+file->text | text,image,file | text | $150.0000 | $600.0000 | 12.4 | - | - | Optional | 2025-03-20 |
| openai | openai/o3 | OpenAI: o3 | 200,000 | text+image+file->text | image,text,file | text | $2.0000 | $8.0000 | 20.2 | - | - | Optional | 2025-04-17 |
| openai | openai/o3:batch | OpenAI: o3 (batch) | 200,000 | text+image+file->text | image,text,file | text | $1.0000 | $4.0000 | 20.2 | - | - | Optional | 2025-04-17 |
| openai | openai/o3-mini | OpenAI: o3 Mini | 200,000 | text+file->text | text,file | text | $1.1000 | $4.4000 | 12.5 | - | - | Optional | 2025-02-01 |
| openai | openai/o3-mini:batch | OpenAI: o3 Mini (batch) | 200,000 | text+file->text | text,file | text | $0.5500 | $2.2000 | 12.5 | - | - | Optional | 2025-02-01 |
| openai | openai/o3-mini-high | OpenAI: o3 Mini High | 200,000 | text+file->text | text,file | text | $1.1000 | $4.4000 | 11 | 16.3 | 0.9 | Mandatory | 2025-02-12 |
| openai | openai/o3-pro | OpenAI: o3 Pro | 200,000 | text+image+file->text | text,file,image | text | $20.0000 | $80.0000 | 21.9 | - | - | Optional | 2025-06-11 |
| openai | openai/o4-mini | OpenAI: o4 Mini | 200,000 | text+image+file->text | image,text,file | text | $1.1000 | $4.4000 | 16.7 | - | - | Optional | 2025-04-17 |
| openai | openai/o4-mini:batch | OpenAI: o4 Mini (batch) | 200,000 | text+image+file->text | image,text,file | text | $0.5500 | $2.2000 | 16.7 | - | - | Optional | 2025-04-17 |
| openai | openai/o4-mini-high | OpenAI: o4 Mini High | 200,000 | text+image+file->text | image,text,file | text | $1.1000 | $4.4000 | - | - | - | Mandatory | 2025-04-17 |
| openrouter | openrouter/auto | Auto Router | 2,000,000 | text+image+file+audio+video->text+image | text,image,audio,file,video | text,image | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2023-11-08 |
| openrouter | openrouter/auto-beta | Auto Router (Beta) | 2,000,000 | text+image+file+audio+video->text+image | text,image,audio,file,video | text,image | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-07-18 |
| openrouter | openrouter/bodybuilder | Body Builder (beta) | 128,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2025-12-05 |
| openrouter | openrouter/free | Free Models Router | 200,000 | text+image->text | text,image | text | $0.0000 | $0.0000 | - | - | - | Optional | 2026-02-01 |
| openrouter | openrouter/fusion | OpenRouter: Fusion | 1,000,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-06-14 |
| openrouter | openrouter/pareto-code | Pareto Code Router | 2,000,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-04-21 |
| perceptron | perceptron/perceptron-mk1 | Perceptron: Perceptron Mk1 | 32,768 | text+image+video->text | text,image,video | text | $0.1500 | $1.5000 | - | - | - | Optional | 2026-05-12 |
| perceptron | perceptron/perceptron-mk1.5 | Perceptron: Perceptron Mk1.5 | 36,864 | text+image+audio+video->text | text,image,video,audio | text | $0.1500 | $1.5000 | - | - | - | Optional | 2026-09-26 |
| perplexity | perplexity/sonar | Perplexity: Sonar | 127,072 | text+image->text | text,image | text | $1.0000 | $1.0000 | 7.7 | - | - | Optional | 2025-01-28 |
| perplexity | perplexity/sonar-deep-research | Perplexity: Sonar Deep Research | 128,000 | text->text | text | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-03-07 |
| perplexity | perplexity/sonar-pro | Perplexity: Sonar Pro | 200,000 | text+image->text | text,image | text | $3.0000 | $15.0000 | 7.6 | - | - | Optional | 2025-03-07 |
| perplexity | perplexity/sonar-pro-search | Perplexity: Sonar Pro Search | 200,000 | text+image->text | text,image | text | $3.0000 | $15.0000 | - | - | - | Mandatory | 2025-10-31 |
| perplexity | perplexity/sonar-reasoning-pro | Perplexity: Sonar Reasoning Pro | 128,000 | text+image->text | text,image | text | $2.0000 | $8.0000 | 11.8 | - | - | Optional | 2025-03-07 |
| poolside | poolside/laguna-s-2.1 | Poolside: Laguna S 2.1 | 1,048,576 | text->text | text | text | $0.0900 | $0.1800 | - | - | - | Default | 2026-07-22 |
| poolside | poolside/laguna-s-2.1:free | Poolside: Laguna S 2.1 (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-07-22 |
| poolside | poolside/laguna-xs-2.1 | Poolside: Laguna XS 2.1 | 262,144 | text->text | text | text | $0.0600 | $0.1200 | - | - | - | Default | 2026-07-02 |
| poolside | poolside/laguna-xs-2.1:free | Poolside: Laguna XS 2.1 (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-07-02 |
| prism-ml | prism-ml/ternary-bonsai-2-27b | PrismML: Ternary Bonsai 2 27B | 262,144 | text+image->text | text,image | text | $0.0750 | $0.5000 | - | - | - | Default | 2026-09-19 |
| qwen | qwen/qwen-2.5-72b-instruct | Qwen2.5 72B Instruct | 32,768 | text->text | text | text | $0.3600 | $0.4000 | 7.7 | - | - | Optional | 2024-09-19 |
| qwen | qwen/qwen-2.5-coder-32b-instruct | Qwen2.5 Coder 32B Instruct | 32,768 | text->text | text | text | $0.6600 | $1.0000 | 6.7 | - | - | Optional | 2024-11-12 |
| qwen | qwen/qwen-plus | Qwen: Qwen-Plus | 1,000,000 | text->text | text | text | $0.2600 | $0.7800 | - | - | - | Optional | 2025-02-01 |
| qwen | qwen/qwen-2.5-7b-instruct | Qwen: Qwen2.5 7B Instruct | 32,768 | text->text | text | text | $0.1000 | $0.2000 | - | - | - | Optional | 2024-10-16 |
| qwen | qwen/qwen2.5-vl-72b-instruct | Qwen: Qwen2.5 VL 72B Instruct | 128,000 | text+image->text | text,image | text | $0.8000 | $1.0000 | - | - | - | Optional | 2025-02-01 |
| qwen | qwen/qwen3-14b | Qwen: Qwen3 14B | 40,960 | text->text | text | text | $0.1200 | $0.2400 | 8.2 | 13.8 | 0.9 | Optional | 2025-04-29 |
| qwen | qwen/qwen3-235b-a22b-2507 | Qwen: Qwen3 235B A22B Instruct 2507 | 262,144 | text->text | text | text | $0.0900 | $0.5500 | 12 | - | - | Optional | 2025-07-22 |
| qwen | qwen/qwen3-235b-a22b-thinking-2507 | Qwen: Qwen3 235B A22B Thinking 2507 | 128,000 | text->text | text | text | $0.4500 | $3.5000 | 12.7 | 22.1 | 1.3 | Mandatory | 2025-07-25 |
| qwen | qwen/qwen3-30b-a3b | Qwen: Qwen3 30B A3B | 40,960 | text->text | text | text | $0.1200 | $0.5000 | 7.6 | - | - | Default | 2025-04-29 |
| qwen | qwen/qwen3-30b-a3b-instruct-2507 | Qwen: Qwen3 30B A3B Instruct 2507 | 262,144 | text->text | text | text | $0.1000 | $0.3000 | 7.5 | - | - | Optional | 2025-07-30 |
| qwen | qwen/qwen3-32b | Qwen: Qwen3 32B | 131,072 | text->text | text | text | $0.0800 | $0.2800 | 8.6 | 15.3 | 0.9 | Optional | 2025-04-29 |
| qwen | qwen/qwen3-coder-30b-a3b-instruct | Qwen: Qwen3 Coder 30B A3B Instruct | 262,144 | text->text | text | text | $0.0700 | $0.2800 | 9.6 | - | - | Optional | 2025-07-31 |
| qwen | qwen/qwen3-coder | Qwen: Qwen3 Coder 480B A35B | 262,144 | text->text | text | text | $0.3000 | $1.0000 | 11.9 | - | - | Optional | 2025-07-23 |
| qwen | qwen/qwen3-coder-flash | Qwen: Qwen3 Coder Flash | 1,000,000 | text->text | text | text | $0.1950 | $0.9750 | - | - | - | Optional | 2025-09-17 |
| qwen | qwen/qwen3-coder-next | Qwen: Qwen3 Coder Next | 262,144 | text->text | text | text | $0.1200 | $0.8000 | 9.2 | 36.2 | 0.9 | Optional | 2026-02-04 |
| qwen | qwen/qwen3-next-80b-a3b-instruct | Qwen: Qwen3 Next 80B A3B Instruct | 262,144 | text->text | text | text | $0.1000 | $1.1000 | 9.6 | - | - | Optional | 2025-09-12 |
| qwen | qwen/qwen3-next-80b-a3b-thinking | Qwen: Qwen3 Next 80B A3B Thinking | 262,144 | text->text | text | text | $0.1500 | $1.2000 | 11.2 | 17.4 | - | Mandatory | 2025-09-12 |
| qwen | qwen/qwen3-vl-235b-a22b-instruct | Qwen: Qwen3 VL 235B A22B Instruct | 262,144 | text+image->text | text,image | text | $0.2100 | $1.9000 | 9.9 | - | - | Optional | 2025-09-24 |
| qwen | qwen/qwen3-vl-30b-a3b-instruct | Qwen: Qwen3 VL 30B A3B Instruct | 262,144 | text+image->text | text,image | text | $0.1500 | $0.6000 | 7.9 | - | - | Optional | 2025-10-07 |
| qwen | qwen/qwen3-vl-30b-a3b-thinking | Qwen: Qwen3 VL 30B A3B Thinking | 262,144 | text+image->text | text,image | text | $0.2900 | $1.0000 | 9.5 | - | - | Mandatory | 2025-10-07 |
| qwen | qwen/qwen3-vl-8b-instruct | Qwen: Qwen3 VL 8B Instruct | 262,144 | text+image->text | image,text | text | $0.2500 | $0.7500 | 7.3 | - | - | Optional | 2025-10-15 |
| qwen | qwen/qwen3.5-397b-a17b | Qwen: Qwen3.5 397B A17B | 262,144 | text+image+video->text | text,image,video | text | $0.5500 | $3.5000 | 21.4 | - | - | Optional | 2026-02-16 |
| qwen | qwen/qwen3.5-plus-02-15 | Qwen: Qwen3.5 Plus 2026-02-15 | 1,000,000 | text+image+video->text | text,image,video | text | $0.2600 | $1.5600 | - | - | - | Optional | 2026-02-16 |
| qwen | qwen/qwen3.5-plus-20260420 | Qwen: Qwen3.5 Plus 2026-04-20 | 1,000,000 | text+image+video->text | text,image,video | text | $0.3000 | $1.8000 | - | - | - | Optional | 2026-04-27 |
| qwen | qwen/qwen3.5-122b-a10b | Qwen: Qwen3.5-122B-A10B | 262,144 | text+image+video->text | text,image,video | text | $0.2600 | $2.0800 | 17.7 | 43.3 | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-27b | Qwen: Qwen3.5-27B | 262,144 | text+image+video->text | text,image,video | text | $0.2600 | $2.6000 | 22.9 | - | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-35b-a3b | Qwen: Qwen3.5-35B-A3B | 262,144 | text+image+video->text | text,image,video | text | $0.0800 | $0.7500 | 19.3 | - | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-9b | Qwen: Qwen3.5-9B | 262,144 | text+image+video->text | text,image,video | text | $0.1000 | $0.1500 | 13.3 | 23.5 | - | Optional | 2026-03-10 |
| qwen | qwen/qwen3.5-flash-02-23 | Qwen: Qwen3.5-Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.0650 | $0.2600 | - | - | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.6-27b | Qwen: Qwen3.6 27B | 262,144 | text+image+video->text | text,image,video | text | $0.3200 | $3.2000 | 21.4 | 53.7 | 18.5 | Default | 2026-04-27 |
| qwen | qwen/qwen3.6-35b-a3b | Qwen: Qwen3.6 35B A3B | 262,144 | text+image+video->text | text,image,video | text | $0.1500 | $1.0000 | 18.2 | 41.9 | 13.1 | Default | 2026-04-27 |
| qwen | qwen/qwen3.6-flash | Qwen: Qwen3.6 Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.1875 | $1.1250 | - | - | - | Optional | 2026-04-27 |
| qwen | qwen/qwen3.6-plus | Qwen: Qwen3.6 Plus | 1,000,000 | text+image+video->text | text,image,video | text | $0.3250 | $1.9500 | 27 | 54.5 | - | Optional | 2026-04-02 |
| qwen | qwen/qwen3.7-flash | Qwen: Qwen3.7 Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.0300 | $0.1300 | - | - | - | Default | 2026-07-28 |
| qwen | qwen/qwen3.7-max | Qwen: Qwen3.7 Max | 1,000,000 | text->text | text | text | $1.4750 | $4.4250 | 29.5 | 66 | 22.5 | Default | 2026-05-21 |
| qwen | qwen/qwen3.7-plus | Qwen: Qwen3.7 Plus | 1,000,000 | text+image->text | text,image | text | $0.3200 | $1.2800 | 25.2 | 55.9 | 17.5 | Default | 2026-06-03 |
| qwen | qwen/qwen3.8-2.4t-a95b | Qwen: Qwen3.8 2.4T A95B | 1,048,576 | text->text | text | text | $2.0000 | $6.0000 | 39.9 | 71.9 | 50.1 | Mandatory | 2026-08-13 |
| qwen | qwen/qwen3.8-27b | Qwen: Qwen3.8 27B | 1,000,000 | text+image+video->text | text,image,video | text | $0.4250 | $2.5500 | 33.7 | 68.1 | 45.8 | Default | 2026-08-14 |
| qwen | qwen/qwen3.8-flash | Qwen: Qwen3.8 Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.1500 | $0.4700 | - | - | - | Default | 2026-08-27 |
| qwen | qwen/qwen3.8-max-0902 | Qwen: Qwen3.8 Max (0902) | 1,000,000 | text+image+video->text | text,image,video | text | $2.0000 | $6.0000 | 45.4 | 76.2 | 56 | Mandatory | 2026-09-04 |
| qwen | qwen/qwen3.8-max-prime | Qwen: Qwen3.8 Max Prime | 1,000,000 | text+image+video->text | text,image,video | text | $4.0000 | $12.0000 | - | - | - | Mandatory | 2026-09-24 |
| qwen | qwen/qwen3.8-omni-flash | Qwen: Qwen3.8 Omni Flash | 1,000,000 | text+image+audio+video->text | text,image,audio,video | text | $0.1500 | $0.4700 | - | - | - | Default | 2026-09-21 |
| rekaai | rekaai/reka-edge | Reka Edge | 16,384 | text+image+video->text | image,text,video | text | $0.1000 | $0.1000 | - | - | - | Optional | 2026-03-21 |
| rekaai | rekaai/reka-flash-3 | Reka Flash 3 | 65,536 | text->text | text | text | $0.1000 | $0.2000 | 6.4 | - | - | Mandatory | 2025-03-13 |
| relace | relace/relace-apply-3 | Relace: Relace Apply 3 | 256,000 | text->text | text | text | $0.8500 | $1.2500 | - | - | - | Optional | 2025-09-26 |
| relace | relace/relace-search | Relace: Relace Search | 256,000 | text->text | text | text | $1.0000 | $3.0000 | - | - | - | Optional | 2025-12-09 |
| sakana | sakana/fugu-max | Sakana: Fugu Max | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | - | - | - | Mandatory | 2026-09-11 |
| sakana | sakana/fugu-ultra | Sakana: Fugu Ultra | 1,000,000 | text+image->text | text,image | text | $5.0000 | $30.0000 | - | - | - | Mandatory | 2026-06-24 |
| sakana | sakana/fugu-ultra-v2 | Sakana: Fugu Ultra v2 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $30.0000 | - | - | - | Mandatory | 2026-09-11 |
| sakana | sakana/sakana-namazu | Sakana: Sakana Namazu | 262,144 | text+image+file->text | text,image,file | text | $0.9500 | $4.0000 | - | - | - | Default | 2026-08-11 |
| sao10k | sao10k/l3-lunaris-8b | Sao10K: Llama 3 8B Lunaris | 8,192 | text->text | text | text | $0.0400 | $0.0500 | - | - | - | Optional | 2024-08-13 |
| sao10k | sao10k/l3.1-euryale-70b | Sao10K: Llama 3.1 Euryale 70B v2.2 | 131,072 | text->text | text | text | $0.8500 | $0.8500 | - | - | - | Optional | 2024-08-28 |
| sao10k | sao10k/l3.3-euryale-70b | Sao10K: Llama 3.3 Euryale 70B | 131,072 | text->text | text | text | $0.6500 | $0.7500 | - | - | - | Optional | 2024-12-18 |
| stepfun | stepfun/step-3.5-flash | StepFun: Step 3.5 Flash | 262,144 | text->text | text | text | $0.1000 | $0.3000 | 17 | - | - | Mandatory | 2026-01-30 |
| stepfun | stepfun/step-3.7-flash | StepFun: Step 3.7 Flash | 262,144 | text+image+video->text | text,image,video | text | $0.2000 | $1.1500 | 19.5 | 39.6 | - | Mandatory | 2026-05-29 |
| stepfun | stepfun/step-5-preview | StepFun: Step 5 Preview | 1,000,000 | text+image+video->text | text,image,video | text | $1.0000 | $2.7000 | - | - | - | Mandatory | 2026-10-08 |
| tencent | tencent/hunyuan-a13b-instruct | Tencent: Hunyuan A13B Instruct | 131,072 | text->text | text | text | $0.1400 | $0.5700 | - | - | - | Optional | 2025-07-08 |
| tencent | tencent/hy-mt2-1.8b | Tencent: Hy-MT2-1.8B | 8,192 | text->text | text | text | $0.0440 | $0.1770 | - | - | - | Optional | 2026-08-20 |
| tencent | tencent/hy-mt2-30b-a3b | Tencent: Hy-MT2-30B-A3B | 8,192 | text->text | text | text | $0.0740 | $0.2950 | - | - | - | Optional | 2026-08-20 |
| tencent | tencent/hy-mt2-7b | Tencent: Hy-MT2-7B | 8,192 | text->text | text | text | $0.0740 | $0.2950 | - | - | - | Optional | 2026-08-19 |
| tencent | tencent/hy3 | Tencent: Hy3 | 262,144 | text->text | text | text | $0.1320 | $0.5280 | - | - | - | Default | 2026-07-06 |
| tencent | tencent/hy3-preview | Tencent: Hy3 preview | 262,144 | text->text | text | text | $0.1800 | $0.6000 | 25.3 | 58.8 | 24.1 | Default | 2026-04-23 |
| tencent | tencent/hy4-preview | Tencent: Hy4 preview | 1,048,576 | text->text | text | text | $0.8340 | $2.5010 | - | - | - | Default | 2026-08-28 |
| thedrummer | thedrummer/cydonia-24b-v4.1 | TheDrummer: Cydonia 24B V4.1 | 131,072 | text->text | text | text | $0.3000 | $0.5000 | - | - | - | Optional | 2025-09-27 |
| thedrummer | thedrummer/skyfall-36b-v2 | TheDrummer: Skyfall 36B V2 | 32,768 | text->text | text | text | $0.5500 | $0.8000 | - | - | - | Optional | 2025-03-11 |
| thedrummer | thedrummer/unslopnemo-12b | TheDrummer: UnslopNemo 12B | 1,024,000 | text->text | text | text | $0.4000 | $0.4000 | - | - | - | Optional | 2024-11-09 |
| thinkingmachines | thinkingmachines/inkling | Thinking Machines: Inkling | 524,288 | text+image+audio->text | text,image,audio | text | $1.0000 | $4.0500 | 25 | 52.1 | 22.5 | Default | 2026-07-18 |
| thinkingmachines | thinkingmachines/inkling:free | Thinking Machines: Inkling (free) | 1,048,576 | text+image+audio->text | text,image,audio | text | $0.0000 | $0.0000 | 25 | 52.1 | 22.5 | Default | 2026-07-18 |
| thinkingmachines | thinkingmachines/inkling-small | Thinking Machines: Inkling Small | 524,288 | text+image+audio->text | text,image,audio | text | $0.4500 | $1.2000 | 25.7 | 52.9 | 23.5 | Default | 2026-07-31 |
| thinkingmachines | thinkingmachines/inkling-small:free | Thinking Machines: Inkling Small (free) | 1,048,576 | text+image+audio->text | text,image,audio | text | $0.0000 | $0.0000 | 25.7 | 52.9 | 23.5 | Default | 2026-07-31 |
| typesafe | typesafe/jev-router | TypeSafe: Jev Router | 1,000,000 | text+image+file+audio+video->text | audio,file,image,text,video | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-09-26 |
| unbiased | unbiased/pareto | Pareto | 262,144 | text+image->text | text,image | text | $2.5000 | $7.5000 | - | - | - | Optional | 2026-09-18 |
| unbiased | unbiased/pareto-26.10-preview | Pareto 26.10 Preview | 1,048,576 | text+image->text | text,image | text | $0.8000 | $3.2000 | - | - | - | Optional | 2026-10-01 |
| undi95 | undi95/remm-slerp-l2-13b | ReMM SLERP 13B | 6,144 | text->text | text | text | $0.3500 | $0.6500 | - | - | - | Optional | 2023-07-22 |
| upstage | upstage/solar-mini4 | Upstage: Solar Mini 4 | 524,288 | text->text | text | text | $0.0500 | $0.2000 | 24.1 | - | - | Optional | 2026-09-23 |
| upstage | upstage/solar-pro-3 | Upstage: Solar Pro 3 | 131,072 | text->text | text | text | $0.1500 | $0.6000 | 7.8 | 16.2 | 1.4 | Optional | 2026-01-27 |
| upstage | upstage/solar-pro4 | Upstage: Solar Pro 4 | 524,288 | text->text | text | text | $0.0900 | $0.3600 | 28.2 | 52.7 | - | Optional | 2026-08-10 |
| writer | writer/palmyra-x5 | Writer: Palmyra X5 | 1,040,000 | text->text | text | text | $0.6000 | $6.0000 | - | - | - | Optional | 2026-01-21 |
| x-ai | x-ai/grok-4.20 | SpaceXAI: Grok 4.20 | 2,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | 25.7 | - | - | Optional | 2026-04-01 |
| x-ai | x-ai/grok-4.20-multi-agent | SpaceXAI: Grok 4.20 Multi-Agent | 2,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | - | - | - | Mandatory | 2026-04-01 |
| x-ai | x-ai/grok-4.3 | SpaceXAI: Grok 4.3 | 1,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | 24.9 | 42.2 | 15.5 | Default | 2026-05-01 |
| x-ai | x-ai/grok-4.3:batch | SpaceXAI: Grok 4.3 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.0000 | $2.0000 | 24.9 | 42.2 | 15.5 | Default | 2026-05-01 |
| x-ai | x-ai/grok-4.5 | SpaceXAI: Grok 4.5 | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | 38.8 | 72.4 | 41.2 | Mandatory | 2026-07-08 |
| x-ai | x-ai/grok-4.6 | SpaceXAI: Grok 4.6 | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | 44.3 | 76.8 | 53 | Mandatory | 2026-08-12 |
| x-ai | x-ai/grok-4.7 | SpaceXAI: Grok 4.7 | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | 46.4 | - | - | Mandatory | 2026-09-22 |
| x-ai | x-ai/grok-build-0.1 | SpaceXAI: Grok Build 0.1 | 256,000 | text+image+file->text | text,image,file | text | $1.0000 | $2.0000 | 27.2 | 51.5 | - | Mandatory | 2026-05-21 |
| xiaomi | xiaomi/mimo-v2.5 | Xiaomi: MiMo-V2.5 | 1,050,000 | text+image+audio+video->text | text,audio,image,video | text | $0.1400 | $0.2800 | 25.2 | 56.8 | 15.8 | Optional | 2026-04-23 |
| xiaomi | xiaomi/mimo-v2.5-pro | Xiaomi: MiMo-V2.5-Pro | 1,050,000 | text->text | text | text | $0.4350 | $0.8700 | 26 | 60.2 | 21.3 | Optional | 2026-04-23 |
| xiaomi | xiaomi/mimo-v2.6-flash | Xiaomi: MiMo-V2.6-Flash | 1,050,000 | text+image+audio+video->text | text,image,video,audio | text | $0.1400 | $0.2800 | 37.9 | - | - | Optional | 2026-09-22 |
| xiaomi | xiaomi/mimo-v2.6-pro | Xiaomi: MiMo-V2.6-Pro | 1,050,000 | text+image+audio+video->text | text,image,video,audio | text | $0.4350 | $0.8700 | 46.3 | - | - | Optional | 2026-09-22 |
| xiaomi | xiaomi/mimo-v2.6-pro-ultraspeed | Xiaomi: MiMo-V2.6-Pro-UltraSpeed | 1,048,576 | text+image+audio+video->text | text,image,video,audio | text | $4.3500 | $8.7000 | - | - | - | Optional | 2026-09-22 |
| z-ai | z-ai/glm-4.5 | Z.ai: GLM 4.5 | 131,072 | text->text | text | text | $0.6000 | $2.2000 | 12.8 | - | - | Optional | 2025-07-26 |
| z-ai | z-ai/glm-4.5-air | Z.ai: GLM 4.5 Air | 131,072 | text->text | text | text | $0.1300 | $0.8500 | 11.1 | - | - | Optional | 2025-07-26 |
| z-ai | z-ai/glm-4.5v | Z.ai: GLM 4.5V | 65,536 | text+image->text | text,image | text | $0.6000 | $1.8000 | 7.6 | - | - | Optional | 2025-08-11 |
| z-ai | z-ai/glm-4.6 | Z.ai: GLM 4.6 | 204,800 | text->text | text | text | $0.5000 | $2.0000 | 18.5 | 45.8 | - | Optional | 2025-09-30 |
| z-ai | z-ai/glm-4.6v | Z.ai: GLM 4.6V | 131,072 | text+image+video->text | image,text,video | text | $0.3000 | $0.9000 | 11.2 | - | - | Optional | 2025-12-08 |
| z-ai | z-ai/glm-4.7 | Z.ai: GLM 4.7 | 204,800 | text->text | text | text | $0.6000 | $2.2000 | 22.2 | 45.3 | - | Default | 2025-12-22 |
| z-ai | z-ai/glm-4.7-flash | Z.ai: GLM 4.7 Flash | 200,000 | text->text | text | text | $0.0605 | $0.4000 | 14.9 | - | - | Default | 2026-01-19 |
| z-ai | z-ai/glm-5 | Z.ai: GLM 5 | 204,800 | text->text | text | text | $0.6000 | $1.9200 | 27.9 | - | - | Default | 2026-02-12 |
| z-ai | z-ai/glm-5-turbo | Z.ai: GLM 5 Turbo | 202,752 | text->text | text | text | $1.2000 | $4.0000 | 26.6 | - | - | Default | 2026-03-15 |
| z-ai | z-ai/glm-5.1 | Z.ai: GLM 5.1 | 204,800 | text->text | text | text | $0.9660 | $3.0360 | 26.1 | 55.8 | 23.9 | Default | 2026-04-08 |
| z-ai | z-ai/glm-5.2 | Z.ai: GLM 5.2 | 1,048,576 | text->text | text | text | $0.0600 | $7.0000 | 33.7 | 68.8 | 38.4 | Default | 2026-06-17 |
| z-ai | z-ai/glm-5.3 | Z.ai: GLM 5.3 | 1,048,576 | text->text | text | text | $0.0390 | $4.8000 | 44.8 | 74.8 | 53.1 | Mandatory | 2026-08-19 |
| z-ai | z-ai/glm-5.3:batch | Z.ai: GLM 5.3 (batch) | 1,048,576 | text->text | text | text | $0.4500 | $2.0000 | 44.8 | 74.8 | 53.1 | Mandatory | 2026-08-19 |
| z-ai | z-ai/glm-5.3-flash | Z.ai: GLM 5.3 Flash | 1,048,576 | text+image+video->text | text,image,video | text | $0.1500 | $0.5000 | 41.8 | 71.5 | 50.9 | Mandatory | 2026-08-26 |
| z-ai | z-ai/glm-5.3-flash:batch | Z.ai: GLM 5.3 Flash (batch) | 1,048,576 | text+image+video->text | text,image,video | text | $0.0600 | $0.2000 | 41.8 | 71.5 | 50.9 | Mandatory | 2026-08-26 |
| z-ai | z-ai/glm-5.3-flashx | Z.ai: GLM 5.3 FlashX | 1,048,576 | text+image+video->text | text,image,video | text | $0.3700 | $1.2500 | - | - | - | Mandatory | 2026-09-18 |
| z-ai | z-ai/glm-5.3-prime | Z.ai: GLM 5.3 Prime | 1,000,000 | text->text | text | text | $2.8000 | $8.8000 | - | - | - | Mandatory | 2026-09-24 |
| z-ai | z-ai/glm-5v-turbo | Z.ai: GLM 5V Turbo | 202,752 | text+image+video->text | image,text,video | text | $1.2000 | $4.0000 | 23.5 | - | - | Default | 2026-04-02 |
| ~anthropic | ~anthropic/claude-fable-latest | Anthropic: Claude Fable Latest | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | - | - | - | Mandatory | 2026-06-10 |
| ~anthropic | ~anthropic/claude-haiku-latest | Anthropic: Claude Haiku Latest | 1,000,000 | text+image+file->text | text,image,file | text | $0.1000 | $0.5000 | - | - | - | Optional | 2026-04-28 |
| ~anthropic | ~anthropic/claude-opus-latest | Anthropic: Claude Opus Latest | 1,000,000 | text+image+file->text | text,image,file | text | $4.0000 | $20.0000 | - | - | - | Mandatory | 2026-04-22 |
| ~anthropic | ~anthropic/claude-sonnet-latest | Anthropic: Claude Sonnet Latest | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | - | - | - | Mandatory | 2026-04-28 |
| ~deepseek | ~deepseek/deepseek-flash-latest | DeepSeek: DeepSeek Flash Latest | 1,048,576 | text+image->text | text,image | text | $0.0001 | $0.6000 | - | - | - | Default | 2026-09-14 |
| ~deepseek | ~deepseek/deepseek-pro-latest | DeepSeek: DeepSeek Pro Latest | 1,048,576 | text->text | text | text | $0.2191 | $0.6574 | - | - | - | Optional | 2026-09-14 |
| ~deepseek | ~deepseek/deepseek-v4-flash-latest | DeepSeek: DeepSeek V4 Flash Latest | 1,048,576 | text->text | text | text | $0.0168 | $1.2800 | - | - | - | Default | 2026-08-02 |
| ~google | ~google/gemini-flash-latest | Google: Gemini Flash Latest | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $3.7500 | - | - | - | Mandatory | 2026-04-28 |
| ~google | ~google/gemini-pro-latest | Google: Gemini Pro Latest | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-04-28 |
| ~moonshotai | ~moonshotai/kimi-latest | MoonshotAI: Kimi Latest | 1,048,576 | text+image+video->text | text,image,video | text | $0.3100 | $14.8900 | - | - | - | Default | 2026-04-28 |
| ~openai | ~openai/gpt-astra-latest | OpenAI: GPT Astra Latest | 1,050,000 | text+image+file->text | file,image,text | text | $10.0000 | $50.0000 | - | - | - | Mandatory | 2026-09-11 |
| ~openai | ~openai/gpt-luna-latest | OpenAI: GPT Luna Latest | 1,050,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.5000 | - | - | - | Default | 2026-09-11 |
| ~openai | ~openai/gpt-mini-latest | OpenAI: GPT Mini Latest | 400,000 | text+image+file->text | file,image,text | text | $0.7500 | $4.5000 | - | - | - | Optional | 2026-04-28 |
| ~openai | ~openai/gpt-sol-latest | OpenAI: GPT Sol Latest | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $10.0000 | - | - | - | Mandatory | 2026-09-11 |
| ~openai | ~openai/gpt-terra-latest | OpenAI: GPT Terra Latest | 1,050,000 | text+image+file->text | file,image,text | text | $2.0000 | $12.0000 | - | - | - | Default | 2026-09-11 |
| ~x-ai | ~x-ai/grok-latest | xAI: Grok Latest | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | - | - | - | Mandatory | 2026-07-08 |
| ~z-ai | ~z-ai/glm-flash-latest | Z.ai: GLM Flash Latest | 1,048,576 | text+image+video->text | text,image,video | text | $0.0400 | $0.5000 | - | - | - | Mandatory | 2026-08-27 |
| ~z-ai | ~z-ai/glm-latest | Z.ai: GLM Latest | 1,048,576 | text->text | text | text | $0.0390 | $4.8000 | - | - | - | Mandatory | 2026-08-19 |
