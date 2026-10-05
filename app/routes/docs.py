"""
API documentation.

    GET /api/openapi.json   OpenAPI 3 spec (generated from the models)
    GET /api/docs           Swagger UI
"""
from flask import Blueprint, Response, jsonify

from ..models import About
from .content import RESOURCES

bp = Blueprint("docs", __name__)

TYPE_MAP = {
    "string": {"type": "string"}, "slug": {"type": "string"}, "text": {"type": "string"},
    "integer": {"type": "integer"}, "boolean": {"type": "boolean"},
    "url": {"type": "string", "format": "uri"}, "image": {"type": "string", "format": "uri"},
    "email": {"type": "string", "format": "email"}, "month": {"type": "string", "example": "2024-06"},
    "date": {"type": "string", "format": "date"}, "color": {"type": "string", "example": "#ff3366"},
    "list": {"type": "array", "items": {"type": "string"}},
}

SECURED = [{"bearerAuth": []}]


def _schema(fields):
    props, required = {}, []
    for name, spec in fields.items():
        if spec["type"] == "choice":
            props[name] = {"type": "string", "enum": spec["choices"]}
        else:
            props[name] = dict(TYPE_MAP.get(spec["type"], {"type": "string"}))
        if "max" in spec and spec["type"] in ("string", "slug"):
            props[name]["maxLength"] = spec["max"]
        if spec.get("required"):
            required.append(name)
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _json(ref=None, schema=None):
    return {"content": {"application/json": {"schema": schema or {"$ref": ref}}}}


