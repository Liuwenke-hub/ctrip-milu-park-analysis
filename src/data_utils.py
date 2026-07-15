# -*- coding: utf-8 -*-
"""
数据加载与文本处理工具
==========================================================================
封装图表生成、报告生成、交互仪表盘三个脚本共享的数据处理逻辑，
避免同一套「读 CSV -> 解析时间 -> 提取衍生特征 -> jieba 分词」的代码
在多个文件里各写一份、日后各自漂移。

对外提供:
    load_reviews()      读取评价 CSV，补全时间与衍生特征，返回 (df, df_valid)
    classify_score_level()  将总评分映射为好评 / 中评 / 差评
    tokenize()          jieba 分词 + 停用词过滤的统一实现
    word_frequency()    对一组文本分词并统计词频，返回 Counter
    add_sentiment_polarity()  用 snownlp 计算每条评论的情感极性(0-1)与分类
    STOPWORDS           统一维护的中文停用词表

情感极性模型说明:
    使用 SnowNLP（snownlp）对每条评论做中文情感极性打分，返回 0-1 区间，
    0 为极负面、1 为极正面。阈值划分：
        极性 >= 0.6  -> 正面
        极性 <= 0.4  -> 负面
        0.4 < 极性 < 0.6 -> 中性
    该模型基于电商评论语料训练，对旅游场景的极性判断为「近似估计」，
    与「按星级分段」互补：星级是游客给的客观评分，极性是文本语义倾向，
    二者对比可发现「高分低极性」（隐性不满）等现象。snownlp 为懒加载，
    未安装时自动跳过并给出警告，不影响其余分析流程。

"""

from collections import Counter

import pandas as pd
import jieba

import config

# ========== 停用词表 ==========
# 统一维护的停用词集合（此前分散在多个脚本中，且已出现不一致）。
# 涵盖虚词 / 代词 / 语气词 / 平台用语 / 景区名称 / 泛化形容词等，
# 这些词出现频率高但对分析无实质意义，需在分词后过滤。
STOPWORDS = {
    # ---- 常见虚词、代词、连词 ----
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "还", "把",
    "让", "被", "从", "能", "可以", "但", "而", "又", "如果", "因为", "所以",
    # ---- 语气词 ----
    "吗", "吧", "啊", "呢", "哦", "嗯", "哈", "呀", "啦", "嘿",
    # ---- 平台用语（非评论内容） ----
    "携程", "点评", "发布", "发布点评", "点评发布", "评价", "评论", "评分",
    # ---- 景区名称与通用词（过于宽泛，不具区分度） ----
    # 注意：核心主题词「麋鹿」已从停用词中移除——
    # 对单景区分析而言它是最具代表性的高频词，应在词云/高频词中正常呈现；
    # 仅保留「中华麋鹿园」「麋鹿园」等长专有名词变体以避免重复计数噪声。
    "中华麋鹿园", "麋鹿园", "大丰", "景区", "地方", "时候", "真的",
    "比较", "觉得", "其实", "虽然", "不过", "这个", "那个", "这样", "那样",
    # ---- 程度副词与泛化形容词 ----
    "非常", "特别", "不错", "好玩", "有趣", "值得", "推荐", "还是",
    "太", "超", "巨", "相当", "挺", "稍", "很多", "不少", "就是", "有点",
    "我们", "他们", "大家", "小时", "进去", "里面", "可能",
}


def load_reviews(csv_path=None, add_features=True):
    """
    读取评价 CSV 并补全分析所需的衍生字段。

    这是所有分析脚本的统一数据入口，保证各脚本使用完全一致的
    预处理逻辑（时间解析、季节划分、评论字数、评分等级）。

    Args:
        csv_path (str|Path|None): CSV 路径，默认使用 config.REVIEWS_CSV
        add_features (bool): 是否补全时间与衍生特征，默认 True

    Returns:
        tuple: (df, df_valid)
            - df: 全量数据（含解析失败的时间记录，年份为 NaN）
            - df_valid: 仅保留时间解析成功的记录，年份/月份已转为 int，
                        用于所有时间相关分析
    """
    csv_path = csv_path or config.REVIEWS_CSV
    # UTF-8-BOM 编码，使用 utf-8-sig 自动去除 BOM 头
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    if add_features:
        df = add_time_features(df)
        df = add_derived_features(df)

    # 过滤时间解析失败的记录，得到用于时间分析的有效子集
    df_valid = df[df["年份"].notna()].copy()
    df_valid["年份"] = df_valid["年份"].astype(int)
    df_valid["月份"] = df_valid["月份"].astype(int)
    return df, df_valid


def add_time_features(df):
    """
    从「发布时间」字段解析并提取时间维度特征。

    新增列：发布时间_dt、年份、月份、年月、季度、季节。
    无法解析的时间会被置为 NaT（对应年份为 NaN）。
    """
    df["发布时间_dt"] = pd.to_datetime(df["发布时间"], errors="coerce")
    df["年份"] = df["发布时间_dt"].dt.year
    df["月份"] = df["发布时间_dt"].dt.month
    df["年月"] = df["发布时间_dt"].dt.to_period("M").astype(str)   # 如 "2025-06"
    df["季度"] = df["发布时间_dt"].dt.quarter
    df["季节"] = df["季度"].map(config.SEASON_MAP)
    return df


