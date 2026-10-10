from .database import Base, engine, SessionLocal
from .models import Doctor

DOCTORS = [
    ("Dr. Ananya Sharma",   "General Physician",    "City Care Clinic",        "Vijayawada", 8,  4.6, "Today 6:00 PM,Tomorrow 10:00 AM,Tomorrow 5:30 PM"),
    ("Dr. Rohit Mehta",     "Cardiologist",         "Heart Plus Hospital",     "Vijayawada", 12, 4.8, "Today 7:00 PM,Tomorrow 11:30 AM,Friday 4:00 PM"),
    ("Dr. Kavya Reddy",     "Gastroenterologist",   "Apollo Clinic",           "Vijayawada", 10, 4.7, "Tomorrow 9:30 AM,Tomorrow 6:30 PM,Friday 12:00 PM"),
    ("Dr. Imran Khan",      "Dermatologist",        "SkinCare Center",         "Vijayawada", 7,  4.5, "Today 5:00 PM,Tomorrow 1:00 PM,Friday 6:00 PM"),
    ("Dr. Priya Nair",      "Neurologist",          "Neuro Life Hospital",     "Vijayawada", 11, 4.6, "Tomorrow 2:00 PM,Friday 10:30 AM,Saturday 4:30 PM"),
    ("Dr. Suresh Babu",     "Orthopedic",           "Bone & Joint Clinic",     "Vijayawada", 15, 4.7, "Today 8:00 PM,Tomorrow 3:00 PM,Saturday 11:00 AM"),
    ("Dr. Neha Verma",      "Ophthalmologist",      "Clear Vision Eye Care",   "Vijayawada", 9,  4.4, "Tomorrow 10:00 AM,Friday 5:00 PM,Saturday 12:00 PM"),
    ("Dr. Arjun Das",       "Psychiatrist",         "Mind Wellness Clinic",    "Vijayawada", 8,  4.6, "Tomorrow 4:00 PM,Friday 7:00 PM,Saturday 9:30 AM"),
    ("Dr. Sridhar Rao",     "Endocrinologist",      "Hormone & Diabetes Care", "Vijayawada", 13, 4.8, "Today 6:30 PM,Tomorrow 9:00 AM,Friday 3:00 PM"),
    ("Dr. Lalitha Devi",    "Nephrologist",         "Kidney Care Hospital",    "Vijayawada", 10, 4.5, "Tomorrow 11:00 AM,Friday 1:00 PM,Saturday 10:00 AM"),
    ("Dr. Venkat Raju",     "Pulmonologist",        "Chest & Lung Centre",     "Vijayawada", 9,  4.6, "Today 7:30 PM,Tomorrow 4:00 PM,Saturday 2:00 PM"),
    ("Dr. Emergency Desk",  "Emergency Medicine",   "Nearest Emergency Unit",  "Vijayawada", 20, 4.3, "Available 24/7"),

    ("Dr. Rajesh Gupta",    "Cardiologist",         "KIMS Heart Institute",    "Hyderabad",  16, 4.9, "Today 5:00 PM,Tomorrow 10:00 AM,Friday 2:00 PM"),
    ("Dr. Meena Iyer",      "Endocrinologist",      "Apollo Hospitals",        "Hyderabad",  14, 4.8, "Tomorrow 9:00 AM,Friday 11:00 AM,Saturday 3:00 PM"),
    ("Dr. Prakash Reddy",   "Gastroenterologist",   "Yashoda Hospital",        "Hyderabad",  12, 4.7, "Today 6:00 PM,Tomorrow 2:00 PM,Friday 4:30 PM"),
    ("Dr. Sunitha Kumari",  "Neurologist",          "CARE Hospitals",          "Hyderabad",  11, 4.7, "Tomorrow 11:00 AM,Friday 9:00 AM,Saturday 1:00 PM"),
    ("Dr. Farid Ahmed",     "Nephrologist",         "Continental Hospitals",   "Hyderabad",  13, 4.6, "Today 7:00 PM,Tomorrow 3:00 PM,Saturday 10:30 AM"),
    ("Dr. Nisha Patel",     "Pulmonologist",        "Lung Care Clinic",        "Hyderabad",  9,  4.5, "Tomorrow 12:00 PM,Friday 5:00 PM,Saturday 11:00 AM"),
    ("Dr. Anand Rao",       "General Physician",    "Medwin Hospitals",        "Hyderabad",  8,  4.5, "Today 8:00 PM,Tomorrow 10:30 AM,Friday 3:30 PM"),
    ("Dr. Divya Sharma",    "Dermatologist",        "Skin & Laser Clinic",     "Hyderabad",  7,  4.6, "Tomorrow 1:00 PM,Friday 6:00 PM,Saturday 9:00 AM"),

    ("Dr. Karthik Rajan",   "Cardiologist",         "Fortis Malar Hospital",   "Chennai",    15, 4.9, "Tomorrow 9:30 AM,Friday 11:30 AM,Saturday 2:00 PM"),
    ("Dr. Bhavani Subbu",   "Endocrinologist",      "MGM Healthcare",          "Chennai",    11, 4.7, "Today 6:00 PM,Tomorrow 4:00 PM,Friday 10:00 AM"),
    ("Dr. Sathish Kumar",   "Gastroenterologist",   "Gleneagles Hospital",     "Chennai",    10, 4.6, "Tomorrow 10:00 AM,Friday 1:00 PM,Saturday 11:00 AM"),
    ("Dr. Padmini Raj",     "General Physician",    "Apollo Hospitals",        "Chennai",    9,  4.5, "Today 7:00 PM,Tomorrow 12:00 PM,Friday 5:30 PM"),
    ("Dr. Arockia Mary",    "Nephrologist",         "SRM Institutes",          "Chennai",    12, 4.6, "Tomorrow 11:30 AM,Friday 3:00 PM,Saturday 9:30 AM"),

    ("Dr. Vikram Shetty",   "Cardiologist",         "Narayana Health",         "Bangalore",  18, 4.9, "Tomorrow 9:00 AM,Friday 10:30 AM,Saturday 1:00 PM"),
    ("Dr. Pooja Menon",     "Endocrinologist",      "Manipal Hospital",        "Bangalore",  12, 4.8, "Today 6:00 PM,Tomorrow 3:30 PM,Friday 12:00 PM"),
    ("Dr. Mohan Krishna",   "Neurologist",          "Sakra World Hospital",    "Bangalore",  14, 4.7, "Tomorrow 10:00 AM,Friday 2:00 PM,Saturday 4:00 PM"),
    ("Dr. Deepa Nair",      "Gastroenterologist",   "Columbia Asia Hospital",  "Bangalore",  11, 4.6, "Today 7:30 PM,Tomorrow 1:00 PM,Friday 6:00 PM"),
    ("Dr. Sunil Gowda",     "Pulmonologist",        "BGS Gleneagles",          "Bangalore",  10, 4.6, "Tomorrow 11:00 AM,Friday 4:00 PM,Saturday 10:00 AM"),
    ("Dr. Rekha Hegde",     "General Physician",    "Aster CMI Hospital",      "Bangalore",  8,  4.5, "Today 8:00 PM,Tomorrow 9:30 AM,Friday 3:00 PM"),
]


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {name for (name,) in db.query(Doctor.name).all()}
        added = 0
        for d in DOCTORS:
            if d[0] in existing:
                continue
            db.add(Doctor(
                name=d[0], specialization=d[1], hospital=d[2],
                location=d[3], experience_years=d[4], rating=d[5],
                available_slots=d[6],
            ))
            added += 1
        if added:
            db.commit()
            print(f"[Seed] Added {added} new doctor(s).")
    finally:
        db.close()
