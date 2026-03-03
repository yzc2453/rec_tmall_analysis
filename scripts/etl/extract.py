# 导入依赖库
import pandas as pd
import os
import logging
import yaml
from datetime import datetime

# 配置日志（解决中文/图标编码问题）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # 日志文件：指定 UTF-8 编码
        logging.FileHandler(
            "D:/Project/rec_tmall_bigdata/data/output/etl_log.log",
            encoding='utf-8'
        ),
        # 控制台输出：指定 UTF-8 编码
        logging.StreamHandler(
            stream=open('CONOUT$', 'w', encoding='utf-8')
        )
    ]
)

# 加载配置文件
def load_config():
    """加载config.yaml配置"""
    config_path = "D:/Project/rec_tmall_bigdata/config/config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logging.info("✅ 配置文件加载成功")
        return config
    except Exception as e:
        logging.error(f"❌ 配置文件加载失败：{e}")
        raise

# 核心抽取函数
def extract_data(file_path, incremental=False, start_date=None, chunk_size=None):
    """
    数据抽取函数：支持多编码、分块读取、增量过滤
    :param file_path: 数据文件路径
    :param incremental: 是否增量抽取
    :param start_date: 增量起始日期
    :param chunk_size: 分块大小
    :return: 抽取后的DataFrame（大文件返回分块列表）
    """
    # 1. 校验文件是否存在
    if not os.path.exists(file_path):
        logging.error(f"❌ 文件不存在：{file_path}")
        return None
    
    # 2. 读取文件（兼容多编码）
    try:
        # 小文件直接读取，大文件分块读取
        if chunk_size and os.path.getsize(file_path) > 1024 * 1024 * 50:  # 50MB以上算大文件
            logging.info(f"📥 分块读取大文件：{os.path.basename(file_path)}，块大小：{chunk_size}")
            chunks = []
            # 尝试gbk编码（你的数据大概率是这个编码）
            try:
                for chunk in pd.read_csv(file_path, encoding='gbk', chunksize=chunk_size):
                    # 增量过滤（只处理指定日期后的数据）
                    if incremental and 'vtime' in chunk.columns:
                        chunk['vtime'] = pd.to_datetime(chunk['vtime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                        chunk = chunk[chunk['vtime'] >= datetime.strptime(start_date, '%Y-%m-%d')]
                    chunks.append(chunk)
                df = pd.concat(chunks, ignore_index=True)
                logging.info(f"✅ 大文件读取成功（GBK编码），总行数：{len(df)}")
            # gbk失败则用utf-8
            except UnicodeDecodeError:
                for chunk in pd.read_csv(file_path, encoding='utf-8', chunksize=chunk_size):
                    if incremental and 'vtime' in chunk.columns:
                        chunk['vtime'] = pd.to_datetime(chunk['vtime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                        chunk = chunk[chunk['vtime'] >= datetime.strptime(start_date, '%Y-%m-%d')]
                    chunks.append(chunk)
                df = pd.concat(chunks, ignore_index=True)
                logging.info(f"✅ 大文件读取成功（UTF-8编码），总行数：{len(df)}")
        else:
            # 小文件直接读取
            try:
                df = pd.read_csv(file_path, encoding='gbk')
                logging.info(f"✅ 小文件读取成功（GBK编码），总行数：{len(df)}")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='utf-8')
                logging.info(f"✅ 小文件读取成功（UTF-8编码），总行数：{len(df)}")
        
        return df
    
    except Exception as e:
        logging.error(f"❌ 文件读取失败：{e}")
        return None

# 测试代码（运行这个文件时执行）
if __name__ == '__main__':
    # 先检查config.yaml是否存在
    config_file = "D:/Project/rec_tmall_bigdata/config/config.yaml"
    if not os.path.exists(config_file):
        logging.error(f"❌ 配置文件不存在：{config_file}")
        logging.info("💡 请先在config文件夹下新建config.yaml并写入配置内容")
    else:
        # 加载配置
        config = load_config()
        # 测试抽取用户行为数据（先注释掉，避免读取大文件耗时）
        # user_behavior_df = extract_data(
        #     file_path=config['path']['raw_data']['user_behavior'],
        #     incremental=config['etl']['incremental'],
        #     start_date=config['etl']['start_date'],
        #     chunk_size=config['etl']['chunk_size']
        # )
        # 先测试抽取商品详情数据（小文件，快）
        product_detail_df = extract_data(config['path']['raw_data']['product_detail'])
        
        if product_detail_df is not None:
            logging.info(f"✅ 测试抽取完成：商品详情数据前5行\n{product_detail_df.head()}")