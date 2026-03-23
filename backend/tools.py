import requests
import numpy as np
from datetime import datetime, timezone, timedelta
import os
from functools import lru_cache

# 从环境变量获取API密钥
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY", "你的Twelve Data API密钥")


# ===================== 核心函数：获取金价数据（增强容错版） =====================
def get_gold_market_data_raw():
    """
    原始金价数据获取函数（无缓存，增强容错）
    - 优先调用实时报价接口，保证数据新鲜度
    - 增加多层容错，避免解析异常
    - 修正时区解析，精准展示数据时间戳
    """
    try:
        # 1. 获取实时报价（核心优化：时效性优先）
        quote_url = f"https://api.twelvedata.com/quote?symbol=XAU/USD&apikey={TWELVE_API_KEY}"
        quote_response = requests.get(quote_url, timeout=8)
        quote_response.raise_for_status()
        quote = quote_response.json()

        # 🛡️ 第一层容错：处理API错误响应
        if quote.get("status") == "error" or quote.get("code"):
            error_msg = quote.get("message", "未知API错误")
            print(f"🚨 API返回错误: {error_msg}")
            # 修复：移除self，直接调用兜底函数
            return _get_gold_from_kline()

        # 🛡️ 第二层容错：校验price字段
        latest_price = None
        if "price" in quote and quote["price"] is not None:
            try:
                latest_price = float(quote["price"])
            except (ValueError, TypeError):
                print("⚠️ price字段格式异常，尝试用close兜底")
                latest_price = float(quote.get("close", 0)) if quote.get("close") else None

        if not latest_price or latest_price <= 0:
            print("⚠️ 实时报价无效，切换到K线数据兜底")
            # 修复：移除self，直接调用兜底函数
            return _get_gold_from_kline()

        # 2. 获取1小时K线（仅用于技术指标计算）
        kline_url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol=XAU/USD&interval=1h&outputsize=26"
            f"&apikey={TWELVE_API_KEY}&timezone=UTC"
        )
        kline_response = requests.get(kline_url, timeout=8)
        kline_response.raise_for_status()
        kline = kline_response.json()

        # 🛡️ 第三层容错：校验K线数据
        if 'values' not in kline or len(kline['values']) < 26:
            print(f"⚠️ K线数据不足，仅返回{len(kline.get('values', []))}条，尝试用更少数据计算")
            if len(kline.get('values', [])) < 14:
                raise ValueError("K线数据不足，无法计算技术指标")

        # 3. 数据计算（保留原逻辑，优化数据源）
        prices = [float(v['close']) for v in kline['values']]
        # 用最新K线收盘价兜底实时价格
        latest_price = latest_price if latest_price else float(kline['values'][0]['close'])
        high_24h = max(prices[-24:]) if len(prices) >= 24 else max(prices)
        low_24h = min(prices[-24:]) if len(prices) >= 24 else min(prices)

        # RSI计算（14周期，增强容错）
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

        # MACD计算（12/26周期，增强容错）
        ema12 = np.mean(prices[-12:]) if len(prices) >= 12 else 0
        ema26 = np.mean(prices[-26:]) if len(prices) >= 26 else 0
        macd_line = ema12 - ema26
        signal_line = np.mean([macd_line])
        macd_hist = macd_line - signal_line

        # 4. 时间戳精准解析（增强容错）
        quote_time = None
        if 'timestamp' in quote and str(quote['timestamp']).isdigit():
            try:
                quote_time = datetime.fromtimestamp(int(quote['timestamp']), tz=timezone.utc)
            except:
                pass
        if not quote_time and 'datetime' in quote:
            try:
                quote_time = datetime.strptime(quote['datetime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            except:
                quote_time = datetime.strptime(kline['values'][0]['datetime'], '%Y-%m-%d %H:%M:%S').replace(
                    tzinfo=timezone.utc)
        if not quote_time:
            quote_time = datetime.now(timezone.utc)

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
            "data_source": "twelve_data_realtime" if data_delay_minutes < 15 else "twelve_data_kline_fallback",
            "warning": "⚠️ 数据延迟超过15分钟，使用K线兜底" if data_delay_minutes > 15 else None
        }

        # 打印调试日志
        print(f"\n📊 金价数据获取成功（UTC {current_utc.strftime('%Y-%m-%d %H:%M:%S')}）")
        print(f"   实时价格: ${result['current_price']} | 数据时间: {result['timestamp']}")
        print(f"   数据延迟: {result['data_delay_minutes']}分钟 | 数据源: {result['data_source']}")

        return result

    except requests.exceptions.RequestException as e:
        error_msg = f"网络请求异常: {str(e)}"
        print(f"🚨 {error_msg}")
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"数据解析异常: {str(e)}"
        print(f"🚨 {error_msg}")
        return {"error": error_msg}


# 🛡️ 兜底函数：当实时报价异常时，用K线数据获取金价
def _get_gold_from_kline():
    """兜底函数：从K线数据获取最新金价，避免解析异常"""
    try:
        kline_url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol=XAU/USD&interval=1h&outputsize=26"
            f"&apikey={TWELVE_API_KEY}&timezone=UTC"
        )
        kline_response = requests.get(kline_url, timeout=8)
        kline_response.raise_for_status()
        kline = kline_response.json()

        if 'values' not in kline or len(kline['values']) == 0:
            return {"error": "K线兜底数据也为空"}

        latest_kline = kline['values'][0]
        latest_price = float(latest_kline['close'])
        prices = [float(v['close']) for v in kline['values']]
        high_24h = max(prices[-24:]) if len(prices) >= 24 else max(prices)
        low_24h = min(prices[-24:]) if len(prices) >= 24 else min(prices)

        # 简化技术指标计算
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[:14]) if len(gain) >= 14 else 0
        avg_loss = np.mean(loss[:14]) if len(loss) >= 14 else 0
        rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
        rsi = 100 - (100 / (1 + rs))

        ema12 = np.mean(prices[-12:]) if len(prices) >= 12 else 0
        ema26 = np.mean(prices[-26:]) if len(prices) >= 26 else 0
        macd_line = ema12 - ema26

        # 时间戳解析
        quote_time = datetime.strptime(latest_kline['datetime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        current_utc = datetime.now(timezone.utc)
        data_delay_minutes = int((current_utc - quote_time).total_seconds() / 60)

        return {
            "current_price": round(latest_price, 2),
            "high_24h": round(high_24h, 2),
            "low_24h": round(low_24h, 2),
            "rsi_14": round(rsi, 2),
            "macd": round(macd_line, 2),
            "macd_signal": round(macd_line, 2),
            "macd_hist": round(macd_line - macd_line, 2),
            "timestamp": quote_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "data_delay_minutes": data_delay_minutes,
            "data_source": "twelve_data_kline_fallback",
            "warning": "⚠️ 实时接口异常，使用K线数据兜底"
        }
    except Exception as e:
        return {"error": f"兜底K线数据也异常: {str(e)}"}


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