# -*- coding: utf-8 -*-
"""
携程中华麋鹿园评价数据分析 - 综合可视化仪表盘
==========================================================================
功能概述:
    使用 pandas + jieba + pyecharts 构建交互式 HTML 仪表盘，
    包含 15 张 pyecharts 交互式图表，覆盖评分分布、时间趋势、
    用户画像、文本分析等全部主题。

图表清单（15 张交互式图表）:
    1.  评分分布饼图              Pie      各星级评价数量与占比
    2.  评价等级饼图              Pie      好评/中评/差评三分类
    3.  评分维度雷达图            Radar    景色/趣味/性价比 + 近3年对比
    4.  月度评价趋势              Line     评价量 + 平均评分双 Y 轴（带缩放）
    5.  年度评价量                Bar      各年度评价数量
    6.  四季评价量与评分          Bar      季节性评价量 + 评分双 Y 轴
    7.  用户等级分布              Pie      携程会员等级占比
    8.  用户等级与评分关系        Bar      各等级平均评分
    9.  IP属地 TOP10              Bar      横向柱状图
    10. 全量词云                  WordCloud 全部评论关键词
    11. 好评词云                  WordCloud 4-5星评论关键词
    12. 差评词云                  WordCloud 1-2星评论关键词
    13. 高频词 TOP20             Bar      出现次数最多的 20 个词
    14. 评论长度分布              Bar      按字数区间统计
    15. 有图 vs 纯文字评论        Pie      图片评论占比

数据源:
    data/中华麋鹿园_评价数据.csv （携程评价，UTF-8-BOM 编码）

输出文件:
    output/中华麋鹿园_评价数据分析仪表盘.html  （交互式仪表盘）
    output/中华麋鹿园_分析摘要.json            （关键指标摘要，供 HTML 报告引用）

重构说明:
    - 路径、景区信息、配色、季节/长度分箱等常量统一取自 config
    - 数据加载、时间特征、评分等级、jieba 分词统一走 data_utils
    - 15 张图表各自封装为独立函数，便于单独调试与复用
    - 全流程收敛到 main()，可作为模块导入而不会执行副作用
    - 采用浅色主题（白底），标题统一置顶居中、图例移至底部/右上，
      避免「标题与图例重叠遮挡」导致难以阅读

"""

import json
import warnings
from collections import Counter

import pandas as pd

# pyecharts 核心组件
from pyecharts import options as opts
from pyecharts.charts import Pie, Bar, Line, Radar, WordCloud, Page

import config
import data_utils

# 忽略 pandas 链式赋值等无关警告
warnings.filterwarnings("ignore")

# 仪表盘主题："default" 即 pyecharts 默认浅色（白底），更适合阅读与打印。
# 注意：不要传 None，Page 聚合依赖时会插入 None 导致渲染报错；
# 如需深色风格可改为 "dark"（深色下标题/图例仍需上述位置调整）。
THEME = "default"


# =====================================================================
# 标题 / 图例定位辅助函数
# 统一约定：标题置顶居中、图例置于底部（饼/雷达）或右上角（柱/线），
# 从根本上避免标题与图例在顶部互相遮挡。
# =====================================================================
def _title(title, subtitle=None):
    """标题统一置顶居中，给图例让出空间。"""
    return opts.TitleOpts(title=title, subtitle=subtitle, pos_top="2%", pos_left="center")


def _legend_bottom():
    """图例置于底部横向排列（适用于饼图、雷达图）。"""
    return opts.LegendOpts(pos_bottom="3%", orient="horizontal")


def _legend_top_right():
    """图例置于右上角（适用于有 X 轴类目、底部已被坐标占用的柱/线图）。"""
    return opts.LegendOpts(pos_top="3%", pos_right="4%")


