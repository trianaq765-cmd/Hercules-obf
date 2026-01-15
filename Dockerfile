FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install dependencies + build tools for Lua 5.4
RUN apt-get update && apt-get install -y \
    build-essential \
    libreadline-dev \
    wget \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Lua 5.4 from source
WORKDIR /tmp
RUN wget https://www.lua.org/ftp/lua-5.4.6.tar.gz && \
    tar zxf lua-5.4.6.tar.gz && \
    cd lua-5.4.6 && \
    make all test && \
    make install && \
    cd .. && \
    rm -rf lua-5.4.6 lua-5.4.6.tar.gz

# Verify Lua version
RUN lua -v

WORKDIR /app

# Clone Hercules Obfuscator
RUN git clone https://github.com/zeusssz/hercules-obfuscator.git /app/hercules

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py .
COPY server.py .
COPY bot.py .
COPY start.sh .

# Create directories
RUN mkdir -p /app/uploads /app/outputs /app/logs

# Make start script executable
RUN chmod +x start.sh

EXPOSE 10000

CMD ["./start.sh"]
EXPOSE 10000

CMD ["./start.sh"]
