"""
Set up the PostgreSQL database and fill it with demo content.

    python seed.py            create database (if missing), tables, admin user, demo content
    python seed.py --reset    DROP all tables first, then seed again
    python seed.py --admin-only   only create the admin user

Everything seeded here can be edited / deleted later from the CMS admin panel.
"""
import os
import sys
import uuid
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import (About, Blog, Education, Experience, Media, Project, Service, Skill,
                        SocialLink, Testimonial, User)


# --------------------------------------------------------------------------- #
#  1. Create the PostgreSQL database if it does not exist yet
# --------------------------------------------------------------------------- #
def ensure_database(url):
    import psycopg
    from psycopg import sql

    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    db_name = parsed.path.lstrip("/")
    # Already reachable? (always true on hosted databases like Render)
    try:
        psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), connect_timeout=10).close()
        print(f"✔ Database '{db_name}' is reachable")
        return
    except psycopg.OperationalError:
        pass
    try:
        conn = psycopg.connect(dbname="postgres", user=parsed.username,
                               password=parsed.password, host=parsed.hostname or "localhost",
                               port=parsed.port or 5432, autocommit=True)
    except psycopg.OperationalError as exc:
        print("\n❌ Could not connect to PostgreSQL.")
        print("   - Is PostgreSQL installed and running?")
        print("   - Is the username/password in DATABASE_URL (.env) correct?")
        print(f"   Details: {exc}")
        sys.exit(1)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if cur.fetchone():
            print(f"✔ Database '{db_name}' already exists")
        else:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"✔ Created database '{db_name}'")
    conn.close()


# --------------------------------------------------------------------------- #
#  2. Colourful placeholder images (so the portfolio looks great on first run)
# --------------------------------------------------------------------------- #
PALETTES = [
    ("#7c3aed", "#ec4899"), ("#06b6d4", "#3b82f6"), ("#f97316", "#facc15"),
    ("#10b981", "#06b6d4"), ("#ec4899", "#f97316"), ("#6366f1", "#22d3ee"),
    ("#ef4444", "#ec4899"), ("#84cc16", "#10b981"),
]


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def gradient(size, a, b):
    """Fast diagonal gradient from colour a to colour b."""
    vertical = Image.linear_gradient("L").resize(size)
    horizontal = Image.linear_gradient("L").rotate(90).transpose(Image.FLIP_LEFT_RIGHT).resize(size)
    mask = Image.blend(horizontal, vertical, 0.4)
    return Image.composite(Image.new("RGB", size, b), Image.new("RGB", size, a), mask)


def make_image(label, index, size=(1200, 750)):
    a, b = (_hex(x) for x in PALETTES[index % len(PALETTES)])
    w, h = size
    img = gradient(size, a, b)
    draw = ImageDraw.Draw(img, "RGBA")
    # playful circles
    draw.ellipse((w * 0.62, -h * 0.25, w * 1.15, h * 0.55), fill=(255, 255, 255, 40))
    draw.ellipse((-w * 0.12, h * 0.55, w * 0.3, h * 1.2), fill=(255, 255, 255, 30))
    draw.rounded_rectangle((w * 0.1, h * 0.3, w * 0.9, h * 0.7), radius=36,
                           fill=(255, 255, 255, 38), outline=(255, 255, 255, 90), width=3)
    size = int(h * 0.09)
    font = _font(size)
    while draw.textbbox((0, 0), label, font=font)[2] > w * 0.74 and size > 20:
        size -= 4
        font = _font(size)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2 - bbox[1]), label, font=font, fill=(255, 255, 255))

    folder = Config.UPLOAD_FOLDER
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(folder, filename)
    img.save(path, optimize=True)
    db.session.add(Media(data=open(path, "rb").read(), filename=filename, original_name=f"{label}.png", mime_type="image/png",
                         size=os.path.getsize(path), width=w, height=h, alt_text=label))
    return f"/uploads/{filename}"


def make_avatar(initials, index):
    a, b = (_hex(x) for x in PALETTES[(index + 3) % len(PALETTES)])
    s = 300
    img = gradient((s, s), a, b)
    draw = ImageDraw.Draw(img)
    font = _font(110)
    bbox = draw.textbbox((0, 0), initials, font=font)
    draw.text(((s - (bbox[2] - bbox[0])) / 2, (s - (bbox[3] - bbox[1])) / 2 - bbox[1]),
              initials, font=font, fill=(255, 255, 255))
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(Config.UPLOAD_FOLDER, filename)
    img.save(path, optimize=True)
    db.session.add(Media(data=open(path, "rb").read(), filename=filename, original_name=f"{initials}.png", mime_type="image/png",
                         size=os.path.getsize(path), width=s, height=s, alt_text=initials))
    return f"/uploads/{filename}"


