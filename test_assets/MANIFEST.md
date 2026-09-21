# 测试素材库清单

> 生成日期：2026-09-20 · 基于**前置校验修复后**的当前行为
> 用法：把某张图拖到 http://127.0.0.1:8000 页面即可复现下表结果。

## 目录结构与用途

| 目录 | 素材数 | 预期行为 |
|---|---|---|
| `03_unsupported_crop/` | 1 | 非支持作物 → 应被 OOD 拒识（<0.25） |
| `04_not_leaf/` | 3 | 非叶片 → 应被前置校验拒绝（未检测到叶片） |
| `05_bad_shooting/` | 3 | 拍摄不合规 → 应被拒（前置校验或 OOD） |
| `06_edge_cases/` | 5 | 边界输入 → 不应崩溃；行为允许为拒识或带警告接受 |
| `supported_diseased/` | 26 | 应被正常识别为对应病害 |
| `supported_healthy/` | 12 | 应被正常识别为对应作物的「健康」 |
| **合计** | **50** | |

## 逐张实测结果

### 03_unsupported_crop/

预期：非支持作物 → 应被 OOD 拒识（<0.25）

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `ginkgo_green_unsupported.jpg` | False | 0.2219 | 0.0807 | 1.92 | 蓝莓 · 健康 | — | 无 | — | 138.4 |

被拒原因：
- `ginkgo_green_unsupported.jpg`：模型对当前图片不够确信，可能不在可识别范围内。请确认叶片属于支持的作物（番茄、葡萄、玉米、马铃薯、苹果、桃、草莓、辣椒、樱桃、大豆、蓝莓、南瓜、树莓、柑橘），并在纯色背景下重新拍摄

### 04_not_leaf/

预期：非叶片 → 应被前置校验拒绝（未检测到叶片）

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `blue_circle.jpg` | False | None | 0.0001 | 0.0 | — | — | 无 | — | None |
| `gray_block.jpg` | False | None | 0.0 | 0.0 | — | — | 无 | — | None |
| `text_card.jpg` | False | None | 0.0 | 19.26 | — | — | 无 | — | None |

被拒原因：
- `blue_circle.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。
- `gray_block.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。
- `text_card.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。

### 05_bad_shooting/

预期：拍摄不合规 → 应被拒（前置校验或 OOD）

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `leaf_too_small.jpg` | False | None | 0.0047 | 0.0 | — | — | 无 | — | None |
| `multiple_leaves.jpg` | False | 0.2225 | 0.2522 | 0.0 | 大豆 · 健康 | — | 无 | — | 19.8 |
| `textured_background.jpg` | True | 0.2531 | 0.376 | None | 大豆 · 健康 | 健康 | 有 | llm | 3492.8 |

被拒原因：
- `leaf_too_small.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。
- `multiple_leaves.jpg`：模型对当前图片不够确信，可能不在可识别范围内。请确认叶片属于支持的作物（番茄、葡萄、玉米、马铃薯、苹果、桃、草莓、辣椒、樱桃、大豆、蓝莓、南瓜、树莓、柑橘），并在纯色背景下重新拍摄

### 06_edge_cases/

预期：边界输入 → 不应崩溃；行为允许为拒识或带警告接受

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `all_white.jpg` | False | None | 0.0 | 0.0 | — | — | 无 | — | None |
| `extreme_aspect.jpg` | True | 0.4924 | 0.1601 | 0.21 | 玉米 · 健康 | 健康 | 有 | llm | 2220.5 |
| `grayscale_leaf.jpg` | False | None | 0.0 | 0.0 | — | — | 无 | — | None |
| `random_noise.jpg` | False | 0.1352 | 0.3259 | None | 番茄 · 斑枯病 | — | 无 | — | 30.4 |
| `tiny_32x32.jpg` | False | None | None | None | — | — | 无 | — | None |

