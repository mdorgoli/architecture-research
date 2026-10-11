"""Build-independent smoke check; accepts a locally available image tag."""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request


def run(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "expense-api:ci"
    name = "expense-smoke-" + secrets.token_hex(6)
    environment = dict(os.environ, JWT_SECRET=secrets.token_hex(32))
    started = False
    try:
        subprocess.run([
            "docker", "run", "-d", "--name", name, "--read-only",
            "--tmpfs", "/data:uid=10001,gid=10001", "--tmpfs", "/tmp",
            "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            "-p", "127.0.0.1::8000", "-e", "JWT_SECRET", image,
            "sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --no-proxy-headers",
        ], env=environment, check=True, stdout=subprocess.DEVNULL)
        started = True
        port = run("port", name, "8000/tcp").rsplit(":", 1)[1]
        base = "http://127.0.0.1:" + port
        for attempt in range(60):
            try:
                with urllib.request.urlopen(base + "/health", timeout=2) as response:
                    assert json.load(response) == {"status": "ok"}
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(1)
        else:
            raise RuntimeError("Container did not become ready")
        with urllib.request.urlopen(base + "/welcome?lang=fa", timeout=3) as response:
            assert response.headers["Content-Language"] == "fa"
            assert json.load(response)["message"] == "به سامانهٔ مدیریت هزینه‌ها خوش آمدید."
        assert run("exec", name, "id", "-u") == "10001"
        check = "import importlib.util,pathlib; assert importlib.util.find_spec('polib') is None; assert importlib.util.find_spec('httpx') is None; assert not pathlib.Path('/app/.git').exists(); assert not pathlib.Path('/app/test_auth.py').exists()"
        run("exec", name, "python", "-c", check)
        run("exec", name, "python", "-m", "alembic", "check")
        print("Container smoke passed: migrations, health, Persian MO, non-root and runtime isolation.")
    finally:
        if started:
            subprocess.run(["docker", "rm", "-f", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
