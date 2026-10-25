"""Generate a small synthetic screenshot graveyard for the README/demo."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "graveyard"
OUT.mkdir(exist_ok=True)


def canvas(w=800, h=450, bg="#1e1e1e"):
    img = Image.new("RGB", (w, h), bg)
    return img, ImageDraw.Draw(img)


# 1. nginx 404 error page
img, d = canvas()
d.rectangle([30, 30, 770, 420], outline="#ff5555", width=3)
d.text((60, 90), "404 Not Found", fill="#ffffff")
d.text((60, 150), "nginx/1.24.0 at api.example.com/v2/users", fill="#aaaaaa")
img.save(OUT / "Screenshot 2026-10-24 at 11.42.07.png")

# 2. a chat thread
img, d = canvas(bg="#f5f5f5")
d.rectangle([20, 20, 780, 60], fill="#2b6cb0")
d.text((35, 32), "# incident-room - 4 unread", fill="#ffffff")
d.text((40, 100), "sam: deploy is stuck, who owns the runner?", fill="#222222")
d.text((40, 150), "me: not me, I am on PTO tomorrow", fill="#222222")
d.text((40, 200), "dana: rollback worked, api is back", fill="#222222")
img.save(OUT / "Screenshot 2026-10-23 at 09.15.44.png")

# 3. a receipt / invoice
img, d = canvas(bg="#ffffff")
d.rectangle([250, 30, 550, 420], outline="#333333", width=2)
d.text((300, 60), "INVOICE #2026-1042", fill="#000000")
d.text((300, 110), "Cloud hosting ................ 48.00", fill="#000000")
d.text((300, 150), "Object storage ............... 12.50", fill="#000000")
d.text((300, 190), "TOTAL ........................ 60.50", fill="#000000")
d.text((300, 380), "Paid via card ****4417", fill="#666666")
img.save(OUT / "Screenshot 2026-10-21 at 18.03.29.png")

# 4. an accidental blank capture (junk)
img, d = canvas(bg="#101010")
img.save(OUT / "Screenshot 2026-10-20 at 03.07.11.png")

# 5. a UI mockup
img, d = canvas(bg="#ffffff")
d.rectangle([40, 40, 760, 100], fill="#eef2ff")
d.text((60, 60), "Settings  >  Billing  >  Plans", fill="#333333")
d.rectangle([40, 140, 380, 380], outline="#6366f1", width=2)
d.text((70, 170), "Free tier", fill="#111111")
d.text((70, 220), "3 projects, 1 seat", fill="#555555")
d.rectangle([420, 140, 760, 380], outline="#6366f1", width=4)
d.text((450, 170), "Pro tier", fill="#111111")
d.text((450, 220), "unlimited, $12/mo", fill="#555555")
img.save(OUT / "Screenshot 2026-10-19 at 14.55.02.png")

print(f"wrote 5 screenshots to {OUT}")
