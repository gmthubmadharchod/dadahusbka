FROM sailvessel/ubuntu:latest

WORKDIR /app

COPY . .

RUN apt-get update && \
    apt-get install --no-install-recommends -y --fix-missing \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    ffmpeg \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

# appxdl binary
COPY appxdl /usr/local/bin/appxdl
RUN chmod +x /usr/local/bin/appxdl

# python venv
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r master.txt && \
    /venv/bin/pip install yt-dlp

ENV PATH="/usr/local/bin:/venv/bin:$PATH"

# Upload JSON to MongoDB then start bot
CMD python upload_appxapis.py && python main.py
