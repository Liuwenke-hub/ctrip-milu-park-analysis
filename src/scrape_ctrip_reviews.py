# -*- coding: utf-8 -*-
"""
携程景区评价数据爬虫 - 中华麋鹿园
==========================================================================
景区: 盐城中华麋鹿园 (sightId=17408, poiId=79598)
排序: 按最新 (sortType=2)
数据源: 携程移动端 REST API

功能概述:
    1. 通过携程移动端 REST API 分页采集中华麋鹿园的全部游客评价数据
    2. 解析 API 返回的 .NET JSON 日期格式为可读时间字符串
    3. 提取评论 ID、用户昵称、评分（总评+景色+趣味+性价比）、评论内容、
       发布时间、IP 属地、官方回复等 22 个字段
    4. 对采集结果去重、按时间排序，保存为 CSV / Excel / JSON 三种格式
    5. 输出数据概览（时间范围、平均评分、评分分布等）

技术要点:
    - 使用移动端 User-Agent 模拟 iPhone Safari 访问，降低被识别为爬虫的概率
    - 每页请求 50 条数据，减少总请求次数
    - 内置重试机制（最多 3 次）和请求间隔（1.5 秒），避免触发反爬限制
    - 连续 3 页无数据时自动终止，防止无效请求

"""

import json
import time
import re
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

import config

# ========== 分页与请求策略参数 ==========
API_URL = "https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"
PAGE_SIZE = 50  # 每页请求数据条数，设为 50 以减少总请求次数（API 最大支持 50）
SORT_TYPE = 2   # 排序方式：1=推荐排序, 2=最新排序（按发布时间倒序）
DELAY = 1.5     # 每次请求间隔（秒），用于避免触发携程 API 的频率限制
MAX_EMPTY_PAGES = 3  # 连续空页阈值：连续无数据达到该值即终止（应对分页上限）

# HTTP 请求头：模拟 iPhone Safari 浏览器访问
# 使用移动端 UA 是因为携程移动端 API 对移动端请求的校验相对宽松
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Content-Type": "application/json",
    # Referer 指向景区页面，模拟从景区页面发起的请求
    "Referer": f"https://m.ctrip.com/webapp/you/sight/yancheng493/{config.SIGHT_ID}.html",
    "Origin": "https://m.ctrip.com",
}


