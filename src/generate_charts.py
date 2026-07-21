# -*- coding: utf-8 -*-
"""
生成 Word 分析报告所需静态图表
==========================================================================
功能概述:
    使用 matplotlib + jieba + wordcloud 生成 12 张静态分析图表（PNG 格式），
    覆盖评分分布、时间趋势、用户画像、文本情感、情感极性五大分析主题。

图表清单:
    01  评分分布              饼图        各星级评价数量与占比
    02  评分维度对比          柱状图      景色/趣味/性价比三维均分对比
    03  年度趋势              双轴图      年度评价量（柱）+ 平均评分（折线）
    04  月度趋势              双轴图      月度评价量（折线）+ 平均评分（折线）
    05  季节性分析            双轴图      四季评价量（柱）+ 平均评分（折线）
    06  用户等级分布          饼图        携程会员等级占比
    07  来源地区 TOP10        横向柱状图   IP 属地 TOP10 省份
    08  评论长度分布          柱状图      按字数区间统计评论数
    09  词云                  词云图      全量评论关键词可视化
    10  高频词 TOP15          横向柱状图   出现次数最多的 15 个词
    11  好评差评关键词对比    双面板图    好评 TOP10 vs 差评 TOP10
    12  情感极性分布          柱状图      SnowNLP 模型 正面/中性/负面

数据源:    config.REVIEWS_CSV （携程评价，UTF-8-BOM 编码）
输出路径:  config.CHART_DIR 下的 12 张 PNG 文件（300 DPI）

"""

import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

import config
import data_utils

# 忽略 matplotlib 版本兼容性警告
warnings.filterwarnings("ignore")

# 通用配色（从 config 取，供本模块简写引用）
COLORS = config.COLORS


def setup_chinese_font():
    """
    检测并设置 matplotlib 可用的中文字体。

    matplotlib 默认不支持中文，需手动指定。本函数按优先级尝试多个
    Windows 自带中文字体，返回第一个可用的 FontProperties 对象。

    Returns:
        FontProperties|None: 可用的中文字体属性对象，未找到时返回 None
    """
    candidates = ["Microsoft YaHei", "SimHei", "SimSun", "STHeiti", "WenQuanYi Micro Hei"]
    for name in candidates:
        try:
            font_prop = font_manager.FontProperties(family=name)
            matplotlib.rcParams["font.family"] = font_prop.get_name()
            print(f"使用字体: {name}")
            return font_prop
        except Exception:
            continue
    print("未找到中文字体，使用默认字体")
    return None


def save_chart(fig, name, tight=True):
    """
    保存 matplotlib 图表为 PNG 文件。

    Args:
        fig (Figure): matplotlib Figure 对象
        name (str): 文件名（不含扩展名），如 "01_评分分布"
        tight (bool): 是否自动调整布局（tight_layout），默认 True
    """
    path = config.CHART_DIR / f"{name}.png"
    if tight:
        fig.tight_layout()
    # 保存为 300 DPI 的 PNG，白色背景（与 README 声明一致）
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)  # 关闭 Figure 释放内存
    print(f"保存: {path}")


# =====================================================================
# 图1: 评分分布饼图
# 展示各星级评价的数量与占比，直观反映景区整体口碑
# =====================================================================
def chart_score_distribution(df, font):
    print("\n生成图1: 评分分布饼图")
    score_dist = df["总评分"].value_counts().sort_index()  # 按评分升序统计数量

    fig, ax = plt.subplots(figsize=(9, 6))
    # 图例标签：星级 + 数量 + 百分比（放在右侧图例，避免小扇区互相遮挡）
    labels = [f"{int(s)}星: {v}条 ({v/len(df)*100:.1f}%)" for s, v in score_dist.items()]
    colors_list = [config.SCORE_COLORS[int(s)] for s in score_dist.index]
    # 轻微分离各扇区，让小扇区不再挤成一团
    explode = [0.03] * len(score_dist)

    wedges, _ = ax.pie(
        score_dist.values,
        colors=colors_list,
        startangle=90,  # 从 12 点钟方向开始绘制
        explode=explode,
        textprops={"fontsize": 11},
    )

    # 右侧图例：信息完整且不遮挡扇区
    legend = ax.legend(
        wedges, labels,
        title="评分",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=11,
    )
    legend.get_title().set_fontproperties(font)
    for text in legend.get_texts():
        text.set_fontproperties(font)

    ax.set_title(
        f"中华麋鹿园评分分布\n(平均 {df['总评分'].mean():.2f}分，共 {len(df)} 条评价)",
        fontsize=14, fontproperties=font, pad=20,
    )
    ax.axis("equal")  # 确保饼图为正圆形
    save_chart(fig, "01_评分分布", tight=False)


