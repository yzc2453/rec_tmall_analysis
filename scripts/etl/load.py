# 导入依赖库
import pandas as pd
import sqlite3
import logging
import os
from sqlalchemy import create_engine

# 配置日志（统一编码）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("D:/Project/rec_tmall_bigdata/data/output/etl_log.log", encoding='utf-8'),
        logging.StreamHandler(stream=open('CONOUT$', 'w', encoding='utf-8'))
    ]
)

# ===================== 1. 初始化数据库连接 =====================
def init_db_connection(config):
    """
    初始化SQLite数据库连接（支持增量追加/全量覆盖）
    :param config: 配置字典
    :return: 数据库连接对象
    """
    # 确保数据库目录存在
    db_dir = os.path.dirname(config['path']['db_path'])
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logging.info(f"📁 创建数据库目录：{db_dir}")
    
    # 方式1：sqlite3原生连接（适合大批量数据）
    conn = sqlite3.connect(config['path']['db_path'])
    # 设置超时时间，避免锁表
    conn.execute("PRAGMA busy_timeout = 30000")
    logging.info(f"✅ 数据库连接成功：{config['path']['db_path']}")
    return conn

# ===================== 2. 数据加载核心函数 =====================
def load_data(df_dict, config, if_exists='replace'):
    """
    批量加载多表数据到SQLite
    :param df_dict: 字典 {表名: 清洗后的DataFrame}
    :param config: 配置字典
    :param if_exists: replace（全量覆盖）/append（增量追加）
    :return: 加载结果
    """
    if not df_dict:
        logging.error("❌ 无数据可加载")
        return False
    
    # 初始化数据库连接
    conn = init_db_connection(config)
    
    try:
        # 遍历加载每张表
        for table_name, df in df_dict.items():
            if df is None or df.empty:
                logging.warning(f"⚠️ 表 {table_name} 无数据，跳过加载")
                continue
            
            # 加载数据（分块加载大表，避免内存溢出）
            chunk_size = config['etl']['chunk_size']
            if len(df) > chunk_size:
                logging.info(f"📤 分块加载表 {table_name}：总行数 {len(df)}，块大小 {chunk_size}")
                # 先清空表（如果是replace模式）
                if if_exists == 'replace':
                    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                # 分块写入
                for i in range(0, len(df), chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    chunk.to_sql(
                        name=table_name,
                        con=conn,
                        if_exists='append',
                        index=False,
                        chunksize=chunk_size
                    )
            else:
                # 小表直接写入
                df.to_sql(
                    name=table_name,
                    con=conn,
                    if_exists=if_exists,
                    index=False
                )
            
            # 验证加载结果
            count = pd.read_sql(f"SELECT COUNT(*) FROM {table_name}", conn).iloc[0,0]
            logging.info(f"✅ 表 {table_name} 加载完成：数据库中总行数 {count}")
        
        # 提交事务
        conn.commit()
        logging.info("✅ 所有表加载完成，事务提交成功")
        return True
    
    except Exception as e:
        # 出错回滚事务
        conn.rollback()
        logging.error(f"❌ 数据加载失败：{e}")
        return False
    
    finally:
        # 关闭数据库连接
        conn.close()
        logging.info("🔌 数据库连接已关闭")

# ===================== 3. 加载后数据校验 =====================
def validate_load(config):
    """
    校验加载后的数据完整性
    :param config: 配置字典
    :return: 校验报告
    """
    conn = init_db_connection(config)
    report = {}
    
    # 校验核心表
    tables = ['user_behavior', 'product_detail', 'review']
    for table in tables:
        try:
            count = pd.read_sql(f"SELECT COUNT(*) FROM {table}", conn).iloc[0,0]
            report[table] = f"存在，行数：{count}"
        except:
            report[table] = "不存在"
    
    conn.close()
    logging.info(f"📊 数据校验报告：{report}")
    return report

# ===================== 测试代码 =====================
if __name__ == '__main__':
    # 导入之前的模块
    from extract import load_config, extract_data
    from transform import transform_product_detail
    
    # 1. 加载配置
    config = load_config()
    
    # 2. 抽取+清洗商品详情表
    product_df = extract_data(config['path']['raw_data']['product_detail'])
    cleaned_product_df, _ = transform_product_detail(product_df)
    
    # 3. 构造待加载字典
    df_dict = {
        'product_detail': cleaned_product_df
    }
    
    # 4. 加载数据（全量覆盖）
    load_result = load_data(df_dict, config, if_exists='replace')
    
    # 5. 校验加载结果
    if load_result:
        validate_load(config)