# The base image is the one Speakr's own Dockerfile pins, by digest.
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce AS base

WORKDIR /app

# Every package at an exact version and hash; see scripts/lock-requirements.sh.
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.lock

COPY src src
ENV PYTHONPATH=/app/src

###############################################################################
# test: the suite, used by tests/e2e/docker-compose.yml and CI
###############################################################################
FROM base AS test

RUN pip install --no-cache-dir pytest==8.4.2
COPY pyproject.toml ./
COPY tests tests
CMD ["pytest", "tests", "-q", "-rs"]

###############################################################################
# runtime: speaks MCP on stdin and stdout, so run it with `docker run -i`
###############################################################################
FROM base AS runtime

RUN useradd --create-home --uid 1000 speakr
USER speakr

ENTRYPOINT ["python", "-m", "speakr_mcp"]
