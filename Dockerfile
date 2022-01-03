FROM python:3.8.1-alpine

RUN addgroup -S aob && adduser -S aob -G aob

WORKDIR /home/aob

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN apk update \
    && apk add postgresql-dev gcc python3-dev musl-dev g++
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn

COPY app app
COPY migrations migrations
COPY aob.py config.py boot.sh ./
COPY .env .env
COPY background_downloading.py background_downloading.py
COPY download_realisation_stats.py download_realisation_stats.py
RUN chmod +x boot.sh

ENV FLASK_APP aob.py

RUN chown -R aob:aob ./
USER aob

EXPOSE 5000
ENTRYPOINT ["sh", "./boot.sh"]