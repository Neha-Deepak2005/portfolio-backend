"""
Interactive helper that creates the .env file.

    python configure.py

It asks for your PostgreSQL details, generates secure secret keys and writes .env.
"""
import getpass
import secrets
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ENV = HERE / ".env"
EXAMPLE = HERE / ".env.example"


def ask(question, default):
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def main():
    print("\n🎨 Portfolio CMS – configuration\n")
    if ENV.exists() and ask(".env already exists. Overwrite it? (y/n)", "n").lower() != "y":
        print("Keeping the existing .env")
        return

    print("Enter your PostgreSQL details (press Enter to accept the default):")
    user = ask("  PostgreSQL username", "postgres")
    password = getpass.getpass("  PostgreSQL password (the one you set while installing PostgreSQL): ")
    host = ask("  Host", "localhost")
    port = ask("  Port", "5432")
    name = ask("  Database name", "portfolio_cms")

    print("\nFirst admin account for the CMS:")
    admin_email = ask("  Admin email", "admin@portfolio.com")
    admin_password = ask("  Admin password", "Admin@123")

    auth = f"{quote(user)}:{quote(password)}" if password else quote(user)
    text = EXAMPLE.read_text(encoding="utf-8")
    replacements = {
        "SECRET_KEY=change-me-to-a-long-random-string": f"SECRET_KEY={secrets.token_urlsafe(48)}",
        "JWT_SECRET_KEY=change-me-too-another-long-random-string": f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}",
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/portfolio_cms":
            f"DATABASE_URL=postgresql://{auth}@{host}:{port}/{name}",
        "TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/portfolio_cms_test":
            f"TEST_DATABASE_URL=postgresql://{auth}@{host}:{port}/{name}_test",
        "ADMIN_EMAIL=admin@portfolio.com": f"ADMIN_EMAIL={admin_email}",
        "ADMIN_PASSWORD=Admin@123": f"ADMIN_PASSWORD={admin_password}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    ENV.write_text(text, encoding="utf-8")
    print(f"\n✔ Saved {ENV.name}. Next step:  python seed.py\n")


if __name__ == "__main__":
    main()
