FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        apt-transport-https \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /usr/share/keyrings/microsoft-prod.gpg >/dev/null \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 \
        build-essential \
        unixodbc \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY templates ./templates

RUN pip install --upgrade pip && pip install --no-cache-dir .

RUN python -c "import pathlib, shutil; from gemba_score import ui; src = pathlib.Path('/app/templates'); dst = ui.templates_dir; \
dst.parent.mkdir(parents=True, exist_ok=True); \
((dst.is_symlink() or dst.is_file()) and dst.unlink(missing_ok=True)); \
(dst.exists() and not dst.is_symlink() and not dst.is_file() and shutil.rmtree(dst)); \
shutil.copytree(src, dst)"

EXPOSE 8000
CMD ["uvicorn", "gemba_score.main:app", "--host", "0.0.0.0", "--port", "8000"]
