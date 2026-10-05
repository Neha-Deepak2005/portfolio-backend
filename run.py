"""Start the development server:  python run.py  ->  http://localhost:5000"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Portfolio CMS API running on http://localhost:{port}")
    print(f"📚 API docs (Swagger):         http://localhost:{port}/api/docs\n")
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
