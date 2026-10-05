"""
Database models for the custom CMS.

Every content type declares a FIELDS spec. The spec drives:
  * request validation (app/utils/validation.py)
  * the generic CRUD API (app/routes/content.py)
  * the OpenAPI documentation (app/routes/docs.py)
"""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


STATUS_CHOICES = ["draft", "published"]


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SerializerMixin:
    """Turns a row into JSON using the model's FIELDS spec."""

    FIELDS: dict = {}

    def to_dict(self):
        data = {"id": self.id}
        for name, spec in self.FIELDS.items():
            value = getattr(self, name)
            if spec["type"] == "list":
                value = [v.strip() for v in (value or "").split(",") if v.strip()]
            data[name] = value
        for extra in ("created_at", "updated_at"):
            if hasattr(self, extra) and getattr(self, extra):
                data[extra] = getattr(self, extra).isoformat() + "Z"
        return data


# --------------------------------------------------------------------------- #
#  Users / auth
# --------------------------------------------------------------------------- #
class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="admin", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "last_login": self.last_login.isoformat() + "Z" if self.last_login else None,
        }


# --------------------------------------------------------------------------- #
#  About / Profile (single row)
# --------------------------------------------------------------------------- #
class About(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "about"

    FIELDS = {
        "name": {"type": "string", "required": True, "max": 120},
        "title": {"type": "string", "required": True, "max": 160},
        "tagline": {"type": "string", "max": 255},
        "bio": {"type": "text"},
        "profile_image": {"type": "image"},
        "resume_url": {"type": "url"},
        "email": {"type": "email"},
        "phone": {"type": "string", "max": 40},
        "location": {"type": "string", "max": 120},
        "years_experience": {"type": "integer", "min": 0},
        "projects_completed": {"type": "integer", "min": 0},
        "happy_clients": {"type": "integer", "min": 0},
        "available_for_work": {"type": "boolean"},
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Your Name")
    title = db.Column(db.String(160), nullable=False, default="Developer")
    tagline = db.Column(db.String(255))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(500))
    resume_url = db.Column(db.String(500))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(40))
    location = db.Column(db.String(120))
    years_experience = db.Column(db.Integer, default=0)
    projects_completed = db.Column(db.Integer, default=0)
    happy_clients = db.Column(db.Integer, default=0)
    available_for_work = db.Column(db.Boolean, default=True)


# --------------------------------------------------------------------------- #
#  Content collections (all support draft / published)
# --------------------------------------------------------------------------- #
class Skill(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "skills"
    FIELDS = {
        "name": {"type": "string", "required": True, "max": 80},
        "category": {"type": "string", "max": 60, "default": "General"},
        "proficiency": {"type": "integer", "min": 0, "max": 100, "default": 70},
        "icon": {"type": "string", "max": 20},
        "color": {"type": "color"},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(60), default="General")
    proficiency = db.Column(db.Integer, default=70)
    icon = db.Column(db.String(20))
    color = db.Column(db.String(20))
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


class Project(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "projects"
    FIELDS = {
        "title": {"type": "string", "required": True, "max": 200},
        "slug": {"type": "slug", "source": "title"},
        "summary": {"type": "string", "max": 300},
        "description": {"type": "text"},
        "image": {"type": "image"},
        "tech_stack": {"type": "list"},
        "category": {"type": "string", "max": 60},
        "github_url": {"type": "url"},
        "live_url": {"type": "url"},
        "featured": {"type": "boolean", "default": False},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "draft"},
    }
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, index=True)
    summary = db.Column(db.String(300))
    description = db.Column(db.Text)
    image = db.Column(db.String(500))
    tech_stack = db.Column(db.String(500))
    category = db.Column(db.String(60))
    github_url = db.Column(db.String(500))
    live_url = db.Column(db.String(500))
    featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="draft", index=True)


class Blog(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "blogs"
    FIELDS = {
        "title": {"type": "string", "required": True, "max": 200},
        "slug": {"type": "slug", "source": "title"},
        "excerpt": {"type": "string", "max": 400},
        "content": {"type": "text", "required": True},
        "cover_image": {"type": "image"},
        "tags": {"type": "list"},
        "author": {"type": "string", "max": 120},
        "featured": {"type": "boolean", "default": False},
        "published_at": {"type": "date"},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "draft"},
    }
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, index=True)
    excerpt = db.Column(db.String(400))
    content = db.Column(db.Text, nullable=False)
    cover_image = db.Column(db.String(500))
    tags = db.Column(db.String(500))
    author = db.Column(db.String(120))
    featured = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.String(10))
    status = db.Column(db.String(20), default="draft", index=True)

    def to_dict(self):
        data = super().to_dict()
        words = len((self.content or "").split())
        data["read_time"] = max(1, round(words / 200))
        return data