# =====================================================================
# 图1: 评分分布饼图
# =====================================================================
def chart_score_distribution(df, score_dist):
    """各星级评价数量与占比环形图。"""
    return (
        Pie(init_opts=opts.InitOpts(width="800px", height="500px", theme=THEME))
        .add(
            series_name="评分分布",
            data_pair=[(f"{int(s)}星", int(count)) for s, count in score_dist.items()],
            radius=["35%", "65%"],  # 内环 35% 外环 65%，形成环形图
            label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)", font_size=14),
            emphasis_opts=opts.EmphasisOpts(is_scale=False),  # 关闭悬停扇区放大，保持整套图表风格统一
        )
        .set_colors(config.SCORE_COLOR_LIST)
        .set_global_opts(
            title_opts=_title(
                f"{config.SIGHT_NAME} 评分分布",
                subtitle=f"总评价数: {len(df)} | 平均评分: {df['总评分'].mean():.2f}",
            ),
            legend_opts=_legend_bottom(),
        )
    )


# =====================================================================
# 图2: 评价等级饼图（好评/中评/差评）
# =====================================================================
def chart_level_distribution(df_valid):
    """好评 / 中评 / 差评三分类环形图。"""
    level_dist = df_valid["评分等级"].value_counts()
    # 按等级映射配色，未命中的用灰色兜底
    level_colors = [config.LEVEL_COLORS.get(k, "#999") for k in level_dist.index]
    return (
        Pie(init_opts=opts.InitOpts(width="800px", height="500px", theme=THEME))
        .add(
            series_name="评价等级",
            data_pair=[(k, int(v)) for k, v in level_dist.items()],
            radius=["35%", "65%"],
            label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)", font_size=14),
            emphasis_opts=opts.EmphasisOpts(is_scale=False),  # 关闭悬停扇区放大，保持整套图表风格统一
        )
        .set_colors(level_colors)
        .set_global_opts(
            title_opts=_title("评价等级分布", subtitle="好评 vs 中评 vs 差评"),
            legend_opts=_legend_bottom(),
        )
    )


# =====================================================================
# 图3: 评分维度雷达图（景色/趣味/性价比）
# =====================================================================
def chart_dimension_radar(df_valid, dim_avgs):
    """三维评分雷达图：总平均 vs 近 3 年。"""
    score_dims = ["景色评分", "趣味评分", "性价比评分"]
    dim_names = ["景色", "趣味", "性价比"]

    # 计算各年度维度平均分（样本量达标的年份才纳入）
    dim_avgs_by_year = {}
    for year in sorted(df_valid["年份"].unique()):
        year_data = df_valid[df_valid["年份"] == year]
        if len(year_data) >= 5:
            dim_avgs_by_year[year] = [year_data[s].mean() for s in score_dims]

    # 雷达图指标：三个维度，最大值 5
    radar_indicator = [opts.RadarIndicatorItem(name=n, max_=5) for n in dim_names]

    # 数据系列：总平均 + 近 3 年
    radar_data = [[round(v, 2) for v in dim_avgs]]
    recent_years = sorted(dim_avgs_by_year.keys())[-3:]
    for year in recent_years:
        radar_data.append([round(v, 2) for v in dim_avgs_by_year[year]])
    series_names = ["总平均"] + [f"{y}年" for y in recent_years]

    radar = Radar(init_opts=opts.InitOpts(width="800px", height="500px", theme=THEME))
    radar.add_schema(schema=radar_indicator, shape="polygon")
    # 逐个添加数据系列（总平均 + 各年度）
    for name, data in zip(series_names, radar_data):
        radar.add(series_name=name, data=[data])
    radar.set_series_opts(label_opts=opts.LabelOpts(is_show=True, formatter="{c}"))
    radar.set_global_opts(
        title_opts=_title("景色·趣味·性价比 三维评分对比", subtitle="总平均 vs 近3年"),
        legend_opts=_legend_bottom(),
    )
    return radar


