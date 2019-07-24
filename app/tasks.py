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


def download_tanks_info():
    _set_task_progress(0)  # начало задания

    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    azs_count = AzsList.query.filter_by(active=True).count()  # получаем количество активных АЗС
    total_queries = int(azs_count)
    queries = 0
    try:
        for i in azs:  # перебираем список азс
            queries += 1
            _set_task_progress(100 * queries // total_queries)
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
                            print("Подключение к базе " + str(azs_config.database) + " на сервере " +
                                  str(azs_config.ip_address) + " успешно")
                            for id in tanks:  # перебераем резервуары
                                if id.active and id.ams:  # если активен и есть система автоматического измерения,
                                    # то строим запрос к базе
                                    sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                           "FROM pj_tanks WHERE tanknum = "
                                           + str(id.tank_number) +
                                           " ORDER BY optime DESC LIMIT 1;")
                                    cursor.execute(sql)

                                    print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(azs_config.ip_address) + " выполнен")
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
                                elif id.active and not id.ams:
                                    # если резервуар активен, но системы измерения нет, то получаем остаток
                                    sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                           "FROM pj_tanks WHERE tanknum = "
                                           + str(id.tank_number) +
                                           " ORDER BY optime DESC LIMIT 1;")
                                    cursor.execute(sql)
                                    print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(azs_config.ip_address) + " выполнен")
                                    query = cursor.fetchall()

                                    # и делаем выборку по реализации с начала смены
                                    realisation = ("SELECT pj_td.id_shop, pj_td.product, pj_td.tank, sum(pj_td.volume) as volume "
                                            "FROM pj_td, sj_tranz WHERE pj_td.id_shop=" + str(i.number) + " and pj_td.tank="
                                            + str(id.tank_number) +
                                            "and pj_td.begtime between current_TIMESTAMP - interval '1 day' "
                                            "and current_TIMESTAMP and (pj_td.err=0 or pj_td.err=2) "
                                            "and sj_tranz.id_shop=pj_td.id_shop "
                                            "and pj_td.trannum=sj_tranz.trannum "
                                            "and sj_tranz.shift=(select max(num) from sj_shifts where id_shop=" + str(i.number) +
                                            "and begtime between current_TIMESTAMP - interval '2 day' "
                                            "and current_TIMESTAMP ) GROUP BY pj_td.id_shop, pj_td.product, pj_td.tank")

                                    cursor.execute(realisation)
                                    realisation = cursor.fetchall()
                                    print(query[0][4]-realisation[0][3])

                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=row[0]).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                        add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            add.fuel_level = row[3]
                                            add.fuel_volume = query[0][4]-realisation[0][3]
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
                                                              fuel_level=row[3], fuel_volume=query[0][4]-realisation[0][3],
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

                # если система oilix
                elif test.system_type == 2:
                    # дергаем конфиги для подключения к БД на АЗС
                    azs_config = CfgDbConnection.query.filter_by(system_type=2, azs_id=i.id).first()
                    # дергаем список АЗС с фильтром по айдишнику
                    azs_list = AzsList.query.filter_by(id=i.id).first()

                    # если есть конфиг для данной азс
                    if azs_config:
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
                                           "insideincomefillinglitres, level, lmsvolume, stamp, tank, temperature, volume, "
                                           "water "
                                           "FROM tanklmsinfo WHERE tank="
                                           + str(id.tank_number) +
                                           " ORDER BY stamp desc limit 1")

                                    cursor.execute(sql)
                                    print("SQL запрос выполнен")
                                    query = cursor.fetchall()
                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=i.number).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=id.tank_number).first()
                                        add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            add.fuel_level = row[6]
                                            add.fuel_volume = row[7]
                                            add.fuel_temperature = row[10]
                                            add.datetime = row[8]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            add.product_code = id.fuel_type
                                            add.download_time = datetime.now()
                                            db.session.add(add)
                                            try:
                                                db.session.commit()
                                            except Exception as error:
                                                print("Данные по АЗС № " + str(azsid.id) + " не найдены", error)
                                        else:
                                            add = FuelResidue(shop_id=azsid.id, tank_id=tankid.id,
                                                              product_code=id.fuel_type, fuel_level=row[6],
                                                              fuel_volume=row[7], fuel_temperature=row[10],
                                                              datetime=row[8], download_time=datetime.now())
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

                # если система serviopump
                elif test.system_type == 3:
                    print("SERVIOPUMP!!!!!!!!!!!!!!!!!!!!!")
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
                                    sql = "select td.fuel as prodcod,td.tank as tanknum,td.datetime " \
                                          "as optime,td.fuelvolume as ost,3 " \
                                          "as typ,tnk.volume_l - tnk.minost_l - td.fuelvolume as svob " \
                                          "from tankdata td, tanks tnk, (select tank, max(datetime) as datetime " \
                                          "from tankdata group by tank) tdm where td.tank = tdm.tank " \
                                          "and td.datetime = tdm.datetime and tnk.num = td.tank and td.tank=" \
                                          + str(id.tank_number)
                                    cursor.execute(sql)
                                    print("SQL запрос выполнен")
                                    query = cursor.fetchall()
                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=i.number).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=id.tank_number).first()
                                        add = FuelResidue.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            # add.fuel_level =
                                            add.fuel_volume = row[3]
                                            # add.fuel_temperature = row[5]
                                            add.datetime = row[2]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            if row[0] is 1:
                                                add.product_code = 95
                                            elif row[0] is 2:
                                                add.product_code = 92
                                            elif row[0] is 3:
                                                add.product_code = 50
                                            elif row[0] is 4:
                                                add.product_code = 51
                                            add.download_time = datetime.now()
                                            db.session.add(add)
                                            try:
                                                db.session.commit()
                                            except Exception as error:
                                                print("Данные по АЗС № " + str(azsid.number) + " не найдены", error)
                                        else:
                                            product_code = 0
                                            if row[0] is 1:
                                                product_code = 95
                                            elif row[0] is 2:
                                                product_code = 92
                                            elif row[0] is 3:
                                                product_code = 50
                                            elif row[0] is 4:
                                                product_code = 51
                                            add = FuelResidue(shop_id=azsid.id, tank_id=tankid.id, product_code=product_code,
                                                              fuel_level=0, fuel_volume=row[3],
                                                              fuel_temperature=0, datetime=row[2],
                                                              download_time=datetime.now())
                                            db.session.add(add)
                                            db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def download_realisation_info(user_id):
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС

    try:
        _set_task_progress(100)
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
                            print("Подключение к базе " + str(azs_config.database) + " на сервере " +
                                  str(azs_config.ip_address) + " успешно")
                            sql_10_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                          "WHERE id_shop = " + str(i.number) + " and begtime between current_TIMESTAMP - " \
                                                                         "interval '10 day' and current_TIMESTAMP " \
                                                                         "and (err=0 or err=2) " \
                                                                         "GROUP BY id_shop, product, tank ORDER BY tank"
                            cursor.execute(sql_10_days)
                            query = cursor.fetchall()
                            print(query)

                            for row in query:
                                azsid = AzsList.query.filter_by(number=row[0]).first()
                                print("1")
                                tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[2]).first()
                                print("11")
                                add = FuelRealisation.query.filter_by(shop_id=azsid.id, tank_id=tankid.id).first()
                                print("122")
                                if add:
                                    add.fuel_realisation_10_days = row[3]
                                    add.shop_id = azsid.id
                                    add.tank_id = tankid.id
                                    add.product_code = row[1]
                                    add.download_time = datetime.now()
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                else:
                                    add = FuelRealisation(shop_id=azsid.id, tank_id=tankid.id, product_code=row[1],
                                                          fuel_realisation_10_days=row[3], download_time=datetime.now())
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
                elif test.system_type == "2":
                    print("Oilix")
                elif test.system_type == "3":
                    print("ServioPump")
                    azs_config = CfgDbConnection.query.filter_by(system_type=3, azs_id=i.id).first()
                    if azs_config:  # если есть конфиг
                        try:
                            connection = fdb.connect(
                                dsn=azs_config.ip_address + ':' + azs_config.database,
                                user=azs_config.username,
                                password=azs_config.password)

                            cursor = connection.cursor()
                            tanks = Tanks.query.filter_by(azs_id=i.id, active=True).all()  # получаем список резервуаров
                            print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(
                                azs_config.ip_address) + " успешно")
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
