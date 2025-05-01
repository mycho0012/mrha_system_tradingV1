import pyupbit
import time
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
from notion_client import Client
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import numpy as np

# Load environment variables
load_dotenv('config/.env')

class NotionLogger:
    def __init__(self):
        self.notion = Client(auth=os.getenv('NOTION_TOKEN'))
        self.database_id = os.getenv('NOTION_DATABASE_ID')
        
    def log_trade(self, trade_data):
        """Log trade information to Notion database"""
        try:
            self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "Time": {
                        "title": [
                            {
                                "text": {
                                    "content": trade_data['time']
                                }
                            }
                        ]
                    },
                    "Signal": {
                        "select": {
                            "name": trade_data['signal']
                        }
                    },
                    "Position": {
                        "select": {
                            "name": trade_data['position']
                        }
                    },
                    "KRW Balance": {
                        "number": trade_data['krw_balance']
                    },
                    "Coin Balance": {
                        "number": trade_data['coin_balance']
                    },
                    "Price": {
                        "number": trade_data['price']
                    },
                    "Total Value": {
                        "number": trade_data['total_value']
                    }
                }
            )
        except Exception as e:
            print(f"Error logging to Notion: {e}")

class SlackNotifier:
    def __init__(self):
        self.client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        self.channel = os.getenv('SLACK_CHANNEL')
        
    def send_message(self, message):
        """Send message to Slack channel"""
        try:
            self.client.chat_postMessage(
                channel=self.channel,
                text=message
            )
        except SlackApiError as e:
            print(f"Error sending message to Slack: {e}")

