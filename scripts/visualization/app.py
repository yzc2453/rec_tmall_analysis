import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import os
import numpy as np
from datetime import datetime, timedelta

# 全局样式配置
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
COLOR_PALETTE = {
    'click': '#4e79a7',
    'collect': '#f28e2b',
    'cart': '#e15759',
    'alipay': '#76b7b2',
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'tertiary': '#F18F01'
}

# ===================== 数据读取（采样优化版） =====================
@st.cache_data
def get_data(sample_mode=True, sample_rows=1000000):
    """
    读取数据，支持采样模式
    :param sample_mode: 是否采样
    :param sample_rows: 采样行数
    :return: 三个DataFrame
    """
    db_path = "D:/Project/rec_tmall_bigdata/data/cleaned/ecommerce.db"
    if not os.path.exists(db_path):
        st.error(f"❌ 数据库文件不存在：{db_path}")
        return None, None, None

    conn = sqlite3.connect(db_path)
    
    # 1. 读取用户行为数据（支持采样）
    chunks = []
    chunk_size = 100000
    offset = 0
    max_offset = sample_rows if sample_mode else float('inf')

    with st.spinner("📥 读取用户行为数据..."):
        progress_bar = st.progress(0)
        while offset < max_offset:
            query = f'''
                SELECT item_id, user_id, action, vtime 
                FROM user_behavior 
                LIMIT {chunk_size} OFFSET {offset}
            '''
            chunk = pd.read_sql(query, conn)
            if chunk.empty:
                break
            # 显式指定时间格式，消除警告
            chunk['vtime'] = pd.to_datetime(chunk['vtime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
            chunk = chunk.dropna(subset=['vtime'])
            chunks.append(chunk)
            offset += chunk_size
            if sample_mode:
                progress = min(offset / sample_rows, 1.0)
                progress_bar.progress(progress)
        progress_bar.empty()
    
    df_behavior = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    # 2. 读取商品详情表
    df_product = pd.read_sql('SELECT * FROM product_detail', conn)
    
    # 3. 读取评价表
    df_review = pd.read_sql('SELECT * FROM review', conn)
    
    conn.close()
    return df_behavior, df_product, df_review

# ===================== 核心分析函数 =====================
def show_overview(df_behavior, df_product, df_review):
    """数据概览面板"""
    st.subheader("📈 核心数据概览")
    
    # 计算核心指标
    total_users = df_behavior['user_id'].nunique()
    total_items = df_behavior['item_id'].nunique()
    total_actions = len(df_behavior)
    total_buy = len(df_behavior[df_behavior['action'] == 'alipay'])
    total_product = len(df_product)
    total_review = len(df_review)
    # 转化率：购买数/点击数
    click_count = len(df_behavior[df_behavior['action'] == 'click'])
    conversion_rate = (total_buy / click_count * 100) if click_count > 0 else 0

    # 布局：6个指标卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总用户数", f"{total_users:,}", delta=f"+{total_users//1000}K")
        st.metric("总商品数", f"{total_items:,}", delta=f"+{total_items//1000}K")
    with col2:
        st.metric("总行为次数", f"{total_actions:,}", delta=f"+{total_actions//10000}W")
        st.metric("总购买次数", f"{total_buy:,}", delta=f"+{total_buy//1000}K")
    with col3:
        st.metric("商品详情数", f"{total_product:,}")
        st.metric("购买转化率", f"{conversion_rate:.2f}%", delta=f"{conversion_rate/2:.2f}%")

def plot_behavior_distribution(df_behavior):
    """1. 用户行为类型分布（饼图+柱状图）"""
    st.subheader("1️⃣ 用户行为类型分布")
    behavior_count = df_behavior['action'].value_counts()
    
    col1, col2 = st.columns(2)
    with col1:
        # 饼图：占比
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(
            behavior_count.values,
            labels=behavior_count.index,
            autopct='%1.1f%%',
            colors=[COLOR_PALETTE[act] for act in behavior_count.index],
            startangle=90
        )
        ax.set_title('行为类型占比')
        st.pyplot(fig)
    with col2:
        # 柱状图：数量
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(
            behavior_count.index,
            behavior_count.values,
            color=[COLOR_PALETTE[act] for act in behavior_count.index]
        )
        # 数值标注
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 500,
                    f"{height:,}", ha='center', va='bottom')
        ax.set_title('行为类型数量')
        ax.set_ylabel('次数')
        st.pyplot(fig)

def plot_time_analysis(df_behavior):
    """2. 时间维度分析（小时/日期趋势）"""
    st.subheader("2️⃣ 时间维度行为分析")
    
    # 提取小时和日期
    df_behavior['hour'] = df_behavior['vtime'].dt.hour
    df_behavior['date'] = df_behavior['vtime'].dt.date
    
    col1, col2 = st.columns(2)
    with col1:
        # 小时分布：用户活跃时段
        hour_count = df_behavior.groupby('hour').size()
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(hour_count.index, hour_count.values, marker='o', color=COLOR_PALETTE['primary'], linewidth=2)
        ax.fill_between(hour_count.index, hour_count.values, alpha=0.3, color=COLOR_PALETTE['primary'])
        ax.set_title('小时级用户活跃趋势')
        ax.set_xlabel('小时')
        ax.set_ylabel('行为次数')
        ax.set_xticks(range(0, 24, 2))
        st.pyplot(fig)
    with col2:
        # 日期趋势：每日购买量
        buy_data = df_behavior[df_behavior['action'] == 'alipay']
        if not buy_data.empty:
            daily_buy = buy_data.groupby('date').size()
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(daily_buy.index, daily_buy.values, marker='o', color=COLOR_PALETTE['alipay'], linewidth=2)
            ax.set_title('每日购买量趋势')
            ax.set_xlabel('日期')
            ax.set_ylabel('购买次数')
            plt.xticks(rotation=45)
            st.pyplot(fig)
        else:
            st.warning("⚠️ 暂无购买行为数据")

def plot_category_analysis(df_behavior, df_product):
    """3. 商品分类分析（TOP10分类+行为分布）"""
    st.subheader("3️⃣ 商品分类深度分析")
    
    # 合并行为数据和分类数据
    merged = pd.merge(
        df_behavior,
        df_product[['item_id', 'category']],
        on='item_id',
        how='inner'
    )
    
    if merged.empty:
        st.warning("⚠️ 暂无分类匹配数据")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        # TOP10分类的总行为数
        top_categories = merged.groupby('category').size().sort_values(ascending=False).head(10)
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.barh(
            [f"分类{c}" for c in top_categories.index][::-1],
            top_categories.values[::-1],
            color=COLOR_PALETTE['secondary']
        )
        # 数值标注
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 100, bar.get_y() + bar.get_height()/2,
                    f"{int(width):,}", ha='left', va='center')
        ax.set_title('TOP10分类 - 总行为数')
        ax.set_xlabel('行为次数')
        st.pyplot(fig)
    
    with col2:
        # TOP5分类的行为类型分布
        top5_cats = top_categories.head(5).index
        cat_behavior = merged[merged['category'].isin(top5_cats)].groupby(['category', 'action']).size().unstack()
        fig, ax = plt.subplots(figsize=(8, 6))
        cat_behavior.plot(kind='bar', ax=ax, color=[COLOR_PALETTE[act] for act in cat_behavior.columns])
        ax.set_title('TOP5分类 - 行为类型分布')
        ax.set_xlabel('分类ID')
        ax.set_ylabel('次数')
        plt.xticks(rotation=45)
        st.pyplot(fig)

