#!/usr/bin/env bash
# =============================================================================
# JACKPOT Bootstrap Script
# Creates directories, installs pixi, initializes git repos, sets up submodule
#
# Prerequisites:
#   - uv installed: curl -LsSf https://astral.sh/uv/install.sh | sh
#   - SSH key linked to gotero GitHub account: ssh -T git@github.com
#   - .gitconfig updated per Section 4.1
#   - Four empty repos created on GitHub: jackpot-backend, jackpot-frontend,
#     jackpot-schema, jackpot-iac
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; NC='\033[0m'

info()    { echo -e "${CYAN}[jackpot]${NC} $*"; }
success() { echo -e "${GREEN}[jackpot]${NC} $*"; }
warn()    { echo -e "${YELLOW}[jackpot]${NC} $*"; }
error()   { echo -e "${RED}[jackpot]${NC} $*" >&2; exit 1; }

JACKPOT_BASE="${HOME}/ASU/jackpot"
GITHUB_USER="gotero"

# =============================================================================
# Pre-flight checks
# =============================================================================
info "Pre-flight checks..."
command -v uv  >/dev/null 2>&1 || error "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v git >/dev/null 2>&1 || error "git not found. Install: xcode-select --install"

SSH_OUTPUT=$(ssh -T git@github.com 2>&1 || true)
if echo "$SSH_OUTPUT" | grep -q "Hi ${GITHUB_USER}"; then
    success "SSH authenticated as ${GITHUB_USER}"
else
    warn "SSH check returned: $SSH_OUTPUT"
    warn "Continuing — fix SSH before pushing."
fi
success "uv: $(uv --version)"

# =============================================================================
# Install pixi
# =============================================================================
if command -v pixi >/dev/null 2>&1; then
    success "pixi already installed: $(pixi --version)"
else
    info "Installing pixi..."
    curl -fsSL https://pixi.sh/install.sh | bash
    export PATH="${HOME}/.pixi/bin:${PATH}"
    success "pixi installed: $(pixi --version)"
fi

# =============================================================================
# Create project directory
# =============================================================================
info "Creating ${JACKPOT_BASE}..."
mkdir -p "${JACKPOT_BASE}"

# =============================================================================
# Initialize git repos
# =============================================================================
for REPO in jackpot-backend jackpot-frontend jackpot-schema jackpot-iac; do
    REPO_PATH="${JACKPOT_BASE}/${REPO}"
    if [[ -d "${REPO_PATH}/.git" ]]; then
        success "${REPO}: already initialized"
    else
        info "Initializing ${REPO}..."
        mkdir -p "${REPO_PATH}"
        cd "${REPO_PATH}"
        git init && git checkout -b main
        echo "# ${REPO}" > README.md
        echo "" >> README.md
        echo "Part of the JACKPOT pathogen genomics platform." >> README.md
        git add README.md && git commit -m "chore: initial commit"
        git remote add origin "git@github.com:${GITHUB_USER}/${REPO}.git" 2>/dev/null || true
        success "${REPO}: initialized"
    fi
done

# =============================================================================
# Wire up jackpot-schema submodule in backend and frontend
# =============================================================================
for CONSUMER in jackpot-backend jackpot-frontend; do
    CONSUMER_PATH="${JACKPOT_BASE}/${CONSUMER}"
    if [[ -f "${CONSUMER_PATH}/.gitmodules" ]] && \
       grep -q "jackpot-schema" "${CONSUMER_PATH}/.gitmodules" 2>/dev/null; then
        success "${CONSUMER}: schema submodule already configured"
    else
        info "Adding schema submodule to ${CONSUMER}..."
        cd "${CONSUMER_PATH}"
        git submodule add "git@github.com:${GITHUB_USER}/jackpot-schema.git" schema \
            2>/dev/null || {
            warn "Submodule add failed — jackpot-schema may not be pushed to GitHub yet."
            warn "After pushing jackpot-schema, run from ${CONSUMER_PATH}:"
            warn "  git submodule add git@github.com:${GITHUB_USER}/jackpot-schema.git schema"
        }
        success "${CONSUMER}: schema submodule configured"
    fi
done

# =============================================================================
# uv project for jackpot-backend
# =============================================================================
cd "${JACKPOT_BASE}/jackpot-backend"
if [[ -f "pyproject.toml" ]]; then
    success "jackpot-backend: pyproject.toml exists"
