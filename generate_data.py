import pandas as pd
import random

# --- CONFIGURATION ---
TOTAL_CAIRO = 40
TOTAL_ALEX  = 30
TOTAL_REST  = 50

# --- DATA POOLS ---
first_names = ["محمد", "أحمد", "محمود", "علي", "عمر", "إبراهيم", "يوسف", "خالد", "حسن", "حسين", "طارق", "عماد", "مصطفى", "سيد", "عبدالله"]
last_names  = ["المنشاوي", "الشريف", "العدلي", "عزت", "سليمان", "نجيب", "مختار", "سالم", "الهواري", "البدري", "عامر", "فوزي", "نصار", "عبد القادر"]
specialties = ["قانون مدني", "قانون جنائي", "أحوال شخصية (أسرة)", "قانون شركات", "قضاء إداري", "جرائم إلكترونية", "قانون عقاري"]
bios = [
    "محامٍ متخصص بخبرة تزيد على 10 سنوات في المحاكم المصرية.",
    "عضو نقابة المحامين، يعمل في قضايا الأحوال الشخصية والتجارية.",
    "خبير قانوني في العقود والنزاعات المدنية والتجارية.",
    "محامية حاصلة على ماجستير الحقوق، متخصصة في الجرائم الإلكترونية والخصوصية.",
    "مستشار قانوني للشركات والمنشآت الصغيرة والمتوسطة.",
    "متخصص في قضايا التقاضي أمام محاكم الاستئناف ومجلس الدولة.",
    "خبرة واسعة في عقود الإيجار والتسويات العقارية في القاهرة الكبرى.",
]
districts_cairo = ["المعادي", "التجمع الخامس", "مدينة نصر", "مصر الجديدة", "وسط البلد", "الزمالك", "المهندسين", "الدقي"]
districts_alex  = ["سموحة", "محطة الرمل", "ميامي", "لوران", "رشدي", "سيدي جابر", "المنشية"]
gov_rest        = ["الجيزة", "المنصورة", "طنطا", "أسيوط", "سوهاج", "الأقصر", "أسوان", "بور سعيد", "الإسماعيلية", "الزقازيق"]

def generate_phone():
    prefixes = ["010", "011", "012", "015"]
    return f"{random.choice(prefixes)}{random.randint(10000000, 99999999)}"

def make_lawyer(name, city, address):
    return {
        "name":      name,
        "city":      city,
        "address":   address,
        "phone":     generate_phone(),
        "specialty": random.choice(specialties),
        "bio":       random.choice(bios),
    }

if __name__ == "__main__":
    data = []

    for _ in range(TOTAL_CAIRO):
        name = f"الأستاذ/ {random.choice(first_names)} {random.choice(last_names)}"
        addr = f"شارع {random.randint(1, 99)}، {random.choice(districts_cairo)}"
        data.append(make_lawyer(name, "القاهرة", addr))

    for _ in range(TOTAL_ALEX):
        name = f"الأستاذ/ {random.choice(first_names)} {random.choice(last_names)}"
        addr = f"عمارة {random.randint(1, 50)}، {random.choice(districts_alex)}"
        data.append(make_lawyer(name, "الإسكندرية", addr))

    for _ in range(TOTAL_REST):
        city = random.choice(gov_rest)
        name = f"الأستاذ/ {random.choice(first_names)} {random.choice(last_names)}"
        addr = f"ميدان المحطة، {city}"
        data.append(make_lawyer(name, city, addr))

    df = pd.DataFrame(data)
    df.to_csv("lawyers.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Generated lawyers.csv with {len(df)} lawyers (including bio field).")