def build_spec():
    paths, schemas = {}, {}
    ok = {"description": "OK"}
    unauthorized = {"description": "Missing / invalid token"}

    paths["/api/auth/login"] = {"post": {
        "tags": ["Auth"], "summary": "Admin login – returns access & refresh JWT",
        "requestBody": _json(schema={"type": "object", "required": ["email", "password"],
                                     "properties": {"email": {"type": "string"},
                                                    "password": {"type": "string"}}}),
        "responses": {"200": ok, "401": {"description": "Invalid credentials"}}}}
    paths["/api/auth/refresh"] = {"post": {
        "tags": ["Auth"], "summary": "Get a new access token (send REFRESH token as Bearer)",
        "security": SECURED, "responses": {"200": ok, "401": unauthorized}}}
    paths["/api/auth/me"] = {"get": {"tags": ["Auth"], "summary": "Current admin",
                                     "security": SECURED, "responses": {"200": ok}}}
    paths["/api/auth/password"] = {"put": {"tags": ["Auth"], "summary": "Change password",
                                           "security": SECURED, "responses": {"200": ok}}}

    schemas["About"] = _schema(About.FIELDS)
    paths["/api/about"] = {
        "get": {"tags": ["About"], "summary": "Get profile / about info", "responses": {"200": ok}},
        "put": {"tags": ["About"], "summary": "Update profile", "security": SECURED,
                "requestBody": _json("#/components/schemas/About"),
                "responses": {"200": ok, "401": unauthorized, "422": {"description": "Validation error"}}},
    }

    for name, (model, label, _cols) in RESOURCES.items():
        schema_name = model.__name__
        schemas[schema_name] = _schema(model.FIELDS)
        tag = label + "s" if not label.endswith("s") else label
        ref = f"#/components/schemas/{schema_name}"
        params = [
            {"name": "search", "in": "query", "schema": {"type": "string"}},
            {"name": "status", "in": "query", "description": "admin only: draft | published",
             "schema": {"type": "string"}},
            {"name": "page", "in": "query", "schema": {"type": "integer"}},
            {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
        ]
        if hasattr(model, "featured"):
            params.append({"name": "featured", "in": "query", "schema": {"type": "boolean"}})
        paths[f"/api/{name}"] = {
            "get": {"tags": [tag], "summary": f"List {tag.lower()} (public sees only published)",
                    "parameters": params, "responses": {"200": ok}},
            "post": {"tags": [tag], "summary": f"Create {label.lower()}", "security": SECURED,
                     "requestBody": _json(ref), "responses": {"201": {"description": "Created"},
                                                              "401": unauthorized, "422": {"description": "Validation error"}}},
        }
        id_param = [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "numeric id" + (" or slug" if "slug" in model.FIELDS else "")}]
        paths[f"/api/{name}/{{id}}"] = {
            "get": {"tags": [tag], "summary": f"Get one {label.lower()}", "parameters": id_param,
                    "responses": {"200": ok, "404": {"description": "Not found"}}},
            "put": {"tags": [tag], "summary": f"Update {label.lower()}", "security": SECURED,
                    "parameters": id_param, "requestBody": _json(ref), "responses": {"200": ok}},
            "delete": {"tags": [tag], "summary": f"Delete {label.lower()}", "security": SECURED,
                       "parameters": id_param, "responses": {"200": ok}},
        }
        paths[f"/api/{name}/{{id}}/status"] = {"patch": {
            "tags": [tag], "summary": "Publish / move to draft", "security": SECURED,
            "parameters": id_param,
            "requestBody": _json(schema={"type": "object", "properties": {
                "status": {"type": "string", "enum": ["draft", "published"]}}}),
            "responses": {"200": ok}}}
        paths[f"/api/{name}/reorder"] = {"post": {
            "tags": [tag], "summary": "Save display order", "security": SECURED,
            "requestBody": _json(schema={"type": "object", "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}}}}),
            "responses": {"200": ok}}}

    upload_body = {"content": {"multipart/form-data": {"schema": {
        "type": "object", "properties": {"file": {"type": "string", "format": "binary"},
                                         "alt_text": {"type": "string"}}}}}}
    paths["/api/upload/image"] = {"post": {"tags": ["Media"], "summary": "Upload image (jpg, png, gif, webp – max 5MB)",
                                           "security": SECURED, "requestBody": upload_body,
                                           "responses": {"201": {"description": "Uploaded"}}}}
    paths["/api/upload/file"] = {"post": {"tags": ["Media"], "summary": "Upload PDF (e.g. resume)",
                                          "security": SECURED, "requestBody": upload_body,
                                          "responses": {"201": {"description": "Uploaded"}}}}
    paths["/api/media"] = {"get": {"tags": ["Media"], "summary": "List media library",
                                   "security": SECURED, "responses": {"200": ok}}}
    paths["/api/media/{id}"] = {
        "put": {"tags": ["Media"], "summary": "Update alt text", "security": SECURED,
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": ok}},
        "delete": {"tags": ["Media"], "summary": "Delete media", "security": SECURED,
                   "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                   "responses": {"200": ok}}}

    paths["/api/contact"] = {"post": {
        "tags": ["Contact"], "summary": "Submit contact form (saves message + sends email)",
        "requestBody": _json(schema={"type": "object", "required": ["name", "email", "message"],
                                     "properties": {"name": {"type": "string"}, "email": {"type": "string"},
                                                    "subject": {"type": "string"}, "message": {"type": "string"}}}),
        "responses": {"201": {"description": "Saved"}, "422": {"description": "Validation error"},
                      "429": {"description": "Rate limited"}}}}
    paths["/api/messages"] = {"get": {"tags": ["Contact"], "summary": "Inbox", "security": SECURED,
                                      "responses": {"200": ok}}}
    paths["/api/messages/{id}"] = {
        "patch": {"tags": ["Contact"], "summary": "Mark read/unread", "security": SECURED,
                  "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                  "responses": {"200": ok}},
        "delete": {"tags": ["Contact"], "summary": "Delete message", "security": SECURED,
                   "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                   "responses": {"200": ok}}}
    paths["/api/site"] = {"get": {"tags": ["Site"], "summary": "All published content in one call",
                                  "responses": {"200": ok}}}
    paths["/api/dashboard"] = {"get": {"tags": ["Site"], "summary": "CMS dashboard stats",
                                       "security": SECURED, "responses": {"200": ok}}}
    paths["/api/health"] = {"get": {"tags": ["Site"], "summary": "Health check", "responses": {"200": ok}}}

    return {
        "openapi": "3.0.3",
        "info": {"title": "Portfolio CMS API", "version": "1.0.0",
                 "description": "Custom-built headless CMS for a developer portfolio. "
                                "Click **Authorize** and paste the access token from /api/auth/login "
                                "to try protected endpoints."},
        "servers": [{"url": "/"}],
        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer",
                                                          "bearerFormat": "JWT"}},
                       "schemas": schemas},
        "paths": paths,
    }


@bp.get("/openapi.json")
def openapi():
    return jsonify(build_spec())


SWAGGER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Portfolio CMS API Docs</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui.min.css">
<style>body{margin:0;background:#faf5ff}.topbar{display:none}
.swagger-ui .info .title{background:linear-gradient(90deg,#7c3aed,#ec4899,#f97316);-webkit-background-clip:text;color:transparent}</style>
</head><body><div id="ui"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui-bundle.min.js"></script>
<script>SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#ui',persistAuthorization:true});</script>
</body></html>"""


@bp.get("/docs")
def swagger_ui():
    return Response(SWAGGER_HTML, mimetype="text/html")
