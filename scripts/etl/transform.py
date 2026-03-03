# 导入依赖库
import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime

# 配置日志（和extract.py保持一致，解决编码问题）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("D:/Project/rec_tmall_bigdata/data/output/etl_log.log", encoding='utf-8'),
        logging.StreamHandler(stream=open('CONOUT$', 'w', encoding='utf-8'))
    ]
)

# ===================== 1. 用户行为表清洗 =====================
def transform_user_behavior(df, config):
    """
    清洗用户行为表：去重、空值处理、数据校验、格式标准化
    :param df: 抽取后的用户行为DataFrame
    :param config: 配置字典
    :return: 清洗后的DataFrame + 质量报告
    """
    if df is None or df.empty:
        logging.error("❌ 用户行为表为空，跳过清洗")
        return None, {}
    
    # 记录清洗前数据量
    before_clean = len(df)
    logging.info(f"📝 开始清洗用户行为表：原始行数 {before_clean}")

    # 步骤1：去重（按全字段去重）
    df = df.drop_duplicates()
    dup_count = before_clean - len(df)
    logging.info(f"🔍 去重：删除 {dup_count} 行重复数据")

    # 步骤2：删除关键字段空值（item_id/user_id/action/vtime是核心）
    key_fields = ['item_id', 'user_id', 'action', 'vtime']
    df = df.dropna(subset=key_fields)
    null_count = before_clean - dup_count - len(df)
    logging.info(f"🧹 删除空值：删除 {null_count} 行空值数据")

    # 步骤3：校验行为类型合法性（只保留click/collect/cart/alipay）
    valid_actions = ['click', 'collect', 'cart', 'alipay']
    df = df[df['action'].isin(valid_actions)]
    invalid_action_count = before_clean - dup_count - null_count - len(df)
    logging.info(f"✅ 过滤无效行为：删除 {invalid_action_count} 行无效行为数据")

    # 步骤4：数据格式标准化
    # 时间格式转datetime（兼容常见格式）
    df['vtime'] = pd.to_datetime(df['vtime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    # 删除时间解析失败的数据
    df = df.dropna(subset=['vtime'])
    time_error_count = before_clean - dup_count - null_count - invalid_action_count - len(df)
    logging.info(f"📅 时间格式标准化：删除 {time_error_count} 行时间解析失败数据")

    # 步骤5：按配置过滤增量数据（如果开启增量）
    if config['etl']['incremental']:
        start_date = datetime.strptime(config['etl']['start_date'], '%Y-%m-%d')
        df = df[df['vtime'] >= start_date]
        incremental_count = before_clean - len(df)
        logging.info(f"📈 增量过滤：保留 {start_date} 之后的数据，删除 {incremental_count} 行")

    # 生成数据质量报告
    quality_report = {
        "表名": "user_behavior",
        "原始行数": before_clean,
        "清洗后行数": len(df),
        "去重行数": dup_count,
        "空值行数": null_count,
        "无效行为行数": invalid_action_count,
        "时间解析失败行数": time_error_count,
        "增量过滤行数": incremental_count if config['etl']['incremental'] else 0,
        "时间范围": [df['vtime'].min(), df['vtime'].max()] if not df.empty else [],
        "行为类型分布": df['action'].value_counts().to_dict()
    }

    logging.info(f"✅ 用户行为表清洗完成：最终行数 {len(df)}")
    return df, quality_report

# ===================== 2. 商品详情表清洗 =====================
def transform_product_detail(df):
    """
    清洗商品详情表：保证商品ID唯一、补全缺失分类、格式标准化
    """
    if df is None or df.empty:
        logging.error("❌ 商品详情表为空，跳过清洗")
        return None, {}
    
    before_clean = len(df)
    logging.info(f"📝 开始清洗商品详情表：原始行数 {before_clean}")

    # 步骤1：商品ID去重（核心主键，必须唯一）
    df = df.drop_duplicates(subset=['item_id'])
    dup_count = before_clean - len(df)
    logging.info(f"🔍 商品ID去重：删除 {dup_count} 行重复数据")

    # 步骤2：删除核心字段空值
    key_fields = ['item_id', 'title', 'category']
    df = df.dropna(subset=key_fields)
    null_count = before_clean - dup_count - len(df)
    logging.info(f"🧹 删除空值：删除 {null_count} 行空值数据")

    # 步骤3：处理category字段，先转成字符串，再提取数字，最后转整型
    # 先转成字符串，避免非字符串类型报错
    df['category'] = df['category'].astype(str)
    # 提取字符串中的数字部分（处理类似"26287"、"分类26287"等情况）
    df['category'] = df['category'].str.extract(r'(\d+)')
    # 删除提取后为空的行
    df = df.dropna(subset=['category'])
    # 转成整型
    df['category'] = df['category'].astype(int)

    # 步骤4：格式标准化（去除标题空格）
    df['title'] = df['title'].astype(str).str.strip()

    # 生成质量报告
    quality_report = {
        "表名": "product_detail",
        "原始行数": before_clean,
        "清洗后行数": len(df),
        "商品ID重复行数": dup_count,
        "空值行数": null_count,
        "分类分布TOP10": df['category'].value_counts().head(10).to_dict()
    }

    logging.info(f"✅ 商品详情表清洗完成：最终行数 {len(df)}")
    return df, quality_report

# ===================== 3. 评价表清洗 =====================
def transform_review(df):
    """
    清洗用户评价表：去重、空值处理、评价内容标准化
    """
    if df is None or df.empty:
        logging.error("❌ 评价表为空，跳过清洗")
        return None, {}
    
    before_clean = len(df)
    logging.info(f"📝 开始清洗评价表：原始行数 {before_clean}")

    # 步骤1：全字段去重
    df = df.drop_duplicates()
    dup_count = before_clean - len(df)
    logging.info(f"🔍 去重：删除 {dup_count} 行重复数据")

    # 步骤2：删除核心字段空值
    key_fields = ['item_id', 'rater_uid', 'feedback']
    df = df.dropna(subset=key_fields)
    null_count = before_clean - dup_count - len(df)
    logging.info(f"🧹 删除空值：删除 {null_count} 行空值数据")

    # 步骤3：评价内容标准化（去除空格、转小写）
    df['feedback'] = df['feedback'].astype(str).str.strip().str.lower()

    # 生成质量报告
    quality_report = {
        "表名": "review",
        "原始行数": before_clean,
        "清洗后行数": len(df),
        "去重行数": dup_count,
        "空值行数": null_count
    }

    logging.info(f"✅ 评价表清洗完成：最终行数 {len(df)}")
    return df, quality_report

# ===================== 4. 保存质量报告 =====================
def save_quality_report(report_list, config):
    """
    把所有表的质量报告保存为CSV文件（数据运维核心）
    """
    report_df = pd.DataFrame(report_list)
    report_path = config['path']['quality_report']
    report_df.to_csv(report_path, index=False, encoding='utf-8')
    logging.info(f"📊 数据质量报告已保存至：{report_path}")

# ===================== 测试代码 =====================
if __name__ == '__main__':
    # 先导入抽取模块
    from extract import load_config, extract_data

    # 加载配置
    config = load_config()

    # 1. 先抽取数据（只抽商品详情表，小文件快）
    product_df = extract_data(config['path']['raw_data']['product_detail'])

    # 2. 清洗商品详情表
    cleaned_product_df, product_report = transform_product_detail(product_df)

    # 3. 保存质量报告
    if product_report:
        save_quality_report([product_report], config)

    # 4. 打印清洗结果
    if cleaned_product_df is not None:
        logging.info(f"\n📌 清洗后商品详情表示例：\n{cleaned_product_df.head()}")