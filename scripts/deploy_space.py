"""Deploy the backend to a Hugging Face Space (Docker SDK). Run by the USER from ~/hrbot:

    python scripts/deploy_space.py

Reads HF_TOKEN, OLLAMA_API_KEY and GEMINI_API_KEY from .env (never printed). It:
  1. checks the token and creates the Space if it does not exist (public, Docker SDK);
  2. stores OLLAMA_API_KEY and GEMINI_API_KEY as Space SECRETS (encrypted by Hugging Face, not in code);
  3. stages exactly the files the Dockerfile needs, scans them for anything that looks like a key,
     and uploads them (the Hub API handles binary files such as PDFs and vectors.npy).
Hugging Face then builds the image (about 5 to 10 minutes) and starts the Space.
"""
import re
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SPACE_NAME = "nia-hr-assistant"
STAGE = ROOT / ".cache" / "space-upload"
SECRET_RE = re.compile(r"ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AIza[0-9A-Za-z_-]{30,}|hf_[A-Za-z0-9]{30,}|"
                       r"sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "backend", STAGE / "backend", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "documents", STAGE / "documents")
    shutil.copy(ROOT / "data" / "employees.csv", STAGE / "data")
    for f in ("Dockerfile", "README.md", "requirements.txt"):
        shutil.copy(ROOT / "deploy" / "space" / f, STAGE / f)
    files = [p for p in STAGE.rglob("*") if p.is_file()]
    hits = [str(p.relative_to(STAGE)) for p in files if p.suffix in (".py", ".json", ".csv", ".md", ".txt", "")
            and SECRET_RE.search(p.read_text(errors="ignore"))]
    return files, hits


def main():
    env = dotenv_values(ROOT / ".env")
    token = (env.get("HF_TOKEN") or "").strip()
    if not token:
        sys.exit("HF_TOKEN is missing from .env. Add it with:  nano ~/hrbot/.env   (a line HF_TOKEN=... ; never paste it in chat)")
    missing = [k for k in ("OLLAMA_API_KEY", "GEMINI_API_KEY") if not (env.get(k) or "").strip()]
    if missing:
        sys.exit(f"Missing in .env: {missing}")
    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/{SPACE_NAME}"
    print(f"Signed in to Hugging Face as {user}. Space: {repo_id}")

    files, hits = stage()
    total = sum(p.stat().st_size for p in files) / 1e6
    print(f"Staged {len(files)} files ({total:.1f} MB). Secret scan: {'CLEAN' if not hits else 'FOUND ' + str(hits)}")
    if hits:
        sys.exit("Aborting: something that looks like a key is in the files to upload.")

    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    for k in ("OLLAMA_API_KEY", "GEMINI_API_KEY"):
        api.add_space_secret(repo_id, k, env[k].strip())
    print("Space secrets set: OLLAMA_API_KEY, GEMINI_API_KEY (values not shown)")
    api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=str(STAGE),
                      commit_message="Deploy Nia backend", delete_patterns=["backend/**", "documents/**", "data/**"])
    sub = f"{user.lower()}-{SPACE_NAME}"
    print("\nUploaded. Hugging Face is now building the image (about 5-10 minutes).")
    print(f"  Space page (build logs): https://huggingface.co/spaces/{repo_id}")
    print(f"  Backend URL:             https://{sub}.hf.space")
    print(f"  Health check:            https://{sub}.hf.space/health")


if __name__ == "__main__":
    main()
