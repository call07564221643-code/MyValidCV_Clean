import json
import re

from cryptography.fernet import Fernet
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import AffiliatePayoutDetails


class PayoutForm(forms.Form):
    account_holder = forms.CharField(max_length=180)
    bank_name = forms.CharField(max_length=180)
    account_number = forms.RegexField(r"^[0-9]{6,20}$", required=False, max_length=20)
    sort_code = forms.CharField(required=False, max_length=8)
    iban = forms.CharField(required=False, max_length=34)
    swift = forms.CharField(required=False, max_length=11, label="SWIFT / BIC")

    def clean(self):
        data = super().clean()
        iban = re.sub(r"\s", "", data.get("iban", "")).upper()
        swift = data.get("swift", "").strip().upper()
        sort_code = data.get("sort_code", "").replace("-", "").replace(" ", "")
        if iban:
            if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", iban):
                self.add_error("iban", "Enter a valid IBAN.")
            else:
                digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in iban[4:] + iban[:4])
                if int(digits) % 97 != 1:
                    self.add_error("iban", "IBAN checksum is invalid.")
        if swift and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", swift):
            self.add_error("swift", "Enter an 8 or 11 character SWIFT / BIC.")
        if sort_code and not re.fullmatch(r"[0-9]{6}", sort_code):
            self.add_error("sort_code", "Enter a six-digit sort code.")
        if not iban and not (data.get("account_number") and (sort_code or swift)):
            self.add_error(None, "Provide an IBAN, or an account number with a sort code or SWIFT / BIC. SWIFT alone does not identify your account.")
        data.update(iban=iban, swift=swift, sort_code=sort_code)
        return data


def payout_cipher():
    key = getattr(settings, "AFFILIATE_PAYOUT_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("Payout encryption is not configured.")
    return Fernet(key.encode())


def save_payout_details(partner, data):
    encrypted = payout_cipher().encrypt(json.dumps(data).encode()).decode()
    last_four = (data.get("iban") or data.get("account_number", ""))[-4:]
    return AffiliatePayoutDetails.objects.update_or_create(partner=partner,
        defaults={"encrypted_details": encrypted, "account_last_four": last_four})[0]
