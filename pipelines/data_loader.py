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


# Table generation functions

def gen_customers():
    rows, used_emails = [], set()
    for _ in range(N_CUSTOMERS):
        name = fake_en.name()
        created = rand_dt(NOW - timedelta(days = 3 * 365), NOW - timedelta(days = 7))
        rows.append({
            "full_name": name,
            "email": gen_email(name, fake_en.free_email_domain(), used_emails),
            "phone": gen_phone() if random.random() > 0.08 else None,  #8% of customers have no phone
            "street_address": fake_en.street_address(),
            "city": fake_en.city(),
            "province": random.choices(PROVINCES, PROV_WEIGHTS)[0],
            "postal_code": fake_en.postalcode(),          # en_CA gives 'A1A 1A1'
            "date_of_birth": fake_en.date_of_birth(minimum_age=19, maximum_age=85)
                             if random.random() > 0.05 else None,        # adults only, no minors seeded
            "segment": random.choices(["smb", "mid_market", "enterprise"],
                                      [0.6, 0.3, 0.1])[0],
            "created_at": created,
        })
    return rows

def gen_users(customers):
    rows, used = [], set()
    #1,500 users over 1,000 customers: everyone gets one, extras go to a random 500
    owners = customers + random.sample(customers, N_USERS - N_CUSTOMERS)
    for cust in owners:
        rows.append({
            "customer_id": cust["customer_id"],
            "login_email": gen_email(cust["full_name"], "maplecrm-client.ca", used),
            "password_hash": "$2b$12$" + "".join(
                                random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=53)
                            ),
            "last_login_ip": (fake_en.ipv4() if random.random() < 0.85 else fake_en.ipv6())
                             if random.random() > 0.10 else None,
            "locale": random.choices(["en-CA", "fr-CA"], [0.75, 0.25])[0],
        })
    return rows
        