else
    info "Initializing uv project..."
    uv init --name jackpot-backend --python 3.11 --no-workspace
    uv python pin 3.11

    info "Adding production dependencies..."
    uv add \
        "fastapi==0.111.0" "uvicorn[standard]==0.29.0" \
        "sqlalchemy==2.0.30" "alembic==1.13.1" "psycopg2-binary==2.9.9" \
        "boto3==1.34.100" "pydantic==2.7.1" "pydantic-settings==2.2.1" \
        "python-multipart==0.0.9" "python-jose[cryptography]==3.3.0" \
        "httpx==0.27.0" "pandas==2.2.2" "linkml==1.7.4" \
        "linkml-runtime==1.7.2" "streamlit==1.35.0" "requests==2.32.2" \
        "epiweeks==2.1.4" "pyyaml==6.0.1"

    info "Adding dev dependencies..."
    uv add --dev \
        "pytest==8.2.0" "pytest-asyncio==0.23.7" "pytest-cov==5.0.0" \
        "testcontainers==4.5.1" "moto[s3]==5.0.10" "respx==0.21.1" \
        "factory-boy==3.3.0" "hypothesis==6.103.0" "freezegun==1.5.0" \
        "pre-commit==3.7.1" "ruff==0.4.4" "mypy==1.10.0" "detect-secrets==1.4.0"

    success "jackpot-backend: uv dependencies installed"
fi

# =============================================================================
# uv project for jackpot-frontend
# =============================================================================
cd "${JACKPOT_BASE}/jackpot-frontend"
if [[ ! -f "pyproject.toml" ]]; then
    uv init --name jackpot-frontend --python 3.11 --no-workspace
    uv python pin 3.11
    uv add "streamlit==1.35.0" "requests==2.32.2" "pyyaml==6.0.1"
    success "jackpot-frontend: uv dependencies installed"
fi

# =============================================================================
# pixi workspace for bioinformatics tools
# =============================================================================
BIOTOOLS="${JACKPOT_BASE}/jackpot-biotools"
if [[ ! -f "${BIOTOOLS}/pixi.toml" ]]; then
    info "Creating pixi bioinformatics workspace..."
    mkdir -p "${BIOTOOLS}" && cd "${BIOTOOLS}"
    pixi init
    pixi add --channel conda-forge --channel bioconda \
        python nextflow multiqc samtools fastp \
        pangolin nextclade vadr mlst ncbi-amrfinderplus 2>/dev/null || \
        warn "Some pixi packages failed — add manually"
    success "jackpot-biotools: pixi workspace created"
fi

# =============================================================================
# .gitignore for backend
# =============================================================================
GITIGNORE="${JACKPOT_BASE}/jackpot-backend/.gitignore"
if [[ ! -f "${GITIGNORE}" ]]; then
    cat > "${GITIGNORE}" << 'GITIGNORE_EOF'
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.venv/
uv.lock.tmp
.env
.env.local
.env.gcp
.env.*.local
*.secrets
.secrets.baseline.local
.vscode/settings.json
.idea/
backend/models_generated.py
db/bigquery_schema.sql
docs/schema.md
.DS_Store
Thumbs.db
GITIGNORE_EOF
    success ".gitignore created"
fi

# =============================================================================
# Alembic
# =============================================================================
cd "${JACKPOT_BASE}/jackpot-backend"
if [[ ! -d "db/migrations" ]]; then
    mkdir -p db
    uv run alembic init db/migrations
    success "Alembic initialized — edit db/migrations/env.py to reference DATABASE_URL"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  JACKPOT bootstrap complete!                     ${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo "  Next steps:"
echo "  1. Push jackpot-schema to GitHub first (needed for submodule):"
echo "     cd ~/ASU/jackpot/jackpot-schema && git push -u origin main"
echo ""
echo "  2. Push remaining repos:"
echo "     cd ~/ASU/jackpot/jackpot-backend && git push -u origin main"
echo "     cd ~/ASU/jackpot/jackpot-frontend && git push -u origin main"
echo "     cd ~/ASU/jackpot/jackpot-iac && git push -u origin main"
echo ""
echo "  3. Run write_files.py to write all application files:"
echo "     cd ~/ASU/jackpot && python3 write_files.py"
echo ""
echo "  4. Copy jackpot_schema_v4_1.yaml to jackpot-schema/schema/jackpot_schema.yaml"
echo ""
echo "  5. Start local services:"
echo "     cd ~/ASU/jackpot/jackpot-backend && docker compose up -d"
echo "     curl http://localhost:8000/health"