class MRHATradingSystem:
    def __init__(self, symbol="KRW-BTC"):
        self.symbol = symbol
        self.running = False
        self.last_check_date = None
        self.pending_signal = None  # 다음 거래일에 실행할 시그널 저장
        
        # Initialize Upbit API
        self.access_key = os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = os.getenv('UPBIT_SECRET_KEY')
        self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)
        
        # Initialize logging systems
        self.notion_logger = NotionLogger()
        self.slack_notifier = SlackNotifier()
        
        # Trading parameters
        self.position = 0  # 0: no position, 1: long position
        
    def should_check_today(self):
        """오늘 이미 체크했는지 확인"""
        today = datetime.now().date()
        if self.last_check_date != today:
            self.last_check_date = today
            return True
        return False
        
    def get_balance(self, currency="KRW"):
        """Get balance for a specific currency"""
        try:
            balances = self.upbit.get_balances()
            for balance in balances:
                if balance['currency'] == currency:
                    return float(balance['balance'])
            return 0.0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0
    
    def get_current_price(self):
        """Get current price of the trading pair"""
        try:
            return pyupbit.get_current_price(self.symbol)
        except Exception as e:
            print(f"Error getting current price: {e}")
            return None
    
    def execute_buy(self):
        """Execute market buy order with 100% of KRW balance"""
        try:
            # Get current KRW balance
            krw_balance = self.get_balance("KRW")
            if krw_balance <= 0:
                print("No KRW balance available")
                return False
            
            # Execute market buy with all available KRW
            result = self.upbit.buy_market_order(self.symbol, krw_balance)
            print(f"Buy order executed: {result}")
            self.position = 1
            return True
        except Exception as e:
            print(f"Error executing buy order: {e}")
            return False
    
    def execute_sell(self):
        """Execute market sell order"""
        try:
            # Get coin balance
            coin_balance = self.get_balance(self.symbol.split('-')[1])
            if coin_balance <= 0:
                print("No coin balance to sell")
                return False
            
            # Execute market sell with all available coins
            result = self.upbit.sell_market_order(self.symbol, coin_balance)
            print(f"Sell order executed: {result}")
            self.position = 0
            return True
        except Exception as e:
            print(f"Error executing sell order: {e}")
            return False
    
    def log_trade_status(self, signal, position_info):
        """Log trade status to Notion and Slack"""
        # Prepare trade data
        trade_data = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'signal': signal,
            'position': position_info['status'],
            'krw_balance': position_info['krw_balance'],
            'coin_balance': position_info['coin_balance'],
            'price': position_info['current_price'],
            'total_value': position_info['total_value']
        }
        
        # Log to Notion
        self.notion_logger.log_trade(trade_data)
        
        # Send to Slack
        slack_message = f"""
=== Trading Status Update ===
Time: {trade_data['time']}
Signal: {trade_data['signal']}
Position: {trade_data['position']}
KRW Balance: {trade_data['krw_balance']:,.2f} KRW
Coin Balance: {trade_data['coin_balance']:.8f} {self.symbol.split('-')[1]}
Current Price: {trade_data['price']:,.2f} KRW
Total Portfolio Value: {trade_data['total_value']:,.2f} KRW
========================"""
        self.slack_notifier.send_message(slack_message)
    
    def get_position_status(self):
        """Get current position status with detailed information"""
        coin_balance = self.get_balance(self.symbol.split('-')[1])
        krw_balance = self.get_balance("KRW")
        current_price = self.get_current_price()
        
        position_info = {
            'status': 'LONG' if coin_balance > 0 else 'NO_POSITION',
            'coin_balance': coin_balance,
            'krw_balance': krw_balance,
            'current_price': current_price,
            'total_value': (coin_balance * current_price) + krw_balance if current_price else krw_balance
        }
        return position_info
    
    def print_status(self):
        """Print current trading status"""
        try:
            position_info = self.get_position_status()
            
            print("\n=== Current Status ===")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Position: {position_info['status']}")
            print(f"KRW Balance: {position_info['krw_balance']:,.2f} KRW")
            print(f"Coin Balance: {position_info['coin_balance']:.8f} {self.symbol.split('-')[1]}")
            print(f"Current Price: {position_info['current_price']:,.2f} KRW")
            print(f"Total Portfolio Value: {position_info['total_value']:,.2f} KRW")
            if self.pending_signal:
                print(f"Pending Signal: {self.pending_signal}")
            print("=====================\n")
        except Exception as e:
            print(f"Error printing status: {e}")
    
    def calculate_mrha(self):
        """Calculate MRHA indicators using 365 daily candles"""
        try:
            # Get 365 daily candles
            df = pyupbit.get_ohlcv(self.symbol, interval="day", count=365)
            
            # Calculate Heikin-Ashi
            df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
            df['ha_open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
            df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
            df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
            
            # Calculate Revised Heikin-Ashi
            df['rha_close'] = df['ha_close']
            df['rha_open'] = (df['ha_open'] + df['ha_close'].shift(1)) / 2
            df['rha_high'] = df[['high', 'rha_open', 'rha_close']].max(axis=1)
            df['rha_low'] = df[['low', 'rha_open', 'rha_close']].min(axis=1)
            
            # Calculate MRHA indicators
            df['Ebr'] = df['rha_high'] - df['rha_open']
            df['Btrg'] = df['rha_open'] - df['rha_low']
            df['Ebl'] = df['rha_close'] - df['rha_low']
            df['Strg'] = df['rha_high'] - df['rha_close']
            
            # Generate signals
            df['Signal'] = 'HOLD'
            df.loc[(df['Ebr'] > df['Btrg']) & (df['Ebl'] > df['Strg']), 'Signal'] = 'BUY'
            df.loc[(df['Ebr'] < df['Btrg']) & (df['Ebl'] < df['Strg']), 'Signal'] = 'SELL'
            
            return df.iloc[-1]['Signal']
        except Exception as e:
            print(f"Error calculating MRHA: {e}")
            return 'HOLD'
    
    def start_trading(self):
        """Start the trading system"""
        self.running = True
        print("\n=== Starting MRHA Trading System ===")
        print("Press 'q' and Enter to stop trading")
        print("Press 's' and Enter to show current status")
        print("Press 'h' and Enter to show help")
        print("===================================\n")
        
        def input_thread():
            while self.running:
                cmd = input().lower()
                if cmd == 'q':
                    self.running = False
                    print("\nStopping trading system...")
                elif cmd == 's':
                    self.print_status()
                elif cmd == 'h':
                    print("\nAvailable commands:")
                    print("q - Quit trading")
                    print("s - Show current status")
                    print("h - Show help")
        
        # Start input thread
        input_handler = threading.Thread(target=input_thread)
        input_handler.daemon = True
        input_handler.start()
        
        try:
            while self.running:
                now = datetime.now()
                
                # 자정 직후 MRHA 시그널 계산 (00:00 ~ 00:05)
                if now.hour == 0 and now.minute < 5:
                    if self.should_check_today():
                        # 전일 데이터로 MRHA 시그널 계산
                        signal = self.calculate_mrha()
                        self.pending_signal = signal
                        print(f"\n[시그널 계산 완료] {now.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"다음 거래 시그널: {signal}")
                        print("장 시작(09:00)에 거래가 실행됩니다.")
                
                # 장 시작 시간에 거래 실행 (09:00 ~ 09:05)
                elif now.hour == 9 and now.minute < 5 and self.pending_signal:
                    print(f"\n[거래 실행] {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"실행 시그널: {self.pending_signal}")
                    
                    # 현재 포지션 확인
                    position_info = self.get_position_status()
                    
                    # 거래 실행
                    if self.pending_signal == 'BUY' and self.position == 0:
                        print("\nExecuting buy order...")
                        if self.execute_buy():
                            position_info = self.get_position_status()
                            self.log_trade_status("BUY", position_info)
                    
                    elif self.pending_signal == 'SELL' and self.position == 1:
                        print("\nExecuting sell order...")
                        if self.execute_sell():
                            position_info = self.get_position_status()
                            self.log_trade_status("SELL", position_info)
                    
                    else:
                        self.log_trade_status("HOLD", position_info)
                    
                    # 시그널 초기화
                    self.pending_signal = None
                
                # 매분마다 상태 업데이트
                time.sleep(60)
            
        except Exception as e:
            print(f"Error in trading loop: {e}")
            self.slack_notifier.send_message(f"Error in trading loop: {str(e)}")
        finally:
            print("\nTrading system stopped successfully")

def main():
    # Initialize trader
    trader = MRHATradingSystem(
        symbol="KRW-BTC"
    )
    
    try:
        trader.start_trading()
    except KeyboardInterrupt:
        print("\nTrading system stopped by user")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        print("\nThank you for using MRHA Trading System!")

if __name__ == "__main__":
    main() 