import streamlit as st
import pyupbit
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from class_mrha import MRHATradingSystem
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

#  .env 파일 로드
load_dotenv()

# API 키 가져오기
UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')

# API 키가 없으면 에러 메시지 표시
if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
    st.error("API keys not found in .env file. Please check your configuration.")
    st.stop()

# 페이지 설정
st.set_page_config(page_title="피보나치를 이용한 트레이딩 시스템", layout="wide")

# MRHA 봇 실행을 위한 함수 (캐시 비활성화)
def run_mrha_bot(ticker, interval):
    try:
        bot = MRHATradingSystem(ticker, interval, count=365)
        bot.run_analysis()
        return bot
    except Exception as e:
        st.error(f"Error in MRHA bot: {str(e)}")
        return None

# 모든 코인에 대한 시그널을 계산하는 함수
def calculate_all_coin_signals():
    try:
        # 모든 코인 티커 가져오기
        tickers = pyupbit.get_tickers(fiat="KRW")
        
        # 중단 버튼을 위한 컨테이너
        stop_container = st.empty()
        if stop_container.button("Stop Analysis", key="stop_button_initial"):
            st.warning("Analysis stopped by user")
            return None
        
        # 진행 상황을 표시할 컨테이너 생성
        progress_container = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()
        result_container = st.empty()
        
        # 데이터프레임 초기화
        data = []
        
        # 오늘부터 과거 10일까지의 날짜 리스트 생성
        dates = []
        for i in range(10):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        # 각 코인에 대해 시그널 계산
        for idx, ticker in enumerate(tickers):
            try:
                # 중단 버튼 상태 확인
                if stop_container.button("Stop Analysis", key=f"stop_button_{idx}"):
                    st.warning("Analysis stopped by user")
                    return None
                
                # 진행 상황 업데이트
                progress = (idx + 1) / len(tickers)
                progress_bar.progress(progress)
                status_text.text(f"Processing {ticker}... ({idx+1}/{len(tickers)})")
                
                # 현재 처리 중인 코인 표시
                progress_container.markdown(f"""
                    ### Processing Status
                    - Current Coin: **{ticker}**
                    - Progress: **{progress*100:.1f}%**
                    - Completed: **{idx}/{len(tickers)}**
                """)
                
                # 백테스팅과 동일한 방식으로 시그널 계산
                bot = MRHATradingSystem(ticker, "day", count=365)
                bot.run_analysis()
                
                # 최근 10일의 시그널 확인
                row = {"Coin": ticker}
                for date in dates:
                    # 해당 날짜의 시그널 찾기
                    signal = "HOLD"
                    for _, trade in bot.trades.iterrows():
                        trade_date = trade['Date'].strftime("%Y-%m-%d")
                        if trade_date == date:
                            signal = "BUY" if trade['Type'] == 'Buy' else "SELL"
                            break
                    row[date] = signal
                
                data.append(row)
                
                # 중간 결과 표시
                if len(data) > 0:
                    df = pd.DataFrame(data)
                    result_container.dataframe(df, use_container_width=True)
                
                time.sleep(0.1)  # API 호출 제한을 위한 지연
                
            except Exception as e:
                st.warning(f"Error processing {ticker}: {str(e)}")
                continue
        
        # 최종 결과 표시
        status_text.text("✅ Analysis Complete!")
        progress_container.markdown("""
            ### Analysis Complete
            All coins have been processed successfully.
        """)
        
        return pd.DataFrame(data)
        
    except Exception as e:
        st.error(f"Error calculating signals: {str(e)}")
        return None

# Upbit API를 통한 계좌 정보 가져오기
def get_account_info():
    try:
        upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
        balances = upbit.get_balances()
        return balances
    except Exception as e:
        st.error(f"Error getting account info: {str(e)}")
        return None

# 사이드바 설정
st.sidebar.title("MRHA Trading System")

# 사용 가능한 티커 가져오기
try:
    tickers = pyupbit.get_tickers(fiat="KRW")
    default_ticker = "KRW-BTC" if "KRW-BTC" in tickers else tickers[0]
    selected_ticker = st.sidebar.selectbox("Select Cryptocurrency", tickers, index=tickers.index(default_ticker))
except Exception as e:
    st.sidebar.error(f"Error fetching tickers: {str(e)}")
    st.stop()

# 메뉴 버튼들
menu = st.sidebar.radio(
    "Select Menu",
    ["Backtesting", "Run Top 10 Coins", "All Coin Signals", "Execute ODA"]
)

# 메인 컨텐츠
st.title("MRHA Trading System")

# 선택된 메뉴에 따라 다른 컨텐츠 표시
if menu == "Backtesting":
    st.header("MRHA Fibonacci Trading System Results")
    
    # Run Backtesting 버튼
    if st.sidebar.button("Run Backtesting"):
        mrha_bot = run_mrha_bot(selected_ticker, "day")
        
        if mrha_bot:
            # 차트 표시
            st.subheader("MRHA Fibonacci Trading System Chart")
            fig_mrha = mrha_bot.plot_results()
            st.plotly_chart(fig_mrha, use_container_width=True)
            
            # 백테스트 결과 표시
            st.subheader("MRHA Fibonacci Trading System Backtest Results")
            mrha_results = mrha_bot.get_results()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Final Portfolio Value", f"{mrha_results['Final Portfolio Value']:,.0f} KRW")
            col2.metric("Total Return", f"{mrha_results['Total Return']:.2f}%")
            col3.metric("Sharpe Ratio", f"{mrha_results['Sharpe Ratio']:.2f}")
            
            col4, col5, col6 = st.columns(3)
            col4.metric("Annualized Return", f"{mrha_results['Annualized Return']:.2f}%")
            col5.metric("Max Drawdown", f"{mrha_results['Max Drawdown']:.2f}%")
            col6.metric("Total Trades", mrha_results['Total Trades'])
            
            # 트레이드 히스토리 표시
            st.subheader("MRHA Fibonacci Trading System Trade History")
            st.dataframe(mrha_bot.trades, use_container_width=True)