def parse_dotnet_date(date_str):
    """
    将 .NET JSON 日期格式转换为可读的时间字符串。

    携程 API 返回的时间字段采用 .NET 框架的 JSON 日期格式：
        /Date(1594988744000+0800)/
    其中：
        - 1594988744000 是 Unix 时间戳（毫秒）
        - +0800 是时区偏移（东八区，即北京时间）

    Args:
        date_str (str): .NET JSON 日期字符串，如 "/Date(1594988744000+0800)/"

    Returns:
        str: 格式化后的时间字符串 "YYYY-MM-DD HH:MM:SS"，若输入为空则返回 None
    """
    if not date_str:
        return None

    # 使用正则表达式提取时间戳和时区偏移
    match = re.match(r'/Date\((\d+)([+-]\d{4})\)/', date_str)
    if match:
        # 提取毫秒级时间戳并转换为秒级
        timestamp = int(match.group(1)) / 1000
        tz_offset = match.group(2)  # 如 "+0800" 或 "-0500"

        # 解析时区偏移量：前 3 位为小时部分（含符号），后 2 位为分钟部分
        tz_hours = int(tz_offset[:3])                # 如 "+08" -> 8
        tz_mins = int(tz_offset[0] + tz_offset[3:])  # 如 "+00" -> 0
        tz = timezone(timedelta(hours=tz_hours, minutes=tz_mins))

        # 将时间戳转换为带时区的 datetime 对象，再格式化为字符串
        dt = datetime.fromtimestamp(timestamp, tz=tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    return None


def build_request(page_index):
    """
    构建携程 API 请求体。

    携程移动端评论 API 采用 POST 方式，请求体为 JSON 格式。
    请求体结构遵循携程 SOA2 架构规范，包含景区 ID、分页参数和请求头信息。

    Args:
        page_index (int): 页码，从 1 开始

    Returns:
        dict: 可直接传给 requests.post(json=...) 的请求体字典
    """
    return {
        "arg": {
            "sightId": config.SIGHT_ID,    # 景区 ID
            "poiId": config.POI_ID,        # 兴趣点 ID
            "pageIndex": page_index,       # 当前页码
            "pageSize": PAGE_SIZE,         # 每页条数
            "sortType": SORT_TYPE,         # 排序方式：2=最新
            "sourceType": 1,               # 来源类型：1=景区详情页
            "commentTagId": 0,             # 评论标签 ID：0=全部标签
            "head": {
                # 携程 SOA2 架构的请求头字段，大部分为固定值
                "cid": "0",                # 客户端 ID
                "ctok": "",                # 客户端 token
                "cver": "1.0",             # 客户端版本
                "lang": "01",              # 语言：01=中文
                "sid": "8888",             # 会话 ID
                "syscode": "09",           # 系统编码：09=移动端 H5
                "auth": "",                # 认证信息（游客模式留空）
            },
        }
    }


def extract_comment_data(item):
    """
    从 API 返回的单条评论 JSON 中提取结构化字段。

    携程 API 返回的每条评论数据是嵌套的 JSON 对象，包含用户信息、
    分项评分、扩展信息、图片视频列表等多个子对象。本函数将这些
    嵌套字段展平为一维字典，便于后续存入 DataFrame。

    Args:
        item (dict): API 返回的单条评论 JSON 对象

    Returns:
        dict: 包含 22 个字段的结构化评论数据，字段名已汉化
    """
    # 安全提取嵌套子对象（使用 or {} 避免 None 引发异常）
    user_info = item.get("userInfo") or {}   # 用户信息子对象
    scores = item.get("scores") or []        # 分项评分数组
    ext_info = item.get("extInfo") or {}     # 扩展信息子对象
    images = item.get("Images") or []        # 图片列表
    videos = item.get("videos") or []        # 视频列表

    # 将分项评分数组转换为字典 {景色: 4.5, 趣味: 4.0, 性价比: 4.0}
    score_dict = {}
    for s in scores:
        name = s.get("name", "")    # 维度名称：景色/趣味/性价比
        score_val = s.get("score")  # 该维度的评分值
        if name:
            score_dict[name] = score_val

    # 评论内容 / 官方回复：去除换行符并去除首尾空白
    content = item.get("content", "")
    content = content.replace("\n", " ").strip() if content else ""
    reply = item.get("replyContent", "")
    reply = reply.replace("\n", " ").strip() if reply else ""

    # 构建并返回结构化的评论数据字典（共 22 个字段）
    return {
        "评论ID": item.get("commentId"),
        "用户昵称": user_info.get("userNick", ""),        # 用户昵称
        "用户等级": user_info.get("userMember", ""),      # 携程会员等级（如"铂金贵宾"）
        "总评分": item.get("score"),                       # 总体评分（1-5 分）
        "景色评分": score_dict.get("景色"),                # 景色维度评分
        "趣味评分": score_dict.get("趣味"),                # 趣味维度评分
        "性价比评分": score_dict.get("性价比"),            # 性价比维度评分
        "评论内容": content,                               # 评论正文
        "发布时间": parse_dotnet_date(item.get("publishTime")),  # 发布时间（已格式化）
        "发布标签": item.get("publishTypeTag", ""),        # 发布标签（如"来自手机端"）
        "有用数": item.get("usefulCount", 0),              # "有用"点击数
        "回复数": item.get("replyCount", 0),               # 回复数
        "收藏数": item.get("collectCnt", 0),               # 收藏数
        "图片数": len(images),                             # 图片数量
        "视频数": len(videos),                             # 视频数量
        "游玩时间": ext_info.get("playTime"),              # 游玩时间
        "人均花费": ext_info.get("avgCost"),               # 人均花费（元）
        "IP属地": item.get("ipLocatedName") or "",         # IP 属地（省份）
        "官方回复": reply,                                  # 官方回复内容
        "官方回复时间": parse_dotnet_date(item.get("replyTime")),  # 官方回复时间
        "评论链接": item.get("jumpH5Url", ""),             # 评论 H5 跳转链接
        "语言": item.get("languageType", ""),              # 评论语言类型
    }


def fetch_page(page_index, max_retries=3):
    """
    获取单页评论数据，内置重试机制。

    向携程 API 发送 POST 请求获取指定页码的评论数据。
    如果请求失败或 API 返回非 200 状态码，将自动重试。

    Args:
        page_index (int): 要获取的页码（从 1 开始）
        max_retries (int): 最大重试次数，默认 3 次

    Returns:
        tuple: (items, total_count)
            - items (list): 当前页的评论列表，每个元素是一条评论的 JSON 对象
            - total_count (int): API 报告的评论总数（仅第一页返回有效值）
            若所有重试均失败，返回 ([], 0)
    """
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                API_URL,
                json=build_request(page_index),  # 构建请求体
                headers=HEADERS,
                timeout=20,                      # 超时时间 20 秒
            )
            data = resp.json()

            # 检查 API 响应状态码
            if data.get("code") == 200:
                result = data.get("result", {})
                items = result.get("items") or []    # 当前页评论列表
                total = result.get("totalCount", 0)  # 评论总数
                return items, total

            # API 返回错误码，打印警告并等待后重试
            print(f"  [警告] API返回 code={data.get('code')}, msg={data.get('msg')}")
            if attempt < max_retries - 1:
                time.sleep(3)  # 等待 3 秒后重试
        except Exception as e:
            # 网络异常或其他错误，打印错误信息并等待后重试
            print(f"  [错误] 第{page_index}页 请求失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 网络异常等待更久（5 秒）

    # 所有重试均失败，返回空结果
    return [], 0


def scrape_all_comments():
    """
    分页采集全部评论数据。

    流程:
        1. 循环分页请求 API，逐页采集评论数据
        2. 第一页获取评论总数，计算预计爬取页数
        3. 连续 MAX_EMPTY_PAGES 页无数据时自动终止（应对分页上限）
        4. 累计达到总数或到达最后一页时终止

    Returns:
        list[dict]: 全部评论的结构化数据列表
    """
    all_comments = []      # 存储所有采集到的评论数据
    total_count = 0        # API 报告的评论总数
    total_pages = 0        # 预计总页数
    page = 1               # 当前页码
    empty_page_count = 0   # 连续空页计数（用于判断是否到达分页上限）

    while True:
        items, total = fetch_page(page)

        # 第一页获取总数并计算预计页数
        if page == 1:
            total_count = total
            total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE  # 向上取整
            print(f"\n总评价数: {total_count}")
            print(f"预计爬取页数: {total_pages} 页 (每页{PAGE_SIZE}条)")
            print("开始爬取...\n")

        # 处理空页情况
        if not items:
            empty_page_count += 1
            print(f"  第 {page}/{total_pages} 页: 无数据 (连续空页: {empty_page_count})")
            # 连续多页无数据，认为已到达分页上限，终止爬取
            if empty_page_count >= MAX_EMPTY_PAGES:
                print(f"  连续{MAX_EMPTY_PAGES}页无数据，停止爬取")
                break
        else:
            empty_page_count = 0  # 重置空页计数
            # 逐条提取评论数据并添加到列表
            for item in items:
                all_comments.append(extract_comment_data(item))
            print(f"  第 {page}/{total_pages} 页: 获取 {len(items)} 条 | 累计 {len(all_comments)} 条")

        # 检查是否已采集全部数据
        if total_count > 0 and len(all_comments) >= total_count:
            print(f"\n已获取全部 {total_count} 条评价!")
            break

        # 检查是否已到达最后一页
        if page >= total_pages and total_pages > 0:
            print(f"\n已到达最后一页 ({total_pages})")
            break

        # 翻到下一页并等待
        page += 1
        time.sleep(DELAY)

    return all_comments


def save_comments(all_comments):
    """
    将采集结果去重、排序后保存为 CSV / Excel / JSON 三种格式。

    Args:
        all_comments (list[dict]): 采集到的评论数据列表

    Returns:
        pandas.DataFrame: 去重排序后的 DataFrame（供数据概览使用）
    """
    df = pd.DataFrame(all_comments)

    # 按"评论ID"去重（API 可能返回重复数据），保留第一次出现的记录
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["评论ID"], keep="first")
    after_dedup = len(df)
    if before_dedup != after_dedup:
        print(f"去重: {before_dedup} -> {after_dedup} (删除 {before_dedup - after_dedup} 条重复)")

    # 按发布时间降序排列（最新的在最前面）
    df = df.sort_values("发布时间", ascending=False).reset_index(drop=True)

    # CSV（UTF-8-BOM 编码，确保 Excel 打开时中文不乱码）
    df.to_csv(config.REVIEWS_CSV, index=False, encoding="utf-8-sig")
    print(f"CSV 已保存: {config.REVIEWS_CSV} ({len(df)} 条)")

    # Excel（使用 openpyxl 引擎）
    df.to_excel(config.REVIEWS_XLSX, index=False, engine="openpyxl")
    print(f"Excel 已保存: {config.REVIEWS_XLSX} ({len(df)} 条)")

    # 原始 JSON（保留所有字段，便于后续扩展分析）
    with open(config.REVIEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=2)
    print(f"JSON 已保存: {config.REVIEWS_JSON}")

    return df


