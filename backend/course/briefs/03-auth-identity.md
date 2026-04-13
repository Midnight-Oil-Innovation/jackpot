# Module 3: Auth & Identity

### Teaching Arc
- **Metaphor:** A secure research building with a key card system. Google is the government ID office (they verify who you are). The domain whitelist is the building's approved-organizations list. Your JWT is the key card you get after passing both checks. Your role (Lab Director vs. Lab Reader) determines which rooms you can enter.
- **Opening hook:** "When you click 'Sign in with Google,' JACKPOT doesn't trust Google alone — it runs your email through two more checks before letting you in."
- **Key insight:** Authentication (who are you?) and authorization (what can you do?) are separate problems solved by separate pieces of code. Google handles the first; JACKPOT's permission system handles the second.
- **"Why should I care?":** When a researcher says "I can't access this lab's data," you need to know whether the issue is authentication (they're not logged in), domain whitelist (their institution isn't approved), or authorization (they're in the wrong role). Three different fixes for what looks like one problem.

### Code Snippets (pre-extracted)

**File: backend/routers/auth.py (lines 16-48) — the full login flow:**
```python
@router.post("/google/login")
async def google_login(code: str, request: Request, response: Response) -> dict:
    """Exchange Google auth code for JWT cookies."""
    redirect_uri = settings.google_oauth_redirect_url
    user_info = await exchange_google_code(code, redirect_uri)
    email = user_info["email"]

    if not check_domain_whitelist(email):
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{email.split('@')[1]}' is not authorised. "
            "Contact a Platform Admin.",
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Account not found. A Platform Admin must create your "
            "account before you can log in.",
        )

    access_token = issue_access_token(user["id"], email)
    refresh_token = issue_refresh_token(user["id"], email)

    response.set_cookie(
        "access", access_token, httponly=True, secure=True, samesite="lax", max_age=900
    )
    response.set_cookie(
        "refresh", refresh_token, httponly=True, secure=True, samesite="lax", max_age=604800
    )

    return {"email": email, "name": user.get("name", "")}
```

**File: backend/auth/oauth.py (lines 35-46) — JWT minting:**
```python
def issue_access_token(user_id: int, email: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + ACCESS_TOKEN_TTL,
            "type": "access",
        },
        settings.secret_key,
        algorithm="HS256",
    )
```

**File: backend/auth/guards.py (lines 61-86) — permission checks:**
```python
def require_platform_admin(current_user: dict) -> None:
    if not current_user.get("is_platform_admin"):
        raise HTTPException(status_code=403, detail="Platform Admin required.")

def require_lab_director(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    m = get_user_lab_membership(current_user["id"], lab_id)
    if not m or not m.get("is_lab_director"):
        raise HTTPException(status_code=403, detail="Lab Director required.")

def require_lab_access(current_user: dict, lab_id: int) -> None:
    if current_user.get("is_platform_admin"):
        return
    if get_user_lab_membership(current_user["id"], lab_id):
        return
    rows = execute_query(
        "SELECT 1 FROM project_membership pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.user_id = :uid AND p.lab_id = :lid LIMIT 1",
        {"uid": current_user["id"], "lid": lab_id},
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Lab access required.")
```

**File: backend/auth/guards.py (lines 8-27) — local dev bypass:**
```python
def get_current_user(request: Request) -> dict:
    settings = get_settings()
    if settings.env == "local":
        rows = execute_query(
            "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
            {"e": settings.mock_user_email},
        )
        return (
            rows[0]
            if rows
            else {
                "id": 1,
                "email": settings.mock_user_email,
                "name": "Dev User",
                "is_platform_admin": True,
            }
        )
    token = request.cookies.get("access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
```

**File: backend/permissions.py (full file):**
```python
class PermissionGroups(str, Enum):
    """APGAP-identical role names. DO NOT rename."""
    PLATFORM_ADMIN = "Platform Admin"
    LAB_DIRECTOR = "Lab Director"
    LAB_COLLABORATOR = "Lab Collaborator"
    LAB_READER = "Lab Reader"
    BIOINFORMATICS_USER = "Bioinformatics User"
    DATA_ANALYST = "Data Analyst"
```

### Interactive Elements

- [x] **Code↔English translation** — auth.py google_login: walk through every line of the 3-gate login flow
- [x] **Code↔English translation** — guards.py require_lab_access: show the "Platform Admin bypasses everything" pattern
- [x] **Data flow animation** — actors: Browser, Google OAuth, JACKPOT API, Domain Whitelist DB, Users DB. Steps: (1) User clicks "Sign in with Google" → (2) Browser redirects to Google → (3) Google sends back a code → (4) API exchanges code with Google for email → (5) API checks domain whitelist → (6) API looks up user in DB → (7) API mints JWT → (8) JWT set as httpOnly cookie → (9) Browser stores cookie automatically
- [x] **Group chat** — actors: New Researcher, JACKPOT API, Domain Whitelist, Platform Admin. Scenario: new researcher tries to log in with a university email not yet whitelisted. Gets error. Contacts Platform Admin. Admin adds domain. Researcher logs in successfully.
- [x] **Quiz** — 3 questions:
  1. "A researcher from a new partner university can't log in, even though their Google account is valid. What's the most likely cause?" (domain not in whitelist)
  2. "An access token expires in 15 minutes. Why so short?" (short-lived tokens limit damage if stolen — the refresh token is the long-lived credential, stored separately)
  3. "A Platform Admin can access any lab's data without being a lab member. Where in the code does this happen?" (require_lab_access guard: `if current_user.get("is_platform_admin"): return`)
- [x] **Glossary tooltips** — OAuth, JWT, access token, refresh token, httpOnly cookie, 401 vs 403, domain whitelist, role-based access control, HS256, "sub" claim

### Reference Files to Read
- `references/interactive-elements.md` → "Group Chat Animation", "Message Flow / Data Flow Animation", "Code ↔ English Translation Blocks", "Multiple-Choice Quizzes", "Glossary Tooltips"
- `references/content-philosophy.md` → full file
- `references/gotchas.md` → full file

### Connections
- **Previous module:** "The API Blueprint" — showed how FastAPI organizes 20 routers; this module digs into the auth router specifically
- **Next module:** "The Ingest Engine" — shows what happens after a user is authenticated and uploads data
- **Tone/style notes:** Accent vermillion (#D94F30). Module 3 uses --color-bg (#FAF7F2). ACCESS_TOKEN_TTL = 15 minutes, REFRESH_TOKEN_TTL = 7 days.