elif menu == "Run Top 10 Coins":
    st.header("Top 10 Coins Analysis")
    
    if st.sidebar.button("Run Top 10 Coins"):
        # 상위 10개 코인 가져오기
        top_10_tickers = tickers[:10]
        
        # 중단 버튼을 위한 컨테이너
        stop_container = st.empty()
        if stop_container.button("Stop Analysis", key="stop_button_initial_top10"):
            st.warning("Analysis stopped by user")
            st.stop()
        
        # 진행 상황을 표시할 컨테이너 생성
        progress_container = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()
        result_container = st.empty()
        
        # 데이터프레임 초기화
        data = []
        
        # 오늘부터 과거 10일까지의 날짜 리스트 생성
        dates = []
        for i in range(10):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        # 각 코인에 대해 시그널 계산
        for idx, ticker in enumerate(top_10_tickers):
            try:
                # 중단 버튼 상태 확인
                if stop_container.button("Stop Analysis", key=f"stop_button_{idx}_top10"):
                    st.warning("Analysis stopped by user")
                    st.stop()
                
                # 진행 상황 업데이트
                progress = (idx + 1) / len(top_10_tickers)
                progress_bar.progress(progress)
                status_text.text(f"Processing {ticker}... ({idx+1}/{len(top_10_tickers)})")
                
                # 현재 처리 중인 코인 표시
                progress_container.markdown(f"""
                    ### Processing Status
                    - Current Coin: **{ticker}**
                    - Progress: **{progress*100:.1f}%**
                    - Completed: **{idx}/{len(top_10_tickers)}**
                """)
                
                # 백테스팅과 동일한 방식으로 시그널 계산
                bot = MRHATradingSystem(ticker, "day", count=365)
                bot.run_analysis()
                
                # 최근 10일의 시그널 확인
                row = {"Coin": ticker}
                for date in dates:
                    # 해당 날짜의 시그널 찾기
                    signal = "HOLD"
                    for _, trade in bot.trades.iterrows():
                        trade_date = trade['Date'].strftime("%Y-%m-%d")
                        if trade_date == date:
                            signal = "BUY" if trade['Type'] == 'Buy' else "SELL"
                            break
                    row[date] = signal
                
                data.append(row)
                
                # 중간 결과 표시
                if len(data) > 0:
                    df = pd.DataFrame(data)
                    result_container.dataframe(df, use_container_width=True)
                
                time.sleep(0.1)  # API 호출 제한을 위한 지연
                
            except Exception as e:
                st.warning(f"Error processing {ticker}: {str(e)}")
                continue
        
        # 최종 결과 표시
        status_text.text("✅ Analysis Complete!")
        progress_container.markdown("""
            ### Analysis Complete
            Top 10 coins have been processed successfully.
        """)

elif menu == "All Coin Signals":
    st.header("All Coin Signals")
    
    if st.sidebar.button("Run All Coin"):
        df = calculate_all_coin_signals()
        if df is not None:
            st.dataframe(df, use_container_width=True)

elif menu == "Execute ODA":
    st.header("Order Execution")
    
    # 계좌 정보 표시
    balances = get_account_info()
    if balances:
        st.subheader("Account Information")
        
        # KRW 잔고
        krw_balance = next((item for item in balances if item['currency'] == 'KRW'), None)
        if krw_balance:
            st.write(f"KRW Balance: {float(krw_balance['balance']):,.0f} KRW")
        
        # 코인 잔고
        st.subheader("Coin Positions")
        for balance in balances:
            if balance['currency'] != 'KRW':
                ticker = f"KRW-{balance['currency']}"
                current_price = pyupbit.get_current_price(ticker)
                total_value = float(balance['balance']) * current_price
                st.write(f"{ticker}: {float(balance['balance']):,.8f} ({total_value:,.0f} KRW)")
    
    # 주문 실행
    st.subheader("Place Order")
    
    # 주문 유형 선택
    order_type = st.selectbox("Order Type", ["Buy", "Sell"])
    
    # 코인 선택
    selected_coin = st.selectbox("Select Coin", tickers)
    
    if order_type == "Buy":
        # 매수 주문
        if krw_balance:
            max_buy_amount = float(krw_balance['balance'])
            st.write(f"Maximum Buy Amount: {max_buy_amount:,.0f} KRW")
            
            buy_amount = st.number_input("Buy Amount (KRW)", min_value=0.0, max_value=max_buy_amount)
            if st.button("Execute Buy Order"):
                try:
                    upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
                    result = upbit.buy_market_order(selected_coin, buy_amount)
                    st.success(f"Buy order executed: {result}")
                except Exception as e:
                    st.error(f"Error executing buy order: {str(e)}")
    
    else:
        # 매도 주문
        coin_balance = next((item for item in balances if item['currency'] == selected_coin.replace("KRW-", "")), None)
        if coin_balance:
            sell_amount = st.number_input("Sell Amount", min_value=0.0, max_value=float(coin_balance['balance']))
            if st.button("Execute Sell Order"):
                try:
                    upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
                    result = upbit.sell_market_order(selected_coin, sell_amount)
                    st.success(f"Sell order executed: {result}")
                except Exception as e:
                    st.error(f"Error executing sell order: {str(e)}")

# 정보 메시지 표시
st.sidebar.info("Select a menu option to proceed.") 
