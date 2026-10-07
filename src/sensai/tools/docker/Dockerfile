FROM python:3.12-slim

RUN groupadd --gid 10001 sensai \
    && useradd --uid 10001 --gid sensai \
       --no-create-home --shell /usr/sbin/nologin sensai \
    && mkdir -p /workspace \
    && chown sensai:sensai /workspace

WORKDIR /workspace

USER sensai:sensai

ENTRYPOINT ["python", "-I", "-B", "-u"]

CMD ["--version"]