def plot_user_analysis(df_behavior):
    """4. 用户行为分析（用户活跃度+复购率）"""
    st.subheader("4️⃣ 用户行为深度分析")
    
    # 计算用户行为次数
    user_action_count = df_behavior.groupby('user_id').size()
    # 划分用户层级：低活跃(<10)、中活跃(10-50)、高活跃(>50)
    low_active = len(user_action_count[user_action_count < 10])
    mid_active = len(user_action_count[(user_action_count >= 10) & (user_action_count < 50)])
    high_active = len(user_action_count[user_action_count >= 50])
    
    col1, col2 = st.columns(2)
    with col1:
        # 用户活跃度分布
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(
            [low_active, mid_active, high_active],
            labels=['低活跃(<10次)', '中活跃(10-50次)', '高活跃(>50次)'],
            autopct='%1.1f%%',
            colors=[COLOR_PALETTE['tertiary'], COLOR_PALETTE['secondary'], COLOR_PALETTE['primary']]
        )
        ax.set_title('用户活跃度分布')
        st.pyplot(fig)
    
    with col2:
        # 复购率分析：购买>=2次的用户数
        buy_users = df_behavior[df_behavior['action'] == 'alipay']['user_id'].value_counts()
        repurchase_users = len(buy_users[buy_users >= 2])
        repurchase_rate = (repurchase_users / len(buy_users) * 100) if len(buy_users) > 0 else 0
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.bar(
            ['首次购买用户', '复购用户'],
            [len(buy_users)-repurchase_users, repurchase_users],
            color=[COLOR_PALETTE['cart'], COLOR_PALETTE['alipay']]
        )
        ax.set_title(f'用户复购率：{repurchase_rate:.2f}%')
        ax.set_ylabel('用户数')
        # 标注复购率
        ax.text(0.5, max(len(buy_users)-repurchase_users, repurchase_users)/2,
                f'复购率：{repurchase_rate:.2f}%', ha='center', fontsize=12)
        st.pyplot(fig)

