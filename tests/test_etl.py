"""
ETL全流程自动化测试用例
覆盖：抽取/清洗/加载/数据质量校验
"""
import pytest
import pandas as pd
import sqlite3
import os
import sys
# 添加项目根目录到Python路径
sys.path.append("D:/Project/rec_tmall_bigdata")

# 导入核心模块
from scripts.etl.extract import load_config, extract_data
from scripts.etl.transform import (
    transform_user_behavior,
    transform_product_detail,
    transform_review
)
from scripts.etl.load import load_data, validate_load

# 全局配置
config = load_config()
TEST_DB_PATH = "D:/Project/rec_tmall_bigdata/data/cleaned/test_ecommerce.db"

# ===================== 测试前置/后置 =====================
@pytest.fixture(scope="module")
def setup_teardown():
    """测试前置：准备测试数据；测试后置：清理测试数据库"""
    # 前置：抽取小批量测试数据（采样1万行）
    config['etl']['chunk_size'] = 10000
    raw_product_df = extract_data(config['path']['raw_data']['product_detail'])
    test_product_df = raw_product_df.head(1000) if raw_product_df is not None else pd.DataFrame()
    
    # 替换数据库路径为测试库
    config['path']['db_path'] = TEST_DB_PATH
    
    yield test_product_df
    
    # 后置：删除测试数据库
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    print("\n✅ 测试环境清理完成")

# ===================== 抽取模块测试 =====================
def test_extract_data():
    """测试数据抽取功能"""
    # 1. 测试商品详情表抽取
    product_df = extract_data(config['path']['raw_data']['product_detail'])
    assert product_df is not None, "❌ 商品详情表抽取失败"
    assert len(product_df) > 0, "❌ 商品详情表抽取结果为空"
    print("✅ 抽取模块测试通过")

# ===================== 清洗模块测试 =====================
def test_transform_product_detail(setup_teardown):
    """测试商品详情表清洗"""
    test_product_df = setup_teardown
    cleaned_df, report = transform_product_detail(test_product_df)
    
    # 断言1：清洗后数据不为空
    assert cleaned_df is not None, "❌ 商品详情表清洗失败"
    # 断言2：核心字段无空值
    assert cleaned_df['item_id'].notna().all(), "❌ 商品ID存在空值"
    assert cleaned_df['category'].notna().all(), "❌ 分类ID存在空值"
    # 断言3：质量报告包含关键指标
    assert "原始行数" in report, "❌ 质量报告缺少原始行数"
    assert "清洗后行数" in report, "❌ 质量报告缺少清洗后行数"
    print("✅ 清洗模块测试通过")

# ===================== 加载模块测试 =====================
def test_load_data(setup_teardown):
    """测试数据加载功能"""
    test_product_df = setup_teardown
    cleaned_df, _ = transform_product_detail(test_product_df)
    
    # 加载测试数据到测试库
    df_dict = {'product_detail_test': cleaned_df}
    load_result = load_data(df_dict, config, if_exists='replace')
    
    # 断言1：加载成功
    assert load_result is True, "❌ 数据加载失败"
    
    # 断言2：数据库中数据行数匹配
    conn = sqlite3.connect(TEST_DB_PATH)
    count = pd.read_sql("SELECT COUNT(*) FROM product_detail_test", conn).iloc[0,0]
    conn.close()
    assert count == len(cleaned_df), "❌ 加载行数不匹配"
    print("✅ 加载模块测试通过")

# ===================== 数据质量校验测试 =====================
def test_data_quality(setup_teardown):
    """测试数据质量校验"""
    test_product_df = setup_teardown
    cleaned_df, report = transform_product_detail(test_product_df)
    
    # 断言1：去重行数≥0
    assert report.get("商品ID重复行数", 0) >= 0, "❌ 去重行数异常"
    # 断言2：空值行数≥0
    assert report.get("空值行数", 0) >= 0, "❌ 空值行数异常"
    # 断言3：清洗后行数≤原始行数
    assert report["清洗后行数"] <= report["原始行数"], "❌ 清洗后行数异常"
    print("✅ 数据质量校验测试通过")

# ===================== 全流程测试 =====================
def test_full_etl(setup_teardown):
    """测试ETL全流程"""
    # 1. 抽取
    product_df = extract_data(config['path']['raw_data']['product_detail'])
    test_df = product_df.head(1000) if product_df is not None else pd.DataFrame()
    
    # 2. 清洗
    cleaned_df, _ = transform_product_detail(test_df)
    
    # 3. 加载
    test_table_name = 'product_detail_fulltest'
    df_dict = {test_table_name: cleaned_df}
    load_result = load_data(df_dict, config, if_exists='replace')
    
    # 4. 手动校验（不依赖validate_load的固定表名）
    assert load_result is True, "❌ ETL全流程失败"
    
    # 手动查询数据库，验证表存在且行数匹配
    conn = sqlite3.connect(TEST_DB_PATH)
    try:
        # 检查表是否存在
        table_exists = pd.read_sql(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{test_table_name}'",
            conn
        ).shape[0] > 0
        assert table_exists, f"❌ 表 {test_table_name} 不存在"
        
        # 检查行数
        count = pd.read_sql(f"SELECT COUNT(*) FROM {test_table_name}", conn).iloc[0, 0]
        assert count == len(cleaned_df), f"❌ 表 {test_table_name} 行数不匹配"
    finally:
        conn.close()
    
    print("✅ ETL全流程测试通过")

if __name__ == '__main__':
    # 运行所有测试用例，生成测试报告
    pytest.main([__file__, "-v", "--tb=short"])