class Experience(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "experience"
    FIELDS = {
        "company": {"type": "string", "required": True, "max": 160},
        "position": {"type": "string", "required": True, "max": 160},
        "employment_type": {"type": "choice",
                            "choices": ["Full-time", "Part-time", "Internship", "Freelance", "Contract"],
                            "default": "Full-time"},
        "location": {"type": "string", "max": 120},
        "description": {"type": "text"},
        "company_logo": {"type": "image"},
        "start_date": {"type": "month", "required": True},
        "end_date": {"type": "month"},
        "current": {"type": "boolean", "default": False},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(160), nullable=False)
    position = db.Column(db.String(160), nullable=False)
    employment_type = db.Column(db.String(30), default="Full-time")
    location = db.Column(db.String(120))
    description = db.Column(db.Text)
    company_logo = db.Column(db.String(500))
    start_date = db.Column(db.String(7), nullable=False)
    end_date = db.Column(db.String(7))
    current = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


class Education(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "education"
    FIELDS = {
        "institution": {"type": "string", "required": True, "max": 200},
        "degree": {"type": "string", "required": True, "max": 160},
        "field": {"type": "string", "max": 160},
        "description": {"type": "text"},
        "start_year": {"type": "integer", "min": 1950, "max": 2100},
        "end_year": {"type": "integer", "min": 1950, "max": 2100},
        "grade": {"type": "string", "max": 40},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    institution = db.Column(db.String(200), nullable=False)
    degree = db.Column(db.String(160), nullable=False)
    field = db.Column(db.String(160))
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    grade = db.Column(db.String(40))
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


class Testimonial(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "testimonials"
    FIELDS = {
        "name": {"type": "string", "required": True, "max": 120},
        "role": {"type": "string", "max": 120},
        "company": {"type": "string", "max": 120},
        "content": {"type": "text", "required": True},
        "avatar": {"type": "image"},
        "rating": {"type": "integer", "min": 1, "max": 5, "default": 5},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120))
    company = db.Column(db.String(120))
    content = db.Column(db.Text, nullable=False)
    avatar = db.Column(db.String(500))
    rating = db.Column(db.Integer, default=5)
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


class Service(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "services"
    FIELDS = {
        "title": {"type": "string", "required": True, "max": 120},
        "description": {"type": "text", "required": True},
        "icon": {"type": "string", "max": 20},
        "color": {"type": "color"},
        "price": {"type": "string", "max": 60},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(20))
    color = db.Column(db.String(20))
    price = db.Column(db.String(60))
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


class SocialLink(SerializerMixin, TimestampMixin, db.Model):
    __tablename__ = "social_links"
    FIELDS = {
        "platform": {"type": "string", "required": True, "max": 60},
        "url": {"type": "url", "required": True},
        "icon": {"type": "string", "max": 20},
        "display_order": {"type": "integer", "default": 0},
        "status": {"type": "choice", "choices": STATUS_CHOICES, "default": "published"},
    }
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(60), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(20))
    display_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="published", index=True)


# --------------------------------------------------------------------------- #
#  Contact messages & media
# --------------------------------------------------------------------------- #
class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    email_sent = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "is_read": self.is_read,
            "email_sent": self.email_sent,
            "created_at": self.created_at.isoformat() + "Z",
        }


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    original_name = db.Column(db.String(255))
    mime_type = db.Column(db.String(100))
    size = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    alt_text = db.Column(db.String(255))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    # File bytes are also kept in PostgreSQL, so uploads survive hosts with a
    # temporary disk (e.g. Render free plan) – the disk copy is just a cache.
    data = db.deferred(db.Column(db.LargeBinary))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def url(self):
        return f"/uploads/{self.filename}"

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "url": self.url,
            "mime_type": self.mime_type,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "alt_text": self.alt_text,
            "created_at": self.created_at.isoformat() + "Z",
        }
