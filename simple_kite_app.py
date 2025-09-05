from kiteconnect import KiteConnect

api_key = "your_api_key"
api_secret = "your_api_secret"

kite = KiteConnect(api_key=api_key)
data = kite.generate_session("request_token_here", api_secret=api_secret)
kite.set_access_token(data["access_token"])

order_id = kite.place_order(
    variety=kite.VARIETY_REGULAR,
    exchange="NSE",
    tradingsymbol="SETFNIF50",
    transaction_type=kite.TRANSACTION_TYPE_BUY,
    quantity=1,
    order_type=kite.ORDER_TYPE_MARKET,
    product=kite.PRODUCT_CNC
)
print("Order placed. ID is:", order_id)

# Replace "your_api_key", "your_api_secret" and "request_token_here" with your specific values.
