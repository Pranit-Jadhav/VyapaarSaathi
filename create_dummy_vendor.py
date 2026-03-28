from supabase_config import get_supabase

def create_dummy():
    supabase = get_supabase()
    data = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "phone": "9999999999",
        "name": "Dummy Tester",
        "vendor_type": "chai"
    }
    try:
        supabase.table("vendors").insert(data).execute()
        print("✅ Dummy vendor created successfully!")
    except Exception as e:
        print("Vendor already exists or error:", e)

if __name__ == "__main__":
    create_dummy()
