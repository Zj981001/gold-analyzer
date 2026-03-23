import requests
import numpy as np
from datetime import datetime, timezone, timedelta
import os
from functools import lru_cache

# 从环境变量获取API密钥
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY", "你的Twelve Data API密钥")


# ===================== 核心函数：获取金价数据（无缓存） =====================
def get_gold_market_data_raw():
    """
    原始金价数据获取函数（无缓存）
    - 优先调用实时报价接口，保证数据新鲜度
    - 修正时区解析，精准展示数据时间戳
    - 增加详细日志，便于排查延迟问题
    """
    try:
        # 1. 获取实时报价（核心优化：时效性优先）
        quote_url = f"https://api.twelvedata.com/quote?symbol=XAU/USD&apikey={TWELVE_API_KEY}"
        quote_response = requests.get(quote_url, timeout=8)
        quote_response.raise_for_status()  # 主动抛出HTTP错误
        quote = quote_response.json()

        # 校验实时报价是否有效
        if 'price' not in quote or quote['price'] is None:
            raise ValueError(f"实时报价接口返回异常: {quote}")

        # 2. 获取1小时K线（仅用于技术指标计算）
        kline_url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol=XAU/USD&interval=1h&outputsize=26"
            f"&apikey={TWELVE_API_KEY}&timezone=UTC"
        )
        kline_response = requests.get(kline_url, timeout=8)
        kline_response.raise_for_status()
        kline = kline_response.json()

        # 校验K线数据是否足够
        if 'values' not in kline or len(kline['values']) < 26:
            raise ValueError(f"K线数据不足，仅返回{len(kline.get('values', []))}条")

        # 3. 数据计算（保留原逻辑，优化数据源）
        latest_price = float(quote['price'])  # 实时价格优先用quote接口
        prices = [float(v['close']) for v in kline['values']]
        high_24h = max(prices[-24:]) if len(prices) >= 24 else max(prices)
        low_24h = min(prices[-24:]) if len(prices) >= 24 else min(prices)

        # RSI计算（14周期）
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[:14]) if len(gain) >= 14 else 0
        avg_loss = np.mean(loss[:14]) if len(loss) >= 14 else 0

        for i in range(14, len(gain)):
            avg_gain = (avg_gain * 13 + gain[i]) / 14
            avg_loss = (avg_loss * 13 + loss[i]) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
        rsi = 100 - (100 / (1 + rs))

        # MACD计算（12/26周期）
        ema12 = np.mean(prices[-12:]) if len(prices) >= 12 else 0
        ema26 = np.mean(prices[-26:]) if len(prices) >= 26 else 0
        macd_line = ema12 - ema26
        signal_line = np.mean([macd_line])
        macd_hist = macd_line - signal_line

        # 4. 时间戳精准解析
        if 'timestamp' in quote and quote['timestamp'].isdigit():
            quote_time = datetime.fromtimestamp(int(quote['timestamp']), tz=timezone.utc)
        else:
            latest_kline_time = kline['values'][-1]['datetime']
            quote_time = datetime.strptime(latest_kline_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

        # 计算数据延迟
        current_utc = datetime.now(timezone.utc)
        data_delay_minutes = int((current_utc - quote_time).total_seconds() / 60)

        # 5. 组装返回数据
        result = {
            "current_price": round(latest_price, 2),
            "high_24h": round(high_24h, 2),
            "low_24h": round(low_24h, 2),
            "rsi_14": round(rsi, 2),
            "macd": round(macd_line, 2),
            "macd_signal": round(signal_line, 2),
            "macd_hist": round(macd_hist, 2),
            "timestamp": quote_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "data_delay_minutes": data_delay_minutes,
            "data_source": "twelve_data_realtime",
            "warning": "⚠️ 数据延迟超过1小时，请检查API密钥/网络" if data_delay_minutes > 60 else None
        }

        # 打印调试日志
        print(f"\n📊 金价数据获取成功（UTC {current_utc.strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"   实时价格: ${result['current_price']} | 数据时间: {result['timestamp']}")
        print(f"   数据延迟: {result['data_delay_minutes']}分钟 | 24h高低: ${result['high_24h']}/${result['low_24h']}")

        return result

    except requests.exceptions.RequestException as e:
        error_msg = f"网络请求异常: {str(e)}"
        print(f"🚨 {error_msg}")
        return {"error": error_msg}
    except ValueError as e:
        error_msg = f"数据解析异常: {str(e)}"
        print(f"🚨 {error_msg}")
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"未知异常: {str(e)}"
        print(f"🚨 {error_msg}")
        return {"error": error_msg}


# ===================== 缓存封装函数（避免递归） =====================
@lru_cache(maxsize=1)
def _cached_gold_data(_cache_key):
    """带缓存的金价数据（内部函数，仅被get_gold_market_data调用）"""
    return get_gold_market_data_raw()


def get_gold_market_data():
    """
    对外暴露的最终函数（5分钟自动刷新缓存）
    - 完全避免递归调用
    - 兼容原有函数名，无需修改其他文件调用逻辑
    """
    now = datetime.now(timezone.utc)
    # 生成5分钟分段的缓存key（确保每5分钟刷新一次）
    cache_key = now - timedelta(
        minutes=now.minute % 5,
        seconds=now.second,
        microseconds=now.microsecond
    )
    return _cached_gold_data(cache_key.isoformat())