"""Sequential example client. TLS certificate verification remains enabled."""
import argparse
import getpass

import httpx


class SessionClient:
    def __init__(self, client, origin):
        self.client = client
        self.origin = origin

    def _send(self, method, path, **kwargs):
        headers = {"Origin": self.origin}
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self.client.cookies.get("__Host-csrf", "")
        return self.client.request(method, path, headers=headers, **kwargs)

    def login(self, username, password):
        self.client.get("/auth/csrf").raise_for_status()
        response = self._send("POST", "/auth/login", json={"username": username, "password": password})
        response.raise_for_status()

    def request(self, method, path, **kwargs):
        response = self._send(method, path, **kwargs)
        if (response.status_code == 401 and response.json().get("detail") in
                {"token_expired", "authentication_required"}):
            renewal = self._send("POST", "/auth/refresh")
            renewal.raise_for_status()
            response = self._send(method, path, **kwargs)  # One retry only.
        response.raise_for_status()
        return response

    def logout(self):
        self._send("POST", "/auth/logout").raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    origin = "https://localhost:8443"
    with httpx.Client(base_url=origin) as client:
        api = SessionClient(client, origin)
        api.login(args.username, getpass.getpass("Password: "))
        print(api.request("GET", "/expenses").json())
        api.logout()
