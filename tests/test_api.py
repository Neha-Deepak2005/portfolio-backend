import io

import pytest
from PIL import Image


# ------------------------------------------------------------------ auth ---
def test_login_success_returns_tokens(tokens):
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["user"]["email"] == "admin@test.com"


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "nope"})
    assert res.status_code == 401


def test_login_missing_fields(client):
    assert client.post("/api/auth/login", json={}).status_code == 400


def test_refresh_token_gives_new_access_token(client, tokens):
    res = client.post("/api/auth/refresh",
                      headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert res.status_code == 200
    assert "access_token" in res.get_json()


def test_access_token_cannot_be_used_to_refresh(client, auth):
    assert client.post("/api/auth/refresh", headers=auth).status_code in (401, 422)


def test_me(client, auth):
    res = client.get("/api/auth/me", headers=auth)
    assert res.get_json()["user"]["email"] == "admin@test.com"


def test_change_password(client, auth):
    res = client.put("/api/auth/password", headers=auth,
                     json={"current_password": "Secret123", "new_password": "NewSecret99"})
    assert res.status_code == 200
    ok = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "NewSecret99"})
    assert ok.status_code == 200


# ----------------------------------------------------------- permissions ---
@pytest.mark.parametrize("resource", ["skills", "projects", "blogs", "experience",
                                      "education", "testimonials", "services", "social-links"])
def test_public_cannot_write(client, resource):
    assert client.post(f"/api/{resource}", json={}).status_code == 401
    assert client.put(f"/api/{resource}/1", json={}).status_code == 401
    assert client.delete(f"/api/{resource}/1").status_code == 401


def test_invalid_token_rejected(client):
    res = client.post("/api/skills", json={"name": "x"},
                      headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


# ------------------------------------------------------------------ CRUD ---
def test_skill_crud(client, auth):
    res = client.post("/api/skills", headers=auth,
                      json={"name": "Python", "category": "Backend", "proficiency": 90})
    assert res.status_code == 201
    skill = res.get_json()["data"]
    assert skill["name"] == "Python" and skill["status"] == "published"

    res = client.put(f"/api/skills/{skill['id']}", headers=auth, json={"proficiency": 95})
    assert res.get_json()["data"]["proficiency"] == 95

    assert len(client.get("/api/skills").get_json()["data"]) == 1
    assert client.delete(f"/api/skills/{skill['id']}", headers=auth).status_code == 200
    assert client.get("/api/skills").get_json()["data"] == []


def test_validation_errors(client, auth):
    res = client.post("/api/skills", headers=auth, json={"proficiency": 150})
    assert res.status_code == 422
    fields = res.get_json()["fields"]
    assert "name" in fields and "proficiency" in fields


def test_url_validation(client, auth):
    res = client.post("/api/projects", headers=auth,
                      json={"title": "X", "github_url": "javascript:alert(1)"})
    assert res.status_code == 422


def test_html_is_stripped_from_plain_fields(client, auth):
    res = client.post("/api/skills", headers=auth, json={"name": "<script>x</script>React"})
    assert res.get_json()["data"]["name"] == "xReact"


def test_project_slug_and_detail_by_slug(client, auth):
    body = {"title": "My Cool App", "tech_stack": ["Flask", "React"], "status": "published"}
    first = client.post("/api/projects", headers=auth, json=body).get_json()["data"]
    second = client.post("/api/projects", headers=auth, json=body).get_json()["data"]
    assert first["slug"] == "my-cool-app"
    assert second["slug"] == "my-cool-app-2"
    assert first["tech_stack"] == ["Flask", "React"]
    res = client.get("/api/projects/my-cool-app")
    assert res.get_json()["data"]["id"] == first["id"]


def test_about_get_and_put(client, auth):
    assert client.get("/api/about").status_code == 200
    res = client.put("/api/about", headers=auth, json={"name": "Deepa", "title": "Developer",
                                                       "years_experience": 2})
    assert res.status_code == 200
    assert client.get("/api/about").get_json()["data"]["name"] == "Deepa"
    assert client.put("/api/about", json={"name": "Hacker"}).status_code == 401


def test_experience_month_validation(client, auth):
    bad = client.post("/api/experience", headers=auth,
                      json={"company": "A", "position": "B", "start_date": "June 2024"})
    assert bad.status_code == 422
    good = client.post("/api/experience", headers=auth,
                       json={"company": "A", "position": "B", "start_date": "2024-06"})
    assert good.status_code == 201


# -------------------------------------------------------- draft/publish ---
def test_drafts_hidden_from_public(client, auth):
    draft = client.post("/api/blogs", headers=auth,
                        json={"title": "Secret", "content": "hello world"}).get_json()["data"]
    assert draft["status"] == "draft"

    assert client.get("/api/blogs").get_json()["data"] == []
    assert client.get(f"/api/blogs/{draft['slug']}").status_code == 404
    assert len(client.get("/api/blogs", headers=auth).get_json()["data"]) == 1

    res = client.patch(f"/api/blogs/{draft['id']}/status", headers=auth, json={"status": "published"})
    assert res.get_json()["data"]["published_at"]
    assert len(client.get("/api/blogs").get_json()["data"]) == 1
    assert client.get(f"/api/blogs/{draft['slug']}").status_code == 200


def test_filters_search_and_pagination(client, auth):
    for i in range(12):
        client.post("/api/projects", headers=auth, json={
            "title": f"Project {i}", "status": "published", "featured": i < 3,
            "category": "Web" if i % 2 else "API"})
    assert client.get("/api/projects?featured=true").get_json()["total"] == 3
    assert client.get("/api/projects?category=Web").get_json()["total"] == 6
    assert client.get("/api/projects?search=Project 1").get_json()["total"] == 3  # 1, 10, 11
    page = client.get("/api/projects?page=2&per_page=5").get_json()
    assert page["pages"] == 3 and len(page["data"]) == 5


def test_reorder(client, auth):
    ids = [client.post("/api/services", headers=auth,
                       json={"title": f"S{i}", "description": "d"}).get_json()["data"]["id"]
           for i in range(3)]
    client.post("/api/services/reorder", headers=auth, json={"ids": list(reversed(ids))})
    titles = [s["title"] for s in client.get("/api/services").get_json()["data"]]
    assert titles == ["S2", "S1", "S0"]


# ---------------------------------------------------------------- upload ---
def _png_bytes(size=(50, 40)):
    buf = io.BytesIO()
    Image.new("RGB", size, "#ff00aa").save(buf, "PNG")
    buf.seek(0)
    return buf


def test_image_upload_and_media_library(client, auth):
    res = client.post("/api/upload/image", headers=auth, content_type="multipart/form-data",
                      data={"file": (_png_bytes(), "pic.png"), "alt_text": "Pink"})
    assert res.status_code == 201
    media = res.get_json()["data"]
    assert media["url"].startswith("/uploads/") and media["width"] == 50

    assert client.get(media["url"]).status_code == 200
    assert client.get("/api/media", headers=auth).get_json()["total"] == 1
    assert client.delete(f"/api/media/{media['id']}", headers=auth).status_code == 200
    assert client.get(media["url"]).status_code == 404


def test_upload_rejects_fake_image(client, auth):
    res = client.post("/api/upload/image", headers=auth, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"not an image"), "evil.png")})
    assert res.status_code == 400