/*
generate a list of payment records w realistic data
paid_at >= customer.created_at
churned customers: No payments in the last 120 days
fraud payments in the last month
*/
def gen_payments(customers):
    churned_ids = set(c["customer_id"] for c in random.sample(customers, int(N_CUSTOMERS * CHURN_RATE)))
    #figure out the last calendar month range for fraud payments
    this_month_start = NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start - timedelta(seconds=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = []
    for _ in range(N_PAYMENTS):
        cust = random.choice(customers)
        window_start = max(cust["created_at"], NOW - timedelta(days=540))
        window_end = NOW - timedelta(days=121) if cust["customer_id"] in churned_ids else NOW
        if window_start >= window_end:            # brand-new churned customer: skip
            continue
        status = random.choices(["settled", "pending", "failed", "refunded"],
                                [0.90, 0.03, 0.04, 0.03])[0]
        rows.append({
            "customer_id": cust["customer_id"],
            "amount_cad": round(random.lognormvariate(4.5, 0.8), 2),
            "card_last4": f"{random.randint(0, 9999):04d}" if random.random() > 0.15 else None,
            "payment_token": make_payment_token(),
            "status": status,
            "fraud_flag": random.random() < FRAUD_RATE,
            "province": cust["province"] if random.random() < 0.90
                        else random.choices(PROVINCES, PROV_WEIGHTS)[0],
            "paid_at": rand_dt(window_start, window_end),
        })

    #make sure there are fraud payments
    active = [c for c in customers if c["customer_id"] not in churned_ids
              and c["created_at"] < last_month_start]
    for _ in range(FRAUD_LAST_MONTH_MIN):
        cust = random.choice(active)
        rows.append({
            "customer_id": cust["customer_id"],
            "amount_cad": round(random.lognormvariate(5.2, 0.9), 2),
            "card_last4": f"{random.randint(0, 9999):04d}",
            "payment_token": make_payment_token(),
            "status": "settled",
            "fraud_flag": True,
            "province": cust["province"],
            "paid_at": rand_dt(last_month_start, last_month_end),
        })
    return rows

TICKET_SUBJECTS = [
    "Cannot log in to dashboard", "Invoice discrepancy", "Feature request: export to CSV",
    "API rate limit questions", "Billing address update", "Password reset not arriving",
    "Slow report generation", "Duplicate charge on account", "Onboarding help needed",
    "Integration webhook failing",
]
BODY_PLAIN = [
    "The dashboard spins forever when I open the reports tab. Started yesterday.",
    "We were charged twice this cycle, please review our latest invoice.",
    "Requesting an export feature for the quarterly summary view.",
    "Webhook deliveries have been failing intermittently since the update.",
    "New team members need onboarding access, current flow is confusing.",
]

BODY_PII_TEMPLATES = [
    ("email", "Please send the corrected invoice to {email} as soon as possible."),
    ("phone", "You can reach me directly at {phone} any weekday after 2pm."),
    ("email_phone", "Best contact is {email}, or call {phone} if it's urgent."),
]

def gen_tickets(customers):
    rows, pii_manifest = [], []
    for _ in range(N_TICKETS):
        cust = random.choice(customers)
        created = rand_dt(cust["created_at"], NOW)
        has_pii = random.random() < TICKET_PII_RATE
        if has_pii:
            kind, tmpl = random.choice(BODY_PII_TEMPLATES)
            phone = cust["phone"] or gen_phone()
            body = random.choice(BODY_PLAIN) + " " + tmpl.format(email=cust["email"], phone=phone)
        else:
            body = random.choice(BODY_PLAIN)
        row = {
            "customer_id": cust["customer_id"],
            "subject": random.choice(TICKET_SUBJECTS),
            "body": body,
            "priority": random.choices(["low", "medium", "high", "urgent"],
                                       [0.3, 0.4, 0.2, 0.1])[0],
            "created_at": created,
        }
        rows.append(row)
        if has_pii:
            pii_manifest.append({"row_index": len(rows) - 1, "pii_kinds": kind.split("_")})
    return rows, pii_manifest

def gen_employees():
    rows, used = [], set()
    for _ in range(N_EMPLOYEES):
        name = fake_en.name()
        rows.append({
            "full_name": name,
            "sin": gen_sin(),                               
            "work_email": gen_email(name, "maplecrm.ca", used),
            "date_of_birth": fake_en.date_of_birth(minimum_age=21, maximum_age=64),
            "salary": round(random.uniform(48_000, 185_000), 2),
            "home_address": f"{fake_en.street_address()}, {fake_en.city()}, "
                            f"{random.choices(PROVINCES, PROV_WEIGHTS)[0]} {fake_en.postalcode()}",
            "home_phone": gen_phone(),
        })
    return rows


def gen_partenaires():
    rows = []
    for _ in range(N_PARTENAIRES):
        nom = fake_fr.name()
        rows.append({
            "nom_complet": nom,
            "courriel": nom.lower().replace(" ", ".").replace("'", "")
                        .replace("é", "e").replace("è", "e").replace("ç", "c")
                        .replace("à", "a").replace("ô", "o").replace("î", "i")
                        + "@partenaire.qc.ca",
            "telephone": gen_phone(),
            "date_naissance": fake_fr.date_of_birth(minimum_age=25, maximum_age=70),
            "ville": fake_fr.city(),
        })
    return rows


def gen_audit_stub():
    actors = ["svc-billing", "svc-mailer", "cron:nightly-scan", "cron:backup",
              "api-key:7f3a91", "api-key:cc02d8", "svc-reporting", "system:migrator"]
    events = ["row_updated", "export_generated", "backup_completed", "job_started",
              "job_finished", "config_reloaded"]
    return [{
        "event": random.choice(events),
        "actor": random.choice(actors),
        "occurred_at": rand_dt(NOW - timedelta(days=180), NOW),
    } for _ in range(N_AUDIT_STUB)]


def gen_marketing_prefs(customers):
    return [{
        "customer_id": c["customer_id"],
        "email_opt_out": random.random() < 0.25,
        "sms_opt_in": random.random() < 0.40,    
        "campaign_source": random.choices(
            ["organic", "google_ads", "linkedin", "referral", "event", None],
            [0.3, 0.25, 0.15, 0.15, 0.1, 0.05])[0],
    } for c in customers]

