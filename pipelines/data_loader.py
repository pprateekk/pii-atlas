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