def test_upload_rejects_bad_extension(client, auth):
    res = client.post("/api/upload/image", headers=auth, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"x"), "script.exe")})
    assert res.status_code == 400


def test_upload_requires_auth(client):
    res = client.post("/api/upload/image", content_type="multipart/form-data",
                      data={"file": (_png_bytes(), "pic.png")})
    assert res.status_code == 401


def test_large_images_are_resized(client, auth):
    res = client.post("/api/upload/image", headers=auth, content_type="multipart/form-data",
                      data={"file": (_png_bytes((3000, 1500)), "big.png")})
    assert res.get_json()["data"]["width"] == 1920


def test_pdf_upload(client, auth):
    res = client.post("/api/upload/file", headers=auth, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"%PDF-1.4 fake resume"), "resume.pdf")})
    assert res.status_code == 201


# --------------------------------------------------------------- contact ---
def test_contact_form_saves_message(client, auth):
    res = client.post("/api/contact", json={"name": "Visitor", "email": "v@example.com",
                                            "subject": "Hi", "message": "I would like to hire you!"})
    assert res.status_code == 201
    inbox = client.get("/api/messages", headers=auth).get_json()
    assert inbox["total"] == 1 and inbox["unread"] == 1

    msg_id = inbox["data"][0]["id"]
    client.patch(f"/api/messages/{msg_id}", headers=auth, json={"is_read": True})
    assert client.get("/api/messages", headers=auth).get_json()["unread"] == 0


def test_contact_validation(client):
    res = client.post("/api/contact", json={"name": "", "email": "bad", "message": "short"})
    assert res.status_code == 422
    assert set(res.get_json()["fields"]) == {"name", "email", "message"}


def test_messages_are_private(client):
    assert client.get("/api/messages").status_code == 401


# ------------------------------------------------------------ site/docs ---
def test_site_and_dashboard(client, auth):
    client.post("/api/projects", headers=auth, json={"title": "Public", "status": "published"})
    client.post("/api/projects", headers=auth, json={"title": "Hidden"})
    site = client.get("/api/site").get_json()["data"]
    assert [p["title"] for p in site["projects"]] == ["Public"]
    dash = client.get("/api/dashboard", headers=auth).get_json()
    assert dash["counts"]["projects"] == {"label": "Project", "total": 2, "published": 1, "draft": 1}
    assert client.get("/api/dashboard").status_code == 401


def test_openapi_docs(client):
    spec = client.get("/api/openapi.json").get_json()
    assert "/api/projects" in spec["paths"] and "/api/auth/login" in spec["paths"]
    assert client.get("/api/docs").status_code == 200


def test_health(client):
    assert client.get("/api/health").get_json()["database"] == "connected"


def test_upload_survives_lost_disk(client, auth, app):
    """Render's free disk is wiped on restart – files must come back from PostgreSQL."""
    import os
    res = client.post("/api/upload/image", headers=auth, content_type="multipart/form-data",
                      data={"file": (_png_bytes(), "pic.png")})
    media = res.get_json()["data"]
    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], media["filename"]))
    again = client.get(media["url"])
    assert again.status_code == 200 and again.mimetype == "image/png"
