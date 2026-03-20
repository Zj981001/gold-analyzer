# backend/tools.py
import requests
import numpy as np
from datetime import datetime, timedelta
import os

TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

# 全局缓存变量
_cached_data = None
_cache_time = None
CACHE_TTL = 60  # 缓存60秒


def get_gold_market_data():
    """获取国际金价(XAU/USD)并计算技术指标（带缓存）"""
    global _cached_data, _cache_time

    now = datetime.now()

    # 如果缓存有效，直接返回
    if _cached_data and _cache_time and (now - _cache_time).total_seconds() < CACHE_TTL:
        print("✅ 使用缓存数据")
        return _cached_data.copy()

    try:
        symbol = "XAU/USD"
        interval = "1h"

        # 获取最近 20 根 K线（用于 RSI）
        kline_url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize=20&apikey={TWELVE_API_KEY}"
        response = requests.get(kline_url, timeout=5)  # ⏱️ 超时缩短到5秒
        kline = response.json()

        if 'values' not in kline or len(kline['values']) < 14:
            return {"error": "数据不足"}

        prices = [float(v['close']) for v in kline['values']]
        latest_price = prices[-1]
        high_24h = max(prices[-24:]) if len(prices) >= 24 else max(prices)
        low_24h = min(prices[-24:]) if len(prices) >= 24 else min(prices)

        # 计算 RSI (14周期)
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[:14])
        avg_loss = np.mean(loss[:14])
        for i in range(14, len(gain)):
            avg_gain = (avg_gain * 13 + gain[i]) / 14
            avg_loss = (avg_loss * 13 + loss[i]) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
        rsi = 100 - (100 / (1 + rs))

        # 计算 MACD（简化版）
        ema12 = np.mean(prices[-12:])
        ema26 = np.mean(prices[-26:])
        macd_line = ema12 - ema26
        signal_line = np.mean([macd_line])  # 极简信号线
        macd_hist = macd_line - signal_line

        data = {
            "current_price": round(latest_price, 2),
            "high_24h": round(high_24h, 2),
            "low_24h": round(low_24h, 2),
            "rsi_14": round(rsi, 2),
            "macd": round(macd_line, 2),
            "macd_signal": round(signal_line, 2),
            "macd_hist": round(macd_hist, 2),
            "timestamp": datetime.fromisoformat(kline['values'][-1]['datetime'].replace('Z', '+00:00')).strftime(
                "%Y-%m-%d %H:%M UTC")
        }

        # 更新缓存
        _cached_data = data
        _cache_time = now
        print("🔄 刷新行情缓存")

        return data.copy()

    except Exception as e:
        print(f"🚨 获取数据异常: {str(e)}")
        return {"error": f"数据获取异常: {str(e)}"}