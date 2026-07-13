FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY pneural_context/ pneural_context/

RUN pip install --no-cache-dir .

EXPOSE 8777

CMD ["pneural-context", "serve"]