被拒原因：
- `all_white.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。
- `grayscale_leaf.jpg`：未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。
- `random_noise.jpg`：模型对当前图片不够确信，可能不在可识别范围内。请确认叶片属于支持的作物（番茄、葡萄、玉米、马铃薯、苹果、桃、草莓、辣椒、樱桃、大豆、蓝莓、南瓜、树莓、柑橘），并在纯色背景下重新拍摄
- `tiny_32x32.jpg`：图片尺寸过小，请上传清晰照片。

### supported_diseased/

预期：应被正常识别为对应病害

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `Apple__Apple_scab.jpg` | True | 0.5536 | 0.7374 | 50.12 | 苹果 · 黑星病 | 中 | 有 | llm | 3501.7 |
| `Apple__Black_rot.jpg` | True | 0.4118 | 0.2601 | 19.93 | 苹果 · 黑腐病 | 中 | 有 | llm | 3298.2 |
| `Apple__Cedar_apple_rust.jpg` | True | 0.5993 | 0.4419 | 32.57 | 苹果 · 雪松苹果锈病 | 重 | 有 | llm | 3849.7 |
| `Cherry_(including_sour)__Powdery_mildew.jpg` | True | 0.5394 | 0.3747 | 18.89 | 樱桃 · 白粉病 | 重 | 有 | llm | 3607.6 |
| `Corn_(maize)__Cercospora_leaf_spot_Gray_leaf_spot.jpg` | True | 0.576 | 0.8261 | 11.44 | 玉米 · 灰斑病（尾孢叶斑病） | 中 | 有 | llm | 4523.0 |
| `Corn_(maize)__Common_rust_.jpg` | True | 0.5669 | 0.6031 | 0.41 | 玉米 · 普通锈病 | 重 | 有 | llm | 4163.6 |
| `Corn_(maize)__Northern_Leaf_Blight.jpg` | True | 0.5829 | 0.3271 | 21.49 | 玉米 · 大斑病 | 重 | 有 | llm | 4678.2 |
| `Grape__Black_rot.jpg` | True | 0.569 | 0.4334 | 33.58 | 葡萄 · 黑腐病 | 重 | 有 | llm | 4151.9 |
| `Grape__Esca_(Black_Measles).jpg` | True | 0.5677 | 0.4049 | 26.23 | 葡萄 · 枝枯病（黑麻疹病） | 重 | 有 | llm | 5510.9 |
| `Grape__Leaf_blight_(Isariopsis_Leaf_Spot).jpg` | True | 0.5977 | 0.4548 | 21.54 | 葡萄 · 叶枯病（拟盘多毛孢叶斑病） | 重 | 有 | llm | 3701.9 |
| `Orange__Haunglongbing_(Citrus_greening).jpg` | True | 0.4853 | 0.4884 | 13.93 | 柑橘 · 黄龙病（青果病） | 重 | 有 | llm | 4212.7 |
| `Peach__Bacterial_spot.jpg` | True | 0.4965 | 0.4465 | 31.75 | 桃 · 细菌性斑点病 | 重 | 有 | llm | 3408.8 |
| `Pepper_bell__Bacterial_spot.jpg` | True | 0.4905 | 0.4398 | 47.69 | 辣椒 · 细菌性斑点病 | 重 | 有 | llm | 3898.5 |
| `Potato__Early_blight.jpg` | True | 0.5328 | 0.5179 | 54.78 | 马铃薯 · 早疫病 | 重 | 有 | llm | 3849.5 |
| `Potato__Late_blight.jpg` | True | 0.5067 | 0.5119 | 23.59 | 马铃薯 · 晚疫病 | 重 | 有 | llm | 4190.6 |
| `Squash__Powdery_mildew.jpg` | True | 0.548 | 0.537 | 19.99 | 南瓜 · 白粉病 | 重 | 有 | llm | 3826.8 |
| `Strawberry__Leaf_scorch.jpg` | True | 0.5195 | 0.4123 | 37.29 | 草莓 · 叶焦病 | 重 | 有 | llm | 3190.9 |
| `Tomato__Bacterial_spot.jpg` | True | 0.4233 | 0.4061 | 16.16 | 番茄 · 细菌性斑点病 | 重 | 有 | llm | 3819.8 |
| `Tomato__Early_blight.jpg` | True | 0.4134 | 0.338 | 29.45 | 番茄 · 早疫病 | 重 | 有 | llm | 3991.8 |
| `Tomato__Late_blight.jpg` | True | 0.3889 | 0.288 | 35.56 | 番茄 · 晚疫病 | 重 | 有 | llm | 4442.3 |
| `Tomato__Leaf_Mold.jpg` | True | 0.4733 | 0.2811 | 22.85 | 番茄 · 叶霉病 | 重 | 有 | llm | 4751.9 |
| `Tomato__Septoria_leaf_spot.jpg` | True | 0.4033 | 0.3513 | 16.78 | 番茄 · 斑枯病 | 中 | 有 | llm | 4354.3 |
| `Tomato__Spider_mites_Two-spotted_spider_mite.jpg` | True | 0.3981 | 0.3703 | 24.16 | 番茄 · 红蜘蛛（二斑叶螨） | 重 | 有 | llm | 4217.3 |
| `Tomato__Target_Spot.jpg` | True | 0.4545 | 0.2776 | 23.39 | 番茄 · 靶斑病 | 重 | 有 | llm | 7717.6 |
| `Tomato__Tomato_mosaic_virus.jpg` | True | 0.5258 | 0.2854 | 24.27 | 番茄 · 花叶病毒病 | 重 | 有 | llm | 5035.3 |
| `Tomato__Tomato_Yellow_Leaf_Curl_Virus.jpg` | True | 0.4666 | 0.2873 | 38.75 | 番茄 · 黄化曲叶病毒病 | 重 | 有 | llm | 4661.6 |

### supported_healthy/

预期：应被正常识别为对应作物的「健康」

| 文件 | ok | ood | leaf | bg_std | 识别结果 | 严重度 | 热力图 | 处方来源 | 耗时ms |
|---|---|---|---|---|---|---|---|---|---|
| `Apple__healthy.jpg` | True | 0.4214 | 0.4177 | 24.01 | 苹果 · 健康 | 健康 | 有 | llm | 3075.5 |
| `Blueberry__healthy.jpg` | True | 0.5165 | 0.3153 | 48.16 | 蓝莓 · 健康 | 健康 | 有 | llm | 2083.3 |
| `Cherry_(including_sour)__healthy.jpg` | True | 0.6204 | 0.5269 | 29.02 | 樱桃 · 健康 | 健康 | 有 | llm | 2144.8 |
| `Corn_(maize)__healthy.jpg` | True | 0.6665 | 0.7402 | None | 玉米 · 健康 | 健康 | 有 | llm | 3014.1 |
| `Grape__healthy.jpg` | True | 0.5438 | 0.4824 | 10.79 | 葡萄 · 健康 | 健康 | 有 | llm | 3195.2 |
| `Peach__healthy.jpg` | True | 0.5949 | 0.2045 | 26.15 | 桃 · 健康 | 健康 | 有 | llm | 2711.8 |
| `Pepper_bell__healthy.jpg` | True | 0.5325 | 0.4838 | 43.2 | 辣椒 · 健康 | 健康 | 有 | llm | 2929.0 |
| `Potato__healthy.jpg` | True | 0.5086 | 0.7303 | 23.77 | 马铃薯 · 健康 | 健康 | 有 | llm | 2854.8 |
| `Raspberry__healthy.jpg` | True | 0.6094 | 0.7944 | 41.77 | 树莓 · 健康 | 健康 | 有 | llm | 2677.3 |
| `Soybean__healthy.jpg` | True | 0.5191 | 0.5507 | 10.01 | 大豆 · 健康 | 健康 | 有 | llm | 2357.0 |
| `Strawberry__healthy.jpg` | True | 0.5504 | 0.8752 | 31.27 | 草莓 · 健康 | 健康 | 有 | llm | 3174.7 |
| `Tomato__healthy.jpg` | True | 0.5155 | 0.3256 | 38.33 | 番茄 · 健康 | 健康 | 有 | llm | 2802.3 |

## 说明

- `01`/`02` 是从 PlantVillage 验证集**抽取的真实样本**（每类 1 张），用于验证正常链路。
- `03` 是拒识演示素材（非支持作物银杏叶），来源与授权见 `docs/演示素材.md`。
- `04`/`05`/`06` 是**代码生成的合成图**，用于验证边界与异常路径，无第三方授权问题。
- 训练集 `data/` 已被 `.gitignore` 排除，因此 `01`/`02` 的抽取结果不进版本控制，
  但**已抽出的这些样本本身在仓库里**，可直接使用。