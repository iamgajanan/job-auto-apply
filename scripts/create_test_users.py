#!/usr/bin/env python3
"""
Create 5 dummy test users — one per plan — for manual testing.

Each user is created via the signup API, then an admin grants them
the appropriate plan quota via the admin API.

Usage:
    python scripts/create_test_users.py --api http://127.0.0.1:8004 \
        --admin-email iamgajanan12@gmail.com \
        --admin-password <your-password>

The script prints a summary table at the end with each user's
credentials and current quota, so you can test each plan manually.

IMPORTANT: These are TEST users only. Do not use real passwords here.
"""

import argparse
import json
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Test user definitions — one per plan
# ---------------------------------------------------------------------------
TEST_USERS = [
    {
        "plan_code": "free",
        "plan_name": "Free (50 searches)",
        "email": "test.free@jobauto.internal",
        "password": "TestFree123!",
        "full_name": "Test User Free",
    },
    {
        "plan_code": "starter",
        "plan_name": "Starter (100 searches)",
        "email": "test.starter@jobauto.internal",
        "password": "TestStarter123!",
        "full_name": "Test User Starter",
    },
    {
        "plan_code": "growth",
        "plan_name": "Growth (500 searches)",
        "email": "test.growth@jobauto.internal",
        "password": "TestGrowth123!",
        "full_name": "Test User Growth",
    },
    {
        "plan_code": "pro",
        "plan_name": "Pro (1000 searches)",
        "email": "test.pro@jobauto.internal",
        "password": "TestPro123!",
        "full_name": "Test User Pro",
    },
    {
        "plan_code": "business",
        "plan_name": "Business (2000 searches)",
        "email": "test.business@jobauto.internal",
        "password": "TestBusiness123!",
        "full_name": "Test User Business",
    },
]

# Quota to grant per plan (must match plans table).
PLAN_QUOTA = {
    "free": 50,
    "starter": 100,
    "growth": 500,
    "pro": 1000,
    "business": 2000,
}