def add_derived_features(df):
    """
    补全文本与评分相关的衍生特征。

    新增列：评论字数（中文字符数）、评分等级（好评/中评/差评）。
    """
    df["评论字数"] = df["评论内容"].apply(lambda x: len(str(x)) if pd.notna(x) else 0)
    df["评分等级"] = df["总评分"].apply(classify_score_level)
    return df


def classify_score_level(score):
    """
    将总评分映射为三分类等级。

    规则：>= 4 星为好评，== 3 星为中评，<= 2 星为差评。

    Args:
        score (float): 总评分（1-5）

    Returns:
        str: "好评(4-5星)" | "中评(3星)" | "差评(1-2星)"
    """
    if score >= config.POSITIVE_MIN_SCORE:
        return "好评(4-5星)"
    if score == 3:
        return "中评(3星)"
    return "差评(1-2星)"


def tokenize(text, min_len=2, drop_digits=True):
    """
    对文本进行 jieba 分词并过滤停用词。

    Args:
        text (str): 待分词文本
        min_len (int): 保留的最小词长，默认 2（过滤单字）
        drop_digits (bool): 是否过滤纯数字词，默认 True

    Returns:
        list[str]: 过滤后的词列表
    """
    words = jieba.lcut(str(text))
    result = []
    for w in words:
        if len(w) < min_len:
            continue
        if w in STOPWORDS:
            continue
        if drop_digits and w.isdigit():
            continue
        result.append(w)
    return result


def word_frequency(texts, min_len=2, drop_digits=True):
    """
    对一组文本分词并统计词频。

    Args:
        texts (Iterable): 文本序列（如某列评论内容），会自动跳过空值
        min_len (int): 保留的最小词长
        drop_digits (bool): 是否过滤纯数字词

    Returns:
        collections.Counter: 词 -> 出现次数
    """
    joined = " ".join(str(t) for t in texts if pd.notna(t))
    return Counter(tokenize(joined, min_len=min_len, drop_digits=drop_digits))


# ========== 情感极性（SnowNLP 模型） ==========
# 阈值：极性 >= 0.6 为正面，<= 0.4 为负面，介于两者之间为中性
POSITIVE_POLARITY = 0.6
NEGATIVE_POLARITY = 0.4


def _snow_sentiment(text):
    """
    对单条文本调用 SnowNLP 计算情感极性得分(0-1)。

    懒加载 snownlp；文本为空、非字符串或解析异常时返回 NaN，
    由调用方统一处理为「未知」类别。

    Args:
        text (Any): 待计算的中文评论文本

    Returns:
        float: 情感极性得分(0-1)，失败时返回 float('nan')
    """
    try:
        from snownlp import SnowNLP
        if text is None or (isinstance(text, float) and pd.isna(text)):
            return float("nan")
        return float(SnowNLP(str(text)).sentiments)
    except Exception:
        return float("nan")


def classify_polarity(polarity):
    """
    将情感极性得分映射为三分类。

    规则：>= 0.6 正面，<= 0.4 负面，中间为中性；NaN 记为「未知」。

    Args:
        polarity (float): 情感极性得分(0-1)，可能为 NaN

    Returns:
        str: "正面" | "中性" | "负面" | "未知"
    """
    if polarity is None or (isinstance(polarity, float) and pd.isna(polarity)):
        return "未知"
    if polarity >= POSITIVE_POLARITY:
        return "正面"
    if polarity <= NEGATIVE_POLARITY:
        return "负面"
    return "中性"


def add_sentiment_polarity(df, text_col="评论内容"):
    """
    为 DataFrame 追加情感极性得分与分类列（就地修改并返回）。

    新增列：
        - 情感极性: SnowNLP 打分(0-1)，失败为 NaN
        - 情感分类: 正面 / 中性 / 负面 / 未知

    Args:
        df (DataFrame): 已加载的评价数据（需含 text_col 列）
        text_col (str): 评论文本列名

    Returns:
        DataFrame: 含新增两列的同一对象
    """
    try:
        import snownlp  # noqa: F401  仅用于探测是否可用
    except Exception:
        print("警告: snownlp 未安装，跳过情感极性计算（不影响其余分析）")
        df["情感极性"] = float("nan")
        df["情感分类"] = "未知"
        return df

    print("计算情感极性（SnowNLP 模型）...")
    df["情感极性"] = df[text_col].apply(_snow_sentiment)
    df["情感分类"] = df["情感极性"].apply(classify_polarity)
    dist = df["情感分类"].value_counts()
    print("  情感分类分布: " + ", ".join(f"{k}={v}" for k, v in dist.items()))
    return df
