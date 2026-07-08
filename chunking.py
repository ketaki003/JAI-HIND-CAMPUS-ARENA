# chunking.py
import json
import csv
import re
import sys

# Increase the CSV field size limit to handle large PDF text blocks
csv.field_size_limit(268435456)

print("⏳ Reading college_data.csv carefully...")

structured_data = []
chunk_id = 0

# 1. Parse your existing scraped CSV data[cite: 3]
with open("college_data.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row_idx, row in enumerate(reader):
        row_text = " ".join([str(cell).strip() for cell in row if cell])
        row_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', row_text)
        
        if len(row_text.split()) < 5 or "Content" in row_text:  # Skip empty or header rows
            continue
            
        structured_data.append({
            "id": chunk_id,
            "text": row_text,
            "source": "Scraped Campus Portal"
        })
        chunk_id += 1

print(f"✅ Created {len(structured_data)} structural row chunks from CSV.[cite: 3]")

# 2. INTERN UPGRADE: Programmatic Injection of Crucial Metadata Chunks
print("💉 Injecting missing high-priority target chunks...")
custom_chunks = [
    {
        "text": "Jai Hind College (Autonomous) is located at 'A' Road, Churchgate, Mumbai - 400 020, Maharashtra, India. It sits in South Mumbai near the Churchgate railway station.",
        "source": "Official Location Portal"
    },
    {
        "text": "Jai Hind College holds an A+ grade with a CGPA score of 3.36 out of 4 in its fourth assessment cycle by the National Assessment and Accreditation Council (NAAC).",
        "source": "NAAC Accreditation Records"
    },
    {
        "text": "Under the Undergraduate Aided Category, Jai Hind College offers distinct degree courses across three main faculties. The Faculty of Arts offers Economics, English, History, Political Science, Philosophy, and Psychology. The Faculty of Commerce offers Environmental Science (EVS), Commerce, Business Law, and Accountancy. The Faculty of Science offers Physics, Microbiology, Mathematics, Life Sciences, Chemistry, and Botany.",
        "source": "Degree College Aided Structure"
    },
    {
        "text": "Admissions for Self-Financing degree programs (such as BAF, BFM, BBI, BMM, BDS, BIA, BSc-IT, BSc-Biotech, and B.Voc) at Jai Hind College require mandatory online pre-admission registration through the University of Mumbai portal. Merit list rankings are heavily determined by either Class XII aggregate percentages or the Jai Hind College Common Entrance Exam (CEE) scores.",
        "source": "FY Degree Admissions Notice"
    }
]

# Append custom chunks with correct sequential IDs
for chunk in custom_chunks:
    structured_data.append({
        "id": chunk_id,
        "text": chunk["text"],
        "source": chunk["source"]
    })
    chunk_id += 1

# 3. Save a cleanly formatted, perfectly valid JSON[cite: 3]
with open("college_data.json", "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=4)

print(f"🎉 Success! High-quality data injected and saved to college_data.json. Total chunks: {len(structured_data)}")