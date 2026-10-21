# pokeldn 简体中文语言插件

独立数据插件，适用于上游保留的 **插件 API 1.9** 语言包格式。
版本 3.0.0 已按上游 `main` 的 `47e34fc` 提交适配，不需要 Babel 或额外的 Python 运行代码。

## 安装

从 [Release](https://github.com/easyworld/pokeldn/releases/tag/plugin-zh-hans-v3.0.0)
下载 `community-zh-hans-3.0.0.pokeplugin`，在程序的 Plugins 页面安装。
然后在 Settings → App language 选择“简体中文”，**重启 pokeldn 后生效**。

插件 ID 为 `community-zh-hans`，可覆盖安装此前使用同一 ID 的版本。
切回 English 后也需要重启。显示语言与生成宝可梦时使用的训练家语言分别设置。

## 资源

- `strings.toml`：全部 1,663 个当前界面文案键。
- `help.toml`：全部 1,882 条按工具和参数区分的高级说明。
- `messages.toml`：3,035 条模块文案，包括礼物预设、增强功能和剑盾活动。
- `templates.toml`：286 条动态消息模板，保留命名参数。
- `terms.toml`：222 条界面术语和选项词语。
- `docs/`：38 篇中文文档，使用本地化标题并保留章节锚点。未提供的页面使用上游英文文档。

宝可梦、招式、特性、性格、属性、精灵球等游戏名称由上游 PKHeX 显示语言服务提供。
本包不携带实体名称数据库，也不修改实体 ID、游戏记录、文件路径、昵称或连接码。
界面中的第三方名称、品牌、协议标识及提供者诊断可能保留原文。

资源采用根目录的扁平 TOML 表，使用上游现有的 `strings`、`messages`、`templates`、`terms`、
`help`、`documents` 和 `font_family` 清单字段。英文复数后缀参数使用字符串精度 `.0`
抑制显示，例如 `{value1:.0}`；参数名称保持一致，不会在中文句尾产生英文 `s`。

## 校验和构建

检出最新上游应用代码，在应用仓库根目录执行，路径指向本插件目录：

```bash
python scripts/check_language_pack.py /path/to/zh-hans-plugin
python scripts/pack_plugin.py /path/to/zh-hans-plugin -o community-zh-hans-3.0.0.pokeplugin
```

缺失文案、未知文案、参数差异、缺失高级说明和未知高级说明均应为 0。
未来上游新增文案或参数后，用该检查脚本定位需要补充的翻译。

本插件的测试放在 `tests/`，打包时排除。将环境变量 `POKELDN_SOURCE` 设为上游应用仓库的
绝对路径后，在本插件目录执行：

```bash
python -m pytest tests -q
```

测试会在临时数据目录中安装本包，检查格式、完整性、动态参数、文档、礼物及活动文案，
并通过 PKHeX 验证中文游戏名称。不访问开发板，也不修改正常使用的设置。

Source: [codex/zh-hans-pack](https://github.com/easyworld/pokeldn/tree/codex/zh-hans-pack).
License: AGPL-3.0, see LICENSE.
