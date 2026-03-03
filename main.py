# 导入核心模块
import logging
import os
from scripts.etl.extract import load_config, extract_data
from scripts.etl.transform import (
    transform_user_behavior,
    transform_product_detail,
    transform_review,
    save_quality_report
)
from scripts.etl.load import load_data, validate_load

# 统一日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("D:/Project/rec_tmall_bigdata/data/output/etl_log.log", encoding='utf-8'),
        logging.StreamHandler(stream=open('CONOUT$', 'w', encoding='utf-8'))
    ]
)

def run_full_etl():
    """执行完整的ETL流程"""
    logging.info("=" * 50)
    logging.info("🚀 开始执行全量ETL流程")
    logging.info("=" * 50)

    # 1. 加载配置
    config = load_config()

    # 2. 数据抽取
    logging.info("\n--- 步骤1：数据抽取 ---")
    raw_data = {}
    raw_data['user_behavior'] = extract_data(
        file_path=config['path']['raw_data']['user_behavior'],
        incremental=config['etl']['incremental'],
        start_date=config['etl']['start_date'],
        chunk_size=config['etl']['chunk_size']
    )
    raw_data['product_detail'] = extract_data(config['path']['raw_data']['product_detail'])
    raw_data['review'] = extract_data(config['path']['raw_data']['review'])

    # 3. 数据清洗
    logging.info("\n--- 步骤2：数据清洗 ---")
    clean_data = {}
    report_list = []

    # 清洗用户行为表
    if raw_data['user_behavior'] is not None:
        clean_data['user_behavior'], report_ub = transform_user_behavior(raw_data['user_behavior'], config)
        report_list.append(report_ub)

    # 清洗商品详情表
    if raw_data['product_detail'] is not None:
        clean_data['product_detail'], report_pd = transform_product_detail(raw_data['product_detail'])
        report_list.append(report_pd)

    # 清洗评价表
    if raw_data['review'] is not None:
        clean_data['review'], report_rv = transform_review(raw_data['review'])
        report_list.append(report_rv)

    # 保存质量报告
    save_quality_report(report_list, config)

    # 4. 数据加载
    logging.info("\n--- 步骤3：数据加载 ---")
    load_success = load_data(clean_data, config, if_exists='replace')

    # 5. 校验结果
    if load_success:
        validate_load(config)
        logging.info("\n🎉 ETL全流程执行成功！")
    else:
        logging.error("\n❌ ETL流程执行失败")

    return load_success

if __name__ == '__main__':
    run_full_etl()