# =====================================================================
# 图4: 月度评价趋势（双 Y 轴折线 + 数据缩放）
# =====================================================================
def chart_monthly_trend(df_valid):
    """月度评价数量与平均评分双 Y 轴折线图（2018 年至今）。"""
    monthly = (
        df_valid.groupby("年月")
        .agg(评价数=("评论ID", "count"), 平均评分=("总评分", "mean"))
        .reset_index()
        .sort_values("年月")
    )
    # 仅保留 2018 年以后的数据（更早数据量过少，折线不美观）
    monthly = monthly[monthly["年月"] >= "2018-01"].copy()

    return (
        Line(init_opts=opts.InitOpts(width="1200px", height="500px", theme=THEME))
        .add_xaxis(monthly["年月"].tolist())
        # 左 Y 轴：评价数量（蓝色）
        .add_yaxis(
            series_name="评价数量",
            y_axis=monthly["评价数"].tolist(),
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=3),
            label_opts=opts.LabelOpts(is_show=False),
            color=config.COLORS["info"],
        )
        # 右 Y 轴：平均评分（红色）
        .add_yaxis(
            series_name="平均评分",
            y_axis=[round(v, 2) for v in monthly["平均评分"].tolist()],
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=3),
            label_opts=opts.LabelOpts(is_show=False),
            color=config.COLORS["danger"],
            yaxis_index=1,
        )
        # 配置右 Y 轴（评分范围 3.5-5）
        .extend_axis(
            yaxis=opts.AxisOpts(
                name="平均评分", min_=3.5, max_=5, type_="value",
                axislabel_opts=opts.LabelOpts(formatter="{value}"),
            )
        )
        .set_global_opts(
            title_opts=_title("月度评价数量与评分趋势", subtitle="2018年至今"),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=30, font_size=10)),
            yaxis_opts=opts.AxisOpts(name="评价数量", type_="value"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=_legend_top_right(),
            # 数据缩放滑块，支持拖拽查看局部
            datazoom_opts=[opts.DataZoomOpts(type_="slider", range_start=0, range_end=100)],
        )
    )


