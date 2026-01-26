import sqlite3
import sys
from pathlib import Path
from nonebot import require
from nonebot.utils import run_sync

# 声明依赖
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

# 添加当前目录到 sys.path，方便导入
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

class DBHelper:
    def __init__(self, db_name="my_plugin_data.db"):
        # 获取插件数据目录
        # 这里使用 "ww_plugin" 作为插件名，localstore 会自动分配路径
        # 通常路径为: data/ww_plugin/
        self.data_dir = store.get_plugin_data_dir("ww_plugin")
        self.db_path = self.data_dir / db_name
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 这里不再硬编码建表逻辑，改为由各个插件自行调用 create_table
        pass

    @run_sync
    def create_table(self, table_sql: str):
        """创建表 (供各插件在启动时调用)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(table_sql)
            conn.commit()

    @run_sync
    def execute_update(self, sql: str, params: tuple = ()):
        """执行更新操作 (INSERT, UPDATE, DELETE) - 异步包装"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    @run_sync
    def fetch_all(self, sql: str, params: tuple = ()):
        """执行查询操作 (SELECT) - 异步包装"""
        with sqlite3.connect(self.db_path) as conn:
            # 设置 row_factory 可以让结果像字典一样访问
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            # 将 sqlite3.Row 对象转换为普通字典列表
            return [dict(row) for row in rows]

    @run_sync
    def fetch_one(self, sql: str, params: tuple = ()):
        """执行单条查询 - 异步包装"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

# 实例化全局对象，供其他插件引用
db = DBHelper()