def api(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    return response


def login(base_url: str, email: str, password: str) -> str:
    """Login and return access token."""
    with httpx.Client(base_url=base_url, timeout=30) as client:
        resp = api(client, "POST", "/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"  ❌ Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    token = resp.json().get("session", {}).get("access_token", "")
    if not token:
        print(f"  ❌ No access token in login response: {resp.json()}")
        sys.exit(1)
    return token


def signup_user(base_url: str, user: dict) -> tuple[str | None, str | None]:
    """
    Sign up a user. Returns (user_id, access_token).
    access_token may be None if email confirmation is required.
    """
    with httpx.Client(base_url=base_url, timeout=30) as client:
        resp = api(
            client,
            "POST",
            "/api/v1/auth/signup",
            json={
                "email": user["email"],
                "password": user["password"],
                "full_name": user["full_name"],
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        user_id = data.get("user", {}).get("id")
        token = (data.get("session") or {}).get("access_token")
        return user_id, token

    if resp.status_code == 429:
        print(f"  ⚠️  Supabase email rate limit (429) — waiting 60s before retrying...")
        time.sleep(60)
        return signup_user(base_url, user)

    if resp.status_code == 422:
        # User may already exist — try to extract profile via login.
        print(f"  ℹ️  Signup returned 422 — user may already exist. Trying login...")
        return None, None

    print(f"  ❌ Signup failed ({resp.status_code}): {resp.text}")
    return None, None


def get_user_id_via_admin(base_url: str, admin_token: str, email: str) -> str | None:
    """Find a user's ID from the admin users list by email."""
    with httpx.Client(base_url=base_url, timeout=30) as client:
        resp = api(
            client,
            "GET",
            "/api/v1/admin/users?limit=500",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    if resp.status_code != 200:
        print(f"  ❌ Admin users list failed ({resp.status_code}): {resp.text}")
        return None
    users = resp.json().get("users", [])
    for u in users:
        if (u.get("email") or "").lower() == email.lower():
            return str(u["id"])
    return None


def grant_quota(base_url: str, admin_token: str, user_id: str, plan_code: str, searches: int) -> bool:
    """Grant quota to a user via admin endpoint."""
    with httpx.Client(base_url=base_url, timeout=30) as client:
        resp = api(
            client,
            "POST",
            f"/api/v1/admin/users/{user_id}/quota",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"searches": searches, "plan_code": plan_code},
        )
    if resp.status_code == 200:
        return True
    print(f"  ❌ Grant quota failed ({resp.status_code}): {resp.text}")
    return False


def verify_account(base_url: str, email: str, password: str, expected_plan: str, expected_searches: int) -> bool:
    """Login as user and verify their plan and quota."""
    try:
        token = login(base_url, email, password)
    except SystemExit:
        print(f"  ❌ Could not login as {email}")
        return False

    with httpx.Client(base_url=base_url, timeout=30) as client:
        resp = api(
            client,
            "GET",
            "/api/v1/account/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code != 200:
        print(f"  ❌ account/me failed ({resp.status_code}): {resp.text}")
        return False

    data = resp.json()
    usage = data.get("usage", {})
    remaining = usage.get("remaining_searches", 0)
    plan = usage.get("plan_code", "?")

    # For non-free plans the free allocation also exists — we just check
    # remaining is at least what the plan grants (may be higher from stacking).
    ok = remaining >= expected_searches
    status = "✅" if ok else "❌"
    print(f"  {status} {email} | plan={plan} | remaining={remaining} (expected ≥{expected_searches})")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Create test users for each plan.")
    parser.add_argument("--api", default="http://127.0.0.1:8004", help="Backend base URL")
    parser.add_argument("--admin-email", required=True, help="Super admin email")
    parser.add_argument("--admin-password", required=True, help="Super admin password")
    args = parser.parse_args()

    base_url = args.api.rstrip("/")
    print(f"\n🚀 Creating test users against {base_url}\n")

    # Login as admin first.
    print("📋 Logging in as admin...")
    admin_token = login(base_url, args.admin_email, args.admin_password)
    print(f"  ✅ Admin logged in\n")

    results = []

    for user in TEST_USERS:
        plan_code = user["plan_code"]
        print(f"👤 Setting up [{plan_code.upper()}] {user['email']}")

        # 1. Sign up (or detect existing).
        user_id, _token = signup_user(base_url, user)

        if not user_id:
            # Try to find via admin list (user already exists).
            user_id = get_user_id_via_admin(base_url, admin_token, user["email"])
            if not user_id:
                print(f"  ❌ Could not find or create user {user['email']}")
                results.append({"user": user, "ok": False, "reason": "not found"})
                continue
            print(f"  ℹ️  Found existing user: {user_id}")
        else:
            print(f"  ✅ Created user: {user_id}")

        # 2. Grant plan quota via admin (skip for free — already granted on signup).
        if plan_code != "free":
            searches = PLAN_QUOTA[plan_code]
            ok = grant_quota(base_url, admin_token, user_id, plan_code, searches)
            if ok:
                print(f"  ✅ Granted {searches} searches ({plan_code})")
            else:
                results.append({"user": user, "ok": False, "reason": "quota grant failed"})
                continue

        # 3. Verify by logging in as the user and checking account/me.
        print(f"  🔍 Verifying account...")
        expected = PLAN_QUOTA[plan_code]
        ok = verify_account(base_url, user["email"], user["password"], plan_code, expected)
        results.append({"user": user, "ok": ok, "user_id": user_id})
        print()

    # Summary table.
    print("\n" + "=" * 70)
    print("TEST USER SUMMARY")
    print("=" * 70)
    print(f"{'Plan':<12} {'Email':<38} {'Status'}")
    print("-" * 70)
    all_ok = True
    for r in results:
        u = r["user"]
        ok = r.get("ok", False)
        if not ok:
            all_ok = False
        icon = "✅" if ok else "❌"
        print(f"{u['plan_code']:<12} {u['email']:<38} {icon}")

    print()
    print("Credentials for manual testing:")
    print("-" * 70)
    for u in TEST_USERS:
        print(f"  {u['plan_code']:<10}  {u['email']}  /  {u['password']}")

    print()
    if all_ok:
        print("✅ ALL TEST USERS READY")
    else:
        print("❌ SOME USERS FAILED — check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
