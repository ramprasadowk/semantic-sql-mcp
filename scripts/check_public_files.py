"""Check staged and publishable working files without printing secret values."""
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    secrets = set()
    for env_file in ROOT.glob(".env*"):
        if env_file.name == ".env.example" or not env_file.is_file():
            continue
        for key, value in dotenv_values(env_file).items():
            if not value:
                continue
            if any(word in key for word in ("KEY", "TOKEN", "PASSWORD", "URL")):
                if len(value) >= 12:
                    secrets.add(value)
                if "://" in value:
                    password = urlsplit(value).password
                    if password and len(unquote(password)) >= 8:
                        secrets.add(unquote(password))
                        secrets.add(password)
    paths = set(filter(None, git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")))
    tracked = set(filter(None, git("ls-files", "--cached", "-z").decode().split("\0")))
    findings = []
    for name in sorted(paths):
        path = ROOT / name
        contents = []
        if path.is_file():
            contents.append(("working", path.read_bytes()))
        if name in tracked:
            contents.append(("staged", git("show", ":" + name)))
        if (path.name.startswith(".env") and name != ".env.example") or path.name == ".neon":
            findings.append(name + ": private config is included")
        for location, data in contents:
            text = data.decode("utf-8", errors="ignore")
            if any(secret in text for secret in secrets):
                findings.append(name + ": local credential match in " + location)
            if re.search(r"sk-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
                findings.append(name + ": secret pattern in " + location)
            if name != ".env.example" and re.search(r"postgres(?:ql)?://[^\s:/]+:[^\s@]+@", text):
                findings.append(name + ": credential-bearing database URL in " + location)
    for name in (".env.local", ".env.development.local", ".neon", ".streamlit/secrets.toml", ".venv/pyvenv.cfg", ".venv-mcp/pyvenv.cfg", "node_modules/.package-lock.json"):
        if subprocess.run(["git", "check-ignore", "-q", "--no-index", name], cwd=ROOT).returncode:
            findings.append(name + ": missing ignore rule")
    if findings:
        print("FAIL: review these files; values are withheld:")
        print("\n".join(sorted(set(findings))))
        raise SystemExit(1)
    print(f"PASS: {len(paths)} publishable files checked, including staged contents. No known local credentials or secret patterns found.")
    print("Ignore rules verified. This scan does not guarantee detection of every possible secret.")


if __name__ == "__main__":
    main()
