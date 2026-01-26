# 使用 `nonebot-plugin-localstore` + SQLite 构建轻量数据库

既然您选择了 `nonebot-plugin-localstore`，我们将利用它来管理数据文件路径，并配合 Python 内置的 `sqlite3` 库实现一个极简的数据库功能。

## 计划实施步骤

1.  **创建数据库工具模块 `ww_db_helper.py`**
    *   **功能**：
        *   使用 `nonebot_plugin_localstore` 获取专属数据目录（确保数据文件存在正确的位置，如 `data/nb2_plugins/`）。
        *   封装 `sqlite3` 操作。
        *   **关键点**：为了不阻塞 NoneBot 的事件循环，我会使用 `nonebot.utils.run_sync` 将同步的 SQLite 操作转换为异步调用。
    *   **包含方法**：`init_db` (建表), `execute_query` (增删改), `fetch_all` (查)。

2.  **创建演示插件 `ww_localstore_demo.py`**
    *   **功能**：演示如何使用上述工具存储用户数据。
    *   **命令**：
        *   `记录 <文本>`：将文本存入数据库。
        *   `查询记录`：列出所有存入的文本。

此方案完全符合“轻量”要求（无额外重型依赖，仅使用您已安装的插件和标准库），且结构清晰。