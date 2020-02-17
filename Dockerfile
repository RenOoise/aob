FROM python:3-onbuild

RUN useradd -ms /bin/bash aob

WORKDIR /home/aob

RUN python -m venv venv
RUN apt-get update && apt-get install -y \
postgresql-server-dev*

RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn pymysql

COPY app app
COPY migrations migrations
COPY aob.py config.py boot.sh ./
RUN chmod a+x boot.sh

ENV FLASK_APP aob.py

RUN chown -R aob:aob ./
USER aob

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
