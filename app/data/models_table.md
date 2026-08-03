# OpenRouter Models Table

Total models: 367

| Provider | Model ID | Name | Context | Modality | Input | Output | Input $/M | Output $/M | Intel | Coding | Agentic | Reasoning | Created |
|----------|----------|------|---------|----------|------|-------|-----------|------------|-------|--------|---------|-----------|---------|
| ai21 | ai21/jamba-large-1.7 | AI21: Jamba Large 1.7 | 256,000 | text->text | text | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-08-09 |
| aion-labs | aion-labs/aion-2.0 | AionLabs: Aion-2.0 | 131,072 | text->text | text | text | $0.8000 | $1.6000 | - | - | - | Mandatory | 2026-02-24 |
| aion-labs | aion-labs/aion-3.0 | AionLabs: Aion-3.0 | 131,072 | text->text | text | text | $3.0000 | $6.0000 | - | - | - | Mandatory | 2026-07-08 |
| aion-labs | aion-labs/aion-3.0-mini | AionLabs: Aion-3.0-Mini | 131,072 | text->text | text | text | $0.7000 | $1.4000 | - | - | - | Mandatory | 2026-07-08 |
| aion-labs | aion-labs/aion-rp-llama-3.1-8b | AionLabs: Aion-RP 1.0 (8B) | 32,768 | text->text | text | text | $0.8000 | $1.6000 | - | - | - | Optional | 2025-02-05 |
| allenai | allenai/olmo-3-32b-think | AllenAI: Olmo 3 32B Think | 65,536 | text->text | text | text | $0.1500 | $0.5000 | - | - | - | Mandatory | 2025-11-22 |
| amazon | amazon/nova-2-lite-v1 | Amazon: Nova 2 Lite | 1,000,000 | text+image+file+video->text | text,image,video,file | text | $0.3000 | $2.5000 | 18.2 | 23 | 3.1 | Optional | 2025-12-03 |
| amazon | amazon/nova-lite-v1 | Amazon: Nova Lite 1.0 | 300,000 | text+image->text | text,image | text | $0.0600 | $0.2400 | - | - | - | Optional | 2024-12-06 |
| amazon | amazon/nova-micro-v1 | Amazon: Nova Micro 1.0 | 128,000 | text->text | text | text | $0.0350 | $0.1400 | - | - | - | Optional | 2024-12-06 |
| amazon | amazon/nova-premier-v1 | Amazon: Nova Premier 1.0 | 1,000,000 | text+image->text | text,image | text | $2.5000 | $12.5000 | - | - | - | Optional | 2025-11-01 |
| amazon | amazon/nova-pro-v1 | Amazon: Nova Pro 1.0 | 300,000 | text+image->text | text,image | text | $0.8000 | $3.2000 | - | - | - | Optional | 2024-12-06 |
| anthracite-org | anthracite-org/magnum-v4-72b | Magnum v4 72B | 16,384 | text->text | text | text | $3.0000 | $5.0000 | - | - | - | Optional | 2024-10-22 |
| anthropic | anthropic/claude-3-haiku | Anthropic: Claude 3 Haiku | 200,000 | text+image->text | text,image | text | $0.2500 | $1.2500 | - | - | - | Optional | 2024-03-13 |
| anthropic | anthropic/claude-fable-5 | Anthropic: Claude Fable 5 | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | 59.9 | 76.5 | 52.8 | Mandatory | 2026-06-09 |
| anthropic | anthropic/claude-fable-5:batch | Anthropic: Claude Fable 5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 59.9 | 76.5 | 52.8 | Mandatory | 2026-06-09 |
| anthropic | anthropic/claude-haiku-4.5 | Anthropic: Claude Haiku 4.5 | 200,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | 29.6 | 43.9 | 16.4 | Optional | 2025-10-16 |
| anthropic | anthropic/claude-haiku-4.5:batch | Anthropic: Claude Haiku 4.5 (batch) | 200,000 | text+image+file->text | text,image,file | text | $0.5000 | $2.5000 | 29.6 | 43.9 | 16.4 | Optional | 2025-10-16 |
| anthropic | anthropic/claude-opus-4 | Anthropic: Claude Opus 4 | 200,000 | text+image+file->text | image,text,file | text | $15.0000 | $75.0000 | - | - | - | Optional | 2025-05-23 |
| anthropic | anthropic/claude-opus-4.1 | Anthropic: Claude Opus 4.1 | 200,000 | text+image+file->text | image,text,file | text | $15.0000 | $75.0000 | - | - | - | Optional | 2025-08-06 |
| anthropic | anthropic/claude-opus-4.1:batch | Anthropic: Claude Opus 4.1 (batch) | 200,000 | text+image+file->text | image,text,file | text | $7.5000 | $37.5000 | - | - | - | Optional | 2025-08-06 |
| anthropic | anthropic/claude-opus-4.5 | Anthropic: Claude Opus 4.5 | 200,000 | text+image+file->text | file,image,text | text | $5.0000 | $25.0000 | - | - | - | Optional | 2025-11-25 |
| anthropic | anthropic/claude-opus-4.5:batch | Anthropic: Claude Opus 4.5 (batch) | 200,000 | text+image+file->text | file,image,text | text | $2.5000 | $12.5000 | - | - | - | Optional | 2025-11-25 |
| anthropic | anthropic/claude-opus-4.6 | Anthropic: Claude Opus 4.6 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | - | - | - | Optional | 2026-02-04 |
| anthropic | anthropic/claude-opus-4.6:batch | Anthropic: Claude Opus 4.6 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | - | - | - | Optional | 2026-02-04 |
| anthropic | anthropic/claude-opus-4.7 | Anthropic: Claude Opus 4.7 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 53.5 | 73.6 | 44.4 | Optional | 2026-04-16 |
| anthropic | anthropic/claude-opus-4.7-fast | Anthropic: Claude Opus 4.7 (Fast) | 1,000,000 | text+image+file->text | text,image,file | text | $30.0000 | $150.0000 | - | - | - | Optional | 2026-05-13 |
| anthropic | anthropic/claude-opus-4.7:batch | Anthropic: Claude Opus 4.7 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 53.5 | 73.6 | 44.4 | Optional | 2026-04-16 |
| anthropic | anthropic/claude-opus-4.8 | Anthropic: Claude Opus 4.8 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 55.7 | 74.3 | 47.2 | Optional | 2026-05-28 |
| anthropic | anthropic/claude-opus-4.8-fast | Anthropic: Claude Opus 4.8 (Fast) | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | - | - | - | Optional | 2026-05-28 |
| anthropic | anthropic/claude-opus-4.8:batch | Anthropic: Claude Opus 4.8 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $2.5000 | $12.5000 | 55.7 | 74.3 | 47.2 | Optional | 2026-05-28 |
| anthropic | anthropic/claude-sonnet-4 | Anthropic: Claude Sonnet 4 | 1,000,000 | text+image+file->text | image,text,file | text | $3.0000 | $15.0000 | 28.9 | 37.6 | 16.6 | Optional | 2025-05-23 |
| anthropic | anthropic/claude-sonnet-4.5 | Anthropic: Claude Sonnet 4.5 | 1,000,000 | text+image+file->text | text,image,file | text | $3.0000 | $15.0000 | 36.4 | 52.1 | 24.6 | Optional | 2025-09-30 |
| anthropic | anthropic/claude-sonnet-4.5:batch | Anthropic: Claude Sonnet 4.5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.5000 | $7.5000 | 36.4 | 52.1 | 24.6 | Optional | 2025-09-30 |
| anthropic | anthropic/claude-sonnet-4.6 | Anthropic: Claude Sonnet 4.6 | 1,000,000 | text+image+file->text | text,image,file | text | $3.0000 | $15.0000 | 47.2 | 63 | 40.8 | Optional | 2026-02-17 |
| anthropic | anthropic/claude-sonnet-5 | Anthropic: Claude Sonnet 5 | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | 53.4 | 71.5 | 46.7 | Default | 2026-07-01 |
| anthropic | anthropic/claude-sonnet-5:batch | Anthropic: Claude Sonnet 5 (batch) | 1,000,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | 53.4 | 71.5 | 46.7 | Default | 2026-07-01 |
| anthropic | anthropic/claude-opus-5 | Claude Opus 5 | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | 60.7 | 78 | 55.3 | Default | 2026-07-25 |
| anthropic | anthropic/claude-opus-5-fast | Claude Opus 5 (Fast) | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | - | - | - | Default | 2026-07-25 |
| arcee-ai | arcee-ai/trinity-large-thinking | Arcee AI: Trinity Large Thinking | 262,144 | text->text | text | text | $0.2200 | $0.8500 | 18.2 | 25.8 | 3.7 | Mandatory | 2026-04-01 |
| arcee-ai | arcee-ai/virtuoso-large | Arcee AI: Virtuoso Large | 131,072 | text->text | text | text | $0.7500 | $1.2000 | - | - | - | Optional | 2025-05-06 |
| baidu | baidu/ernie-4.5-vl-424b-a47b | Baidu: ERNIE 4.5 VL 424B A47B  | 123,000 | text+image->text | image,text | text | $0.4200 | $1.2500 | - | - | - | Optional | 2025-07-01 |
| bytedance | bytedance/ui-tars-1.5-7b | ByteDance: UI-TARS 7B  | 128,000 | text+image->text | image,text | text | $0.1000 | $0.2000 | - | - | - | Optional | 2025-07-23 |
| bytedance-seed | bytedance-seed/seed-1.6 | ByteDance Seed: Seed 1.6 | 262,144 | text+image+video->text | image,text,video | text | $0.2500 | $2.0000 | - | - | - | Optional | 2025-12-23 |
| bytedance-seed | bytedance-seed/seed-1.6-flash | ByteDance Seed: Seed 1.6 Flash | 262,144 | text+image+video->text | image,text,video | text | $0.0750 | $0.3000 | - | - | - | Optional | 2025-12-23 |
| bytedance-seed | bytedance-seed/seed-2.0-lite | ByteDance Seed: Seed-2.0-Lite | 262,144 | text+image+video->text | text,image,video | text | $0.2500 | $2.0000 | - | - | - | Optional | 2026-03-10 |
| bytedance-seed | bytedance-seed/seed-2.0-mini | ByteDance Seed: Seed-2.0-Mini | 262,144 | text+image+video->text | text,image,video | text | $0.1000 | $0.4000 | - | - | - | Optional | 2026-02-27 |
| cognitivecomputations | cognitivecomputations/dolphin-mistral-24b-venice-edition | Venice: Uncensored | 128,000 | text->text | text | text | $0.2000 | $0.9000 | - | - | - | Optional | 2025-07-10 |
| cohere | cohere/command-a | Cohere: Command A | 256,000 | text->text | text | text | $2.5000 | $10.0000 | 22.5 | 27.8 | 9.2 | Optional | 2025-03-14 |
| cohere | cohere/command-r-08-2024 | Cohere: Command R (08-2024) | 128,000 | text->text | text | text | $0.1500 | $0.6000 | - | - | - | Optional | 2024-08-30 |
| cohere | cohere/command-r-plus-08-2024 | Cohere: Command R+ (08-2024) | 128,000 | text->text | text | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-08-30 |
| cohere | cohere/command-r7b-12-2024 | Cohere: Command R7B (12-2024) | 128,000 | text->text | text | text | $0.0375 | $0.1500 | - | - | - | Optional | 2024-12-14 |
| cohere | cohere/north-mini-code:free | Cohere: North Mini Code (free) | 256,000 | text->text | text | text | $0.0000 | $0.0000 | 19.8 | 36.5 | 3.1 | Optional | 2026-06-18 |
| deepcogito | deepcogito/cogito-v2.1-671b | Deep Cogito: Cogito v2.1 671B | 128,000 | text->text | text | text | $1.2500 | $1.2500 | - | - | - | Optional | 2025-11-14 |
| deepseek | deepseek/deepseek-chat | DeepSeek: DeepSeek V3 | 163,840 | text->text | text | text | $0.2574 | $1.0287 | - | - | - | Optional | 2024-12-27 |
| deepseek | deepseek/deepseek-chat-v3-0324 | DeepSeek: DeepSeek V3 0324 | 163,840 | text->text | text | text | $0.2700 | $1.1200 | 15.4 | 21.2 | 1.5 | Optional | 2025-03-24 |
| deepseek | deepseek/deepseek-chat-v3.1 | DeepSeek: DeepSeek V3.1 | 163,840 | text->text | text | text | $0.2500 | $0.9500 | - | - | - | Optional | 2025-08-21 |
| deepseek | deepseek/deepseek-v3.1-terminus | DeepSeek: DeepSeek V3.1 Terminus | 163,840 | text->text | text | text | $0.2700 | $1.0000 | 30.4 | 43.5 | 18.1 | Optional | 2025-09-22 |
| deepseek | deepseek/deepseek-v3.2 | DeepSeek: DeepSeek V3.2 | 163,840 | text->text | text | text | $0.2690 | $0.4000 | 32 | 44.2 | 18.3 | Optional | 2025-12-01 |
| deepseek | deepseek/deepseek-v3.2-exp | DeepSeek: DeepSeek V3.2 Exp | 163,840 | text->text | text | text | $0.2700 | $0.4100 | - | - | - | Optional | 2025-09-29 |
| deepseek | deepseek/deepseek-v4-flash | DeepSeek: DeepSeek V4 Flash | 1,048,576 | text->text | text | text | $0.1400 | $0.2800 | 40.3 | 56.2 | 31.1 | Optional | 2026-04-24 |
| deepseek | deepseek/deepseek-v4-pro | DeepSeek: DeepSeek V4 Pro | 1,048,576 | text->text | text | text | $0.4350 | $0.8700 | 44.3 | 59.4 | 36.4 | Optional | 2026-04-24 |
| deepseek | deepseek/deepseek-r1 | DeepSeek: R1 | 163,840 | text->text | text | text | $0.7000 | $2.5000 | 18.5 | 24.6 | 3.1 | Mandatory | 2025-01-20 |
| deepseek | deepseek/deepseek-r1-0528 | DeepSeek: R1 0528 | 163,840 | text->text | text | text | $0.5000 | $2.1500 | - | - | - | Mandatory | 2025-05-29 |
| deepseek | deepseek/deepseek-r1-distill-llama-70b | DeepSeek: R1 Distill Llama 70B | 8,192 | text->text | text | text | $0.8000 | $0.8000 | - | - | - | Optional | 2025-01-24 |
| google | google/gemini-2.5-flash | Google: Gemini 2.5 Flash | 1,048,576 | text+image+file+audio+video->text | file,image,text,audio,video | text | $0.3000 | $2.5000 | - | - | - | Optional | 2025-06-17 |
| google | google/gemini-2.5-flash:batch | Google: Gemini 2.5 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | file,image,text,audio,video | text | $0.1500 | $1.2500 | - | - | - | Optional | 2025-06-17 |
| google | google/gemini-2.5-flash-lite | Google: Gemini 2.5 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.1000 | $0.4000 | - | - | - | Optional | 2025-07-23 |
| google | google/gemini-2.5-flash-lite:batch | Google: Gemini 2.5 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.0500 | $0.2000 | - | - | - | Optional | 2025-07-23 |
| google | google/gemini-2.5-pro | Google: Gemini 2.5 Pro | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $1.2500 | $10.0000 | 25.8 | 33.3 | 7.1 | Mandatory | 2025-06-17 |
| google | google/gemini-2.5-pro:batch | Google: Gemini 2.5 Pro (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.6250 | $5.0000 | 25.8 | 33.3 | 7.1 | Mandatory | 2025-06-17 |
| google | google/gemini-2.5-pro-preview-05-06 | Google: Gemini 2.5 Pro Preview 05-06 | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-05-07 |
| google | google/gemini-2.5-pro-preview | Google: Gemini 2.5 Pro Preview 06-05 | 1,048,576 | text+image+file+audio->text | file,image,text,audio | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-06-05 |
| google | google/gemini-3-flash-preview | Google: Gemini 3 Flash Preview | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.5000 | $3.0000 | - | - | - | Optional | 2025-12-17 |
| google | google/gemini-3-flash-preview:batch | Google: Gemini 3 Flash Preview (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,file,audio,video | text | $0.2500 | $1.5000 | - | - | - | Optional | 2025-12-17 |
| google | google/gemini-3.1-flash-lite | Google: Gemini 3.1 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.2500 | $1.5000 | - | - | - | Default | 2026-05-07 |
| google | google/gemini-3.1-flash-lite:batch | Google: Gemini 3.1 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.1250 | $0.7500 | - | - | - | Default | 2026-05-07 |
| google | google/gemini-3.1-flash-lite-preview | Google: Gemini 3.1 Flash Lite Preview | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.2500 | $1.5000 | 25 | 34.7 | 6.2 | Default | 2026-03-03 |
| google | google/gemini-3.1-pro-preview | Google: Gemini 3.1 Pro Preview | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $2.0000 | $12.0000 | 46.5 | 68.8 | 21.4 | Mandatory | 2026-02-19 |
| google | google/gemini-3.1-pro-preview:batch | Google: Gemini 3.1 Pro Preview (batch) | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $1.0000 | $6.0000 | 46.5 | 68.8 | 21.4 | Mandatory | 2026-02-19 |
| google | google/gemini-3.1-pro-preview-customtools | Google: Gemini 3.1 Pro Preview Custom Tools | 1,048,576 | text+image+file+audio+video->text | text,audio,image,video,file | text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-02-26 |
| google | google/gemini-3.5-flash | Google: Gemini 3.5 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $1.5000 | $9.0000 | 50.2 | 70.1 | 37.4 | Mandatory | 2026-05-19 |
| google | google/gemini-3.5-flash:batch | Google: Gemini 3.5 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $4.5000 | 50.2 | 70.1 | 37.4 | Mandatory | 2026-05-19 |
| google | google/gemini-3.5-flash-lite | Google: Gemini 3.5 Flash Lite | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.3000 | $2.5000 | 36.5 | 49.3 | 26.8 | Mandatory | 2026-07-21 |
| google | google/gemini-3.5-flash-lite:batch | Google: Gemini 3.5 Flash Lite (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.1500 | $1.2500 | 36.5 | 49.3 | 26.8 | Mandatory | 2026-07-21 |
| google | google/gemini-3.6-flash | Google: Gemini 3.6 Flash | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $1.5000 | $7.5000 | 50.1 | 69.2 | 38.7 | Mandatory | 2026-07-21 |
| google | google/gemini-3.6-flash:batch | Google: Gemini 3.6 Flash (batch) | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $0.7500 | $3.7500 | 50.1 | 69.2 | 38.7 | Mandatory | 2026-07-21 |
| google | google/gemma-2-27b-it | Google: Gemma 2 27B | 8,192 | text->text | text | text | $0.6500 | $0.6500 | - | - | - | Optional | 2024-07-13 |
| google | google/gemma-3-12b-it | Google: Gemma 3 12B | 131,072 | text+image->text | text,image | text | $0.0500 | $0.1500 | 5.5 | 5.8 | 0.3 | Optional | 2025-03-14 |
| google | google/gemma-3-27b-it | Google: Gemma 3 27B | 262,144 | text+image->text | text,image | text | $0.0800 | $0.4500 | 7.4 | 10.1 | 0.3 | Optional | 2025-03-12 |
| google | google/gemma-3-4b-it | Google: Gemma 3 4B | 131,072 | text+image->text | text,image | text | $0.0500 | $0.1000 | - | 2.7 | - | Optional | 2025-03-14 |
| google | google/gemma-3n-e4b-it | Google: Gemma 3n 4B | 32,768 | text->text | text | text | $0.0600 | $0.1200 | - | 3.2 | - | Optional | 2025-05-21 |
| google | google/gemma-4-26b-a4b-it | Google: Gemma 4 26B A4B  | 262,144 | text+image+video->text | image,text,video | text | $0.0700 | $0.3400 | 25.7 | 39.3 | 11 | Optional | 2026-04-03 |
| google | google/gemma-4-26b-a4b-it:free | Google: Gemma 4 26B A4B  (free) | 262,144 | text+image+video->text | image,text,video | text | $0.0000 | $0.0000 | 25.7 | 39.3 | 11 | Optional | 2026-04-03 |
| google | google/gemma-4-31b-it | Google: Gemma 4 31B | 262,144 | text+image+video->text | image,text,video | text | $0.1000 | $0.3400 | 29.4 | 43.4 | 14.4 | Optional | 2026-04-03 |
| google | google/gemma-4-31b-it:free | Google: Gemma 4 31B (free) | 262,144 | text+image+video->text | image,text,video | text | $0.0000 | $0.0000 | 29.4 | 43.4 | 14.4 | Optional | 2026-04-03 |
| google | google/lyria-3-clip-preview | Google: Lyria 3 Clip Preview | 1,048,576 | text+image->text+audio | text,image | text,audio | $0.0000 | $0.0000 | - | - | - | Optional | 2026-03-31 |
| google | google/lyria-3-pro-preview | Google: Lyria 3 Pro Preview | 1,048,576 | text+image->text+audio | text,image | text,audio | $0.0000 | $0.0000 | - | - | - | Optional | 2026-03-31 |
| google | google/gemini-2.5-flash-image | Google: Nano Banana (Gemini 2.5 Flash Image) | 32,768 | text+image->text+image | image,text | image,text | $0.3000 | $2.5000 | - | - | - | Optional | 2025-10-08 |
| google | google/gemini-3.1-flash-image-preview | Google: Nano Banana 2 (Gemini 3.1 Flash Image Preview) | 65,536 | text+image->text+image | image,text | image,text | $0.5000 | $3.0000 | - | - | - | Default | 2026-02-26 |
| google | google/gemini-3.1-flash-image | Google: Nano Banana 2 (Gemini 3.1 Flash Image) | 131,072 | text+image->text+image | image,text | image,text | $0.5000 | $3.0000 | - | - | - | Default | 2026-06-18 |
| google | google/gemini-3.1-flash-lite-image | Google: Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image) | 65,536 | text+image->text+image | image,text | image,text | $0.2500 | $1.5000 | - | - | - | Default | 2026-07-01 |
| google | google/gemini-3-pro-image-preview | Google: Nano Banana Pro (Gemini 3 Pro Image Preview) | 65,536 | text+image->text+image | image,text | image,text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2025-11-20 |
| google | google/gemini-3-pro-image | Google: Nano Banana Pro (Gemini 3 Pro Image) | 131,072 | text+image->text+image | image,text | image,text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-06-18 |
| gryphe | gryphe/mythomax-l2-13b | MythoMax 13B | 8,192 | text->text | text | text | $0.0600 | $0.0600 | - | - | - | Optional | 2023-07-02 |
| ibm-granite | ibm-granite/granite-4.0-h-micro | IBM: Granite 4.0 Micro | 131,000 | text->text | text | text | $0.0170 | $0.1120 | - | - | - | Optional | 2025-10-20 |
| ibm-granite | ibm-granite/granite-4.1-8b | IBM: Granite 4.1 8B | 131,072 | text->text | text | text | $0.0500 | $0.1000 | - | 9.5 | - | Optional | 2026-05-01 |
| inception | inception/mercury-2 | Inception: Mercury 2 | 128,000 | text->text | text | text | $0.2500 | $0.7500 | 21.4 | 31.1 | 9.6 | Default | 2026-03-04 |
| inclusionai | inclusionai/ling-3.0-flash:free | Ling-3.0-flash (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-07-23 |
| inclusionai | inclusionai/ling-2.6-1t | inclusionAI: Ling-2.6-1T | 262,144 | text->text | text | text | $0.0750 | $0.6250 | - | - | - | Optional | 2026-04-23 |
| inclusionai | inclusionai/ling-2.6-flash | inclusionAI: Ling-2.6-flash | 262,144 | text->text | text | text | $0.0100 | $0.0300 | 14.1 | 25.3 | 2.3 | Optional | 2026-04-22 |
| inclusionai | inclusionai/ring-2.6-1t | inclusionAI: Ring-2.6-1T | 262,144 | text->text | text | text | $0.0750 | $0.6250 | 30.6 | 42.8 | 18.9 | Mandatory | 2026-05-08 |
| kwaipilot | kwaipilot/kat-coder-air-v2.5 | Kwaipilot: KAT-Coder-Air V2.5 | 256,000 | text->text | text | text | $0.1500 | $0.6000 | - | - | - | Optional | 2026-07-11 |
| kwaipilot | kwaipilot/kat-coder-pro-v2 | Kwaipilot: KAT-Coder-Pro V2 | 262,144 | text->text | text | text | $0.3000 | $1.2000 | 33.7 | 59.5 | 15.5 | Optional | 2026-03-28 |
| kwaipilot | kwaipilot/kat-coder-pro-v2.5 | Kwaipilot: KAT-Coder-Pro V2.5 | 256,000 | text->text | text | text | $0.7400 | $2.9600 | - | - | - | Optional | 2026-07-11 |
| mancer | mancer/weaver | Mancer: Weaver (alpha) | 8,000 | text->text | text | text | $0.5000 | $0.7500 | - | - | - | Optional | 2023-08-02 |
| meituan | meituan/longcat-2.0 | Meituan: LongCat 2.0 | 1,048,756 | text->text | text | text | $0.3000 | $1.2000 | - | - | - | Default | 2026-07-20 |
| meta | meta/muse-spark-1.1 | Meta: Muse Spark 1.1 | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $1.2500 | $4.2500 | 50.6 | 71.3 | 37.5 | Mandatory | 2026-07-16 |
| meta-llama | meta-llama/llama-3.1-70b-instruct | Meta: Llama 3.1 70B Instruct | 131,072 | text->text | text | text | $0.4000 | $0.4000 | - | - | - | Optional | 2024-07-23 |
| meta-llama | meta-llama/llama-3.1-8b-instruct | Meta: Llama 3.1 8B Instruct | 131,072 | text->text | text | text | $0.0500 | $0.0800 | 7.6 | 5.4 | 0.5 | Optional | 2024-07-23 |
| meta-llama | meta-llama/llama-3.2-1b-instruct | Meta: Llama 3.2 1B Instruct | 60,000 | text->text | text | text | $0.0270 | $0.2010 | - | - | - | Optional | 2024-09-25 |
| meta-llama | meta-llama/llama-3.2-3b-instruct | Meta: Llama 3.2 3B Instruct | 131,072 | text->text | text | text | $0.0500 | $0.3300 | - | - | - | Optional | 2024-09-25 |
| meta-llama | meta-llama/llama-3.3-70b-instruct | Meta: Llama 3.3 70B Instruct | 131,072 | text->text | text | text | $0.1300 | $0.4000 | 9.4 | 11.9 | 0.3 | Optional | 2024-12-07 |
| meta-llama | meta-llama/llama-4-maverick | Meta: Llama 4 Maverick | 1,048,576 | text+image->text | text,image | text | $0.2000 | $0.8000 | 14.3 | 16.3 | 1.3 | Optional | 2025-04-06 |
| meta-llama | meta-llama/llama-4-scout | Meta: Llama 4 Scout | 1,310,720 | text+image->text | text,image | text | $0.1000 | $0.3000 | 10 | 8.2 | 1.1 | Optional | 2025-04-06 |
| meta-llama | meta-llama/llama-guard-4-12b | Meta: Llama Guard 4 12B | 1,048,576 | text+image->text | image,text | text | $0.1800 | $0.1800 | - | - | - | Optional | 2025-04-30 |
| microsoft | microsoft/phi-4 | Microsoft: Phi 4 | 16,384 | text->text | text | text | $0.0700 | $0.1400 | - | - | - | Optional | 2025-01-10 |
| microsoft | microsoft/wizardlm-2-8x22b | WizardLM-2 8x22B | 65,535 | text->text | text | text | $0.6200 | $0.6200 | - | - | - | Optional | 2024-04-16 |
| minimax | minimax/minimax-m1 | MiniMax: MiniMax M1 | 1,000,000 | text->text | text | text | $0.5500 | $2.2000 | - | - | - | Optional | 2025-06-18 |
| minimax | minimax/minimax-m2 | MiniMax: MiniMax M2 | 204,800 | text->text | text | text | $0.2550 | $1.0200 | - | - | - | Mandatory | 2025-10-24 |
| minimax | minimax/minimax-m2-her | MiniMax: MiniMax M2-her | 65,536 | text->text | text | text | $0.3000 | $1.2000 | - | - | - | Optional | 2026-01-23 |
| minimax | minimax/minimax-m2.1 | MiniMax: MiniMax M2.1 | 204,800 | text->text | text | text | $0.3000 | $1.2000 | - | - | - | Mandatory | 2025-12-23 |
| minimax | minimax/minimax-m2.5 | MiniMax: MiniMax M2.5 | 204,800 | text->text | text | text | $0.1500 | $0.9000 | - | - | - | Mandatory | 2026-02-12 |
| minimax | minimax/minimax-m2.7 | MiniMax: MiniMax M2.7 | 204,800 | text->text | text | text | $0.2500 | $1.0000 | 38.1 | 52.6 | 25.6 | Mandatory | 2026-03-18 |
| minimax | minimax/minimax-m3 | MiniMax: MiniMax M3 | 1,048,576 | text+image+video->text | text,image,video | text | $0.3000 | $1.2000 | 44.4 | 58.6 | 35.4 | Optional | 2026-06-01 |
| minimax | minimax/minimax-m3:batch | MiniMax: MiniMax M3 (batch) | 524,288 | text+image+video->text | text,image,video | text | $0.1500 | $0.6000 | 44.4 | 58.6 | 35.4 | Optional | 2026-06-01 |
| minimax | minimax/minimax-01 | MiniMax: MiniMax-01 | 1,000,192 | text+image->text | text,image | text | $0.2000 | $1.1000 | - | - | - | Optional | 2025-01-15 |
| mistralai | mistralai/mistral-large | Mistral Large | 128,000 | text+file->text | text,file | text | $2.0000 | $6.0000 | - | - | - | Optional | 2024-02-26 |
| mistralai | mistralai/mistral-large-2407 | Mistral Large 2407 | 131,072 | text+file->text | text,file | text | $2.0000 | $6.0000 | - | - | - | Optional | 2024-11-19 |
| mistralai | mistralai/codestral-2508 | Mistral: Codestral 2508 | 256,000 | text+file->text | text,file | text | $0.3000 | $0.9000 | - | - | - | Optional | 2025-08-02 |
| mistralai | mistralai/devstral-2512 | Mistral: Devstral 2 2512 | 262,144 | text+file->text | text,file | text | $0.4000 | $2.0000 | 19.2 | 31.3 | 10.6 | Optional | 2025-12-09 |
| mistralai | mistralai/ministral-14b-2512 | Mistral: Ministral 3 14B 2512 | 262,144 | text+image->text | text,image | text | $0.2000 | $0.2000 | 11.1 | 14.4 | 2.2 | Optional | 2025-12-02 |
| mistralai | mistralai/ministral-3b-2512 | Mistral: Ministral 3 3B 2512 | 131,072 | text+image->text | text,image | text | $0.1000 | $0.1000 | 6.3 | 4.8 | 1.6 | Optional | 2025-12-02 |
| mistralai | mistralai/ministral-8b-2512 | Mistral: Ministral 3 8B 2512 | 262,144 | text+image->text | text,image | text | $0.1500 | $0.1500 | 9 | 9.7 | 1.2 | Optional | 2025-12-02 |
| mistralai | mistralai/mistral-large-2512 | Mistral: Mistral Large 3 2512 | 262,144 | text+image+file->text | text,image,file | text | $0.5000 | $1.5000 | 15.9 | 20.1 | 5.5 | Optional | 2025-12-02 |
| mistralai | mistralai/mistral-medium-3 | Mistral: Mistral Medium 3 | 131,072 | text+image+file->text | text,image,file | text | $0.4000 | $2.0000 | - | - | - | Optional | 2025-05-07 |
| mistralai | mistralai/mistral-medium-3.1 | Mistral: Mistral Medium 3.1 | 131,072 | text+image+file->text | text,image,file | text | $0.4000 | $2.0000 | 14.7 | 20.5 | 6.2 | Optional | 2025-08-13 |
| mistralai | mistralai/mistral-medium-3-5 | Mistral: Mistral Medium 3.5 | 262,144 | text+image+file->text | text,image,file | text | $1.5000 | $7.5000 | 29.9 | 46.9 | 19 | Optional | 2026-05-01 |
| mistralai | mistralai/mistral-nemo | Mistral: Mistral Nemo | 131,072 | text->text | text | text | $0.0190 | $0.0300 | - | - | - | Optional | 2024-07-19 |
| mistralai | mistralai/mistral-small-24b-instruct-2501 | Mistral: Mistral Small 3 | 32,768 | text->text | text | text | $0.0500 | $0.0800 | - | - | - | Optional | 2025-01-31 |
| mistralai | mistralai/mistral-small-3.1-24b-instruct | Mistral: Mistral Small 3.1 24B | 128,000 | text+image->text | text,image | text | $0.3510 | $0.5550 | - | - | - | Optional | 2025-03-18 |
| mistralai | mistralai/mistral-small-3.2-24b-instruct | Mistral: Mistral Small 3.2 24B | 256,000 | text+image->text | image,text | text | $0.1000 | $0.3000 | - | - | - | Optional | 2025-06-21 |
| mistralai | mistralai/mistral-small-2603 | Mistral: Mistral Small 4 | 262,144 | text+image->text | text,image | text | $0.1500 | $0.6000 | 19.6 | 26.6 | 4.7 | Optional | 2026-03-17 |
| mistralai | mistralai/mixtral-8x22b-instruct | Mistral: Mixtral 8x22B Instruct | 65,536 | text+file->text | text,file | text | $2.0000 | $6.0000 | - | - | - | Optional | 2024-04-17 |
| mistralai | mistralai/mistral-saba | Mistral: Saba | 32,768 | text+file->text | text,file | text | $0.2000 | $0.6000 | - | - | - | Optional | 2025-02-17 |
| mistralai | mistralai/voxtral-small-24b-2507 | Mistral: Voxtral Small 24B 2507 | 32,000 | text+file+audio->text | text,audio,file | text | $0.1000 | $0.3000 | - | - | - | Optional | 2025-10-30 |
| moonshotai | moonshotai/kimi-k2 | MoonshotAI: Kimi K2 0711 | 131,072 | text->text | text | text | $0.5700 | $2.3000 | - | - | - | Optional | 2025-07-12 |
| moonshotai | moonshotai/kimi-k2-0905 | MoonshotAI: Kimi K2 0905 | 262,144 | text->text | text | text | $0.6000 | $2.5000 | - | - | - | Optional | 2025-09-05 |
| moonshotai | moonshotai/kimi-k2-thinking | MoonshotAI: Kimi K2 Thinking | 262,144 | text->text | text | text | $0.6000 | $2.5000 | 17.3 | 21 | 1.8 | Mandatory | 2025-11-06 |
| moonshotai | moonshotai/kimi-k2.5 | MoonshotAI: Kimi K2.5 | 262,144 | text+image->text | text,image | text | $0.5700 | $2.8500 | 35.4 | 46.8 | 21.7 | Default | 2026-01-27 |
| moonshotai | moonshotai/kimi-k2.6 | MoonshotAI: Kimi K2.6 | 262,144 | text+image->text | text,image | text | $0.6460 | $2.7200 | 44.2 | 61.8 | 30.3 | Default | 2026-04-20 |
| moonshotai | moonshotai/kimi-k2.7-code | MoonshotAI: Kimi K2.7 Code | 262,144 | text+image->text | text,image | text | $0.7300 | $3.5000 | 41.9 | 60.8 | 29.6 | Mandatory | 2026-06-12 |
| moonshotai | moonshotai/kimi-k3 | MoonshotAI: Kimi K3 | 1,048,576 | text+image->text | text,image | text | $3.0000 | $15.0000 | 57.1 | 76.2 | 50.1 | Default | 2026-07-16 |
| morph | morph/morph-v3-fast | Morph: Morph V3 Fast | 81,920 | text->text | text | text | $0.8000 | $1.2000 | - | - | - | Optional | 2025-07-08 |
| morph | morph/morph-v3-large | Morph: Morph V3 Large | 262,144 | text->text | text | text | $0.9000 | $1.9000 | - | - | - | Optional | 2025-07-08 |
| nex-agi | nex-agi/nex-n2-mini | Nex AGI: Nex-N2-Mini | 262,144 | text+image->text | text,image | text | $0.0250 | $0.1000 | - | - | - | Optional | 2026-06-24 |
| nex-agi | nex-agi/nex-n2-pro | Nex AGI: Nex-N2-Pro | 262,144 | text+image->text | text,image | text | $0.2500 | $1.0000 | 41 | 59.1 | 31 | Optional | 2026-06-09 |
| nousresearch | nousresearch/hermes-3-llama-3.1-405b | Nous: Hermes 3 405B Instruct | 131,072 | text->text | text | text | $1.0000 | $1.0000 | - | - | - | Optional | 2024-08-16 |
| nousresearch | nousresearch/hermes-3-llama-3.1-70b | Nous: Hermes 3 70B Instruct | 131,072 | text->text | text | text | $0.7000 | $0.7000 | - | - | - | Optional | 2024-08-18 |
| nousresearch | nousresearch/hermes-4-405b | Nous: Hermes 4 405B | 131,072 | text->text | text | text | $1.0000 | $3.0000 | - | - | - | Optional | 2025-08-27 |
| nousresearch | nousresearch/hermes-4-70b | Nous: Hermes 4 70B | 131,072 | text->text | text | text | $0.1300 | $0.4000 | - | - | - | Optional | 2025-08-27 |
| nvidia | nvidia/nemotron-3-nano-30b-a3b | NVIDIA: Nemotron 3 Nano 30B A3B | 262,144 | text->text | text | text | $0.0500 | $0.2000 | 14.2 | 14.4 | 2 | Optional | 2025-12-15 |
| nvidia | nvidia/nemotron-3-nano-30b-a3b:free | NVIDIA: Nemotron 3 Nano 30B A3B (free) | 256,000 | text->text | text | text | $0.0000 | $0.0000 | 14.2 | 14.4 | 2 | Optional | 2025-12-15 |
| nvidia | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | NVIDIA: Nemotron 3 Nano Omni (free) | 256,000 | text+image+audio+video->text | text,audio,image,video | text | $0.0000 | $0.0000 | - | 13.8 | - | Default | 2026-04-29 |
| nvidia | nvidia/nemotron-3-super-120b-a12b | NVIDIA: Nemotron 3 Super | 1,000,000 | text->text | text | text | $0.0850 | $0.4000 | 25.4 | 37.7 | 8.7 | Default | 2026-03-12 |
| nvidia | nvidia/nemotron-3-super-120b-a12b:free | NVIDIA: Nemotron 3 Super (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | 25.4 | 37.7 | 8.7 | Default | 2026-03-12 |
| nvidia | nvidia/nemotron-3-ultra-550b-a55b | NVIDIA: Nemotron 3 Ultra | 512,288 | text->text | text | text | $0.6000 | $3.6000 | 37.8 | 49.3 | 27.4 | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3-ultra-550b-a55b:free | NVIDIA: Nemotron 3 Ultra (free) | 1,000,000 | text->text | text | text | $0.0000 | $0.0000 | 37.8 | 49.3 | 27.4 | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-3.5-content-safety:free | NVIDIA: Nemotron 3.5 Content Safety (free) | 128,000 | text+image->text | text,image | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-06-04 |
| nvidia | nvidia/nemotron-nano-12b-v2-vl:free | NVIDIA: Nemotron Nano 12B 2 VL (free) | 128,000 | text+image+video->text | image,text,video | text | $0.0000 | $0.0000 | - | - | - | Optional | 2025-10-29 |
| nvidia | nvidia/nemotron-nano-9b-v2:free | NVIDIA: Nemotron Nano 9B V2 (free) | 128,000 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Optional | 2025-09-06 |
| openai | openai/gpt-audio | OpenAI: GPT Audio | 128,000 | text+audio->text+audio | text,audio | text,audio | $2.5000 | $10.0000 | - | - | - | Optional | 2026-01-20 |
| openai | openai/gpt-audio-mini | OpenAI: GPT Audio Mini | 128,000 | text+audio->text+audio | text,audio | text,audio | $0.6000 | $2.4000 | - | - | - | Optional | 2026-01-20 |
| openai | openai/gpt-chat-latest | OpenAI: GPT Chat Latest | 400,000 | text+image+file->text | text,image,file | text | $5.0000 | $30.0000 | - | - | - | Optional | 2026-05-06 |
| openai | openai/gpt-3.5-turbo | OpenAI: GPT-3.5 Turbo | 16,385 | text->text | text | text | $0.5000 | $1.5000 | - | 10.7 | - | Optional | 2023-05-28 |
| openai | openai/gpt-3.5-turbo-0613 | OpenAI: GPT-3.5 Turbo (older v0613) | 4,095 | text->text | text | text | $1.0000 | $2.0000 | - | - | - | Optional | 2024-01-25 |
| openai | openai/gpt-3.5-turbo-16k | OpenAI: GPT-3.5 Turbo 16k | 16,385 | text->text | text | text | $3.0000 | $4.0000 | - | - | - | Optional | 2023-08-28 |
| openai | openai/gpt-3.5-turbo-instruct | OpenAI: GPT-3.5 Turbo Instruct | 4,095 | text->text | text | text | $1.5000 | $2.0000 | - | - | - | Optional | 2023-09-28 |
| openai | openai/gpt-4 | OpenAI: GPT-4 | 8,191 | text->text | text | text | $30.0000 | $60.0000 | - | 13.1 | - | Optional | 2023-05-28 |
| openai | openai/gpt-4-turbo | OpenAI: GPT-4 Turbo | 128,000 | text+image->text | text,image | text | $10.0000 | $30.0000 | - | 21.5 | - | Optional | 2024-04-09 |
| openai | openai/gpt-4-turbo-preview | OpenAI: GPT-4 Turbo Preview | 128,000 | text->text | text | text | $10.0000 | $30.0000 | - | - | - | Optional | 2024-01-25 |
| openai | openai/gpt-4.1 | OpenAI: GPT-4.1 | 1,047,576 | text+image+file->text | image,text,file | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-mini | OpenAI: GPT-4.1 Mini | 1,047,576 | text+image+file->text | image,text,file | text | $0.4000 | $1.6000 | 14.8 | 20.2 | 1.7 | Optional | 2025-04-15 |
| openai | openai/gpt-4.1-nano | OpenAI: GPT-4.1 Nano | 1,047,576 | text+image+file->text | image,text,file | text | $0.1000 | $0.4000 | 9.6 | 11.1 | 1.2 | Optional | 2025-04-15 |
| openai | openai/gpt-4o | OpenAI: GPT-4o | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-05-13 |
| openai | openai/gpt-4o-2024-05-13 | OpenAI: GPT-4o (2024-05-13) | 128,000 | text+image+file->text | text,image,file | text | $5.0000 | $15.0000 | - | 24.2 | - | Optional | 2024-05-13 |
| openai | openai/gpt-4o-2024-08-06 | OpenAI: GPT-4o (2024-08-06) | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-08-06 |
| openai | openai/gpt-4o-2024-11-20 | OpenAI: GPT-4o (2024-11-20) | 128,000 | text+image+file->text | text,image,file | text | $2.5000 | $10.0000 | - | - | - | Optional | 2024-11-21 |
| openai | openai/gpt-4o-mini | OpenAI: GPT-4o-mini | 128,000 | text+image+file->text | text,image,file | text | $0.1500 | $0.6000 | - | 11.4 | 1 | Optional | 2024-07-18 |
| openai | openai/gpt-4o-mini-2024-07-18 | OpenAI: GPT-4o-mini (2024-07-18) | 128,000 | text+image+file->text | text,image,file | text | $0.1500 | $0.6000 | - | - | - | Optional | 2024-07-18 |
| openai | openai/gpt-5 | OpenAI: GPT-5 | 400,000 | text+image+file->text | text,image,file | text | $1.2500 | $10.0000 | 34.7 | 37.8 | 25.7 | Mandatory | 2025-08-08 |
| openai | openai/gpt-5:batch | OpenAI: GPT-5 (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.6250 | $5.0000 | 34.7 | 37.8 | 25.7 | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-codex | OpenAI: GPT-5 Codex | 400,000 | text+image->text | text,image | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-09-24 |
| openai | openai/gpt-5-image | OpenAI: GPT-5 Image | 400,000 | text+image+file->text+image | image,text,file | image,text | $10.0000 | $10.0000 | - | - | - | Mandatory | 2025-10-14 |
| openai | openai/gpt-5-image-mini | OpenAI: GPT-5 Image Mini | 400,000 | text+image+file->text+image | file,image,text | image,text | $2.5000 | $2.0000 | - | - | - | Mandatory | 2025-10-16 |
| openai | openai/gpt-5-mini | OpenAI: GPT-5 Mini | 400,000 | text+image+file->text | text,image,file | text | $0.2500 | $2.0000 | 25.3 | 15.6 | 19.4 | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-mini:batch | OpenAI: GPT-5 Mini (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.1250 | $1.0000 | 25.3 | 15.6 | 19.4 | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-nano | OpenAI: GPT-5 Nano | 400,000 | text+image+file->text | text,image,file | text | $0.0500 | $0.4000 | - | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-nano:batch | OpenAI: GPT-5 Nano (batch) | 400,000 | text+image+file->text | text,image,file | text | $0.0250 | $0.2000 | - | - | - | Mandatory | 2025-08-08 |
| openai | openai/gpt-5-pro | OpenAI: GPT-5 Pro | 400,000 | text+image+file->text | image,text,file | text | $15.0000 | $120.0000 | - | - | - | Mandatory | 2025-10-07 |
| openai | openai/gpt-5.1 | OpenAI: GPT-5.1 | 400,000 | text+image+file->text | image,text,file | text | $1.2500 | $10.0000 | 36.9 | 49.4 | 21 | Default | 2025-11-14 |
| openai | openai/gpt-5.1:batch | OpenAI: GPT-5.1 (batch) | 400,000 | text+image+file->text | image,text,file | text | $0.6250 | $5.0000 | 36.9 | 49.4 | 21 | Default | 2025-11-14 |
| openai | openai/gpt-5.1-chat | OpenAI: GPT-5.1 Chat | 128,000 | text+image+file->text | file,image,text | text | $1.2500 | $10.0000 | - | - | - | Optional | 2025-11-14 |
| openai | openai/gpt-5.1-codex | OpenAI: GPT-5.1-Codex | 400,000 | text+image->text | text,image | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-11-14 |
| openai | openai/gpt-5.1-codex-max | OpenAI: GPT-5.1-Codex-Max | 400,000 | text+image->text | text,image | text | $1.2500 | $10.0000 | - | - | - | Mandatory | 2025-12-05 |
| openai | openai/gpt-5.1-codex-mini | OpenAI: GPT-5.1-Codex-Mini | 400,000 | text+image->text | image,text | text | $0.2500 | $2.0000 | - | - | - | Optional | 2025-11-14 |
| openai | openai/gpt-5.2 | OpenAI: GPT-5.2 | 400,000 | text+image+file->text | file,image,text | text | $1.7500 | $14.0000 | - | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2:batch | OpenAI: GPT-5.2 (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.8750 | $7.0000 | - | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2-chat | OpenAI: GPT-5.2 Chat | 128,000 | text+image+file->text | file,image,text | text | $1.7500 | $14.0000 | - | - | - | Optional | 2025-12-11 |
| openai | openai/gpt-5.2-pro | OpenAI: GPT-5.2 Pro | 400,000 | text+image+file->text | image,text,file | text | $21.0000 | $168.0000 | - | - | - | Mandatory | 2025-12-11 |
| openai | openai/gpt-5.2-codex | OpenAI: GPT-5.2-Codex | 400,000 | text+image->text | text,image | text | $1.7500 | $14.0000 | - | - | - | Mandatory | 2026-01-15 |
| openai | openai/gpt-5.3-chat | OpenAI: GPT-5.3 Chat | 128,000 | text+image+file->text | text,image,file | text | $1.7500 | $14.0000 | - | - | - | Optional | 2026-03-04 |
| openai | openai/gpt-5.3-codex | OpenAI: GPT-5.3-Codex | 400,000 | text+image+file->text | text,image,file | text | $1.7500 | $14.0000 | - | - | - | Optional | 2026-02-25 |
| openai | openai/gpt-5.4 | OpenAI: GPT-5.4 | 1,050,000 | text+image+file->text | text,image,file | text | $2.5000 | $15.0000 | 51.4 | 71.1 | 41.1 | Optional | 2026-03-06 |
| openai | openai/gpt-5.4:batch | OpenAI: GPT-5.4 (batch) | 1,050,000 | text+image+file->text | text,image,file | text | $1.2500 | $7.5000 | 51.4 | 71.1 | 41.1 | Optional | 2026-03-06 |
| openai | openai/gpt-5.4-image-2 | OpenAI: GPT-5.4 Image 2 | 272,000 | text+image+file->text+image | image,text,file | image,text | $8.0000 | $15.0000 | - | - | - | Optional | 2026-04-22 |
| openai | openai/gpt-5.4-mini | OpenAI: GPT-5.4 Mini | 400,000 | text+image+file->text | file,image,text | text | $0.7500 | $4.5000 | 40 | 56.1 | 30.2 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-mini:batch | OpenAI: GPT-5.4 Mini (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.3750 | $2.2500 | 40 | 56.1 | 30.2 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-nano | OpenAI: GPT-5.4 Nano | 400,000 | text+image+file->text | file,image,text | text | $0.2000 | $1.2500 | 38.2 | 56.1 | 27.5 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-nano:batch | OpenAI: GPT-5.4 Nano (batch) | 400,000 | text+image+file->text | file,image,text | text | $0.1000 | $0.6250 | 38.2 | 56.1 | 27.5 | Optional | 2026-03-17 |
| openai | openai/gpt-5.4-pro | OpenAI: GPT-5.4 Pro | 1,050,000 | text+image+file->text | text,image,file | text | $30.0000 | $180.0000 | - | - | - | Mandatory | 2026-03-06 |
| openai | openai/gpt-5.5 | OpenAI: GPT-5.5 | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $30.0000 | 54.8 | 74.9 | 44.9 | Default | 2026-04-25 |
| openai | openai/gpt-5.5:batch | OpenAI: GPT-5.5 (batch) | 1,050,000 | text+image+file->text | file,image,text | text | $2.5000 | $15.0000 | 54.8 | 74.9 | 44.9 | Default | 2026-04-25 |
| openai | openai/gpt-5.5-pro | OpenAI: GPT-5.5 Pro | 1,050,000 | text+image+file->text | file,image,text | text | $30.0000 | $180.0000 | - | - | - | Mandatory | 2026-04-25 |
| openai | openai/gpt-5.6-luna | OpenAI: GPT-5.6 Luna | 1,050,000 | text+image+file->text | file,image,text | text | $0.5000 | $3.0000 | 51.2 | 71.4 | 45.6 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-luna-pro | OpenAI: GPT-5.6 Luna Pro | 1,050,000 | text+image+file->text | file,image,text | text | $0.5000 | $3.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol | OpenAI: GPT-5.6 Sol | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $30.0000 | 58.9 | 77.4 | 54 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-sol-pro | OpenAI: GPT-5.6 Sol Pro | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $30.0000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra | OpenAI: GPT-5.6 Terra | 1,050,000 | text+image+file->text | file,image,text | text | $1.2500 | $7.5000 | 55 | 76.7 | 47.4 | Default | 2026-07-09 |
| openai | openai/gpt-5.6-terra-pro | OpenAI: GPT-5.6 Terra Pro | 1,050,000 | text+image+file->text | file,image,text | text | $1.2500 | $7.5000 | - | - | - | Default | 2026-07-09 |
| openai | openai/gpt-oss-120b | OpenAI: gpt-oss-120b | 131,072 | text->text | text | text | $0.0370 | $0.1700 | 23.8 | 30.4 | 13.2 | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-20b | OpenAI: gpt-oss-20b | 131,072 | text->text | text | text | $0.0300 | $0.1300 | 14.9 | 20.7 | 3.1 | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-20b:free | OpenAI: gpt-oss-20b (free) | 131,072 | text->text | text | text | $0.0000 | $0.0000 | 14.9 | 20.7 | 3.1 | Mandatory | 2025-08-06 |
| openai | openai/gpt-oss-safeguard-20b | OpenAI: gpt-oss-safeguard-20b | 131,072 | text->text | text | text | $0.0750 | $0.3000 | - | - | - | Mandatory | 2025-10-29 |
| openai | openai/o1 | OpenAI: o1 | 200,000 | text+image+file->text | text,image,file | text | $15.0000 | $60.0000 | - | 39.7 | - | Optional | 2024-12-18 |
| openai | openai/o1-pro | OpenAI: o1-pro | 200,000 | text+image+file->text | text,image,file | text | $150.0000 | $600.0000 | - | - | - | Optional | 2025-03-20 |
| openai | openai/o3 | OpenAI: o3 | 200,000 | text+image+file->text | image,text,file | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-04-17 |
| openai | openai/o3-deep-research | OpenAI: o3 Deep Research | 200,000 | text+image+file->text | image,text,file | text | $10.0000 | $40.0000 | - | - | - | Optional | 2025-10-11 |
| openai | openai/o3-mini | OpenAI: o3 Mini | 200,000 | text+file->text | text,file | text | $1.1000 | $4.4000 | - | - | - | Optional | 2025-02-01 |
| openai | openai/o3-mini-high | OpenAI: o3 Mini High | 200,000 | text+file->text | text,file | text | $1.1000 | $4.4000 | 15.6 | 16.3 | 1.7 | Mandatory | 2025-02-12 |
| openai | openai/o3-pro | OpenAI: o3 Pro | 200,000 | text+image+file->text | text,file,image | text | $20.0000 | $80.0000 | - | - | - | Optional | 2025-06-11 |
| openai | openai/o4-mini | OpenAI: o4 Mini | 200,000 | text+image+file->text | image,text,file | text | $1.1000 | $4.4000 | - | - | - | Optional | 2025-04-17 |
| openai | openai/o4-mini-deep-research | OpenAI: o4 Mini Deep Research | 200,000 | text+image+file->text | file,image,text | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-10-11 |
| openai | openai/o4-mini-high | OpenAI: o4 Mini High | 200,000 | text+image+file->text | image,text,file | text | $1.1000 | $4.4000 | - | - | - | Mandatory | 2025-04-17 |
| openrouter | openrouter/auto | Auto Router | 2,000,000 | text+image+file+audio+video->text+image | text,image,audio,file,video | text,image | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2023-11-08 |
| openrouter | openrouter/auto-beta | Auto Router (Beta) | 2,000,000 | text+image+file+audio+video->text+image | text,image,audio,file,video | text,image | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-07-18 |
| openrouter | openrouter/bodybuilder | Body Builder (beta) | 128,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2025-12-05 |
| openrouter | openrouter/free | Free Models Router | 200,000 | text+image->text | text,image | text | $0.0000 | $0.0000 | - | - | - | Optional | 2026-02-01 |
| openrouter | openrouter/fusion | OpenRouter: Fusion | 1,000,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-06-14 |
| openrouter | openrouter/pareto-code | Pareto Code Router | 2,000,000 | text->text | text | text | $-1000000.0000 | $-1000000.0000 | - | - | - | Optional | 2026-04-21 |
| perceptron | perceptron/perceptron-mk1 | Perceptron: Perceptron Mk1 | 32,768 | text+image+video->text | text,image,video | text | $0.1500 | $1.5000 | - | - | - | Optional | 2026-05-12 |
| perplexity | perplexity/sonar | Perplexity: Sonar | 127,072 | text+image->text | text,image | text | $1.0000 | $1.0000 | - | - | - | Optional | 2025-01-28 |
| perplexity | perplexity/sonar-deep-research | Perplexity: Sonar Deep Research | 128,000 | text->text | text | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-03-07 |
| perplexity | perplexity/sonar-pro | Perplexity: Sonar Pro | 200,000 | text+image->text | text,image | text | $3.0000 | $15.0000 | - | - | - | Optional | 2025-03-07 |
| perplexity | perplexity/sonar-pro-search | Perplexity: Sonar Pro Search | 200,000 | text+image->text | text,image | text | $3.0000 | $15.0000 | - | - | - | Mandatory | 2025-10-31 |
| perplexity | perplexity/sonar-reasoning-pro | Perplexity: Sonar Reasoning Pro | 128,000 | text+image->text | text,image | text | $2.0000 | $8.0000 | - | - | - | Optional | 2025-03-07 |
| poolside | poolside/laguna-s-2.1 | Poolside: Laguna S 2.1 | 1,048,576 | text->text | text | text | $0.1000 | $0.2000 | - | - | - | Default | 2026-07-22 |
| poolside | poolside/laguna-s-2.1:free | Poolside: Laguna S 2.1 (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-07-22 |
| poolside | poolside/laguna-xs-2.1 | Poolside: Laguna XS 2.1 | 262,144 | text->text | text | text | $0.0600 | $0.1200 | - | - | - | Default | 2026-07-02 |
| poolside | poolside/laguna-xs-2.1:free | Poolside: Laguna XS 2.1 (free) | 262,144 | text->text | text | text | $0.0000 | $0.0000 | - | - | - | Default | 2026-07-02 |
| qwen | qwen/qwen-2.5-72b-instruct | Qwen2.5 72B Instruct | 32,768 | text->text | text | text | $0.3600 | $0.4000 | - | - | - | Optional | 2024-09-19 |
| qwen | qwen/qwen-2.5-coder-32b-instruct | Qwen2.5 Coder 32B Instruct | 32,768 | text->text | text | text | $0.6600 | $1.0000 | - | - | - | Optional | 2024-11-12 |
| qwen | qwen/qwen-plus-2025-07-28 | Qwen: Qwen Plus 0728 | 1,000,000 | text->text | text | text | $0.2600 | $0.7800 | - | - | - | Optional | 2025-09-09 |
| qwen | qwen/qwen-plus-2025-07-28:thinking | Qwen: Qwen Plus 0728 (thinking) | 1,000,000 | text->text | text | text | $0.4000 | $1.2000 | - | - | - | Optional | 2025-09-09 |
| qwen | qwen/qwen-plus | Qwen: Qwen-Plus | 1,000,000 | text->text | text | text | $0.2600 | $0.7800 | - | - | - | Optional | 2025-02-01 |
| qwen | qwen/qwen-2.5-7b-instruct | Qwen: Qwen2.5 7B Instruct | 32,768 | text->text | text | text | $0.1000 | $0.2000 | - | - | - | Optional | 2024-10-16 |
| qwen | qwen/qwen2.5-vl-72b-instruct | Qwen: Qwen2.5 VL 72B Instruct | 128,000 | text+image->text | text,image | text | $0.8000 | $1.0000 | - | - | - | Optional | 2025-02-01 |
| qwen | qwen/qwen3-14b | Qwen: Qwen3 14B | 131,072 | text->text | text | text | $0.2275 | $0.9100 | 10.4 | 13.8 | 1.8 | Optional | 2025-04-29 |
| qwen | qwen/qwen3-235b-a22b | Qwen: Qwen3 235B A22B | 131,072 | text->text | text | text | $0.4550 | $1.8200 | - | - | - | Optional | 2025-04-29 |
| qwen | qwen/qwen3-235b-a22b-2507 | Qwen: Qwen3 235B A22B Instruct 2507 | 262,144 | text->text | text | text | $0.0900 | $0.5500 | - | - | - | Optional | 2025-07-22 |
| qwen | qwen/qwen3-235b-a22b-thinking-2507 | Qwen: Qwen3 235B A22B Thinking 2507 | 262,144 | text->text | text | text | $0.3000 | $3.0000 | 19.6 | 22.1 | 3.8 | Mandatory | 2025-07-25 |
| qwen | qwen/qwen3-30b-a3b | Qwen: Qwen3 30B A3B | 131,072 | text->text | text | text | $0.1200 | $0.5000 | - | - | - | Default | 2025-04-29 |
| qwen | qwen/qwen3-30b-a3b-instruct-2507 | Qwen: Qwen3 30B A3B Instruct 2507 | 262,144 | text->text | text | text | $0.0481 | $0.1930 | - | - | - | Optional | 2025-07-30 |
| qwen | qwen/qwen3-30b-a3b-thinking-2507 | Qwen: Qwen3 30B A3B Thinking 2507 | 81,920 | text->text | text | text | $0.2000 | $2.4000 | 14.4 | 12.1 | 1.8 | Mandatory | 2025-08-29 |
| qwen | qwen/qwen3-32b | Qwen: Qwen3 32B | 131,072 | text->text | text | text | $0.0800 | $0.2800 | 11.5 | 15.3 | 1.8 | Optional | 2025-04-29 |
| qwen | qwen/qwen3-8b | Qwen: Qwen3 8B | 131,072 | text->text | text | text | $0.1170 | $0.4550 | 8.3 | 9 | 1.5 | Default | 2025-04-29 |
| qwen | qwen/qwen3-coder-30b-a3b-instruct | Qwen: Qwen3 Coder 30B A3B Instruct | 262,144 | text->text | text | text | $0.0700 | $0.2700 | - | - | - | Optional | 2025-07-31 |
| qwen | qwen/qwen3-coder | Qwen: Qwen3 Coder 480B A35B | 262,144 | text->text | text | text | $0.3000 | $1.0000 | - | - | - | Optional | 2025-07-23 |
| qwen | qwen/qwen3-coder-flash | Qwen: Qwen3 Coder Flash | 1,000,000 | text->text | text | text | $0.1950 | $0.9750 | - | - | - | Optional | 2025-09-17 |
| qwen | qwen/qwen3-coder-next | Qwen: Qwen3 Coder Next | 262,144 | text->text | text | text | $0.1200 | $0.8000 | 21.1 | 36.2 | 8.8 | Optional | 2026-02-04 |
| qwen | qwen/qwen3-coder-plus | Qwen: Qwen3 Coder Plus | 1,000,000 | text->text | text | text | $0.6500 | $3.2500 | - | - | - | Optional | 2025-09-24 |
| qwen | qwen/qwen3-max | Qwen: Qwen3 Max | 262,144 | text->text | text | text | $0.7800 | $3.9000 | - | - | - | Optional | 2025-09-24 |
| qwen | qwen/qwen3-max-thinking | Qwen: Qwen3 Max Thinking | 262,144 | text->text | text | text | $0.7800 | $3.9000 | - | - | - | Optional | 2026-02-10 |
| qwen | qwen/qwen3-next-80b-a3b-instruct | Qwen: Qwen3 Next 80B A3B Instruct | 262,144 | text->text | text | text | $0.1000 | $1.1000 | - | - | - | Optional | 2025-09-12 |
| qwen | qwen/qwen3-next-80b-a3b-thinking | Qwen: Qwen3 Next 80B A3B Thinking | 262,144 | text->text | text | text | $0.1500 | $1.2000 | 16.7 | 17.4 | 2.1 | Mandatory | 2025-09-12 |
| qwen | qwen/qwen3-vl-235b-a22b-instruct | Qwen: Qwen3 VL 235B A22B Instruct | 262,144 | text+image->text | text,image | text | $0.2100 | $1.9000 | - | - | - | Optional | 2025-09-24 |
| qwen | qwen/qwen3-vl-235b-a22b-thinking | Qwen: Qwen3 VL 235B A22B Thinking | 131,072 | text+image->text | text,image | text | $0.4000 | $4.0000 | - | - | - | Mandatory | 2025-09-24 |
| qwen | qwen/qwen3-vl-30b-a3b-instruct | Qwen: Qwen3 VL 30B A3B Instruct | 262,144 | text+image->text | text,image | text | $0.1300 | $0.5200 | - | - | - | Optional | 2025-10-07 |
| qwen | qwen/qwen3-vl-30b-a3b-thinking | Qwen: Qwen3 VL 30B A3B Thinking | 262,144 | text+image->text | text,image | text | $0.2000 | $2.4000 | - | - | - | Mandatory | 2025-10-07 |
| qwen | qwen/qwen3-vl-32b-instruct | Qwen: Qwen3 VL 32B Instruct | 131,072 | text+image->text | text,image | text | $0.1040 | $0.4160 | - | - | - | Optional | 2025-10-23 |
| qwen | qwen/qwen3-vl-8b-instruct | Qwen: Qwen3 VL 8B Instruct | 262,144 | text+image->text | image,text | text | $0.1170 | $0.4550 | - | - | - | Optional | 2025-10-15 |
| qwen | qwen/qwen3-vl-8b-thinking | Qwen: Qwen3 VL 8B Thinking | 131,072 | text+image->text | image,text | text | $0.1800 | $2.1000 | - | - | - | Mandatory | 2025-10-15 |
| qwen | qwen/qwen3.5-397b-a17b | Qwen: Qwen3.5 397B A17B | 262,144 | text+image+video->text | text,image,video | text | $0.3900 | $2.3400 | 33.7 | 48.2 | 19.8 | Optional | 2026-02-16 |
| qwen | qwen/qwen3.5-plus-02-15 | Qwen: Qwen3.5 Plus 2026-02-15 | 1,000,000 | text+image+video->text | text,image,video | text | $0.2600 | $1.5600 | - | - | - | Optional | 2026-02-16 |
| qwen | qwen/qwen3.5-plus-20260420 | Qwen: Qwen3.5 Plus 2026-04-20 | 1,000,000 | text+image+video->text | text,image,video | text | $0.3000 | $1.8000 | - | - | - | Optional | 2026-04-27 |
| qwen | qwen/qwen3.5-122b-a10b | Qwen: Qwen3.5-122B-A10B | 262,144 | text+image+video->text | text,image,video | text | $0.2600 | $2.0800 | 32.3 | 45.7 | 20.7 | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-27b | Qwen: Qwen3.5-27B | 262,144 | text+image+video->text | text,image,video | text | $0.1950 | $1.5600 | - | - | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-35b-a3b | Qwen: Qwen3.5-35B-A3B | 262,144 | text+image+video->text | text,image,video | text | $0.1400 | $1.0000 | 24 | 37 | 11.8 | Optional | 2026-02-26 |
| qwen | qwen/qwen3.5-9b | Qwen: Qwen3.5-9B | 262,144 | text+image+video->text | text,image,video | text | $0.1000 | $0.1500 | 21.4 | 28.7 | 7.4 | Optional | 2026-03-10 |
| qwen | qwen/qwen3.5-flash-02-23 | Qwen: Qwen3.5-Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.0650 | $0.2600 | - | - | - | Optional | 2026-02-26 |
| qwen | qwen/qwen3.6-27b | Qwen: Qwen3.6 27B | 262,144 | text+image+video->text | text,image,video | text | $0.3000 | $2.0000 | 37.1 | 53.7 | 27 | Default | 2026-04-27 |
| qwen | qwen/qwen3.6-35b-a3b | Qwen: Qwen3.6 35B A3B | 262,144 | text+image+video->text | text,image,video | text | $0.1400 | $1.0000 | 31.6 | 41.9 | 21.4 | Default | 2026-04-27 |
| qwen | qwen/qwen3.6-flash | Qwen: Qwen3.6 Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.1875 | $1.1250 | - | - | - | Optional | 2026-04-27 |
| qwen | qwen/qwen3.6-max-preview | Qwen: Qwen3.6 Max Preview | 262,144 | text->text | text | text | $1.0270 | $6.1620 | - | - | - | Default | 2026-04-27 |
| qwen | qwen/qwen3.6-plus | Qwen: Qwen3.6 Plus | 1,000,000 | text+image+video->text | text,image,video | text | $0.3250 | $1.9500 | 39.6 | 54.5 | 27.6 | Optional | 2026-04-02 |
| qwen | qwen/qwen3.7-flash | Qwen: Qwen3.7 Flash | 1,000,000 | text+image+video->text | text,image,video | text | $0.0300 | $0.1300 | - | - | - | Default | 2026-07-28 |
| qwen | qwen/qwen3.7-max | Qwen: Qwen3.7 Max | 1,000,000 | text->text | text | text | $1.4750 | $4.4250 | 46 | 66 | 30.6 | Default | 2026-05-21 |
| qwen | qwen/qwen3.7-plus | Qwen: Qwen3.7 Plus | 1,000,000 | text+image->text | text,image | text | $0.3200 | $1.2800 | 39 | 55.9 | 20.8 | Default | 2026-06-03 |
| rekaai | rekaai/reka-edge | Reka Edge | 16,384 | text+image+video->text | image,text,video | text | $0.1000 | $0.1000 | - | - | - | Optional | 2026-03-21 |
| rekaai | rekaai/reka-flash-3 | Reka Flash 3 | 65,536 | text->text | text | text | $0.1000 | $0.2000 | - | - | - | Mandatory | 2025-03-13 |
| relace | relace/relace-apply-3 | Relace: Relace Apply 3 | 256,000 | text->text | text | text | $0.8500 | $1.2500 | - | - | - | Optional | 2025-09-26 |
| relace | relace/relace-search | Relace: Relace Search | 256,000 | text->text | text | text | $1.0000 | $3.0000 | - | - | - | Optional | 2025-12-09 |
| sakana | sakana/fugu-ultra | Sakana: Fugu Ultra | 1,000,000 | text+image->text | text,image | text | $5.0000 | $30.0000 | - | - | - | Mandatory | 2026-06-24 |
| sao10k | sao10k/l3-lunaris-8b | Sao10K: Llama 3 8B Lunaris | 8,192 | text->text | text | text | $0.0400 | $0.0500 | - | - | - | Optional | 2024-08-13 |
| sao10k | sao10k/l3.1-euryale-70b | Sao10K: Llama 3.1 Euryale 70B v2.2 | 131,072 | text->text | text | text | $0.8500 | $0.8500 | - | - | - | Optional | 2024-08-28 |
| sao10k | sao10k/l3.3-euryale-70b | Sao10K: Llama 3.3 Euryale 70B | 131,072 | text->text | text | text | $0.6500 | $0.7500 | - | - | - | Optional | 2024-12-18 |
| stepfun | stepfun/step-3.5-flash | StepFun: Step 3.5 Flash | 262,144 | text->text | text | text | $0.1000 | $0.3000 | - | - | - | Mandatory | 2026-01-30 |
| stepfun | stepfun/step-3.7-flash | StepFun: Step 3.7 Flash | 262,144 | text+image+video->text | text,image,video | text | $0.2000 | $1.1500 | 30.3 | 39.6 | 21.5 | Mandatory | 2026-05-29 |
| tencent | tencent/hunyuan-a13b-instruct | Tencent: Hunyuan A13B Instruct | 131,072 | text->text | text | text | $0.1400 | $0.5700 | - | - | - | Optional | 2025-07-08 |
| tencent | tencent/hy3 | Tencent: Hy3 | 262,144 | text->text | text | text | $0.1320 | $0.5280 | - | - | - | Default | 2026-07-06 |
| tencent | tencent/hy3-preview | Tencent: Hy3 preview | 262,144 | text->text | text | text | $0.0630 | $0.2100 | 41.2 | 58.8 | 30.7 | Default | 2026-04-23 |
| thedrummer | thedrummer/cydonia-24b-v4.1 | TheDrummer: Cydonia 24B V4.1 | 131,072 | text->text | text | text | $0.3000 | $0.5000 | - | - | - | Optional | 2025-09-27 |
| thedrummer | thedrummer/rocinante-12b | TheDrummer: Rocinante 12B | 65,536 | text->text | text | text | $0.2500 | $0.5000 | - | - | - | Optional | 2024-09-30 |
| thedrummer | thedrummer/skyfall-36b-v2 | TheDrummer: Skyfall 36B V2 | 32,768 | text->text | text | text | $0.5500 | $0.8000 | - | - | - | Optional | 2025-03-11 |
| thedrummer | thedrummer/unslopnemo-12b | TheDrummer: UnslopNemo 12B | 32,768 | text->text | text | text | $0.4000 | $0.4000 | - | - | - | Optional | 2024-11-09 |
| thinkingmachines | thinkingmachines/inkling | Thinking Machines: Inkling | 1,048,576 | text+image+audio->text | text,image,audio | text | $1.0000 | $4.0500 | 40.7 | 52.1 | 32.3 | Default | 2026-07-18 |
| undi95 | undi95/remm-slerp-l2-13b | ReMM SLERP 13B | 6,144 | text->text | text | text | $0.4500 | $0.6500 | - | - | - | Optional | 2023-07-22 |
| upstage | upstage/solar-pro-3 | Upstage: Solar Pro 3 | 128,000 | text->text | text | text | $0.1500 | $0.6000 | 14.1 | 16.2 | 2.7 | Optional | 2026-01-27 |
| writer | writer/palmyra-x5 | Writer: Palmyra X5 | 1,040,000 | text->text | text | text | $0.6000 | $6.0000 | - | - | - | Optional | 2026-01-21 |
| x-ai | x-ai/grok-4.20 | xAI: Grok 4.20 | 2,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | - | - | - | Optional | 2026-04-01 |
| x-ai | x-ai/grok-4.20-multi-agent | xAI: Grok 4.20 Multi-Agent | 2,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | - | - | - | Mandatory | 2026-04-01 |
| x-ai | x-ai/grok-4.3 | xAI: Grok 4.3 | 1,000,000 | text+image+file->text | text,image,file | text | $1.2500 | $2.5000 | 37.6 | 42.2 | 24.1 | Default | 2026-05-01 |
| x-ai | x-ai/grok-4.5 | xAI: Grok 4.5 | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | 53.8 | 72.4 | 45.7 | Mandatory | 2026-07-08 |
| x-ai | x-ai/grok-build-0.1 | xAI: Grok Build 0.1 | 256,000 | text+image+file->text | text,image,file | text | $1.0000 | $2.0000 | 39.8 | 51.5 | 28 | Mandatory | 2026-05-21 |
| xiaomi | xiaomi/mimo-v2.5 | Xiaomi: MiMo-V2.5 | 1,050,000 | text+image+audio+video->text | text,audio,image,video | text | $0.1400 | $0.2800 | 37.2 | 56.8 | 23.7 | Optional | 2026-04-23 |
| xiaomi | xiaomi/mimo-v2.5-pro | Xiaomi: MiMo-V2.5-Pro | 1,050,000 | text->text | text | text | $0.4350 | $0.8700 | 42.2 | 60.2 | 29.1 | Optional | 2026-04-23 |
| z-ai | z-ai/glm-4.5 | Z.ai: GLM 4.5 | 131,072 | text->text | text | text | $0.6000 | $2.2000 | - | - | - | Optional | 2025-07-26 |
| z-ai | z-ai/glm-4.5-air | Z.ai: GLM 4.5 Air | 131,072 | text->text | text | text | $0.1300 | $0.8500 | - | - | - | Optional | 2025-07-26 |
| z-ai | z-ai/glm-4.5v | Z.ai: GLM 4.5V | 65,536 | text+image->text | text,image | text | $0.6000 | $1.8000 | - | - | - | Optional | 2025-08-11 |
| z-ai | z-ai/glm-4.6 | Z.ai: GLM 4.6 | 204,800 | text->text | text | text | $0.5000 | $2.0000 | 28.7 | 45.8 | 17.7 | Optional | 2025-09-30 |
| z-ai | z-ai/glm-4.6v | Z.ai: GLM 4.6V | 131,072 | text+image+video->text | image,text,video | text | $0.3000 | $0.9000 | - | - | - | Optional | 2025-12-08 |
| z-ai | z-ai/glm-4.7 | Z.ai: GLM 4.7 | 204,800 | text->text | text | text | $0.4000 | $1.7500 | 33.7 | 45.3 | 25.4 | Default | 2025-12-22 |
| z-ai | z-ai/glm-4.7-flash | Z.ai: GLM 4.7 Flash | 202,752 | text->text | text | text | $0.0600 | $0.4000 | - | - | - | Default | 2026-01-19 |
| z-ai | z-ai/glm-5 | Z.ai: GLM 5 | 204,800 | text->text | text | text | $0.9500 | $2.5500 | - | - | - | Default | 2026-02-12 |
| z-ai | z-ai/glm-5-turbo | Z.ai: GLM 5 Turbo | 202,752 | text->text | text | text | $1.2000 | $4.0000 | - | - | - | Default | 2026-03-15 |
| z-ai | z-ai/glm-5.1 | Z.ai: GLM 5.1 | 204,800 | text->text | text | text | $0.9660 | $3.0360 | 40.2 | 55.8 | 29.9 | Default | 2026-04-08 |
| z-ai | z-ai/glm-5.2 | Z.ai: GLM 5.2 | 1,048,576 | text->text | text | text | $0.9660 | $3.0360 | 51.1 | 68.8 | 43.1 | Default | 2026-06-17 |
| z-ai | z-ai/glm-5v-turbo | Z.ai: GLM 5V Turbo | 202,752 | text+image+video->text | image,text,video | text | $1.2000 | $4.0000 | - | - | - | Default | 2026-04-02 |
| ~anthropic | ~anthropic/claude-haiku-latest | Anthropic Claude Haiku Latest | 200,000 | text+image+file->text | text,image,file | text | $1.0000 | $5.0000 | - | - | - | Optional | 2026-04-28 |
| ~anthropic | ~anthropic/claude-sonnet-latest | Anthropic Claude Sonnet Latest | 1,000,000 | text+image+file->text | text,image,file | text | $2.0000 | $10.0000 | - | - | - | Default | 2026-04-28 |
| ~anthropic | ~anthropic/claude-fable-latest | Anthropic: Claude Fable Latest | 1,000,000 | text+image+file->text | text,image,file | text | $10.0000 | $50.0000 | - | - | - | Mandatory | 2026-06-10 |
| ~anthropic | ~anthropic/claude-opus-latest | Anthropic: Claude Opus Latest | 1,000,000 | text+image+file->text | text,image,file | text | $5.0000 | $25.0000 | - | - | - | Default | 2026-04-22 |
| ~google | ~google/gemini-flash-latest | Google Gemini Flash Latest | 1,048,576 | text+image+file+audio+video->text | text,image,video,file,audio | text | $1.5000 | $7.5000 | - | - | - | Mandatory | 2026-04-28 |
| ~google | ~google/gemini-pro-latest | Google Gemini Pro Latest | 1,048,576 | text+image+file+audio+video->text | audio,file,image,text,video | text | $2.0000 | $12.0000 | - | - | - | Mandatory | 2026-04-28 |
| ~moonshotai | ~moonshotai/kimi-latest | MoonshotAI Kimi Latest | 1,048,576 | text+image->text | text,image | text | $2.9000 | $15.0000 | - | - | - | Default | 2026-04-28 |
| ~openai | ~openai/gpt-latest | OpenAI GPT Latest | 1,050,000 | text+image+file->text | file,image,text | text | $5.0000 | $30.0000 | - | - | - | Default | 2026-04-28 |
| ~openai | ~openai/gpt-mini-latest | OpenAI GPT Mini Latest | 400,000 | text+image+file->text | file,image,text | text | $0.7500 | $4.5000 | - | - | - | Optional | 2026-04-28 |
| ~x-ai | ~x-ai/grok-latest | xAI: Grok Latest | 500,000 | text+image+file->text | text,image,file | text | $2.0000 | $6.0000 | - | - | - | Mandatory | 2026-07-08 |
