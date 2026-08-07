# core/execution/executor.py
import os
from dotenv import load_dotenv
from core.strategy.base import Signal
from binance.client import Client

load_dotenv()

api_key = os.getenv("BINANCE_TESTNET_API_KEY")
api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")

client = Client(api_key=api_key, api_secret=api_secret, testnet=True)

def execute_signal(signal: Signal):
    if signal.action == "hold":
        print(f"No action needed: {signal.reason}")
        return None

    order = client.create_order(
        symbol=signal.symbol,
        side=signal.action.upper(),
        type="MARKET",
        quantity=0.001
    )
    return order