FROM --platform=amd64 python:3.11

WORKDIR /app
VOLUME /data
EXPOSE 8080
ENV PREFIX="/enc" \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install -r ./requirements.txt

COPY enc.py ./
COPY example ./data/
CMD waitress-serve --url-prefix=${PREFIX} enc:app
