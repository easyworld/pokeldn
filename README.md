# 简体中文语言包

用于 pokeldn 语义本地化接口的独立数据插件。需要插件 API 1.10、本地化资源格式 1；
当前上游 main 的旧版程序不能加载此格式，需要包含本地化接口改造的版本。

## 安装

从 [Releases](https://github.com/easyworld/pokeldn/releases/tag/plugin-zh-hans-v2.0.3)
下载 `community-zh-hans-2.0.3.pokeplugin`，在程序的 Plugins 页面安装，
然后在 Settings → App language 选择“简体中文”。

包 ID 为 `community-zh-hans`，仅包含 TOML 和 Markdown 数据，无 Python 执行代码。
切回 English 或卸载插件即可恢复英文。游戏记录中的训练家语言与显示语言分别设置。

## 构建和验证

本分支只保存语言插件源码。另行检出包含语义本地化接口的 pokeldn 仓库，
在该应用仓库根目录运行以下命令，路径指向本插件源码目录：

```bash
python scripts/check_localization.py --language-pack /path/to/zh-hans-plugin --require-complete
python scripts/build_language_pack.py /path/to/zh-hans-plugin --require-complete
python scripts/preview_language.py dist/community-zh-hans-2.0.3.pokeplugin --web 8815
```

生成安装包和对应 SHA-256 文件。浏览器打开 `http://127.0.0.1:8815/`。
预览使用独立数据目录，禁用开发板访问、更新检查和精灵图片下载。

使用本包运行应用仓库的双语测试：先将环境变量 `POKELDN_TEST_LANGUAGE_PACK`
设为本插件源码的绝对路径，再执行：

```bash
python -m pytest tests/test_semantic_i18n.py tests/test_i18n_bilingual.py
```

## 资源覆盖

- 全部 5,554 个核心文案键，以及 `hello-localized` 插件示例的 4 个文案键。
- 高级参数说明及选项、礼物预设与效果说明、剑盾官方活动标题和分类。
- 游戏实体名称由 PKHeX 简体中文名称表提供，语言包补充指定名称和形态覆盖。
- 39 篇中文文档；其余 7 篇文档的正文、标题和目录整体使用英文。
- 训练家姓名、昵称、文件路径、连接码和导入记录中的原始文本保持原值。

核心接口见应用仓库的 `docs/localization.md`，本包也提供
`locales/zh-Hans/docs/localization.md`。新增核心文案后，用完整性检查定位需补充的翻译。

Source: [codex/zh-hans-pack](https://github.com/easyworld/pokeldn/tree/codex/zh-hans-pack).
License: AGPL-3.0, see LICENSE.