# --------------------------------------------------------------------------- #
#  3. Seed data
# --------------------------------------------------------------------------- #
def seed_admin():
    email = os.getenv("ADMIN_EMAIL", "admin@portfolio.com").lower()
    user = User.query.filter_by(email=email).first()
    if user:
        print(f"✔ Admin user {email} already exists")
        return
    user = User(name=os.getenv("ADMIN_NAME", "Portfolio Admin"), email=email, role="admin")
    user.set_password(os.getenv("ADMIN_PASSWORD", "Admin@123"))
    db.session.add(user)
    db.session.commit()
    print(f"✔ Admin user created: {email} / {os.getenv('ADMIN_PASSWORD', 'Admin@123')}")


def seed_content():
    if About.query.first() or Project.query.first():
        print("✔ Content already exists – skipping demo content (use --reset to start over)")
        return

    db.session.add(About(
        name="Alex Morgan",
        title="Full-Stack Developer",
        tagline="I build colourful, fast and friendly web experiences with Python & React.",
        bio=("Hi! I'm Alex, a full-stack developer who loves turning ideas into real products. "
             "I work mostly with **Python (Flask, Django)**, **React / Next.js** and **PostgreSQL**.\n\n"
             "I enjoy designing clean APIs, building smooth user interfaces and learning something "
             "new every week. When I'm not coding you'll find me sketching UI ideas, reading tech "
             "blogs or playing football."),
        profile_image=make_avatar("AM", 0),
        email="hello@alexmorgan.dev",
        phone="+91 98765 43210",
        location="Bengaluru, India",
        years_experience=3,
        projects_completed=24,
        happy_clients=15,
        available_for_work=True,
    ))

    skills = [
        ("Python", "Backend", 92, "🐍", "#3b82f6"), ("Flask", "Backend", 88, "🧪", "#10b981"),
        ("Django", "Backend", 80, "🎸", "#059669"), ("PostgreSQL", "Database", 85, "🐘", "#6366f1"),
        ("REST APIs", "Backend", 90, "🔌", "#f97316"), ("React", "Frontend", 88, "⚛️", "#06b6d4"),
        ("Next.js", "Frontend", 82, "▲", "#8b5cf6"), ("Tailwind CSS", "Frontend", 90, "🎨", "#14b8a6"),
        ("JavaScript", "Frontend", 87, "✨", "#eab308"), ("Git & GitHub", "Tools", 85, "🌿", "#ef4444"),
        ("Docker", "Tools", 70, "🐳", "#0ea5e9"), ("Figma", "Design", 75, "🖌️", "#ec4899"),
    ]
    for i, (name, cat, prof, icon, color) in enumerate(skills):
        db.session.add(Skill(name=name, category=cat, proficiency=prof, icon=icon, color=color,
                             display_order=i, status="published"))

    projects = [
        ("Custom Portfolio CMS", "Headless CMS built from scratch with Flask, JWT auth and a React admin panel.",
         "Python, Flask, PostgreSQL, React, Tailwind", "Full-Stack", True),
        ("ShopSwift E-commerce", "A lightning-fast online store with cart, payments and an order dashboard.",
         "Next.js, Stripe, PostgreSQL, Tailwind", "Web App", True),
        ("QuizMaster Platform", "Online assessment platform with timers, auto-scoring and leaderboards.",
         "FastAPI, React, PostgreSQL, Recharts", "Full-Stack", True),
        ("WeatherWave", "Beautiful weather app with animated backgrounds and 7-day forecasts.",
         "React, OpenWeather API, Framer Motion", "Frontend", False),
        ("TaskFlow Kanban", "Drag-and-drop kanban board with real-time collaboration.",
         "React, Flask-SocketIO, Redis", "Web App", False),
        ("ExpenseEye", "Personal finance tracker with charts, budgets and CSV export.",
         "Django, Chart.js, PostgreSQL", "Full-Stack", False),
    ]
    for i, (title, summary, tech, cat, featured) in enumerate(projects):
        db.session.add(Project(
            title=title, slug=title.lower().replace(" ", "-").replace("&", "and"),
            summary=summary,
            description=(f"## Overview\n{summary}\n\n## Key features\n- Clean, responsive UI\n"
                         "- Secure authentication\n- REST API with full CRUD\n- Deployed to the cloud\n\n"
                         "## What I learned\nDesigning a scalable data model and polishing the UX "
                         "with small delightful animations."),
            image=make_image(title, i), tech_stack=tech, category=cat,
            github_url="https://github.com/", live_url="https://example.com",
            featured=featured, display_order=i, status="published"))

    blogs = [
        ("Building a CMS From Scratch with Flask", "flask,cms,python", "2026-09-20", True),
        ("JWT Authentication Explained Simply", "jwt,security,auth", "2026-09-05", False),
        ("10 Tailwind Tricks for Vibrant UIs", "tailwind,css,design", "2026-08-18", False),
        ("Draft vs Published: Content Workflows", "cms,workflow", "2026-08-02", False),
    ]
    for i, (title, tags, date, featured) in enumerate(blogs):
        db.session.add(Blog(
            title=title, slug=title.lower().replace(" ", "-").replace(":", ""),
            excerpt=f"A practical, beginner-friendly guide: {title.lower()}.",
            content=("In this post I share what I learned while working on my portfolio CMS.\n\n"
                     "## Why it matters\nKeeping content separate from code means you can update your "
                     "website **without touching a single line of code**.\n\n"
                     "## Step by step\n1. Design the data model\n2. Build the REST API\n"
                     "3. Protect it with JWT\n4. Connect the frontend\n\n"
                     "```python\n@app.get('/api/projects')\ndef projects():\n    return jsonify(data=[...])\n```\n\n"
                     "## Wrapping up\nStart small, ship often and keep learning! 🚀"),
            cover_image=make_image(title.split(":")[0], i + 3), tags=tags, author="Alex Morgan",
            featured=featured, published_at=date, status="published"))
    db.session.add(Blog(title="Upcoming: My 2026 Dev Setup", slug="upcoming-my-2026-dev-setup",
                        excerpt="This one is still a draft – only visible in the CMS.",
                        content="Draft content...", tags="setup", author="Alex Morgan", status="draft"))

    experience = [
        ("PixelCraft Studios", "Full-Stack Developer", "Full-Time", "2024-06", None, True,
         "Building client portfolios and CMS-driven websites with Flask, React and PostgreSQL. "
         "Led the migration to a headless architecture, cutting page load time by 40%."),
        ("CodeNest Labs", "Backend Developer", "Full-Time", "2023-01", "2024-05", False,
         "Designed REST APIs used by 20k+ users, wrote automated tests and set up CI/CD pipelines."),
        ("BrightByte Solutions", "Software Engineering Intern", "Internship", "2022-06", "2022-12", False,
         "Built internal dashboards in React and learned production-grade Python development."),
    ]
    for i, (company, pos, typ, start, end, current, desc) in enumerate(experience):
        db.session.add(Experience(company=company, position=pos,
                                  employment_type=typ.replace("Full-Time", "Full-time"),
                                  location="Bengaluru, India", description=desc, start_date=start,
                                  end_date=end, current=current, display_order=i, status="published"))

    db.session.add(Education(institution="National Institute of Technology", degree="B.Tech",
                             field="Computer Science & Engineering", start_year=2019, end_year=2023,
                             grade="8.7 CGPA", description="Core CS, databases, web development.",
                             display_order=0, status="published"))
    db.session.add(Education(institution="Delhi Public School", degree="Senior Secondary (XII)",
                             field="Science – PCM", start_year=2017, end_year=2019, grade="92%",
                             display_order=1, status="published"))

    testimonials = [
        ("Priya Sharma", "Product Manager", "PixelCraft Studios",
         "Alex turned our messy requirements into a beautiful, fast product. Communication was superb!"),
        ("Rahul Verma", "Founder", "ShopSwift",
         "Our online store launched on time and sales went up 35% in the first month. Highly recommended."),
        ("Emily Chen", "Tech Lead", "CodeNest Labs",
         "One of the most reliable backend developers I've worked with. Clean code, great tests."),
    ]
    for i, (name, role, company, content) in enumerate(testimonials):
        initials = "".join(p[0] for p in name.split())[:2]
        db.session.add(Testimonial(name=name, role=role, company=company, content=content, rating=5,
                                   avatar=make_avatar(initials, i + 1), display_order=i,
                                   status="published"))

    services = [
        ("Web Development", "Fast, responsive websites and web apps built with React, Next.js and Tailwind.", "💻", "#8b5cf6", "From ₹15,000"),
        ("Backend & APIs", "Secure REST APIs with Python (Flask / Django), JWT auth and PostgreSQL.", "⚙️", "#06b6d4", "From ₹20,000"),
        ("Custom CMS", "Manage your own content easily with a tailor-made admin dashboard.", "🗂️", "#f97316", "From ₹25,000"),
        ("UI / UX Design", "Colourful, modern interfaces designed in Figma and brought to life.", "🎨", "#ec4899", "From ₹10,000"),
    ]
    for i, (title, desc, icon, color, price) in enumerate(services):
        db.session.add(Service(title=title, description=desc, icon=icon, color=color, price=price,
                               display_order=i, status="published"))

    socials = [("GitHub", "https://github.com/", "🐙"), ("LinkedIn", "https://linkedin.com/", "💼"),
               ("Twitter", "https://x.com/", "🐦"), ("Instagram", "https://instagram.com/", "📸")]
    for i, (platform, url, icon) in enumerate(socials):
        db.session.add(SocialLink(platform=platform, url=url, icon=icon, display_order=i,
                                  status="published"))

    db.session.commit()
    print("✔ Demo content created (about, skills, projects, blogs, experience, education, "
          "testimonials, services, social links, media)")


def main():
    args = set(sys.argv[1:])
    ensure_database(Config.SQLALCHEMY_DATABASE_URI)
    app = create_app()
    with app.app_context():
        if "--reset" in args:
            db.drop_all()
            db.create_all()
            print("✔ Tables dropped and re-created")
        seed_admin()
        if "--admin-only" not in args:
            seed_content()
    print("\n🎉 Done! Start the API with:  python run.py")


if __name__ == "__main__":
    main()
