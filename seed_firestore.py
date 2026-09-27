# Copyright 2026 Google LLC
# Seed script for FitCoach AI Firestore database

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-a4a086486940"
COLLECTION_NAME = "workout_plans"

SEED_PLANS = [
    {
        "id": "plan-101",
        "title": "5K Aerobic Base Builder",
        "category": "Running",
        "duration_mins": 45,
        "difficulty": "Beginner",
        "target_hr_zone": "Zone 2 (Cardio Aerobic)",
        "description": "Steady easy run focusing on maintaining Zone 2 heart rate to build cardiovascular endurance.",
        "calories_burn_est": 380,
    },
    {
        "id": "plan-102",
        "title": "HIIT Cardio & Core Blitz",
        "category": "HIIT",
        "duration_mins": 30,
        "difficulty": "Intermediate",
        "target_hr_zone": "Zone 4 (Anaerobic / Threshold)",
        "description": "High-intensity interval intervals alternating kettlebell swings, burpees, and plank holds.",
        "calories_burn_est": 320,
    },
    {
        "id": "plan-103",
        "title": "Strength & Hypertrophy Full Body",
        "category": "Strength",
        "duration_mins": 60,
        "difficulty": "Intermediate",
        "target_hr_zone": "Zone 3 (Aerobic Moderate)",
        "description": "Compound barbell and dumbbell lifts targeting major muscle groups with 3-minute rest sets.",
        "calories_burn_est": 450,
    },
    {
        "id": "plan-104",
        "title": "Zone 2 Long Distance Cycling",
        "category": "Cycling",
        "duration_mins": 90,
        "difficulty": "Advanced",
        "target_hr_zone": "Zone 2 (Endurance)",
        "description": "Low-cadence steady pedaling workout for building aerobic threshold on road or trainer.",
        "calories_burn_est": 750,
    },
    {
        "id": "plan-105",
        "title": "Active Recovery & Mobility Flow",
        "category": "Recovery",
        "duration_mins": 25,
        "difficulty": "All Levels",
        "target_hr_zone": "Zone 1 (Active Recovery)",
        "description": "Guided dynamic stretching, foam rolling, and mobility drills to reduce muscle soreness.",
        "calories_burn_est": 120,
    },
]


def seed_database():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    for plan in SEED_PLANS:
        doc_ref = collection_ref.document(plan["id"])
        doc_ref.set(plan)
        print(f"  ✓ Seeded workout plan '{plan['title']}' ({plan['id']})")

    print(f"\nSuccessfully seeded {len(SEED_PLANS)} workout plans into Firestore collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    seed_database()
