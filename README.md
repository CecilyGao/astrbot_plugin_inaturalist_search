# iNaturalist 自然观察数据查询插件

## 📖 简介

本插件通过调用 [iNaturalist API](https://api.inaturalist.org/v1/)，提供对全球生物多样性观察数据的快速查询。支持搜索**物种的分类单元信息**和**观察记录**，并以文本或图片形式返回结果。适合自然爱好者、科研人员或聊天机器人集成使用。

## ✨ 功能

- 🔍 **分类单元查询**：通过关键词（学名或俗名）获取物种的分类等级、常用名、观察数量等信息。
- 🌍 **观察记录搜索**：返回指定关键词的观察记录总数，并列出最近若干条样本（含地点、日期、链接及缩略图）。
- 🖼️ **图文双模式**：可分别设置分类单元和观察记录查询的返回方式为**纯文本**或**渲染图片**。
- 🤖 **LLM 工具调用**：为 AI 助手提供 `get_inaturalist_taxon` 和 `get_inaturalist_observations` 两个函数，便于自然语言交互。
- ⚙️ **灵活配置**：支持独立控制两种查询的输出模式，并自定义默认样本数量。

## 📦 安装

### 方法一：通过 AstrBot 管理面板安装
1. 进入 AstrBot 管理面板 → 插件市场。
2. 搜索 `astrbot_plugin_inaturalist_search` 并点击安装。

### 方法二：手动安装
```bash
# 进入 AstrBot 的 data/plugins 目录
cd /path/to/astrbot/data/plugins
# 克隆仓库
git clone https://github.com/CecilyGao/astrbot_plugin_inaturalist_search.git
# 重启 AstrBot
```

## ⚙️ 配置说明

插件支持以下配置项，可在管理面板或 `data/config.json` 中修改：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `inat_user` | string | `""` | iNaturalist 用户名（预留，当前读 API 无需填写） |
| `inat_password` | string | `""` | iNaturalist 密码（预留） |
| `send_mode` | string | `"text"` | 全局发送模式：`text` 或 `image` |
| `taxon_send_mode` | string | `""` | 分类单元查询专用模式，留空则继承 `send_mode` |
| `observations_send_mode` | string | `""` | 观察记录查询专用模式，留空则继承 `send_mode` |
| `default_observation_limit` | int | `5` | 观察记录搜索未指定数量时，默认返回的样本条数 |

## 🧑‍💻 命令用法

主命令为 `ina`，后跟子命令。所有子命令均支持中文关键词。

### 1. 查询分类单元（物种）
```
ina taxon <关键词>
ina t <关键词>          # 缩写
```
**示例**：
```
ina taxon 大熊猫
ina t Ailuropoda melanoleuca
```
**返回信息**：学名、常用名、分类等级、Iconic 分类、父分类、观察总数、iNaturalist ID 及详情链接。

### 2. 搜索观察记录
```
ina observations [数量] <关键词>
ina obs [数量] <关键词>   # 缩写
```
- `[数量]` 为可选数字，指定返回的样本条数（不超过 200），默认为配置中的 `default_observation_limit`。
**示例**：
```
ina observations 10 啄木鸟
ina obs 5 蜻蜓
```
**返回信息**：总记录数、样本列表（含地点、观察日期、网页链接，图片模式下显示缩略图）。

### 3. 显示帮助
```
ina help
```
列出所有命令及示例。

## 🤖 LLM 函数调用工具

插件为 AI 助手提供了两个函数，可在 LLM 调用时直接使用：

### `get_inaturalist_taxon(keyword: str)`
- **描述**：查询 iNaturalist 中的分类单元信息。
- **参数**：`keyword` – 物种关键词（如“大熊猫”）。

### `get_inaturalist_observations(keyword: str)`
- **描述**：搜索 iNaturalist 中的观察记录。
- **参数**：`keyword` – 搜索关键词（如“啄木鸟”）。

调用结果会根据相应的发送模式（`taxon_send_mode` / `observations_send_mode`）返回文本或图片。

## 📷 图片渲染效果

当发送模式设为 `image` 时，插件会将数据渲染为固定尺寸（1280×720）的图片，样式简洁美观，包含关键信息和来源声明。

- **分类单元图片**：展示学名、常用名、分类树、代表照片（若有）。
- **观察记录图片**：展示关键词、总记录数、样本列表及缩略图。

## 🌐 数据来源

所有数据均来自 [iNaturalist.org](https://www.inaturalist.org) 的公开 API，遵循 [iNaturalist 服务条款](https://www.inaturalist.org/terms)。请合理使用，避免高频请求（建议 ≤60 次/分钟）。

## ⚠️ 注意事项

- 当前版本仅使用只读 API，无需认证。预留的认证字段供后续扩展。
- 搜索关键词支持中文、学名、俗名，但 API 的匹配程度可能因语言而异，建议优先使用学名。
- 图片模式下，若某样本无照片，将显示占位图标。
- 观察记录返回的样本按观察日期倒序排列（最新优先）。


欢迎提交 Issue 或 PR 改进插件！