# =====================================================================
# 图5: 年度评价量柱状图
# =====================================================================
def chart_yearly_count(yearly):
    """各年度评价数量柱状图（样本量达标的年份）。"""
    return (
        Bar(init_opts=opts.InitOpts(width="900px", height="450px", theme=THEME))
        .add_xaxis([str(y) for y in yearly["年份"]])
        .add_yaxis(
            "评价数", yearly["评价数"].tolist(), color=config.COLORS["info"],
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .set_global_opts(
            title_opts=_title(
                "年度评价数量", subtitle=f"数据量≥{config.MIN_YEAR_SAMPLES}条的年份"
            ),
            yaxis_opts=opts.AxisOpts(name="评价数"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图6: 四季评价量与评分（双 Y 轴柱状图）
# =====================================================================
def chart_seasonal(seasonal):
    """四季评价量与平均评分对比双 Y 轴柱状图。"""
    return (
        Bar(init_opts=opts.InitOpts(width="800px", height="450px", theme=THEME))
        .add_xaxis(seasonal["季节"].tolist())
        .add_yaxis(
            "评价数", seasonal["评价数"].tolist(), color=config.COLORS["success"],
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .add_yaxis(
            "平均评分", [round(v, 2) for v in seasonal["平均评分"].tolist()],
            color=config.COLORS["danger"], yaxis_index=1,
            label_opts=opts.LabelOpts(is_show=True, formatter="{c}", position="top"),
        )
        .extend_axis(yaxis=opts.AxisOpts(name="评分", min_=4.0, max_=5.0, type_="value"))
        .set_global_opts(
            title_opts=_title(
                "四季评价量与评分对比",
                subtitle="春季1-3月 夏季4-6月 秋季7-9月 冬季10-12月",
            ),
            yaxis_opts=opts.AxisOpts(name="评价数", type_="value"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图7: 用户等级分布饼图
# =====================================================================
def chart_member_distribution(df):
    """携程会员等级占比环形图。"""
    member_dist = df["用户等级"].value_counts()
    # 7 色循环配色
    member_colors = ["#9b59b6", "#3498db", "#2ecc71", "#f39c12", "#e74c3c", "#1abc9c", "#34495e"]
    return (
        Pie(init_opts=opts.InitOpts(width="800px", height="500px", theme=THEME))
        .add(
            series_name="用户等级分布",
            data_pair=[(k, int(v)) for k, v in member_dist.items()],
            radius=["30%", "60%"],
            label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)", font_size=13),
            emphasis_opts=opts.EmphasisOpts(is_scale=False),  # 关闭悬停扇区放大，保持整套图表风格统一
        )
        .set_colors(member_colors)
        .set_global_opts(
            title_opts=_title("用户等级分布", subtitle="评价用户群体画像"),
            legend_opts=_legend_bottom(),
        )
    )


# =====================================================================
# 图8: 用户等级与评分关系柱状图
# =====================================================================
def chart_member_score(df_valid):
    """各会员等级平均评分与评价数柱状图（取评价数 TOP7）。"""
    member_score = (
        df_valid.groupby("用户等级")
        .agg(平均评分=("总评分", "mean"), 评价数=("评论ID", "count"))
        .reset_index()
        .sort_values("评价数", ascending=False)
        .head(7)
    )
    return (
        Bar(init_opts=opts.InitOpts(width="800px", height="450px", theme=THEME))
        .add_xaxis(member_score["用户等级"].tolist())
        .add_yaxis(
            "平均评分", [round(v, 2) for v in member_score["平均评分"].tolist()],
            color=config.COLORS["danger"],
            label_opts=opts.LabelOpts(is_show=True, formatter="{c}", position="top"),
        )
        .add_yaxis(
            "评价数", member_score["评价数"].tolist(), color=config.COLORS["info"],
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .set_global_opts(
            title_opts=_title("用户等级与评分关系"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图9: IP属地 TOP10 横向柱状图
# =====================================================================
def chart_ip_top10(df):
    """评价来源地区 IP 属地 TOP10 横向柱状图。"""
    ip_dist = df["IP属地"].value_counts().head(10)
    return (
        Bar(init_opts=opts.InitOpts(width="900px", height="450px", theme=THEME))
        .add_xaxis(ip_dist.index.tolist())
        .add_yaxis(
            "评价数", ip_dist.values.tolist(), color=config.COLORS["success"],
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .reversal_axis()  # 翻转为横向柱状图
        .set_global_opts(
            title_opts=_title("IP属地 TOP10", subtitle="评价来源地区分布"),
            xaxis_opts=opts.AxisOpts(name="评价数"),
            yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(font_size=13)),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图10: 全量词云
# =====================================================================
def chart_wordcloud(top_words):
    """全部评论关键词词云。"""
    return (
        WordCloud(init_opts=opts.InitOpts(width="900px", height="600px", theme=THEME))
        .add(
            series_name="高频词汇",
            data_pair=top_words[:100],    # 词云最多展示 100 个词
            word_size_range=[12, 60],     # 字号范围 12-60px
            shape="diamond",              # 菱形布局
        )
        .set_global_opts(
            title_opts=_title("评论关键词词云", subtitle=f"全部{len(top_words)}+关键词"),
        )
    )


# =====================================================================
# 图11/12: 好评 / 差评关键词词云
# =====================================================================
def chart_sentiment_wordcloud(freq_pairs, title, subtitle):
    """构建单个情感词云（好评或差评）。"""
    return (
        WordCloud(init_opts=opts.InitOpts(width="800px", height="500px", theme=THEME))
        .add(
            series_name=title,
            data_pair=freq_pairs,
            word_size_range=[10, 50],
            shape="circle",
        )
        .set_global_opts(
            title_opts=_title(title, subtitle=subtitle),
        )
    )


# =====================================================================
# 图13: 高频词 TOP20 柱状图
# =====================================================================
def chart_top_words(top_words):
    """出现次数最多的 20 个词柱状图。"""
    return (
        Bar(init_opts=opts.InitOpts(width="900px", height="500px", theme=THEME))
        .add_xaxis([w for w, _ in top_words[:20]])
        .add_yaxis(
            "出现次数", [c for _, c in top_words[:20]], color=config.COLORS["warning"],
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .set_global_opts(
            title_opts=_title("评论高频词 TOP20"),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(font_size=12)),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图14: 评论长度分布柱状图
# =====================================================================
def chart_length_distribution(df_valid):
    """按字数区间统计的评论长度分布柱状图。"""
    length_bin = pd.cut(
        df_valid["评论字数"], bins=config.LENGTH_BINS,
        labels=config.LENGTH_LABELS, right=True,
    )
    length_dist = length_bin.value_counts().reindex(config.LENGTH_LABELS)
    return (
        Bar(init_opts=opts.InitOpts(width="800px", height="450px", theme=THEME))
        .add_xaxis(config.LENGTH_LABELS)
        .add_yaxis(
            "评论数", length_dist.values.tolist(), color="#9b59b6",
            label_opts=opts.LabelOpts(is_show=True, position="top"),
        )
        .set_global_opts(
            title_opts=_title(
                "评论长度分布", subtitle=f"平均字数: {df_valid['评论字数'].mean():.0f}字"
            ),
            xaxis_opts=opts.AxisOpts(name="字数区间"),
            yaxis_opts=opts.AxisOpts(name="评论数"),
            legend_opts=_legend_top_right(),
        )
    )


# =====================================================================
# 图15: 有图 vs 纯文字评论饼图
# =====================================================================
def chart_image_ratio(has_image):
    """有图评论 vs 纯文字评论占比饼图。"""
    image_dist = has_image.value_counts().rename({True: "有图评论", False: "纯文字评论"})
    return (
        Pie(init_opts=opts.InitOpts(width="600px", height="400px", theme=THEME))
        .add(
            series_name="图片评论占比",
            data_pair=[(k, int(v)) for k, v in image_dist.items()],
            radius=["35%", "60%"],
            label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)", font_size=13),
            emphasis_opts=opts.EmphasisOpts(is_scale=False),  # 关闭悬停扇区放大，保持整套图表风格统一
        )
        .set_colors(["#e67e22", "#3498db"])
        .set_global_opts(
            title_opts=_title("有图 vs 纯文字评论"),
            legend_opts=_legend_bottom(),
        )
    )


# =====================================================================
# 分析摘要 JSON
# =====================================================================
def build_summary(df, df_valid, score_dist, dim_avgs, top_words,
                  yearly, seasonal, df_positive, df_negative, has_image):
    """汇总关键指标为字典，供 generate_html_report.py 引用。"""
    return {
        "景区": config.SIGHT_NAME,
        "总评价数": len(df),
        "时间范围": f"{df_valid['发布时间_dt'].min()} ~ {df_valid['发布时间_dt'].max()}",
        "平均评分": round(df["总评分"].mean(), 2),
        "评分分布": {f"{int(k)}星": int(v) for k, v in score_dist.items()},
        "维度平均": {
            "景色": round(dim_avgs[0], 2),
            "趣味": round(dim_avgs[1], 2),
            "性价比": round(dim_avgs[2], 2),
        },
        "好评占比": round(len(df_positive) / len(df) * 100, 1),
        "差评占比": round(len(df_negative) / len(df) * 100, 1),
        "有图评论占比": round(has_image.mean() * 100, 1),
        "平均评论字数": round(df_valid["评论字数"].mean(), 0),
        "TOP5高频词": [w for w, _ in top_words[:5]],
        "最活跃年份": int(yearly.sort_values("评价数", ascending=False).iloc[0]["年份"]),
        "最活跃季节": seasonal.sort_values("评价数", ascending=False).iloc[0]["季节"],
    }


def main():
    """加载数据 -> 构建 15 张图表 -> 组装仪表盘 -> 导出摘要 JSON。"""
    # ---- 数据加载与预处理（统一入口） ----
    print("=" * 60)
    print("  Step 1: 数据加载与预处理")
    print("=" * 60)
    df, df_valid = data_utils.load_reviews()
    print(f"原始数据: {len(df)} 条, {len(df.columns)} 列")
    print(f"有效时间数据: {len(df_valid)} 条")
    print(f"时间范围: {df_valid['发布时间_dt'].min()} ~ {df_valid['发布时间_dt'].max()}")

    # ---- 预计算各图表共享的聚合结果 ----
    score_dims = ["景色评分", "趣味评分", "性价比评分"]
    dim_avgs = [df_valid[s].mean() for s in score_dims]
    score_dist = df["总评分"].value_counts().sort_index()

    # 年度聚合（过滤样本量不足的年份）
    yearly = (
        df_valid.groupby("年份")
        .agg(评价数=("评论ID", "count"), 平均评分=("总评分", "mean"))
        .reset_index()
    )
    yearly = yearly[yearly["评价数"] >= config.MIN_YEAR_SAMPLES]

    # 季节聚合（按春夏秋冬顺序排列）
    seasonal = (
        df_valid.groupby("季节")
        .agg(评价数=("评论ID", "count"), 平均评分=("总评分", "mean"))
        .reset_index()
        .set_index("季节")
        .reindex(config.SEASON_ORDER)
        .reset_index()
    )

    # ---- 文本分析：全量 / 好评 / 差评词频 ----
    print("\n  Step 2: 文本分析 (jieba 分词 + 词云)")
    top_words = data_utils.word_frequency(df["评论内容"].dropna()).most_common(200)

    df_positive = df_valid[df_valid["总评分"] >= config.POSITIVE_MIN_SCORE]
    df_negative = df_valid[df_valid["总评分"] <= config.NEGATIVE_MAX_SCORE]
    pos_freq = data_utils.word_frequency(df_positive["评论内容"].dropna()).most_common(80)
    neg_freq = data_utils.word_frequency(df_negative["评论内容"].dropna()).most_common(80)

    has_image = df_valid["图片数"] > 0

    # ---- 构建 15 张图表 ----
    print("\n  Step 3: 构建交互式图表")
    charts = [
        chart_score_distribution(df, score_dist),                          # 1
        chart_level_distribution(df_valid),                                # 2
        chart_dimension_radar(df_valid, dim_avgs),                         # 3
        chart_monthly_trend(df_valid),                                     # 4
        chart_yearly_count(yearly),                                        # 5
        chart_seasonal(seasonal),                                          # 6
        chart_member_distribution(df),                                     # 7
        chart_member_score(df_valid),                                      # 8
        chart_ip_top10(df),                                                # 9
        chart_wordcloud(top_words),                                        # 10
        chart_sentiment_wordcloud(pos_freq, "好评关键词词云 (4-5星)",
                                  f"好评数: {len(df_positive)} 条"),         # 11
        chart_sentiment_wordcloud(neg_freq, "差评关键词词云 (1-2星)",
                                  f"差评数: {len(df_negative)} 条"),         # 12
        chart_top_words(top_words),                                        # 13
        chart_length_distribution(df_valid),                              # 14
        chart_image_ratio(has_image),                                     # 15
    ]

    # ---- 组装并渲染仪表盘 ----
    print("\n  Step 4: 组装 HTML 仪表盘")
    dashboard = Page(layout=Page.SimplePageLayout)
    dashboard.add(*charts)
    dashboard.render(str(config.DASHBOARD_HTML))
    print(f"仪表盘已生成: {config.DASHBOARD_HTML}")

    # ---- 导出分析摘要 JSON ----
    print("\n  Step 5: 生成分析摘要 JSON")
    summary = build_summary(
        df, df_valid, score_dist, dim_avgs, top_words,
        yearly, seasonal, df_positive, df_negative, has_image,
    )
    with open(config.SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"分析摘要已保存: {config.SUMMARY_JSON}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("  全部分析完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
