#!/usr/bin/env python3
"""
Test script to verify Kite Connect API credentials and basic functionality.
"""

import os
import sys
from dotenv import load_dotenv
from kite_auto_trading.api import KiteAPIClient
from kite_auto_trading.config.models import APIConfig

def test_kite_login():
    """Test Kite Connect API login and basic operations."""
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    api_key = ""#os.getenv('KITE_API_KEY')
    #access_token = os.getenv('KITE_ACCESS_TOKEN')
    api_secret = ""#os.getenv('KITE_API_SECRET')
    
    print("🚀 Testing Kite Connect API Login")
    print("=" * 50)
    
    # Validate credentials are provided
    if not api_key:
        print("❌ ERROR: KITE_API_KEY not found in environment variables")
        print("   Please set KITE_API_KEY in your .env file")
        return False
    
    # if not access_token:
    #     print("❌ ERROR: KITE_ACCESS_TOKEN not found in environment variables")
    #     print("   Please set KITE_ACCESS_TOKEN in your .env file")
    #     print("   Note: You need to generate this through Kite Connect login flow")
    #     return False
    
    print(f"✅ API Key: {api_key[:8]}...")
    #print(f"✅ Access Token: {access_token[:8]}...")
    
    try:
        # Create API configuration
        config = APIConfig(
            api_key=api_key,
            api_secret=api_secret,
            timeout=30,
            max_retries=3,
            retry_delay=1.0,
            rate_limit_delay=0.5
        )
        
        # Initialize Kite client
        print("\n📡 Initializing Kite API Client...")
        client = KiteAPIClient(config)
        
        # Test authentication
        print("🔐 Testing authentication...")
        auth_result = client.authenticate(api_key, access_token)
        
        if not auth_result:
            print("❌ Authentication failed!")
            print("   Possible reasons:")
            print("   - Invalid API key or access token")
            print("   - Access token expired (tokens expire daily)")
            print("   - Network connectivity issues")
            return False
        
        print("✅ Authentication successful!")
        
        # Test profile retrieval
        print("\n👤 Fetching user profile...")
        profile = client.get_profile()
        print(f"   User ID: {profile.get('user_id')}")
        print(f"   User Name: {profile.get('user_name')}")
        print(f"   Email: {profile.get('email')}")
        print(f"   Broker: {profile.get('broker')}")
        
        # Test funds retrieval
        print("\n💰 Fetching account funds...")
        funds = client.get_funds()
        print(f"   Available Cash: ₹{funds.get('available_cash', 0):,.2f}")
        print(f"   Total Margin: ₹{funds.get('total_margin', 0):,.2f}")
        print(f"   Used Margin: ₹{funds.get('used_margin', 0):,.2f}")
        
        # Test positions retrieval
        print("\n📊 Fetching current positions...")
        positions = client.get_positions()
        if positions:
            print(f"   Found {len(positions)} positions:")
            for pos in positions[:5]:  # Show first 5 positions
                print(f"   - {pos.instrument}: {pos.quantity} @ ₹{pos.average_price:.2f} (PnL: ₹{pos.unrealized_pnl:.2f})")
        else:
            print("   No open positions found")
        
        # Test orders retrieval
        print("\n📋 Fetching today's orders...")
        orders = client.get_orders()
        if orders:
            print(f"   Found {len(orders)} orders today:")
            for order in orders[:3]:  # Show first 3 orders
                print(f"   - {order.get('tradingsymbol')}: {order.get('transaction_type')} {order.get('quantity')} @ {order.get('status')}")
        else:
            print("   No orders found for today")
        
        # Test instruments (sample)
        print("\n📈 Testing instruments retrieval...")
        instruments = client.get_instruments()
        print(f"   Retrieved {len(instruments)} instruments from NSE")
        
        # Test quote retrieval
        print("\n💹 Testing quote retrieval (RELIANCE)...")
        try:
            quotes = client.get_quote(['RELIANCE'])
            if quotes:
                reliance_quote = quotes.get('NSE:RELIANCE', {})
                if reliance_quote:
                    print(f"   RELIANCE Last Price: ₹{reliance_quote.get('last_price', 'N/A')}")
                    ohlc = reliance_quote.get('ohlc', {})
                    if ohlc:
                        print(f"   OHLC: O:{ohlc.get('open')} H:{ohlc.get('high')} L:{ohlc.get('low')} C:{ohlc.get('close')}")
        except Exception as e:
            print(f"   Quote test failed: {e}")
        
        print("\n🎉 All tests completed successfully!")
        print("✅ Your Kite Connect API credentials are working properly")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure your access token is valid and not expired")
        print("2. Check your internet connection")
        print("3. Verify API key and access token are correct")
        print("4. Make sure you have active Kite Connect subscription")
        return False

def main():
    """Main function to run the test."""
    print("Kite Connect API Test Script")
    print("This script will test your Kite API credentials and basic functionality\n")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please create a .env file with your Kite credentials:")
        print("KITE_API_KEY=your_api_key_here")
        print("KITE_ACCESS_TOKEN=your_access_token_here")
        print("KITE_API_SECRET=your_api_secret_here")
        sys.exit(1)
    
    success = test_kite_login()
    >>> from kiteconnect import KiteConnect
    >>> kite = KiteConnect(api_key="df")
    >>> #data = kite.generate_session("request_token_here", api_secret="fdgd")
    >>> hjk = kite.login_url()
    >>> hjk
    'https://kite.zerodha.com/connect/login?api_key=&v=3'
    >>> data = kite.generate_session("", api_secret="")
    >>> kite.set_access_token(data["access_token"])
    >>> dir(kite)
    
    if success:
        print("\n🚀 Ready to start automated trading!")
        sys.exit(0)
    else:
        print("\n❌ Please fix the issues above before proceeding")
        sys.exit(1)

if __name__ == "__main__":
    main()