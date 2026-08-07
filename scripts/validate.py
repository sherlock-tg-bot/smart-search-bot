#!/usr/bin/env python3
"""Validate the repository's content contract without third-party packages."""

from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("README.md", "FAQ.md", "SECURITY.md", "index.html", "metadata.json")
CTA_TEXTS = ("Открыть в Telegram", "Перейти в Telegram")
FORBIDDEN_HOSTS = {"sherlockbot.is", "www.sherlockbot.is", "glazboga.is", "www.glazboga.is", "t.me", "telegram.me"}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = []
        self.links = []
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self._in_h1 = True
        if tag == "a" and attrs.get("href"):
            self.links.append((attrs["href"], ""))

    def handle_data(self, data):
        if self._in_h1:
            self.h1.append(data)

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False


def fail(message):
    print(f"ERROR: {message}")
    return 1


def check_urls(text, filename, target_url):
    errors = []
    for token in text.replace('"', " ").replace("'", " ").split():
        if not token.startswith(("http://", "https://")):
            continue
        host = urlparse(token.rstrip(")>,.;")).hostname
        if host in FORBIDDEN_HOSTS:
            errors.append(f"{filename}: запрещённый домен {host}")
    return errors


def main():
    errors = []
    metadata_path = ROOT / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"metadata.json: {exc}")

    keyword = metadata.get("keyword")
    target_url = metadata.get("target_url")
    slug = metadata.get("slug")
    if not isinstance(keyword, str) or not keyword.strip():
        errors.append("metadata.json: отсутствует непустой keyword")
    if not isinstance(target_url, str) or not target_url.startswith("https://"):
        errors.append("metadata.json: отсутствует корректный target_url")
    if not isinstance(slug, str) or not slug.strip():
        errors.append("metadata.json: отсутствует непустой slug")

    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append(f"отсутствует обязательный файл: {name}")
    workflow = ROOT / ".github/workflows/validate.yml"
    script = ROOT / "scripts/validate.py"
    if not workflow.is_file():
        errors.append("отсутствует .github/workflows/validate.yml")
    if not script.is_file():
        errors.append("отсутствует scripts/validate.py")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    keyword_lower = keyword.lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    faq = (ROOT / "FAQ.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    workflow_text = workflow.read_text(encoding="utf-8")

    if keyword_lower not in readme.lower() or keyword_lower not in html.lower():
        errors.append("keyword должен встречаться в README.md и index.html")
    if not readme.lstrip().startswith("# "):
        errors.append("README.md должен начинаться с H1")
    if keyword_lower not in readme.split("\n", 1)[0].lower():
        errors.append("H1 README.md должен содержать точный keyword")
    if target_url not in readme[:700]:
        errors.append("target_url должен быть в начале README.md")
    if target_url not in readme[-900:]:
        errors.append("target_url должен быть в итоговом блоке README.md")
    if target_url not in html:
        errors.append("target_url должен встречаться в index.html")
    if not any(text in readme for text in CTA_TEXTS) or not any(text in html for text in CTA_TEXTS):
        errors.append("CTA должен иметь понятный текст в README.md и index.html")
    if readme.count("![") != 1 or "https://github.com/sherlock-tg-bot/" not in readme:
        errors.append("разрешён только badge workflow этого репозитория")
    if readme.count("![") == 1 and "actions/workflows/validate.yml/badge.svg" not in readme:
        errors.append("badge должен ссылаться на validate.yml")
    if faq.count("## ") < 4 or faq.count("## ") > 7:
        errors.append("FAQ.md должен содержать от 4 до 7 вопросов второго уровня")
    content_lower = (readme + faq + security).lower()
    if any(phrase in content_lower for phrase in ("официальный сервис", "официальный инструмент", "официальный бот")):
        errors.append("не называйте сервис официальным вне государственного способа проверки")

    parser = PageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        errors.append(f"index.html: ошибка разбора ({exc})")
    if not parser.h1 or keyword_lower not in "".join(parser.h1).lower():
        errors.append("index.html должен содержать H1 с keyword")
    if "<meta name=\"viewport\"" not in html.lower():
        errors.append("index.html должен быть адаптивным (viewport)")
    if "Content validation" not in workflow_text or "python3 scripts/validate.py" not in workflow_text:
        errors.append("workflow должен называться Content validation и запускать валидатор")

    for filename, text in (("README.md", readme), ("FAQ.md", faq), ("SECURITY.md", security), ("index.html", html)):
        errors.extend(check_urls(text, filename, target_url))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: content validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
