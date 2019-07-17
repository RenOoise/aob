import json
import sys
import time
from flask import render_template
from rq import get_current_job
from app import create_app, db
from app.models import User, Post, Task, FuelResidue, CfgDbConnection, FuelRealisation, AzsList, Tanks, AzsSystems
from app.email import send_email
import psycopg2
from datetime import datetime
import fdb

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
    _set_task_progress(0)  # начало задания
    azs = AzsList.query.filter_by(active=True).all()  # получаем список активных АЗС
    for i in azs:  # перебираем список азс
        test = CfgDbConnection.query.filter_by(azs_id=i.id).first()
        if test is not None:  # если тестирование соединения успешно
            if test.system_type == 1:  # если БукТС
                azs_config = CfgDbConnection.query.filter_by(system_type=1, azs_id=i.id).first()
                if azs_config:  # если есть конфиг
                    try:
                        connection = psycopg2.connect(user=azs_config.username,
                                                      password=azs_config.password,
                                                      host=azs_config.ip_address,
                                                      database=azs_config.database,
                                                      connect_timeout=10)
                        cursor = connection.cursor()
                        tanks = Tanks.query.filter_by(azs_id=i.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(azs_config.ip_address) + " успешно")
                        for id in tanks:  # перебераем резервуары
                            if id.active:  # если активен, то строим запрос к базе
                                sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                       "FROM pj_tanks WHERE tanknum = "
                                       + str(id.tank_number) +
                                       " ORDER BY optime DESC LIMIT 1;")
                                cursor.execute(sql)
                                print("SQL запрос выполнен")
                                query = cursor.fetchall()
                                for row in query:
                                    azsid = AzsList.query.filter_by(number=row[0]).first()
                                    tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                    add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                    if add:
                                        add.fuel_level = row[3]
                                        add.fuel_volume = row[4]
                                        add.fuel_temperature = row[5]
                                        add.datetime = row[6]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.product_code = row[2]
                                        add.download_time = datetime.now()
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                    else:
                                        add = FuelResidue(shop_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                          fuel_level=row[3], fuel_volume=row[4],
                                                          fuel_temperature=row[5], datetime=row[6],
                                                          download_time=datetime.now())
                                        db.session.add(add)
                                        db.session.commit()
                    except(Exception, psycopg2.Error) as error:
                        print("Ошибка во время получения данных", error)
                        pass
                    finally:
                        if (connection):
                            cursor.close()
                            connection.close()
                            print("Соединение закрыто")
                            _set_task_progress(100)
            elif test.system_type == 2:  # oilix
                azs_config = CfgDbConnection.query.filter_by(system_type=2, azs_id=i.id).first()
                azs_list = AzsList.query.filter_by(id=i.id).first()
                if azs_config:  # если есть конфиг
                    try:
                        connection = psycopg2.connect(user=azs_config.username,
                                                      password=azs_config.password,
                                                      host=azs_config.ip_address,
                                                      database=azs_config.database,
                                                      connect_timeout=10)
                        cursor = connection.cursor()
                        tanks = Tanks.query.filter_by(azs_id=i.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(
                            azs_config.ip_address) + " успешно")
                        for id in tanks:  # перебераем резервуары
                            if id.active:  # если активен, то строим запрос к базе

                                sql = ("SELECT id, calculatedvolume, comment, density, incomeactive, "
                                       "insideincomefillinglitres, level, lmsvolume, stamp, tank, temperature, "
                                       "version, volume, water "
                                       "FROM tanklmsinfo WHERE id Like " + "knp-azs" + str(azs_list.number) + "_%" + " AND tank="
                                       + str(id.tank_number) + " order by stamp desc limit 1")
                                cursor.execute(sql)
                                print("SQL запрос выполнен")
                                query = cursor.fetchall()
                                for row in query:
                                    azsid = AzsList.query.filter_by(number=row[0]).first()
                                    tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                    add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                    if add:
                                        add.fuel_level = row[3]
                                        add.fuel_volume = row[4]
                                        add.fuel_temperature = row[5]
                                        add.datetime = row[6]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.product_code = row[2]
                                        add.download_time = datetime.now()
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                    else:
                                        add = FuelResidue(shop_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                          fuel_level=row[3], fuel_volume=row[4],
                                                          fuel_temperature=row[5], datetime=row[6],
                                                          download_time=datetime.now())
                                        db.session.add(add)
                                        db.session.commit()
                    except(Exception, psycopg2.Error) as error:
                        print("Ошибка во время получения данных", error)
                        pass

                    finally:
                        if (connection):
                            cursor.close()
                            connection.close()
                            print("Соединение закрыто")
                            _set_task_progress(100)

            elif test.system_type == 3:  # serviopump
                azs_config = CfgDbConnection.query.filter_by(system_type=3, azs_id=i.id).first()
                if azs_config:  # если есть конфиг
                    try:
                        connection = fdb.connect(
                            dsn=azs_config.ip_address+':'+azs_config.database,
                            user=azs_config.username,
                            password=azs_config.password)

                        cursor = connection.cursor()
                        tanks = Tanks.query.filter_by(azs_id=i.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(
                            azs_config.ip_address) + " успешно")
                        for id in tanks:  # перебераем резервуары
                            if id.active:  # если активен, то строим запрос к базе
                                sql = ("SELECT FIRST 1 id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                       "FROM pj_tanks WHERE tanknum = "
                                       + str(id.tank_number) +
                                       " ORDER BY optime DESC;")
                                cursor.execute(sql)
                                print("SQL запрос выполнен")
                                query = cursor.fetchall()
                                for row in query:
                                    azsid = AzsList.query.filter_by(number=row[0]).first()
                                    tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                    add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                    if add:
                                        add.fuel_level = row[3]
                                        add.fuel_volume = row[4]
                                        add.fuel_temperature = row[5]
                                        add.datetime = row[6]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.product_code = row[2]
                                        add.download_time = datetime.now()
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                    else:
                                        add = FuelResidue(shop_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                          fuel_level=row[3], fuel_volume=row[4],
                                                          fuel_temperature=row[5], datetime=row[6],
                                                          download_time=datetime.now())
                                        db.session.add(add)
                                        db.session.commit()
                    except Exception as error:
                        pass
                        print("Ошибка во время получения данных", error)