# =====================================================================
# 图2: 评分维度对比柱状图
# 对比景色、趣味、性价比三个维度的平均评分，发现景区的强项与短板
# =====================================================================
def chart_dimension_comparison(df, font):
    print("\n生成图2: 评分维度对比")
    dim_scores = {
        "景色": df["景色评分"].mean(),
        "趣味": df["趣味评分"].mean(),
        "性价比": df["性价比评分"].mean(),
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        dim_scores.keys(), dim_scores.values(),
        color=[COLORS["primary"], COLORS["info"], COLORS["warning"]],
        width=0.6,
    )
    ax.set_ylim(0, 5)  # Y 轴范围 0-5 分
    ax.set_ylabel("评分", fontproperties=font, fontsize=12)
    ax.set_title("评分维度对比", fontproperties=font, fontsize=14, pad=15)

    # 在柱顶标注具体分值
    for bar, val in zip(bars, dim_scores.values()):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
            f"{val:.2f}", ha="center", va="bottom", fontsize=12, fontweight="bold",
        )

    ax.set_xticklabels(dim_scores.keys(), fontproperties=font, fontsize=12)
    ax.axhline(y=4.5, color="gray", linestyle="--", alpha=0.5, label="4.5基准线")
    ax.legend(prop=font, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    save_chart(fig, "02_评分维度对比")


# =====================================================================
# 图3: 年度评价量趋势（双 Y 轴图）
# 左轴：年度评价数量（柱）；右轴：年度平均评分（折线）
# =====================================================================
def chart_yearly_trend(df_valid, font):
    print("\n生成图3: 年度评价量趋势")
    yearly = df_valid.groupby("年份").agg(
        评价数=("评论ID", "count"),
        平均评分=("总评分", "mean"),
    ).reset_index()
    # 过滤样本量过少的年份（不具统计意义）
    yearly = yearly[yearly["评价数"] >= config.MIN_YEAR_SAMPLES]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    # 左 Y 轴：柱状图显示年度评价数量
    color1 = COLORS["primary"]
    ax1.bar(yearly["年份"].astype(str), yearly["评价数"], color=color1, alpha=0.8, label="评价数")
    ax1.set_xlabel("年份", fontproperties=font, fontsize=12)
    ax1.set_ylabel("评价数", color=color1, fontproperties=font, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_title("年度评价数量与评分趋势", fontproperties=font, fontsize=14, pad=15)
    ax1.set_xticklabels(yearly["年份"].astype(str), fontproperties=font, rotation=45)

    # 右 Y 轴：折线图显示年度平均评分
    ax2 = ax1.twinx()
    color2 = COLORS["danger"]
    ax2.plot(yearly["年份"].astype(str), yearly["平均评分"], color=color2, marker="o", linewidth=2, label="平均评分")
    ax2.set_ylabel("平均评分", color=color2, fontproperties=font, fontsize=12)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(4, 5)  # 评分范围固定在 4-5 以突出波动
    ax2.grid(axis="y", alpha=0.3)

    # 合并左右轴的图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, prop=font, loc="upper left")
    save_chart(fig, "03_年度趋势")


# =====================================================================
# 图4: 月度评价趋势（2023年至今）
# 双 Y 轴折线图：评价数量 + 平均评分，按月粒度展示更精细的趋势
# =====================================================================
def chart_monthly_trend(df_valid, font):
    print("\n生成图4: 月度评价趋势")
    monthly = df_valid.groupby("年月").agg(
        评价数=("评论ID", "count"),
        平均评分=("总评分", "mean"),
    ).reset_index()
    # 只保留 2023-01 以后的数据（之前数据量太少）
    monthly_recent = monthly[monthly["年月"] >= "2023-01"].sort_values("年月")

    fig, ax1 = plt.subplots(figsize=(12, 5))
    color1 = COLORS["info"]
    ax1.plot(monthly_recent["年月"], monthly_recent["评价数"], color=color1, marker="o", linewidth=2, label="评价数")
    ax1.set_xlabel("月份", fontproperties=font, fontsize=12)
    ax1.set_ylabel("评价数", color=color1, fontproperties=font, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.tick_params(axis="x", rotation=45)
    ax1.set_xticklabels(monthly_recent["年月"], fontproperties=font, fontsize=9)
    ax1.set_title("月度评价数量趋势（2023年至今）", fontproperties=font, fontsize=14, pad=15)

    ax2 = ax1.twinx()
    color2 = COLORS["danger"]
    ax2.plot(monthly_recent["年月"], monthly_recent["平均评分"], color=color2, marker="s", linewidth=2, alpha=0.7, label="平均评分")
    ax2.set_ylabel("平均评分", color=color2, fontproperties=font, fontsize=12)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(3.5, 5)

    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(loc="upper left", prop=font)
    ax2.legend(loc="upper right", prop=font)
    save_chart(fig, "04_月度趋势")


# =====================================================================
# 图5: 季节性分析
# 双 Y 轴图：四季评价量（柱）+ 平均评分（折线），识别旺季/淡季窗口
# =====================================================================
def chart_seasonal(df_valid, font):
    print("\n生成图5: 季节性分析")
    seasonal = df_valid.groupby("季节").agg(
        评价数=("评论ID", "count"),
        平均评分=("总评分", "mean"),
    ).reset_index()
    # 按春夏秋冬顺序排列
    seasonal = seasonal.set_index("季节").reindex(config.SEASON_ORDER).reset_index()

    fig, ax1 = plt.subplots(figsize=(10, 5))
    color1 = COLORS["success"]
    bars = ax1.bar(seasonal["季节"], seasonal["评价数"], color=color1, alpha=0.8, label="评价数")
    ax1.set_xlabel("季节", fontproperties=font, fontsize=12)
    ax1.set_ylabel("评价数", color=color1, fontproperties=font, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_title("四季评价量与评分对比", fontproperties=font, fontsize=14, pad=15)
    ax1.set_xticklabels(seasonal["季节"], fontproperties=font, fontsize=11)

    # 在柱顶标注具体数值
    for bar, val in zip(bars, seasonal["评价数"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10, f"{int(val)}",
                 ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax2 = ax1.twinx()
    color2 = COLORS["danger"]
    ax2.plot(seasonal["季节"], seasonal["平均评分"], color=color2, marker="o", linewidth=2, markersize=8, label="平均评分")
    ax2.set_ylabel("平均评分", color=color2, fontproperties=font, fontsize=12)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(4, 5)
    ax2.grid(axis="y", alpha=0.3)

    ax1.legend(loc="upper left", prop=font)
    ax2.legend(loc="upper right", prop=font)
    save_chart(fig, "05_季节性分析")


# =====================================================================
# 图6: 用户等级分布饼图
# 展示携程会员等级分布，了解景区客群的用户画像
# =====================================================================
def chart_member_distribution(df, font):
    print("\n生成图6: 用户等级分布")
    member_dist = df["用户等级"].value_counts()  # 全部有效等级（实际 4 类）
    valid_total = int(df["用户等级"].notna().sum())  # 有效样本 2547 条，作为百分比分母
    fig, ax = plt.subplots(figsize=(9, 6))
    colors_list = [COLORS["primary"], COLORS["info"], COLORS["success"],
                   COLORS["warning"], COLORS["danger"], COLORS["secondary"]]
    # 百分比基于有效样本（2547 条）计算，使各扇区占比之和恰为 100%，
    # 避免原先以全量 3050 做分母导致"扇区之和仅 83.5%"的语义偏差
    labels = [f"{k}: {v}条 ({v/valid_total*100:.1f}%)" for k, v in member_dist.items()]
    explode = [0.03] * len(member_dist)

    wedges, _ = ax.pie(
        member_dist.values,
        colors=colors_list,
        startangle=90,
        explode=explode,
        textprops={"fontsize": 11},
    )

    legend = ax.legend(
        wedges, labels,
        title="用户等级",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=11,
    )
    legend.get_title().set_fontproperties(font)
    for text in legend.get_texts():
        text.set_fontproperties(font)

    ax.set_title(f"用户等级分布（基于 {valid_total} 条有效样本）", fontproperties=font, fontsize=14, pad=20)
    ax.axis("equal")
    save_chart(fig, "06_用户等级分布", tight=False)


# =====================================================================
# 图7: 来源地区 TOP10（横向柱状图）
# 展示 IP 属地排名前 10 的省份，分析客源地理分布
# =====================================================================
def chart_source_regions(df, font):
    print("\n生成图7: 来源地区TOP10")
    ip_dist = df["IP属地"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(9, 6))
    y_pos = np.arange(len(ip_dist))
    bars = ax.barh(y_pos, ip_dist.values, color=COLORS["primary"], alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ip_dist.index, fontproperties=font, fontsize=11)
    ax.invert_yaxis()  # 数量最多的在最上方
    ax.set_xlabel("评价数", fontproperties=font, fontsize=12)
    ax.set_title("评价来源地区 TOP10", fontproperties=font, fontsize=14, pad=15)

    for bar, val in zip(bars, ip_dist.values):
        ax.text(val + 10, bar.get_y() + bar.get_height() / 2, f"{int(val)}",
                va="center", fontsize=10, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    save_chart(fig, "07_来源地区TOP10")


# =====================================================================
# 图8: 评论长度分布
# 按字数区间统计评论数量，了解游客评价的表达深度
# =====================================================================
def chart_length_distribution(df_valid, font):
    print("\n生成图8: 评论长度分布")
    # 使用 config 统一的分箱边界与标签
    df_valid = df_valid.copy()
    df_valid["长度区间"] = pd.cut(df_valid["评论字数"], bins=config.LENGTH_BINS,
                                   labels=config.LENGTH_LABELS, right=True)
    length_dist = df_valid["长度区间"].value_counts().reindex(config.LENGTH_LABELS)

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(config.LENGTH_LABELS, length_dist.values, color=COLORS["secondary"], alpha=0.8)
    ax.set_xlabel("评论字数区间", fontproperties=font, fontsize=12)
    ax.set_ylabel("评论数", fontproperties=font, fontsize=12)
    ax.set_title(f"评论长度分布（平均 {df_valid['评论字数'].mean():.0f}字）", fontproperties=font, fontsize=14, pad=15)
    ax.set_xticklabels(config.LENGTH_LABELS, fontproperties=font, fontsize=10, rotation=30)

    for bar, val in zip(bars, length_dist.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5, f"{int(val)}",
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    save_chart(fig, "08_评论长度分布")


# =====================================================================
# 图9 & 图10: 词云 + 高频词 TOP15
# 对全量评论 jieba 分词后，生成词云与高频词柱状图
# =====================================================================
def chart_wordcloud_and_top_words(df, font):
    import wordcloud

    print("\n生成图9: 词云")
    # 统一使用 data_utils 的分词与词频统计（含停用词过滤）
    word_freq = data_utils.word_frequency(df["评论内容"])

    # ---- 图9: 词云 ----
    simhei = "C:/Windows/Fonts/simhei.ttf"
    wc = wordcloud.WordCloud(
        font_path=simhei if os.path.exists(simhei) else None,  # 黑体支持中文渲染
        width=800, height=500,
        background_color="white",
        max_words=100,
        colormap="viridis",
        max_font_size=120,
        min_font_size=10,
    ).generate_from_frequencies(dict(word_freq.most_common(100)))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("全部评价词云", fontproperties=font, fontsize=14, pad=15)
    save_chart(fig, "09_词云")

    # ---- 图10: 高频词 TOP15 ----
    print("\n生成图10: 高频词TOP15")
    words_list, counts_list = zip(*word_freq.most_common(15))

    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = np.arange(len(words_list))
    bars = ax.barh(y_pos, counts_list, color=COLORS["info"], alpha=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(words_list, fontproperties=font, fontsize=12)
    ax.invert_yaxis()  # 频率最高的在最上方
    ax.set_xlabel("出现次数", fontproperties=font, fontsize=12)
    ax.set_title("评论高频词 TOP15", fontproperties=font, fontsize=14, pad=15)

    for bar, val in zip(bars, counts_list):
        ax.text(val + 3, bar.get_y() + bar.get_height() / 2, f"{int(val)}",
                va="center", fontsize=10, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    save_chart(fig, "10_高频词TOP15")


# =====================================================================
# 图11: 好评差评关键词对比（双面板图）
# 左右对比好评（4-5星）与差评（1-2星）的高频关键词
# =====================================================================
def chart_positive_negative_keywords(df_valid, font):
    print("\n生成图11: 好评差评关键词对比")
    df_positive = df_valid[df_valid["总评分"] >= config.POSITIVE_MIN_SCORE]
    df_negative = df_valid[df_valid["总评分"] <= config.NEGATIVE_MAX_SCORE]

    # 好评/差评分别统计词频（保留数字词，与原逻辑一致）
    pos_freq = data_utils.word_frequency(df_positive["评论内容"], drop_digits=False).most_common(10)
    neg_freq = data_utils.word_frequency(df_negative["评论内容"], drop_digits=False).most_common(10)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # ---- 左图：好评关键词 TOP10 ----
    pos_words_list, pos_counts = zip(*pos_freq)
    y_pos = np.arange(len(pos_words_list))
    bars = ax1.barh(y_pos, pos_counts, color=COLORS["success"], alpha=0.8)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(pos_words_list, fontproperties=font, fontsize=12)
    ax1.invert_yaxis()
    ax1.set_xlabel("出现次数", fontproperties=font, fontsize=12)
    ax1.set_title(f"好评关键词 TOP10\n({len(df_positive)}条好评)", fontproperties=font, fontsize=14, pad=15)
    for bar, val in zip(bars, pos_counts):
        ax1.text(val + 2, bar.get_y() + bar.get_height() / 2, f"{int(val)}",
                 va="center", fontsize=10, fontweight="bold")
    ax1.grid(axis="x", alpha=0.3)

    # ---- 右图：差评关键词 TOP10 ----
    neg_words_list, neg_counts = zip(*neg_freq)
    y_pos = np.arange(len(neg_words_list))
    bars = ax2.barh(y_pos, neg_counts, color=COLORS["danger"], alpha=0.8)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(neg_words_list, fontproperties=font, fontsize=12)
    ax2.invert_yaxis()
    ax2.set_xlabel("出现次数", fontproperties=font, fontsize=12)
    ax2.set_title(f"差评关键词 TOP10\n({len(df_negative)}条差评)", fontproperties=font, fontsize=14, pad=15)
    for bar, val in zip(bars, neg_counts):
        ax2.text(val + 1, bar.get_y() + bar.get_height() / 2, f"{int(val)}",
                 va="center", fontsize=10, fontweight="bold")
    ax2.grid(axis="x", alpha=0.3)

    save_chart(fig, "11_好评差评关键词对比")


# =====================================================================
# 图12: 情感极性分布（SnowNLP 模型）
# 对每条评论做中文情感极性打分，按 正面/中性/负面 展示分布
# =====================================================================
def chart_sentiment_polarity(df, font):
    print("\n生成图12: 情感极性分布（SnowNLP 模型）")
    dist = df["情感分类"].value_counts()
    order = ["正面", "中性", "负面"]
    vals = [int(dist.get(c, 0)) for c in order]
    colors = [COLORS["success"], COLORS["warning"], COLORS["danger"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(order, vals, color=colors, alpha=0.85)
    ax.set_ylabel("评论数", fontproperties=font, fontsize=12)
    ax.set_title("情感极性分布（SnowNLP 模型）", fontproperties=font, fontsize=14, pad=15)
    ax.set_xticklabels(order, fontproperties=font, fontsize=13)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                f"{int(val)}", ha="center", fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    save_chart(fig, "12_情感极性分布")


def main():
    """图表生成主入口：加载数据 -> 设置字体 -> 依次生成 12 张图表。"""
    plt.style.use("default")
    font = setup_chinese_font()

    # 统一从 data_utils 加载并预处理数据
    df, df_valid = data_utils.load_reviews()

    # 情感极性（SnowNLP 模型）：为 df 追加 情感极性/情感分类 列
    data_utils.add_sentiment_polarity(df)
    # 重新推导有效时间子集，使其携带情感极性列
    df_valid = df[df["年份"].notna()].copy()
    df_valid["年份"] = df_valid["年份"].astype(int)
    df_valid["月份"] = df_valid["月份"].astype(int)

    chart_score_distribution(df, font)
    chart_dimension_comparison(df, font)
    chart_yearly_trend(df_valid, font)
    chart_monthly_trend(df_valid, font)
    chart_seasonal(df_valid, font)
    chart_member_distribution(df, font)
    chart_source_regions(df, font)
    chart_length_distribution(df_valid, font)
    chart_wordcloud_and_top_words(df, font)
    chart_positive_negative_keywords(df_valid, font)
    chart_sentiment_polarity(df, font)

    print("\n" + "=" * 60)
    print("所有图表生成完成!")
    print(f"图表保存位置: {config.CHART_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