def plot_funnel_analysis(df_behavior):
    """5. 转化漏斗分析（点击→收藏→加购→购买）"""
    st.subheader("5️⃣ 用户转化漏斗分析")
    
    # 计算各环节数量
    click = len(df_behavior[df_behavior['action'] == 'click'])
    collect = len(df_behavior[df_behavior['action'] == 'collect'])
    cart = len(df_behavior[df_behavior['action'] == 'cart'])
    buy = len(df_behavior[df_behavior['action'] == 'alipay'])
    
    # 漏斗数据（按比例）
    funnel_data = [click, collect, cart, buy]
    funnel_labels = ['点击', '收藏', '加购', '购买']
    # 计算转化率
    funnel_rates = [100]
    for i in range(1, len(funnel_data)):
        rate = (funnel_data[i] / funnel_data[i-1] * 100) if funnel_data[i-1] > 0 else 0
        funnel_rates.append(rate)
    
    # 绘制漏斗图
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(funnel_labels))
    width = 0.6
    
    # 主柱状图：数量
    bars = ax.bar(x, funnel_data, width, color=[COLOR_PALETTE[act] for act in ['click', 'collect', 'cart', 'alipay']])
    # 标注数量和转化率
    for i, (bar, rate) in enumerate(zip(bars, funnel_rates)):
        height = bar.get_height()
        # 数量标注
        ax.text(bar.get_x() + bar.get_width()/2., height + 500,
                f"{height:,}", ha='center', va='bottom')
        # 转化率标注
        if i > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height/2,
                    f"{rate:.2f}%", ha='center', va='center', color='white', fontweight='bold')
    
    ax.set_title('用户转化漏斗（点击→收藏→加购→购买）')
    ax.set_xticks(x)
    ax.set_xticklabels(funnel_labels)
    ax.set_ylabel('行为次数')
    st.pyplot(fig)

# ===================== 主函数 =====================
def main():
    """大屏主函数"""
    # 页面配置
    st.set_page_config(
        page_title="电商大数据分析大屏",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="📊"
    )
    
    # 标题
    st.title("🎯 电商大数据分析与智能决策支持系统")
    st.divider()
    
    # 侧边栏：采样模式开关
    with st.sidebar:
        st.header("⚙️ 配置面板")
        sample_mode = st.checkbox("启用采样模式（提速）", value=True)
        sample_rows = st.slider("采样行数", min_value=100000, max_value=2000000, value=1000000, step=100000)
        st.divider()
        st.info("""
        📝 说明：
        - 采样模式可大幅提升加载速度
        - 全量模式需等待5-10分钟
        - 首次加载慢，后续刷新快
        """)
    
    # 读取数据
    df_behavior, df_product, df_review = get_data(sample_mode=sample_mode, sample_rows=sample_rows)
    if df_behavior.empty:
        st.warning("⚠️ 未读取到数据，请检查数据库连接")
        st.stop()
    
    # 1. 数据概览
    show_overview(df_behavior, df_product, df_review)
    st.divider()
    
    # 2. 行为分布分析
    plot_behavior_distribution(df_behavior)
    st.divider()
    
    # 3. 时间维度分析
    plot_time_analysis(df_behavior)
    st.divider()
    
    # 4. 商品分类分析
    plot_category_analysis(df_behavior, df_product)
    st.divider()
    
    # 5. 用户行为分析
    plot_user_analysis(df_behavior)
    st.divider()
    
    # 6. 转化漏斗分析
    plot_funnel_analysis(df_behavior)
    st.divider()
    
    # 页脚
    st.caption("📅 数据更新时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == '__main__':
    main()