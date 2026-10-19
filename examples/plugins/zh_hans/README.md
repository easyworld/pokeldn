# pokeldn 简体中文语言包

基于 easyworld/pokeldn 已有汉化，按上游语言包 API 1.9 制作。插件为纯数据包，不包含 Python 模块，不修改交换数据、存档或协议参数。

兼容基线：上游 0.32.0，提交 `a224ec1a97657c202af6e78e3428f5f5910576f2`。

## 安装

在上游应用的 Plugins 页面添加 `easyworld-zh-hans-1.0.3.pokeplugin`，然后在 Settings → App language 选择“简体中文”，重新启动。

涵盖上游全部 1,630 个界面键值、2,204 项高级选项帮助，以及礼物说明、道具、招式、特性、性格、属性、NPC 搭档和地区名称。包含现有汉化的 42 篇参考文档；这些文档继承本分支 0.31.4 的内容，新页面按上游机制回退到英文。

### 上游 0.32.0 的显示接口遗漏

原版 0.32.0 可直接安装本语言包，但以下控件尚未调用语言包接口，仅更新数据无法翻译：

- 基本选项里的动态下拉框，包括极巨大冒险的传说宝可梦。
- 极巨大冒险的租借宝可梦和途中遭遇预览。
- NPC 训练家名称、已选搭档摘要，以及与属性同名的“Psychic”招式。
- 未提供中文正文的新文档的目录标题（正文继续回退到上游英文）。

仓库的 `scripts/zh_hans_upstream.patch` 为上述位置补充显示层调用，适用于其他语言包；选项值、训练家标识和游戏数据保持原样。预览脚本会检查并应用该补丁，重复运行不会重复应用。它不随 `.pokeplugin` 安装，也不会通过插件执行代码。

## 复现开发与预览

在本汉化仓库根目录执行，要求 Python、上游运行依赖及已构建的 PKHeX 服务：

```powershell
git fetch upstream main
git worktree add --detach build/upstream-language-preview upstream/main
python scripts/build_zh_hans_plugin.py --upstream build/upstream-language-preview
python scripts/run_zh_hans_preview.py --upstream build/upstream-language-preview
```

预览数据保存在 `build/language-preview-data`，与默认应用数据目录隔离。语言包输出到 `dist/`。

在上游工作目录运行回归测试：

```powershell
python -m pytest ../../examples/plugins/zh_hans/tests --confcutdir=../../examples/plugins/zh_hans/tests -q
python -m pytest tests/test_i18n.py tests/test_i18n_resources.py tests/test_i18n_templates.py tests/test_localization.py tests/test_gui_views.py -q
```

`overrides.toml` 维护新增英文原文到中文的翻译；`term_overrides.toml` 维护属性、地区和 NPC 名称；`template_overrides.toml` 维护动态说明；`context_strings.toml` 处理招式与属性同名的上下文。其余 TOML 由构建脚本生成，`coverage.json` 记录基线与覆盖数量。

`pkhex_terms.json` 和 `event_messages.json` 是按游戏及数字 ID 配对的 PKHeX.Core 26.8.26 中英文词表、官方道具礼物标题。官方礼物标题按卡片中的道具 ID 翻译，避免把 Level Ball 拆成“等级＋精灵球”。需要更新时先在本汉化分支构建 `services/pkhex`，再执行 `python scripts/export_zh_hans_terms.py`；打包后的语言包不依赖此导出工具。

资源来源：本仓库既有汉化、[PKHeX](https://github.com/kwsch/PKHeX)、[NPC 多语言名称表](https://bulbapedia.bulbagarden.net/wiki/Tera_Raid_Battle#In_other_languages)、[中文搭档列表](https://wiki.52poke.com/zh-hans/太晶团体战)。
