# -*- coding: utf-8 -*-
"""
项目全局配置
==========================================================================
集中管理所有分析脚本共享的常量，作为项目的「单一配置来源」：
    - 路径（基于项目根目录动态解析，避免硬编码绝对路径）
    - 景区信息（名称、携程内部 ID）
    - 配色方案（通用色板、评分等级色）
    - 季节映射、评论长度分箱、评分等级阈值

设计目的:
    1. 消除各脚本中重复且易漂移的路径 / 配色 / 常量定义
    2. 路径基于本文件位置动态推导，项目整体移动或换机后仍可运行
    3. 修改配置只需改动本文件一处，其余脚本自动生效

"""

from pathlib import Path

# ========== 路径配置（基于项目根目录动态解析） ==========
# 本文件位于 <项目根>/src/config.py，因此项目根目录 = 父目录的父目录。
# 相比硬编码绝对路径，这种方式让项目可以整体移动、在任意机器上克隆后直接运行。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"        # 原始数据层（CSV / Excel / JSON）
CHART_DIR = PROJECT_ROOT / "charts"     # matplotlib 静态图表输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"    # 报告与摘要产出目录

# 确保数据 / 图表 / 产出目录存在（不存在则自动创建）
for _dir in (DATA_DIR, CHART_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---- 数据文件路径 ----
REVIEWS_CSV = DATA_DIR / "中华麋鹿园_评价数据.csv"     # 主数据文件（pandas 直接读取）
REVIEWS_XLSX = DATA_DIR / "中华麋鹿园_评价数据.xlsx"   # Excel 格式（通用查看）
REVIEWS_JSON = DATA_DIR / "中华麋鹿园_评价数据_raw.json"  # API 原始 JSON（保留全部字段）

# ---- 产出文件路径 ----
SUMMARY_JSON = OUTPUT_DIR / "中华麋鹿园_分析摘要.json"         # 关键指标摘要（供 HTML 报告引用）
DOCX_REPORT = OUTPUT_DIR / "中华麋鹿园_评价数据分析报告.docx"   # Word 正式报告
HTML_REPORT = OUTPUT_DIR / "中华麋鹿园_评价数据分析报告.html"   # HTML 宽屏在线报告
DASHBOARD_HTML = OUTPUT_DIR / "中华麋鹿园_评价数据分析仪表盘.html"  # pyecharts 交互式仪表盘

# ========== 景区信息 ==========
SIGHT_NAME = "中华麋鹿园"          # 景区简称（用于标题、日志）
SIGHT_FULL_NAME = "盐城中华麋鹿园"  # 景区全称（用于报告正文）
SIGHT_ID = 17408                  # 携程景区 ID（API 请求参数）
POI_ID = 79598                    # 携程兴趣点 ID（API 请求参数）

# ========== 配色方案 ==========
# 通用色板（十六进制），供 matplotlib 图表统一取色
COLORS = {
    "primary": "#2E86AB",    # 主色：蓝色
    "secondary": "#A23B72",  # 次色：紫红色
    "success": "#27AE60",    # 成功 / 好评：绿色
    "warning": "#F39C12",    # 警告 / 提醒：橙色
    "danger": "#E74C3C",     # 危险 / 差评：红色
    "info": "#3498DB",       # 信息：浅蓝色
    "dark": "#2C3E50",       # 深色
    "gray": "#95A5A6",       # 灰色
    "light": "#ECF0F1",      # 浅灰
}

# 评分等级配色：1 星红色 -> 5 星绿色，形成渐变
SCORE_COLORS = {
    1: "#E74C3C",   # 1 星：红色
    2: "#E67E22",   # 2 星：橙色
    3: "#F39C12",   # 3 星：黄色
    4: "#27AE60",   # 4 星：绿色
    5: "#2ECC71",   # 5 星：亮绿色
}
# pyecharts 需要按 1->5 顺序传入的颜色列表
SCORE_COLOR_LIST = [SCORE_COLORS[i] for i in range(1, 6)]

# 评价三分类配色（好评 / 中评 / 差评）
LEVEL_COLORS = {
    "好评(4-5星)": "#2ECC71",
    "中评(3星)": "#F39C12",
    "差评(1-2星)": "#E74C3C",
}

# ========== 季节映射 ==========
# 按公历月份对应的季度划分为中文季节名（注意：非传统节气季节）
SEASON_MAP = {
    1: "春季(1-3月)",
    2: "夏季(4-6月)",
    3: "秋季(7-9月)",
    4: "冬季(10-12月)",
}
# 季节的固定展示顺序（春 -> 夏 -> 秋 -> 冬）
SEASON_ORDER = ["春季(1-3月)", "夏季(4-6月)", "秋季(7-9月)", "冬季(10-12月)"]

# ========== 评论长度分箱 ==========
# 用于「评论长度分布」图的字数区间划分
LENGTH_BINS = [0, 10, 30, 50, 100, 200, 500, 1000, float("inf")]
LENGTH_LABELS = [
    "≤10字", "11-30字", "31-50字", "51-100字",
    "101-200字", "201-500字", "501-1000字", ">1000字",
]

# ========== 评分等级阈值 ==========
POSITIVE_MIN_SCORE = 4  # 好评下限：>= 4 星
NEGATIVE_MAX_SCORE = 2  # 差评上限：<= 2 星
MIN_YEAR_SAMPLES = 10   # 年度趋势分析所需的最小样本量（低于此值的年份不纳入统计）
