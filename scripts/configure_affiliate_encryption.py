"""Configure the live payout encryption key without printing or saving the secret."""
import subprocess
from cryptography.fernet import Fernet

CLI = [r"C:\Program Files\heroku\client\bin\node.exe", r"C:\Program Files\heroku\client\bin\run"]

result = subprocess.run(CLI + ["config:get", "AFFILIATE_PAYOUT_ENCRYPTION_KEY", "--app", "myvalidcv"], capture_output=True, text=True)
if result.returncode:
    raise SystemExit("Could not read Heroku encryption configuration; no change made.")
key = result.stdout.strip()
if key:
    Fernet(key.encode())
    print("Existing payout encryption key retained.")
else:
    key = Fernet.generate_key().decode()
    configured = subprocess.run(CLI + ["config:set", "AFFILIATE_PAYOUT_ENCRYPTION_KEY=" + key, "--app", "myvalidcv"], capture_output=True, text=True)
    if configured.returncode:
        raise SystemExit("Could not configure payout encryption; see Heroku configuration privately.")
    print("Payout encryption key configured in Heroku. No secret printed or stored locally.")
