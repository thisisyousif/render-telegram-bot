from telegram.ext import Application, ContextTypes
import ccxt
import pandas as pd
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID1=os.getenv("CHAT_ID1")
CHAT_ID2=os.getenv("CHAT_ID2")
exchange = ccxt.coinex({
    'enableRateLimit': True,
})

# 2. قائمة العملات المتابعة
symbols = ['MODE/USDT', 'GOAL/USDT', 'LISTEN/USDT','HAT/USDT','PAW/USDT',
           'HOLO/USDT','DIA/USDT','EMP/USDT','RIO/USDT','ELIZA/USDT','MOCA/USDT']
last_update="29042025"
# 3. حساب الـ EMA (للحجم أو السعر)
def calculate_ema(data, window=10):
    series = pd.Series(data)
    return series.ewm(span=window, adjust=False).mean().iloc[-1]

# 4. التحقق من الشروط المطلوبة
def check_conditions(symbol):
    # جلب آخر 11 شمعة (لحساب الـ EMA 10 نحتاج إلى 10 بيانات سابقة + الشمعة الحالية)
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=21)
    except Exception as e:
        print(f"network error with {symbol}:{e}")
        return False
    
    if len(candles) < 21:
        return False  # لا توجد بيانات كافية
    
    # تفكيك البيانات
    opens = [candle[1] for candle in candles]
    closes = [candle[4] for candle in candles]
    volumes = [candle[5] for candle in candles]
    
    # الشمعة الأخيرة (التي نتحقق منها)
    last_open = opens[-1]
    last_volume = volumes[-1]
    
    # الشرط 1: لون الشمعة (أخضر أم أحمر)
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']  
    is_green = current_price > last_open
    if not is_green:
        return False  # تستبعد إذا كانت حمراء
    
    # الشرط 2: حجم الشمعة الخضراء > EMA(10) للحجم
    ema_10_volume = calculate_ema(volumes[10:-1])  # نحسب الـ EMA على الـ 10 شموع السابقة (بدون الأخيرة)
    if last_volume<ema_10_volume:
        return False
    ema_20_close=calculate_ema(closes[:-1],window=20)
    return current_price>ema_20_close
async def handle(request):
    return web.Response(text="Bot is running")
async def health_check(request):
    return web.Response(text="Bot is running",status=200)
async def start_web_server():
    app=web.Application()
    app.router.add_get('/',handle)
    app.router.add_get('/health',health_check)
    port=int(os.environ.get("PORT",8080))
    runner=web.AppRunner(app)
    await runner.setup()
    site=web.TCPSite(runner,'0.0.0.0',port)
    await site.start()
    print(f"web server started on port {port}")
async def send_auto_message(context: ContextTypes.DEFAULT_TYPE):
    try:
        eligible_coins = []
        for symbol in symbols:
            if check_conditions(symbol):
                eligible_coins.append(symbol)
                
        message=' '.join(eligible_coins) if eligible_coins else "no chances now..."
        message=message+"..from Render "+last_update
        await context.bot.send_message(
            chat_id=CHAT_ID1,
            text=message
        )
        await context.bot.send_message(
            chat_id=CHAT_ID2,
            text=message
        )
        print(message)
    except Exception as e:
        print(f"fail to send: {e}")
        

async def main():
    # 1. تهيئة التطبيق مع JobQueue
    app = Application.builder() \
        .token(TOKEN) \
        .build()  # JobQueue يتم تهيئته تلقائياً مع [job-queue]
    
    # 2. جدولة المهمة (تأكد من وجود app.job_queue)
    if hasattr(app, 'job_queue') and app.job_queue:
        app.job_queue.run_repeating(
            callback=send_auto_message,
            interval=300,  # 5 دقائق
            first=10  # بدء بعد 10 ثواني
        )
    else:
        raise RuntimeError("JobQueue not avialable [job-queue]")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await start_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())