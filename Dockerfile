# Dissonance – small image: Python + Waitress (pure-Python web server, pinned with its hash).
FROM python:3.13.18-alpine3.23

# tzdata: TZ=Europe/Berlin etc. (used for the timestamps of deleted songs)
RUN apk add --no-cache tzdata \
 && adduser -D -H -u 1000 dissonance \
 && mkdir /songs && chown dissonance /songs

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-deps --only-binary=:all: --require-hashes -r requirements.txt \
 && rm requirements.txt
COPY VERSION app.py auth.py i18n.py ug2chordpro.py index.html sw.js manifest.webmanifest \
     icon.svg icon-192.png icon-512.png icon-maskable-512.png apple-touch-icon.png nosleep.mp4 nosleep.webm chords.json ./

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SONG_DIR=/songs PORT=8080
USER dissonance
VOLUME /songs
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python", "-I", "app.py"]
