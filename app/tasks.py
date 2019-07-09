import json
import sys
import time
from flask import render_template
from rq import get_current_job
from app import create_app, db
from app.models import User, Post, Task, FuelResidue, CfgDbConnection, FuelRealisation, AzsList
from app.email import send_email
import psycopg2

app = create_app()
app.app_context().push()


def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = Task.query.get(job.get_id())
        task.user.add_notification('task_progress', {'task_id': job.get_id(),
                                                     'progress': progress})
        if progress >= 100:
            task.complete = True
        db.session.commit()


def export_posts(user_id):
    try:
        user = User.query.get(user_id)
        _set_task_progress(0)
        data = []
        i = 0
        total_posts = user.posts.count()
        for post in user.posts.order_by(Post.timestamp.asc()):
            data.append({'body': post.body,
                         'timestamp': post.timestamp.isoformat() + 'Z'})
            time.sleep(5)
            i += 1
            _set_task_progress(100 * i // total_posts)

        send_email('[Microblog] Your blog posts',
                sender=app.config['ADMINS'][0], recipients=[user.email],
                text_body=render_template('email/export_posts.txt', user=user),
                html_body=render_template('email/export_posts.html',
                                          user=user),
                attachments=[('posts.json', 'application/json',
                              json.dumps({'posts': data}, indent=4))],
                sync=True)
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def download_tanks_info(user_id):
    azs_list = AzsList.query.filter_by(active=True).all()

    for i in azs_list:
        config = CfgDbConnection.query.filter_by(azs_id=i.id).first()
        user = "db_report"
        password = "db_report"
        host = config.ip_address
        port = config.port
        database = "ubuk"
        _set_task_progress(0)
        try:
            connection = psycopg2.connect(user=user,
                                          password=password,
                                          host=host,
                                          port=port,
                                          database=database)
            cursor = connection.cursor()
            print("Подключение к базе " + database + " на сервере " + host + " успешно")
            sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime FROM pj_tanks WHERE optime > now() - interval '1 days';")
            cursor.execute(sql)
            print("SQL запрос выполнен")
            query = cursor.fetchall()
            for row in query:
                add = FuelRealisation(shop_id=row[0], tank_id=row[1], product_code=row[2], fuel_level=row[3],
                                      fuel_volume=row[4],fuel_temperature=row[5], datetime=row[6])
                db.session.add(add)
                db.session.commit()

        except(Exception, psycopg2.Error) as error:
            print("Ошибка во время получения данных", error)

        finally:
            if (connection):
                cursor.close()
                connection.close()
                print("Соединение закрыто")
                _set_task_progress(100)
