# Coesita Benchmark — production image
#
# Build:  docker build -t coesita .
# Run:    docker run -p 5050:5050 -v coesita-data:/data coesita
# Open:   http://localhost:5050/benchmark

FROM python:3.11-slim

WORKDIR /app

# Install the package (no build deps needed: pure-Python, 2 runtime deps)
COPY pyproject.toml README.md LICENSE.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# All benchmark artifacts and decision logs live in /data (mount a volume)
ENV COESITA_LOG_DIR=/data
VOLUME /data

EXPOSE 5050

# Drop privileges
RUN useradd -m coesita && chown coesita /data
USER coesita

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/benchmark/status')"

CMD ["coesita", "dashboard", "--port", "5050"]
