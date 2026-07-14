# SumUp setup for MyValidCV

MyValidCV uses SumUp Hosted Checkout for the first payment integration.

## 1. Get SumUp credentials

In your SumUp developer account, create or open an app and collect:

- Access token
- Merchant code

For local testing, set these environment variables before running Django:

```powershell
$env:SUMUP_ACCESS_TOKEN="your_access_token"
$env:SUMUP_MERCHANT_CODE="your_merchant_code"
$env:SUMUP_WEBHOOK_SECRET="optional_shared_secret"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## 2. Configure webhook

When your local server is publicly reachable, configure this webhook URL in SumUp:

```text
https://your-domain.com/sumup/webhook/
```

For local development you need a tunnel such as ngrok or Cloudflare Tunnel, then use:

```text
https://your-tunnel-url/sumup/webhook/
```

## 3. Test checkout

1. Visit `/pricing/`.
2. Choose Plus or Enterprise.
3. Use discount code `FOUNDER25` if you want to test discount handling.
4. If SumUp credentials are configured, MyValidCV redirects to SumUp hosted checkout.
5. If credentials are missing, MyValidCV creates a pending transaction and shows the setup screen.

## 4. Admin controls

Django admin now includes:

- Subscription plans
- Customer subscriptions
- Discount codes
- Payment transactions
- Invoices
- Refunds
- Webhook logs

While testing, admin can mark a payment as paid and activate the user plan from the Payment Transactions list.
