import os
import random
from datetime import datetime

from faker import Faker

#config var for data generation
SEED = 42      #same data every time 
N_CUSTOMERS = 1000
N_USERS = 1500
N_PAYMENTS = 20000
N_TICKETS = 5000
N_EMPLOYEES = 200
N_PARTENAIRES = 150
N_AUDIT_STUB = 500 

TICKET_PII_RATE = 0.10 #10% of the tickets will have PII embedded in the description
FRAUD_RATE = 0.02 #around 400 fraud payments 
CHURN_RATE = 0.15 #around 150 customers with no payment in 90+ days

DB_URL = os.environ.get("DATABASE_URL", "postgresql:///pii_atlas")
GROUND_TRUTH_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "ground_truth")

random.seed(SEED)
fake_en = Faker("en_CA"); fake_en.seed_instance(SEED)
fake_fr = Faker("fr_CA"); fake_fr.seed_instance(SEED)   #french names and cities for the canadian context

NOW = datetime.now()

PROVINCES = ["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"]
PROV_WEIGHTS = [0.38, 0.22, 0.14, 0.12, 0.04, 0.03, 0.03, 0.02, 0.015, 0.005]

#real area codes
AREA_CODES = ["416", "647", "437", "905", "604", "778", "403", "587",
              "514", "438", "613", "343", "902", "306", "204", "709"]


#find the check digit to make it a valid Luhn number
def luhn_check_digit(number: str) -> int:
    total_sum = 0
    reverse_digits = number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 0:
            n = n * 2
            if n > 9:
                n = n - 9
        total_sum = total_sum + n
    check_digit = (10 - (total_sum % 10)) % 10
    return check_digit

#generate luhn valid SIN
def gen_sin() -> str:
    first8 = str(random.randint(1,7)) + "".join(random.choices("0123456789", k = 7))
    check_digit = luhn_check_digit(first8)
    sin = first8 + str(check_digit)
    return f"{sin[0:3]}-{sin[3:6]}-{sin[6:9]}"

#generate different formats of phone numbers
#NANP-valid, fake (555-01XX) 
def gen_phone() -> str:
    area = random.choices(AREA_CODES)
    last4 = f"01{random.randint(0,99):02d}"
    style = random.random()
    if style < 0.5:
        return f"({area}) 555-{last4}"
    elif style < 0.85:
        return f"{area}-555-{last4}"
    return f"+1 {area} 555 {last4}"

#generate a random payment token
def make_payment_token() -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "tok_" + "".join(random.choices(chars, k=24))

#generate a random datetime between two datetime
def rand_dt(start:datetime, end:datetime) -> datetime:
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

#generate a unique email address based on name and domain, avoiding duplicates in the used set
def gen_email(name:str, domain:str, used:set) -> str:
    base = name.lower().replace(" ", ".").replace("'", "")
    base = "".join(c for c in base if c.isalnum() or c == ".")
    email = f"{base}@{domain}"
    i = 1
    while email in used:
        email = f"{base}{i}@{domain}"
        i += 1
    used.add(email)
    return email


        