def print_overview(df):
    """打印数据概览（时间范围、平均评分、评分分布等统计信息）。"""
    print("\n" + "=" * 70)
    print("  数据概览")
    print("=" * 70)
    print(f"总评价数: {len(df)}")
    print(f"时间范围: {df['发布时间'].min()} ~ {df['发布时间'].max()}")
    print(f"平均评分: {df['总评分'].mean():.2f}")
    print("评分分布:")
    print(df['总评分'].value_counts().sort_index().to_string())
    print(f"\n有图片的评价: {df[df['图片数'] > 0].shape[0]} 条")
    print(f"有官方回复的评价: {df[df['官方回复'].notna() & (df['官方回复'] != '')].shape[0]} 条")


def main():
    """爬虫主入口：采集 -> 保存 -> 输出概览。"""
    print("=" * 70)
    print(f"  携程景区评价爬虫 - {config.SIGHT_NAME}")
    print(f"  sightId={config.SIGHT_ID}, poiId={config.POI_ID}")
    print(f"  排序: 按最新 | 每页: {PAGE_SIZE}条")
    print("=" * 70)

    all_comments = scrape_all_comments()

    print("\n" + "=" * 70)
    print("  保存数据")
    print("=" * 70)
    df = save_comments(all_comments)

    print_overview(df)
    print("\n爬取完成!")


if __name__ == "__main__":
    main()
