FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash \
       ca-certificates \
       git \
       build-essential \
       cmake \
       python3 \
       python3-venv \
       rustc \
       cargo \
    && rm -rf /var/lib/apt/lists/*


RUN groupadd --gid 10001 sensai \
    && useradd --uid 10001 --gid sensai \
       --no-create-home --shell /usr/sbin/nologin sensai \
    && mkdir -p /workspace \
    && chown sensai:sensai /workspace

WORKDIR /workspace

USER sensai:sensai

ENTRYPOINT ["/bin/bash"]

CMD ["--version"]
