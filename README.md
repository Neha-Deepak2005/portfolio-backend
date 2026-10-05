# Portfolio CMS – Backend (Flask + PostgreSQL)

The custom-built CMS: REST API, JWT auth, content models, media uploads and the contact form with email. The admin panel is a separate project in `../portfolio-admin`.

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python configure.py      # creates .env (asks for your PostgreSQL password)
python seed.py           # creates the database, tables, admin user, demo content
python run.py            # http://localhost:5000  ·  docs: /api/docs
python -m pytest -v      # 38 tests
```

See the main README one folder up for the full documentation.
