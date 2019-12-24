import json
import sys
import time
from flask import render_template, redirect, url_for
from rq import get_current_job
from app import create_app, db
from app.models import User, Post, Message, Notification, FuelResidue, AzsList, Tanks, FuelRealisation, Priority, \
    PriorityList, ManualInfo, Trucks, TruckTanks, TruckFalse, Trip, TempAzsTrucks, TempAzsTrucks2, WorkType, Errors, \
    AzsList, AzsSystems, CfgDbConnection, Task
from app.models import Close1Tank1, Close1Tank2, Close1Tank3, Close1Tank4, Close1Tank5, Close2Tank1, Close2Tank2, \
    Close2Tank3, Close2Tank4, Close2Tank5, Close3Tank1, Close3Tank2, Close3Tank3, Close3Tank4, Close3Tank5,\
    Close4Tank1, Close4Tank2, Close4Tank3, Close4Tank4, Close4Tank5, Test, TripForToday, TruckFalse, RealisationStats, \
    TempAzsTrucks3, TempAzsTrucks4, TruckTanksVariations, UserLogs
from app.email import send_email
import psycopg2
from datetime import datetime, timedelta
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
                            # получаем список резервуаров
                            tanks = Tanks.query.filter_by(azs_id=i.id, active=True).order_by("tank_number").all()

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
                                    print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(
                                        azs_config.ip_address) + " выполнен")
                                    query = cursor.fetchall()
                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=row[0]).first()
                                        tankid = Tanks.query.order_by("tank_number").filter_by(azs_id=azsid.id,
                                                                                               tank_number=row[1]).first()
                                        add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            add.fuel_level = row[3]
                                            add.fuel_volume = row[4]
                                            add.fuel_temperature = row[5]
                                            add.datetime = row[6]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            add.product_code = row[2]
                                            add.download_time = datetime.now()
                                            add.auto = True
                                            db.session.add(add)
                                            try:
                                                db.session.commit()
                                            except Exception as error:
                                                print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                        else:
                                            add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                              fuel_level=row[3], fuel_volume=row[4],
                                                              fuel_temperature=row[5], datetime=row[6],
                                                              download_time=datetime.now(), auto=True)
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

                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=row[0]).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                        add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            add.fuel_level = row[3]
                                            add.fuel_volume = query[0][4]-realisation[0][3]
                                            add.fuel_temperature = row[5]
                                            add.datetime = row[6]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            add.product_code = row[2]
                                            add.download_time = datetime.now()
                                            add.auto = False
                                            db.session.add(add)
                                            try:
                                                db.session.commit()
                                            except Exception as error:
                                                print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                        else:
                                            add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                              fuel_level=row[3], fuel_volume=query[0][4]-realisation[0][3],
                                                              fuel_temperature=row[5], datetime=row[6],
                                                              download_time=datetime.now(), auto=False)
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
                                    print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(
                                        azs_config.ip_address) + " выполнен")
                                    query = cursor.fetchall()
                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=i.number).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=id.tank_number).first()
                                        add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            add.fuel_level = row[6]
                                            add.fuel_volume = row[7]
                                            add.fuel_temperature = row[10]
                                            add.datetime = row[8]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            add.product_code = id.fuel_type
                                            add.download_time = datetime.now()
                                            add.auto = True
                                            db.session.add(add)
                                            try:
                                                db.session.commit()
                                            except Exception as error:
                                                print("Данные по АЗС № " + str(azsid.id) + " не найдены", error)
                                        else:
                                            add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id,
                                                              product_code=id.fuel_type, fuel_level=row[6],
                                                              fuel_volume=row[7], fuel_temperature=row[10],
                                                              datetime=row[8], download_time=datetime.now(), auto=True)
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
                    print("SERVIOPUMP")
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
                                    print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(
                                        azs_config.ip_address) + " выполнен")
                                    query = cursor.fetchall()
                                    for row in query:
                                        azsid = AzsList.query.filter_by(number=i.number).first()
                                        tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=id.tank_number).first()
                                        add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()
                                        if add:
                                            # add.fuel_level =
                                            add.fuel_volume = row[3]
                                            # add.fuel_temperature = row[5]
                                            add.datetime = row[2]
                                            add.shop_id = azsid.id
                                            add.tank_id = tankid.id
                                            add.auto = True
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
                                            add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=product_code,
                                                              fuel_level=0, fuel_volume=row[3],
                                                              fuel_temperature=0, datetime=row[2],
                                                              download_time=datetime.now(), auto=True)
                                            db.session.add(add)
                                            db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def download_realisation_info(user_id):
    _set_task_progress(0)  # начало задания
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    azs_count = AzsList.query.filter_by(active=True).count()  # получаем количество активных АЗС
    total_queries = int(azs_count)
    queries = 0
    try:

        for i in azs:  # перебираем список азс
            test = CfgDbConnection.query.filter_by(azs_id=i.id).first()
            queries += 1
            _set_task_progress(100 * queries // total_queries)
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

                            print("Подключение к базе " + str(azs_config.database) + " на сервере " +
                                  str(azs_config.ip_address) + " успешно")
                            sql_10_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                          " WHERE id_shop = " \
                                          + str(i.number) + \
                                          " and begtime between current_TIMESTAMP - interval '10 day'" \
                                          " and current_TIMESTAMP and (err=0 or err=2)" \
                                          " GROUP BY id_shop, product, tank ORDER BY tank"
                            cursor.execute(sql_10_days)
                            query = cursor.fetchall()
                            print("SQL запрос книжных остатков на АЗС №" + str(
                                azs_config.ip_address) + " выполнен")
                            for row in query:

                                tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[2]).first()
                                add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()

                                if add:
                                    add.fuel_realisation_10_days = row[3]
                                    add.shop_id = i.number
                                    add.tank_id = tankid.id
                                    add.product_code = row[1]
                                    add.download_time = datetime.now()
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                else:
                                    add = FuelRealisation(shop_id=i.number, tank_id=tankid.id, product_code=row[1],
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
                elif test.system_type == 2:
                    print("Oilix")

                elif test.system_type == 3:
                    azs_config = CfgDbConnection.query.filter_by(system_type=3, azs_id=i.id).first()
                    if azs_config:  # если есть конфиг
                        try:
                            connection = fdb.connect(
                                dsn=azs_config.ip_address + ':' + azs_config.database,
                                user=azs_config.username,
                                password=azs_config.password)

                            cursor = connection.cursor()

                            print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(
                                azs_config.ip_address) + " успешно")
                            sql_10_days = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                          "where datetime >= current_date-10 group by 1,fuel_id, tank"
                            cursor.execute(sql_10_days)
                            query = cursor.fetchall()

                            for row in query:
                                tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[0]).first()
                                add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()
                                if add:
                                    add.fuel_realisation_10_days = row[2]
                                    add.shop_id = i.number
                                    add.tank_id = tankid.id
                                    product_code = 0
                                    if row[1] is 1:
                                        product_code = 95
                                    elif row[1] is 2:
                                        product_code = 92
                                    elif row[1] is 3:
                                        product_code = 50
                                    elif row[1] is 4:
                                        product_code = 51
                                    add.product_code = product_code
                                    add.download_time = datetime.now()
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                else:
                                    product_code = 0
                                    if row[1] is 1:
                                        product_code = 95
                                    elif row[1] is 2:
                                        product_code = 92
                                    elif row[1] is 3:
                                        product_code = 50
                                    elif row[1] is 4:
                                        product_code = 51
                                    add = FuelRealisation(shop_id=i.number, tank_id=tankid.id,
                                                          product_code=product_code, fuel_realisation_10_days=row[2],
                                                          download_time=datetime.now())
                                    db.session.add(add)
                                    db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)


    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def prepare_tables(user_id):
    logs = UserLogs(user_id=user_id,
                    action="preparation_started",
                    timestamp=datetime.now())
    db.session.add(logs)
    db.session.commit()

    def preparation():
        _set_task_progress(0)
        # функция создает таблицу всех возможных комбинаций налива топлива в бензовозы
        # для каждой азс и каждого бензовоза

        # очистка таблицы TempAzsTrucks в БД
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks`")
        # формируем массивы данных из БД
        azs_list = AzsList.query.filter_by(active=True).all()  # получаем список АКТИВНЫХ АЗС
        truck_list = Trucks.query.filter_by(active=True).all()  # получаем список АКТИВНЫХ бензовозов
        azs_tanks = Tanks.query.filter_by(active=True).all()  # получаем список АКТИЫНЫХ резервуаров всех АЗС
        truck_cells_list = TruckTanks.query.all()  # получаем список всех отсеков бензовозов
        # счетчик номера варианта налива
        variant_counter = 1
        # создаем список для записи в таблицу TempAzsTrucks
        temp_azs_truck_list = list()
        # создаем словарь для добавления в список temp_azs_trucks_list
        temp_azs_truck_dict = dict()
        for azs in azs_list:  # перебераем активные АЗС
            # создаем переменные для определения есть эти виды топлива на АЗС или нет
            is_92 = 0
            is_95 = 0
            is_50 = 0
            # перебираем таблицу из памяти со всеми АКТИЫНЫМИ резервуарами АЗС
            for row in azs_tanks:
                # проверяем есть ли у этой АЗС (которую перебираем в цикле) резервуары с 92 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 92):
                    is_92 = 1  # если есть, то помечаем соответствующий вид топлива
                # проверяем есть ли у этой АЗС резервуары с 95 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 95):
                    is_95 = 1  # если есть, то помечаем соответствующий вид топлива
                # проверяем есть ли у этой АЗС резервуары с 50 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 50):
                    is_50 = 1  # если есть, то помечаем соответствующий вид топлива

                # для ускорения проверяем, если все три вида топлив есть,
                # то можно цикл остановить, так как больше точно ничего не найдем
                if (is_92 == 1 and is_95 == 1 and is_50 == 1) and row.azs_id == azs.id:
                    break
            # В зависимости от найденных видов топлива на АЗС, формируем список
            azs_types = list()
            if (is_92 == 1) and (is_95 == 1) and (is_50 == 1):
                azs_types = [92, 95, 50]
            if (is_92 == 1) and (is_95 == 1) and (is_50 == 0):
                azs_types = [92, 95]
            if (is_92 == 1) and (is_95 == 0) and (is_50 == 1):
                azs_types = [92, 50]
            if (is_92 == 0) and (is_95 == 1) and (is_50 == 1):
                azs_types = [95, 50]
            if (is_92 == 1) and (is_95 == 0) and (is_50 == 0):
                azs_types = [92]
            if (is_92 == 0) and (is_95 == 1) and (is_50 == 0):
                azs_types = [95]
            if (is_92 == 0) and (is_95 == 0) and (is_50 == 1):
                azs_types = [50]

            # считаем количество отсеков в каждом из активных бензовозов
            # для этого:
            # перебираем список всех АКТИВНЫХ бензовозов
            for truck in truck_list:
                # создаем список для хранения видов топлива для заполнения данного бензовоза
                fuel_types = list()
                cell_counter = 0  # при смене бензовоза обнуляем счетчик отсеков
                for cell in truck_cells_list:  # перебираем все отсеки всех бензовозов
                    if cell.truck_id == truck.id:  # выбираем все отсеки у конкретного бензовоза
                        cell_counter = cell_counter + 1  # увеличиваем счетчик отсеков бензовоза
                # если у бензовоза ОДИН отсек
                if cell_counter == 1:
                    # тогда делаем 1 вложенный цикл, который перебирает все возможные виды топлива данной АЗС
                    for a in azs_types:
                        # добавляем в список один из всех возможных видов топлива данного бензовоза
                        fuel_types = [a]
                        # считаем количество отсеков с каждым видом топлива в данном варианте налива
                        cells_count_92 = 0
                        cells_count_95 = 0
                        cells_count_50 = 0
                        for i in fuel_types:
                            if i == 92:
                                cells_count_92 = cells_count_92 + 1
                            if i == 95:
                                cells_count_95 = cells_count_95 + 1
                            if i == 50:
                                cells_count_50 = cells_count_50 + 1

                        # перебираем все возможные виды топлива для данного бензовоза, с получением порядкового номера
                        # отсека и его емкости
                        for index, type in enumerate(fuel_types):
                            # перебираем список всего отсеков данного бензовоза
                            for cell in truck_cells_list:
                                # если нашли id нашего бензовоза и порядковый номер отсека совпадает с порядковым
                                # номером из списка fuel_types
                                if cell.truck_id == truck.id and cell.number == index + 1:
                                    # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                    temp_azs_truck_dict = {'variant_id': variant_counter,
                                                           'azs_id': azs.id,
                                                           'truck_tank_id': cell.id,
                                                           'truck_id': truck.id,
                                                           'fuel_type': fuel_types[index],
                                                           'capacity': cell.capacity,
                                                           'cells_92': cells_count_92,
                                                           'cells_95': cells_count_95,
                                                           'cells_50': cells_count_50}
                                    # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                    temp_azs_truck_list.append(temp_azs_truck_dict)
                                    # останавливаем итерацию цикла, так как искать больше нет смысла
                                    break
                        variant_counter = variant_counter + 1

                # если у бензовоза ДВА отсека
                if cell_counter == 2:
                    # тогда делаем 2 вложенных цикла которые переберают все возможные виды топлива данной азс
                    for a in azs_types:
                        for b in azs_types:
                            # добавляем в список два из всех возможных видов топлива данного бензовоза
                            fuel_types = [a, b]
                            # считаем количество отсеков с каждым видом топлива в данном варианте налива
                            cells_count_92 = 0
                            cells_count_95 = 0
                            cells_count_50 = 0
                            for i in fuel_types:
                                if i == 92:
                                    cells_count_92 = cells_count_92 + 1
                                if i == 95:
                                    cells_count_95 = cells_count_95 + 1
                                if i == 50:
                                    cells_count_50 = cells_count_50 + 1

                            # перебираем все возможные виды топлива для данного бензовоза,
                            # с получением порядкового номера отсека и его емкости
                            for index, type in enumerate(fuel_types):
                                # перебираем список всего отсеков данного бензовоза
                                for cell in truck_cells_list:
                                    # если нашли id нашего бензовоза и порядковый номер отсека совпадает с порядковым
                                    # номером из списка fuel_types
                                    if cell.truck_id == truck.id and cell.number == index + 1:
                                        # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                        temp_azs_truck_dict = {'variant_id': variant_counter,
                                                               'azs_id': azs.id,
                                                               'truck_tank_id': cell.id,
                                                               'truck_id': truck.id,
                                                               'fuel_type': fuel_types[index],
                                                               'capacity': cell.capacity,
                                                               'cells_92': cells_count_92,
                                                               'cells_95': cells_count_95,
                                                               'cells_50': cells_count_50}
                                        # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                        temp_azs_truck_list.append(temp_azs_truck_dict)
                                        # останавливаем итерацию цикла, так как искать больше нет смысла
                                        break
                # по аналогии для ТРЕХ отсеков бензовоза
                if cell_counter == 3:
                    for a in azs_types:
                        for b in azs_types:
                            for c in azs_types:
                                fuel_types = [a, b, c]
                                # считаем количество отсеков с каждым видом топлива в данном варианте налива
                                cells_count_92 = 0
                                cells_count_95 = 0
                                cells_count_50 = 0
                                for i in fuel_types:
                                    if i == 92:
                                        cells_count_92 = cells_count_92 + 1
                                    if i == 95:
                                        cells_count_95 = cells_count_95 + 1
                                    if i == 50:
                                        cells_count_50 = cells_count_50 + 1

                                # перебираем все возможные виды топлива для данного бензовоза,
                                # с получением порядкового номера отсека и его емкости
                                for index, type in enumerate(fuel_types):
                                    for cell in truck_cells_list:
                                        if cell.truck_id == truck.id and cell.number == index + 1:
                                            # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                            temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                   'azs_id': azs.id,
                                                                   'truck_tank_id': cell.id,
                                                                   'truck_id': truck.id,
                                                                   'fuel_type': fuel_types[index],
                                                                   'capacity': cell.capacity,
                                                                   'cells_92': cells_count_92,
                                                                   'cells_95': cells_count_95,
                                                                   'cells_50': cells_count_50}
                                            # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                            temp_azs_truck_list.append(temp_azs_truck_dict)
                                            # останавливаем итерацию цикла, так как искать больше нет смысла
                                            break
                                variant_counter = variant_counter + 1
                # по аналогии для ЧЕТЫРЕХ отсеков бензовоза
                if cell_counter == 4:
                    for a in azs_types:
                        for b in azs_types:
                            for c in azs_types:
                                for d in azs_types:
                                    fuel_types = [a, b, c, d]
                                    cells_count_92 = 0
                                    cells_count_95 = 0
                                    cells_count_50 = 0
                                    for i in fuel_types:
                                        if i == 92:
                                            cells_count_92 = cells_count_92 + 1
                                        if i == 95:
                                            cells_count_95 = cells_count_95 + 1
                                        if i == 50:
                                            cells_count_50 = cells_count_50 + 1
                                    for index, type in enumerate(fuel_types):
                                        for cell in truck_cells_list:
                                            if cell.truck_id == truck.id and cell.number == index + 1:
                                                # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                                temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                       'azs_id': azs.id,
                                                                       'truck_tank_id': cell.id,
                                                                       'truck_id': truck.id,
                                                                       'fuel_type': fuel_types[index],
                                                                       'capacity': cell.capacity,
                                                                       'cells_92': cells_count_92,
                                                                       'cells_95': cells_count_95,
                                                                       'cells_50': cells_count_50}
                                                # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                                temp_azs_truck_list.append(temp_azs_truck_dict)
                                                # останавливаем итерацию цикла, так как искать больше нет смысла
                                                break
                                    variant_counter = variant_counter + 1
                    # по аналогии для ПЯТИ отсеков бензовоза
                    if cell_counter == 5:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            fuel_types = [a, b, c, d, e]
                                            # считаем количество отсеков с каждым видом топлива в данном варианте налива
                                            cells_count_92 = 0
                                            cells_count_95 = 0
                                            cells_count_50 = 0
                                            for i in fuel_types:
                                                if i == 92:
                                                    cells_count_92 = cells_count_92 + 1
                                                if i == 95:
                                                    cells_count_95 = cells_count_95 + 1
                                                if i == 50:
                                                    cells_count_50 = cells_count_50 + 1

                                            for index, type in enumerate(fuel_types):
                                                for cell in truck_cells_list:
                                                    if cell.truck_id == truck.id and cell.number == index + 1:
                                                        # то формируем словарь с данными для записи в таблицу
                                                        # TempAzsTrucks в БД
                                                        temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                               'azs_id': azs.id,
                                                                               'truck_tank_id': cell.id,
                                                                               'truck_id': truck.id,
                                                                               'fuel_type': fuel_types[index],
                                                                               'capacity': cell.capacity,
                                                                               'cells_92': cells_count_92,
                                                                               'cells_95': cells_count_95,
                                                                               'cells_50': cells_count_50}
                                                        # добавляем словарь в список temp_azs_truck_list,
                                                        # созданный ранее
                                                        temp_azs_truck_list.append(temp_azs_truck_dict)
                                                        # останавливаем итерацию цикла, так как искать больше нет смысла
                                                        break

                                            variant_counter = variant_counter + 1
                    # по аналогии для ШЕСТИ отсеков бензовоза
                    if cell_counter == 6:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                fuel_types = [a, b, c, d, e, f]
                                                # считаем количество отсеков с каждым видом топлива
                                                # в данном варианте налива
                                                cells_count_92 = 0
                                                cells_count_95 = 0
                                                cells_count_50 = 0
                                                for i in fuel_types:
                                                    if i == 92:
                                                        cells_count_92 = cells_count_92 + 1
                                                    if i == 95:
                                                        cells_count_95 = cells_count_95 + 1
                                                    if i == 50:
                                                        cells_count_50 = cells_count_50 + 1

                                                for index, type in enumerate(fuel_types):
                                                    for cell in truck_cells_list:
                                                        if cell.truck_id == truck.id and cell.number == index + 1:
                                                            # то формируем словарь с данными для записи в таблицу
                                                            # TempAzsTrucks в БД
                                                            temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                   'azs_id': azs.id,
                                                                                   'truck_tank_id': cell.id,
                                                                                   'truck_id': truck.id,
                                                                                   'fuel_type': fuel_types[index],
                                                                                   'capacity': cell.capacity,
                                                                                   'cells_92': cells_count_92,
                                                                                   'cells_95': cells_count_95,
                                                                                   'cells_50': cells_count_50}
                                                            # добавляем словарь в список temp_azs_truck_list,
                                                            # созданный ранее
                                                            temp_azs_truck_list.append(temp_azs_truck_dict)
                                                            # останавливаем итерацию цикла,
                                                            # так как искать больше нет смысла
                                                            break

                                            variant_counter = variant_counter + 1
                    # по аналогии для СЕМИ отсеков бензовоза
                    if cell_counter == 7:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                for g in azs_types:
                                                    fuel_types = [a, b, c, d, e, f, g]

                                                    # считаем количество отсеков с каждым видом топлива
                                                    # в данном варианте налива
                                                    cells_count_92 = 0
                                                    cells_count_95 = 0
                                                    cells_count_50 = 0
                                                    for i in fuel_types:
                                                        if i == 92:
                                                            cells_count_92 = cells_count_92 + 1
                                                        if i == 95:
                                                            cells_count_95 = cells_count_95 + 1
                                                        if i == 50:
                                                            cells_count_50 = cells_count_50 + 1

                                                    for index, type in enumerate(fuel_types):
                                                        for cell in truck_cells_list:
                                                            if cell.truck_id == truck.id and cell.number == index + 1:
                                                                # то формируем словарь с данными для записи в таблицу
                                                                # TempAzsTrucks в БД
                                                                temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                       'azs_id': azs.id,
                                                                                       'truck_tank_id': cell.id,
                                                                                       'truck_id': truck.id,
                                                                                       'fuel_type': fuel_types[index],
                                                                                       'capacity': cell.capacity,
                                                                                       'cells_92': cells_count_92,
                                                                                       'cells_95': cells_count_95,
                                                                                       'cells_50': cells_count_50}
                                                                # добавляем словарь в список temp_azs_truck_list,
                                                                # созданный ранее
                                                                temp_azs_truck_list.append(temp_azs_truck_dict)
                                                                # останавливаем итерацию цикла, так как искать больше нет смысла
                                                                break

                                            variant_counter = variant_counter + 1
                    # по аналогии для ВОСЬМИ отсеков бензовоза
                    if cell_counter == 8:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                for g in azs_types:
                                                    for h in azs_types:
                                                        fuel_types = [a, b, c, d, e, f, g, h]

                                                        # считаем количество отсеков с каждым видом топлива
                                                        # в данном варианте налива
                                                        cells_count_92 = 0
                                                        cells_count_95 = 0
                                                        cells_count_50 = 0
                                                        for i in fuel_types:
                                                            if i == 92:
                                                                cells_count_92 = cells_count_92 + 1
                                                            if i == 95:
                                                                cells_count_95 = cells_count_95 + 1
                                                            if i == 50:
                                                                cells_count_50 = cells_count_50 + 1

                                                        for index, type in enumerate(fuel_types):
                                                            for cell in truck_cells_list:
                                                                if cell.truck_id == truck.id and cell.number == index + 1:
                                                                    # то формируем словарь с данными для записи в таблицу
                                                                    # TempAzsTrucks в БД
                                                                    temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                           'azs_id': azs.id,
                                                                                           'truck_tank_id': cell.id,
                                                                                           'truck_id': truck.id,
                                                                                           'fuel_type': fuel_types[index],
                                                                                           'capacity': cell.capacity,
                                                                                           'cells_92': cells_count_92,
                                                                                           'cells_95': cells_count_95,
                                                                                           'cells_50': cells_count_50}
                                                                    # добавляем словарь в список temp_azs_truck_list,
                                                                    # созданный ранее
                                                                    temp_azs_truck_list.append(temp_azs_truck_dict)
                                                                    # останавливаем итерацию цикла,
                                                                    # так как искать больше нет смысла
                                                                    break

                                            variant_counter = variant_counter + 1
        # После выполнения функции записываем все полученные данные в таблицу TempAzsTrucks в базе данных
        return temp_azs_truck_list

    Close1_Tank1 = Close1Tank1.query.all()
    Close1_Tank2 = Close1Tank2.query.all()
    Close1_Tank3 = Close1Tank3.query.all()
    Close1_Tank4 = Close1Tank4.query.all()
    Close2_Tank1 = Close2Tank1.query.all()
    Close2_Tank2 = Close2Tank2.query.all()
    Close2_Tank3 = Close2Tank3.query.all()
    Close2_Tank4 = Close2Tank4.query.all()
    Close3_Tank1 = Close3Tank1.query.all()
    Close3_Tank2 = Close3Tank2.query.all()
    Close3_Tank3 = Close3Tank3.query.all()
    Close3_Tank4 = Close3Tank4.query.all()

    def select_close_tank_table(count, tanks_counter):
        if count == 1 and tanks_counter == 1:
            table_sliv_variant = Close1_Tank1
            return table_sliv_variant
        if count == 1 and tanks_counter == 2:
            table_sliv_variant = Close1_Tank2
            return table_sliv_variant
        if count == 1 and tanks_counter == 3:
            table_sliv_variant = Close1_Tank3
            return table_sliv_variant
        if count == 1 and tanks_counter == 4:
            table_sliv_variant = Close1_Tank4
            return table_sliv_variant

        if count == 2 and tanks_counter == 1:
            table_sliv_variant = Close2_Tank1
            return table_sliv_variant
        if count == 2 and tanks_counter == 2:
            table_sliv_variant = Close2_Tank2
            return table_sliv_variant
        if count == 2 and tanks_counter == 3:
            table_sliv_variant = Close2_Tank3
            return table_sliv_variant
        if count == 2 and tanks_counter == 4:
            table_sliv_variant = Close2_Tank4
            return table_sliv_variant

        if count == 3 and tanks_counter == 1:
            table_sliv_variant = Close3_Tank1
            return table_sliv_variant
        if count == 3 and tanks_counter == 2:
            table_sliv_variant = Close3_Tank2
            return table_sliv_variant
        if count == 3 and tanks_counter == 3:
            table_sliv_variant = Close3_Tank3
            return table_sliv_variant
        if count == 3 and tanks_counter == 4:
            table_sliv_variant = Close3_Tank4
            return table_sliv_variant


    # функция формирует все возмоные варианты слива топлива на АЗС
    def preparation_two():
        _set_task_progress(20)
        # очищаем таблицу
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks2`")
        # создаем массив для хранения сформированных итоговых данных
        # для последующей записи в таблицу TempAzsTrucks2 в БД
        temp_azs_trucks_2_list = list()
        temp_azs_trucks_2_dict = dict()
        # помещаем таблицу всех вариантов налива бензовозов TempAzsTrucks в переменную
        temp_azs_trucks = preparation()
        # помещаем таблицу всех АКТИВНЫХ АЗС в переменную
        table_azs_list = AzsList.query.filter_by(active=True).all()
        # помещаем таблицу все АКТИВНЫЕ резервуары АЗС в переменную
        table_tanks = Tanks.query.filter_by(active=True).all()

        # Получаем количество вариантов заполнения бензовоза (благодаря таблице TempAzsTrucks полю - variant_id)
        # счетчик варианта слива для таблицы TempAzsTrucks2
        variant_counter_sliv = 1
        # Для каждой АКТИВНОЙ АЗС считаем количество АКТИЫНЫХ резервуаров по каждому из видов топлива
        tanks_count = dict()
        # перебираем таблицу со списком АКТИВНЫХ АЗС

        for i in table_azs_list:

            # счетчик для хранения количества АКТИВНЫХ резервуаров данной азс
            tank_count_92 = 0
            tank_count_95 = 0
            tank_count_50 = 0
            # список с айдишниками АКТИВНЫХ резервуаров данной АЗС
            tanks_list_92 = list()
            tanks_list_95 = list()
            tanks_list_50 = list()
            # перебираем список АКТИВНЫХ резервуаров данной АЗС
            for tank in table_tanks:
                if i.id == tank.azs_id:
                    if tank.fuel_type == 92:
                        tank_count_92 = tank_count_92 + 1
                        tanks_list_92.append(tank.id)
                    if tank.fuel_type == 95:
                        tank_count_95 = tank_count_95 + 1
                        tanks_list_95.append(tank.id)
                    if tank.fuel_type == 50:
                        tank_count_50 = tank_count_50 + 1
                        tanks_list_50.append(tank.id)
                    tanks_count[i.id] = {
                        'tank_count_92': tank_count_92,
                        'tank_count_95': tank_count_95,
                        'tank_count_50': tank_count_50,
                        'tanks_list_92': tanks_list_92,
                        'tanks_list_95': tanks_list_95,
                        'tanks_list_50': tanks_list_50}
        # создаем словарь с обобщенными даннными для каждого варианта налива (основным ключем в словаре
        # является variant_id)
        slovar = dict()

        # создаем словарь с заполнеными ключами "variant_id, truck_id, cells_92, cells_95 и cells_50".
        # Остальные ячейки обнуляем
        for i in temp_azs_trucks:
            slovar[i['variant_id']] = {'azs_id': i['azs_id'],
                                       'cells_list_92': [],
                                       'cells_list_95': [],
                                       'cells_list_50': [],
                                       'capacity_92': 0,
                                       'capacity_95': 0,
                                       'capacity_50': 0,
                                       'cells_92': i['cells_92'],
                                       'cells_95': i['cells_95'],
                                       'cells_50': i['cells_50'],
                                       'truck_id': i['truck_id'],
                                       'cells_capacity_list_92': [],
                                       'cells_capacity_list_95': [],
                                       'cells_capacity_list_50': []
                                       }
        # перебираем таблицу TempAzsTrucks с вариантами налива и дополняем словарь
        for i in temp_azs_trucks:
            # обращаемся к ячейкам словаря по ключу variant_id
            temp_variant = i['variant_id']
            # если в текущей строке в таблице TempAzsTrucks вид топлива - 92,
            # то заполняем словарь согласно таблице для этого вида топлива
            if i['fuel_type'] == 92:
                # создаем пустой список для хранения айдишников отвеков бензовоза
                cells_list_92 = list()
                # создаем пустой список для хранения емкостей отсеков бензовоза
                cells_capacity_list_92 = list()
                # добавляем емкость отсека из текущей строки в список
                cells_capacity_list_92.append(i['capacity'])
                # добавляем айдишник отсека из текущей строки в список
                cells_list_92.append(i['truck_tank_id'])
                # обновляем данные в словаре
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'] + i['capacity'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'] + cells_list_92,
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'],
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'],
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'] + cells_capacity_list_92,
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'],
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50']
                                        }
            # выполняем действия для 95 вида топлива по аналогии с 92 видом топлива
            if i['fuel_type'] == 95:
                cells_list_95 = list()
                cells_capacity_list_95 = list()
                cells_capacity_list_95.append(i['capacity'])
                cells_list_95.append(i['truck_tank_id'])
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'] + i['capacity'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'],
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'] + cells_list_95,
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'],
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'],
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'] + cells_capacity_list_95,
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50']
                                        }

            # выполняем действия для дизеля вида топлива по аналогии с 92 и 95 видами топлива
            if i['fuel_type'] == 50:
                cells_list_50 = list()
                cells_capacity_list_50 = list()
                cells_capacity_list_50.append(i['capacity'])
                cells_list_50.append(i['truck_tank_id'])
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'] + i['capacity'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'],
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'],
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'] + cells_list_50,
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'],
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'],
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50'] + cells_capacity_list_50
                                        }

        # перебираем варианты налива от первого до последнего
        for variant in range(1, temp_azs_trucks[-1]['variant_id']):
            # получаем айдишник текущей АЗС
            azs_id = slovar[variant]['azs_id']
            # Получаем количество резервуаров АЗС по каждому виду топлива
            count_92 = tanks_count[azs_id]['tank_count_92']
            count_95 = tanks_count[azs_id]['tank_count_95']
            count_50 = tanks_count[azs_id]['tank_count_50']
            # создаем переменные для хранения таблиц необходимых для перебора всех возможных вариантов слива
            table_sliv_variant_92 = None
            table_sliv_variant_50 = None
            table_sliv_variant_95 = None

            # Благодаря тому, что мы знаем количество резервуаров АЗС и количество отсеков бензовоза с этим видом
            # топлива получаем нужную константную таблицу с вариантами слива бензовоза
            # для 92 вида топлива
            if count_92 == 1 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            # для 95 вида топлива
            if count_95 == 1 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            # # для 50 вида топлива
            if count_50 == 1 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])
            # если у данной АЗС есть 92 топливо, то перебираем таблицу, возвращенную функцией select_close_tank_table
            if table_sliv_variant_92 is not None:
                # если резервуар с таким видом топлива один, то
                if count_92 == 1:
                    # перебираем таблицу
                    for variant_sliv in table_sliv_variant_92:
                        # если первая ячейка таблицы не пуста или не равна NULL, то
                        if variant_sliv.tank1 is not None:
                            # обнуляем счетчик суммарного слива
                            sum_sliv = 0
                            # создаем список, в котором будем хранить айди отсеков бензовоза в виде строковых параметров
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            # перебираем варианты слива, записанные в виде строки, разделенные знаком "+"
                            # из таблицы table_sliv_variant_92
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                # по индексу получаем емкость каждого отсека, суммируем емкости
                                # и получаем суммарный слив
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                # по индексу получаем айди отсеков бензовоза, и формирвем из них строку,
                                # где айди разделены знаком "+"
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            # формируем целую строку
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            # заполняем словарь полученными даннми
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            # добавляем полученынй словарь в списокдля последующей записи в базу
                            # в таблицу TempAzsTrucks2
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        # увеличиваем счетчик варианта слива на единицу
                        variant_counter_sliv = variant_counter_sliv + 1
                # для двух резервуаров выполняем те же действия как с одним
                if count_92 == 2:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()

                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()

                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1
                # для трех резервуаров, по аналогии с одним
                if count_92 == 3:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1
                # по аналогии с 4 резервуарами
                if count_92 == 4:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1

            # --- Для 95 вида топлива выполняем по аналогии с 92 видом топлива
            if table_sliv_variant_95 is not None:
                if count_95 == 1:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 2:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 3:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 4:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
            # --- Для 50 вида топлива выполняем по аналогии с 92 и 95 видом топлива
            if table_sliv_variant_50 is not None:
                if count_50 == 1:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 2:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 3:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""

                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 4:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
        db.engine.execute(TempAzsTrucks.__table__.insert(), temp_azs_trucks)
        return temp_azs_trucks_2_list, temp_azs_trucks

    ''' 
    # функция определяет может ли вариант слива в данный момент слиться на АЗС,
    # сможет ли вариант слива слиться после времени бензовоза в пути
    # определяет новый запас суток
    # определяет остатки топлива после слива
    # определяет, может ли бензовой зайти на АЗС
    # может ли этот варинат налива пройти по дороге с весами
    '''
    "------------------------------------------------------------------------------------------------------------"
    "---------------------------- определяем, сможет ли бензовоз пройти весы ------------------------------------"
    "------------------------------------------------------------------------------------------------------------"

    def is_it_fit():
        _set_task_progress(50)
        temp_azs_trucks_2_list, temp_azs_trucks = preparation_two()
        # получаем остатки из базы
        residue = FuelResidue.query.all()
        # получаем реализацию из базы
        realisation = FuelRealisation.query.all()
        # получаем информацию о времени до азс
        trip = Trip.query.all()
        # получаем список отсеков всех бензовозов
        truck_tanks = TruckTanks.query.all()
        # получаем информанию об азс, на которые не могут заехать определенные бензовозы
        trucks_false = TruckFalse.query.all()
        # создаем пустой словарь для хранеия в нем данных о реализации и остатков
        realisation_n_residue = dict()
        # создаем пустой словарь для хранеия в нем данных времени пути до АЗС
        azs_trip_access = dict()
        azs_trip_time = dict()

        # заполняем словарь с данными об остатках топлива
        for i in residue:
            realisation_n_residue[i.tank_id] = {'azs_id': i.azs_id,  # id_АЗС
                                                'fuel_volume': i.fuel_volume,  # остаток топлива в резервуаре
                                                'free_volume': i.free_volume,  # свободная емкость в резервуаре
                                                # реализация в резервуаре (нулевая, так как заполняем ее потом)
                                                'fuel_realisation': 0,
                                                # максимальная реализация топлива в резервуаре (среди всех периодов)
                                                'fuel_realisation_max': 0
                                                }
        # заполняем словарь данными о реализации топлива
        for i in realisation:
            realisation_n_residue[i.tank_id] = {'azs_id': i.azs_id,  # id_АЗС
                                                # Оставляем прошлое значение остатка топлива в резервуаре
                                                'fuel_volume': realisation_n_residue[i.tank_id]['fuel_volume'],
                                                # свободная емкость в резервуаре
                                                'free_volume': realisation_n_residue[i.tank_id]['free_volume'],
                                                # Добавляем в словарь реализацию из этого резервуара
                                                # (среднюю в час за шестичасовой период)
                                                'fuel_realisation': i.fuel_realisation_hour / 6,
                                                # максимальная реализация топлива в резервуаре (среди всех периодов)
                                                'fuel_realisation_max': i.fuel_realisation_max
                                                }

        # формируем словарь для хранения данных о растоянии до АЗС и времени пути
        for i in trip:
            azs_trip_time[i.azs_id] = {'time_to_before_lunch': i.time_to_before_lunch,
                                       'time_to': i.time_to,
                                       'weigher': i.weigher}
        # формируем словарь для хранения данных о бензовозах и азс на которые они не могут заезжать
        for i in trucks_false:
            azs_trip_access[str(i.azs_id)+'-'+str(i.truck_id)] = {'access': False}

        is_it_fit_list = list()
        for i in temp_azs_trucks_2_list:
            # проверяем, сольется ли бензовоз в данный момент
            # из свободной емкости резервуара вычитаем сумму слива бензовоза
            sliv = realisation_n_residue[i['tank_id']]['free_volume'] - i['sum_sliv']
            # переводим время из вида db.time() в strptime() и переводим результат в секунды
            time_to_string = azs_trip_time[i['azs_id']]['time_to_before_lunch']
            x = time.strptime(str(time_to_string), '%H:%M:%S')
            time_to_seconds = timedelta(hours=x.tm_hour, minutes=x.tm_min,
                                        seconds=x.tm_sec).total_seconds()
            # считаем примерное количество топлива, которое будет реализовано за время в пути бензовоза
            realis_time = realisation_n_residue[i["tank_id"]]['fuel_realisation'] * ((time_to_seconds / 60) / 60)
            # проверяем сольется ли бензовоз, с учетом реализации за время его пути к АЗС
            # из свободной емкости резервуара вычитаем сумму слива бензовоза, и прибавляем количество топлива,
            # которое реализуется у данного резервуара за время пути бензовоза к ней
            sliv_later = realisation_n_residue[i['tank_id']]['free_volume'] - i['sum_sliv'] + realis_time

            # если бензовоз не сливается в данный момент (то есть переменная sliv - меньше нуля)
            if sliv < 0:
                # записываем в базу, что бензовоз в данный момент слиться не сможет
                i['is_it_fit'] = False
                # новый запас суток и новые остатки не считаем
                i['new_fuel_volume'] = 0
                i['new_days_stock'] = 0
            # если бензовоз сможет слиться нат екущий момент (то есть переменная sliv - больше нуля)
            else:
                # записываем в базу, что бензовоз в данный момент сольется
                i['is_it_fit'] = True
                # расчитываем количество отстатков в резервуаре после слива
                i['new_fuel_volume'] = realisation_n_residue[i['tank_id']]['fuel_volume'] + i['sum_sliv']
                # расчитываем новый запас суток
                i['new_days_stock'] = i['new_fuel_volume'] / realisation_n_residue[i['tank_id']]['fuel_realisation_max']
            # если бензовоз не сливается после времени затраченного на дорогу (то есть переменная sliv_later
            # - меньше нуля)
            if sliv_later < 0:
                # записываем в базу, что бензовоз слиться не сможет
                i['is_it_fit_later'] = False
                # новый запас суток и новые остатки не считаем
                i['new_fuel_volume'] = 0
                i['new_days_stock'] = 0
            else:
                # записываем в базу, что бензовоз сольется спустя время затраченное на дорогу
                i['is_it_fit_later'] = True
                # расчитываем количество отстатков в резервуаре после слива
                i['new_fuel_volume'] = realisation_n_residue[i['tank_id']]['fuel_volume'] + i['sum_sliv']
                # расчитываем новый запас суток
                i['new_days_stock'] = i['new_fuel_volume'] / realisation_n_residue[i['tank_id']]['fuel_realisation_max']
            # проверяем, сможет ли бензовоз заехать на АЗС (нет ли для него никаких ограничений)
            # т.е. проверяем наличие ключа в словаре azs_trip_access, в котором содержатся ограничения для бензовозов
            # ключ АЗС-АйдиБензовоза
            if str(i['azs_id']) + '-' + str(i['truck_id']) in azs_trip_access:
                # если ограничения есть, то ставим False
                i['is_it_able_to_enter'] = False
            else:
                # если ограничений нет, то ставим True
                i['is_it_able_to_enter'] = True

            # добавляем словарь в список для записи в базу данных, в таблицу TempAzsTrucks2
            is_it_fit_list.append(i)
        # создаем словарь для хранения переменных с информацией о том, влезет ли определенный вид топлива
        # в резервуар на АЗС (3 переменные по всем видам топлива)
        fuel_types_dict = dict()
        # создаем список  для хранеия обновленной таблицы TempAzsTrucks2
        is_variant_sliv_good_list = list()
        # заполняем переменные словаря fuel_types_dict единицами
        # ключем в словаре является связка variant:variant_sliv
        for i in is_it_fit_list:
            fuel_types_dict[str(i['variant'])+':'+str(i['variant_sliv'])] = {'is_it_fit_92': 1,
                                                                             'is_it_fit_95': 1,
                                                                             'is_it_fit_50': 1}
        # заново перебираем таблицу TempAzsTrucks2(которая хранится в виде списка словарей)
        for i in is_it_fit_list:
            # в переменную key заносим ключ итого словаря (связка variant:variant_sliv)
            key = str(i['variant']) + ':' + str(i['variant_sliv'])
            # если находим вид топлива которое не сливается, то помечаем его нулем
            if i['fuel_type'] == 92 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': 0,
                                        'is_it_fit_95': fuel_types_dict[key]['is_it_fit_95'],
                                        'is_it_fit_50': fuel_types_dict[key]['is_it_fit_50']}
            if i['fuel_type'] == 95 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': fuel_types_dict[key]['is_it_fit_92'],
                                        'is_it_fit_95': 0,
                                        'is_it_fit_50': fuel_types_dict[key]['is_it_fit_50']}
            if i['fuel_type'] == 50 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': fuel_types_dict[key]['is_it_fit_92'],
                                        'is_it_fit_95': fuel_types_dict[key]['is_it_fit_95'],
                                        'is_it_fit_50': 0}
        # снова беребираем список словарей с данными из таблицы TempAzsTrucks2
        for i in is_it_fit_list:
            # в переменную key заносим ключ итого словаря (связка variant:variant_sliv)
            key = str(i['variant']) + ':' + str(i['variant_sliv'])
            # если все три вида топлива (или все виды топлива которые мы везем на азс) сливаются, то помечаем столбец
            # в котором хранится информация о том, сливается ли данный вариант (is_variant_sliv_good) единицей
            if fuel_types_dict[key]['is_it_fit_92'] == 1 and fuel_types_dict[key]['is_it_fit_95'] == 1 and fuel_types_dict[key]['is_it_fit_50'] == 1:
                i['is_variant_sliv_good'] = 1
                # добавляем обновленный словарь в список
                is_variant_sliv_good_list.append(i)
            # если не все топливо из данного варианта слива сливается, то ставим в ячейке ноль (False)
            else:
                i['is_variant_sliv_good'] = 0
                # добавляем обновленный словарь в список
                is_variant_sliv_good_list.append(i)
        # создаем словарь для хранения обновленных данных (по факту - в словаре появится ячейка is_variant_good)
        is_variant_good_list = dict()
        # перебираем список словарей с данными из таблицы TempAzsTrucks2 (из предыдущего цикла)
        for i in is_variant_sliv_good_list:
            # в созданные ранее словарь добавляем ячейки с нулями
            is_variant_good_list[str(i['variant'])] = {'is_it_92': 0,
                                                       'is_it_95': 0,
                                                       'is_it_50': 0}
        # снова перебираем список словарей
        for i in is_variant_sliv_good_list:
            # если находим определенный вид топлива, и вариант слива относящийся к этой строке таблицы отмечен True,
            # то помечаем го цифрой 2
            # а если нет, то единицей
            if i['fuel_type'] == 92 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': 2,
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 92 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': 1,
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 95 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': 2,
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 95 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': 1,
                                                           'is_it_50': is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 50 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50': 2}
            if i['fuel_type'] == 50 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50': 1}
        # создаем финальный список для данной функции, который будет записан в таблицу TempAzsTrucks2 в БД
        final_list2 = list()
        final_list = list()
        test_dict = dict()
        weigher_dict = dict()  # словарь с наполнением при весах
        weigher_variant_good_dict = dict()
        trip = Trip.query.filter_by(weigher=1).all()
        cells = TruckTanks.query.all()
        truck_tanks_variations = TruckTanksVariations.query.all()
        azs_list_weigher_variant_id = list()
        azs_list_weigher_truck_id = list()
        azs_list_weigher_fuel_type = list()
        azs_list_weigher_truck_tank_id = list()
        for i in trip:
            for azs in temp_azs_trucks:
                if azs['azs_id'] == i.azs_id:
                    azs_list_weigher_variant_id.append(azs['variant_id'])
                    azs_list_weigher_truck_id.append(azs['truck_id'])
            for index, x in enumerate(azs_list_weigher_variant_id):
                key = str(azs_list_weigher_variant_id[index]) + ':' + str(azs_list_weigher_truck_id[index])
                test_dict[key] = {'1': None,
                                  '2': None,
                                  '3': None,
                                  '4': None,
                                  '5': None,
                                  '6': None,
                                  '7': None,
                                  '8': None
                                  }

        azs_list_weigher_variant_id = list()
        azs_list_weigher_truck_id = list()
        azs_list_weigher_fuel_type = list()
        azs_list_weigher_truck_tank_id = list()
        for i in trip:
            for azs in temp_azs_trucks:
                if azs['azs_id'] == i.azs_id:
                    azs_list_weigher_variant_id.append(azs['variant_id'])
                    azs_list_weigher_truck_id.append(azs['truck_id'])
                    azs_list_weigher_fuel_type.append(azs['fuel_type'])
                    azs_list_weigher_truck_tank_id.append(azs['truck_tank_id'])
            for index, x in enumerate(azs_list_weigher_variant_id):
                key = str(azs_list_weigher_variant_id[index]) + ':' + str(azs_list_weigher_truck_id[index])

                fuel_type_boolean = azs_list_weigher_fuel_type[index]
                for cell in cells:
                    if cell.id == azs_list_weigher_truck_tank_id[index]:
                        if cell.number == 1:
                            test_dict[key] = {'1': fuel_type_boolean,
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['4'],
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 2:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': fuel_type_boolean,
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['4'],
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 3:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': fuel_type_boolean,
                                              '4': test_dict[key]['4'],
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 4:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': fuel_type_boolean,
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 5:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['4'],
                                              '5': fuel_type_boolean,
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 6:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['4'],
                                              '5': test_dict[key]['5'],
                                              '6': fuel_type_boolean,
                                              '7': test_dict[key]['7'],
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 7:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['7'],
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': fuel_type_boolean,
                                              '8': test_dict[key]['8']
                                              }
                        if cell.number == 8:
                            test_dict[key] = {'1': test_dict[key]['1'],
                                              '2': test_dict[key]['2'],
                                              '3': test_dict[key]['3'],
                                              '4': test_dict[key]['4'],
                                              '5': test_dict[key]['5'],
                                              '6': test_dict[key]['6'],
                                              '7': test_dict[key]['7'],
                                              '8': fuel_type_boolean
                                              }

        for cell in truck_tanks_variations:
            weigher_dict[str(cell.truck_id) + ":" + str(cell.variant_good)] = {'1': None,
                                                                               '2': None,
                                                                               '3': None,
                                                                               '4': None,
                                                                               '5': None,
                                                                               '6': None,
                                                                               '7': None,
                                                                               '8': None
                                                                               }

            weigher_variant_good_dict[cell.truck_id] = {'variant_good': []}

        for cell in truck_tanks_variations:
            if cell.variant_good not in weigher_variant_good_dict[cell.truck_id]['variant_good']:
                temp_list = list()
                temp_list.append(cell.variant_good)
                weigher_variant_good_dict[cell.truck_id] = {'variant_good':
                                                                weigher_variant_good_dict[cell.truck_id][
                                                                    'variant_good'] + temp_list
                                                            }

            for truck_cell in cells:
                if truck_cell.id == cell.truck_tank_id:
                    number = truck_cell.number

            key = str(cell.truck_id) + ':' + str(cell.variant_good)
            if number == 1:
                weigher_dict[key] = {'1': cell.diesel,
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 2:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': cell.diesel,
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 3:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': cell.diesel,
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 4:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': cell.diesel,
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 5:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': cell.diesel,
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 6:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': cell.diesel,
                                     '7': weigher_dict[key]['7'],
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 7:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': cell.diesel,
                                     '8': weigher_dict[key]['8']
                                     }

            if number == 8:
                weigher_dict[key] = {'1': weigher_dict[key]['1'],
                                     '2': weigher_dict[key]['2'],
                                     '3': weigher_dict[key]['3'],
                                     '4': weigher_dict[key]['4'],
                                     '5': weigher_dict[key]['5'],
                                     '6': weigher_dict[key]['6'],
                                     '7': weigher_dict[key]['7'],
                                     '8': cell.diesel
                                     }

        # перебираем список словарей
        for i in is_variant_sliv_good_list:
            # если все виды топлива данного варианта сливаются, то ячейку is_variant_good в таблице записываем True,
            # если же нет, то в ячейку is_variant_good пишем False
            if is_variant_good_list[str(i['variant'])]['is_it_92'] != 1 \
                    and is_variant_good_list[str(i['variant'])]['is_it_95'] != 1 \
                    and is_variant_good_list[str(i['variant'])]['is_it_50'] != 1:
                i['is_variant_good'] = True
                # добавляем получившийся словарь в список
                final_list.append(i)
            else:
                i['is_variant_good'] = False
                # добавляем получившийся словарь в список
                final_list.append(i)

        is_variant_weighter_good = list()
        is_variant_weighter_not_good = list()
        for i in final_list:
            key = str(i['variant']) + ':' + str(i['truck_id'])

            if key in test_dict:
                trig_final = 0  # Изначально считаем, что бензовоз нельзя везти если есть весы
                cells_list = list()

                cell_1 = test_dict[key]['1']
                cells_list.append(cell_1)
                cell_2 = test_dict[key]['2']
                cells_list.append(cell_2)
                cell_3 = test_dict[key]['3']
                cells_list.append(cell_3)
                cell_4 = test_dict[key]['4']
                cells_list.append(cell_4)
                cell_5 = test_dict[key]['5']
                cells_list.append(cell_5)
                cell_6 = test_dict[key]['6']
                cells_list.append(cell_6)
                cell_7 = test_dict[key]['7']
                cells_list.append(cell_7)
                cell_8 = test_dict[key]['8']
                cells_list.append(cell_8)

                for variant_good in weigher_variant_good_dict[i['truck_id']]['variant_good']:
                    variant_key = str(i['truck_id']) + ":" + str(variant_good)
                    weigher_list = list()

                    weigher_list.append(weigher_dict[variant_key]['1'])
                    weigher_list.append(weigher_dict[variant_key]['2'])
                    weigher_list.append(weigher_dict[variant_key]['3'])
                    weigher_list.append(weigher_dict[variant_key]['4'])
                    weigher_list.append(weigher_dict[variant_key]['5'])
                    weigher_list.append(weigher_dict[variant_key]['6'])
                    weigher_list.append(weigher_dict[variant_key]['7'])
                    weigher_list.append(weigher_dict[variant_key]['8'])

                    trig = 1  # Можно завозить дизель для этой комбинации налива
                    for index, cell in enumerate(cells_list):
                        if cells_list[index] == 50 and (weigher_list[index] == 0 or weigher_list[index] == None):
                            trig = 0  # Нельзя завозить дизель для этой комбинации налива
                            break

                    if trig == 1:  # Если можнно завозить дизель для одной их всевозможных комбинаций налива,
                        trig_final = 1  # то значит  можно завозить

                if trig_final == 1:  # Значит вариант подходит (дизель можно везти)!
                    is_variant_weighter_good.append(i['variant'])
                else:
                    is_variant_weighter_not_good.append(i['variant'])

        for i in final_list:
            if i['variant'] in is_variant_weighter_not_good:
                i['is_variant_weigher_good'] = False
            else:
                i['is_variant_weigher_good'] = True
            final_list2.append(i)
        # записываем данные из списка в базу
        db.engine.execute(TempAzsTrucks2.__table__.insert(), final_list2)
        return final_list2


    ''' функция отсеивает все варианты из таблицы TempAzsTrucks2 и дает им оценку'''
    def preparation_four():
        _set_task_progress(70)
        final_list = is_it_fit()
        # очищаем таблицу
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks3`")
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks4`")
        temp_azs_trucks3_list = list()
        fuel_realisation = FuelRealisation.query.all()
        days_stock_dict = dict()

        # перебираем список из предыдущей функции
        for i in final_list:
            # если вариант сливается, бензовоз может заехать на АЗС и бензовоз сливается полностью,
            # и бензовоз проходит через весы
            if i['is_it_fit_later'] == True and i['is_it_able_to_enter'] == True and i['is_variant_good'] == True \
                    and i['is_variant_sliv_good'] == True and i['is_variant_weigher_good'] == True:
                # добавляем словарь в список
                temp_azs_trucks3_list.append(i)
        new_days_stock_dict = dict()
        temp_azs_trucks4_dict = dict()

        for i in temp_azs_trucks3_list:
            temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': [],
                                                        'variant_sliv_95': [],
                                                        'variant_sliv_50': [],
                                                        'volume_92': [],
                                                        'volume_95': [],
                                                        'volume_50': [],
                                                        'azs_id': i['azs_id'],
                                                        'truck_id': i['truck_id']
                                                        }
        for i in temp_azs_trucks3_list:
            variant_sliv_92 = list()
            variant_sliv_95 = list()
            variant_sliv_50 = list()
            volume_92 = list()
            volume_95 = list()
            volume_50 = list()

            if i['fuel_type'] == 92:
                variant_sliv_92.append(i['variant_sliv'])
                volume_92.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_92'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_92'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_92'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'] + variant_sliv_92,
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'],
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'],
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'] + volume_92,
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'],
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'],
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])]['azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])]['truck_id']
                                                                }
            if i['fuel_type'] == 95:
                variant_sliv_95.append(i['variant_sliv'])
                volume_95.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_95'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_95'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_95'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'],
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'] + variant_sliv_95,
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'],
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'],
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'] + volume_95,
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'],
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'truck_id']

                                                                }
            if i['fuel_type'] == 50:
                variant_sliv_50.append(i['variant_sliv'])
                volume_50.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_50'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_50'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_50'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'],
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'],
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'] + variant_sliv_50,
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'],
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'],
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'] + volume_50,
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'truck_id']
                                                                }
        azs_trucks_4_list_final = list()
        azs_trucks_4_dict_final = {'variant': 0,
                                   'sum_92': 0,
                                   'sum_95': 0,
                                   'sum_50': 0,
                                   'min_rez1': 0,
                                   'min_rez2': 0,
                                   'min_rez3': 0,
                                   'variant_sliv_50': 0,
                                   'variant_sliv_92': 0,
                                   'variant_sliv_95': 0,
                                   'azs_id': 0,
                                   'truck_id': 0
                                   }

        for i in temp_azs_trucks4_dict:
            variant_sliv_92 = temp_azs_trucks4_dict[i]['variant_sliv_92']
            variant_sliv_95 = temp_azs_trucks4_dict[i]['variant_sliv_95']
            variant_sliv_50 = temp_azs_trucks4_dict[i]['variant_sliv_50']
            volume_92 = temp_azs_trucks4_dict[i]['volume_92']
            volume_95 = temp_azs_trucks4_dict[i]['volume_95']
            volume_50 = temp_azs_trucks4_dict[i]['volume_50']
            if len(variant_sliv_92) != 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) != 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_b, b in enumerate(variant_sliv_95):
                        for index_c, c in enumerate(variant_sliv_50):
                            azs_trucks_4_dict_final = {'variant': i,
                                                       'sum_92': volume_92[index_a],
                                                       'sum_95': volume_95[index_b],
                                                       'sum_50': volume_50[index_c],
                                                       'min_rez1': 0,
                                                       'min_rez2': 0,
                                                       'min_rez3': 0,
                                                       'variant_sliv_50': c,
                                                       'variant_sliv_92': a,
                                                       'variant_sliv_95': b,
                                                       'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                       'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                       }
                            azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

            if len(variant_sliv_92) != 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) == 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_b, b in enumerate(variant_sliv_95):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': volume_92[index_a],
                                                   'sum_95': volume_95[index_b],
                                                   'sum_50': 0,
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': 0,
                                                   'variant_sliv_92': a,
                                                   'variant_sliv_95': b,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

            if len(variant_sliv_92) != 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) != 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_c, c in enumerate(variant_sliv_50):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': volume_92[index_a],
                                                   'sum_95': 0,
                                                   'sum_50': volume_50[index_c],
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': c,
                                                   'variant_sliv_92': a,
                                                   'variant_sliv_95': 0,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) != 0:
                for index_b, b in enumerate(variant_sliv_95):
                    for index_c, c in enumerate(variant_sliv_50):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': 0,
                                                   'sum_95': volume_95[index_b],
                                                   'sum_50': volume_50[index_c],
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': c,
                                                   'variant_sliv_92': 0,
                                                   'variant_sliv_95': b,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) != 0:
                for index_c, c in enumerate(variant_sliv_50):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': 0,
                                               'sum_95': 0,
                                               'sum_50': volume_50[index_c],
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': c,
                                               'variant_sliv_92': 0,
                                               'variant_sliv_95': 0,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) == 0:
                for index_b, b in enumerate(variant_sliv_95):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': 0,
                                               'sum_95': volume_95[index_b],
                                               'sum_50': 0,
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': 0,
                                               'variant_sliv_92': 0,
                                               'variant_sliv_95': b,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) != 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) == 0:
                for index_a, a in enumerate(variant_sliv_92):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': volume_92[index_a],
                                               'sum_95': 0,
                                               'sum_50': 0,
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': 0,
                                               'variant_sliv_92': a,
                                               'variant_sliv_95': 0,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

        db.engine.execute(TempAzsTrucks3.__table__.insert(), temp_azs_trucks3_list)
        return azs_trucks_4_list_final, temp_azs_trucks3_list


    # определение худшего запаса суток среди всех резервуаров АЗС
    def preparation_six():
        _set_task_progress(75)
        # берем таблицу 4
        table_azs_trucks_4, table_azs_trucks_3 = preparation_four()
        table_azs_trucks_4_list = list()
        fuel_realisation = FuelRealisation.query.all()
        days_stock_old_dict = dict()
        for i in fuel_realisation:
            days_stock_old_dict[i.azs_id] = {'days_stock': [],
                                             'tank_id': []}

        for i in fuel_realisation:
            days_stock_min_old_list = [i.days_stock_min]
            tank_ids_list = [i.tank_id]
            days_stock_old_dict[i.azs_id] = {'days_stock': days_stock_old_dict[i.azs_id]['days_stock'] + days_stock_min_old_list,
                                             'tank_id': days_stock_old_dict[i.azs_id]['tank_id'] + tank_ids_list}
        variants_dict = dict()
        for i in table_azs_trucks_3:
            variants_dict[(i['variant'], i['variant_sliv'])] = {'days_stock': [],
                                                                'tank_id': []}
        for i in table_azs_trucks_3:
            days_stock_min_new_list = [i['new_days_stock']]
            tank_ids_list = [i['tank_id']]
            variants_dict[(i['variant'], i['variant_sliv'])] = {'days_stock': variants_dict[(i['variant'], i['variant_sliv'])]['days_stock'] + days_stock_min_new_list,
                                                                'tank_id': variants_dict[(i['variant'], i['variant_sliv'])]['tank_id'] + tank_ids_list
                                                                }
        for row in table_azs_trucks_4:

            variant = row['variant']
            variants_list = list()
            if row['variant_sliv_92']:
                variants_list.append(row['variant_sliv_92'])
            if row['variant_sliv_95']:
                variants_list.append(row['variant_sliv_95'])
            if row['variant_sliv_50']:
                variants_list.append(row['variant_sliv_50'])
            new_days_stock_dict = dict()
            tank_list = days_stock_old_dict[row['azs_id']]['tank_id']
            stock_list = days_stock_old_dict[row['azs_id']]['days_stock']
            for index, tank in enumerate(tank_list):
                new_days_stock_dict[tank] = stock_list[index]
            for variant_sliv in variants_list:
                tank_list_new = variants_dict[(int(row['variant']), variant_sliv)]['tank_id']
                stock_list_new = variants_dict[(int(row['variant']), variant_sliv)]['days_stock']
                for index, tank in enumerate(tank_list_new):
                    new_days_stock_dict[tank] = stock_list_new[index]

            sorted_new_days_stock_dict = sorted(new_days_stock_dict.items(), key=lambda x: x[1])
            temp_azs_trucks_4_dict = {'truck_id': row['truck_id'],
                                      'azs_id': row['azs_id'],
                                      'variant': row['variant'],
                                      'sum_92': row['sum_92'],
                                      'sum_95': row['sum_95'],
                                      'sum_50': row['sum_50'],
                                      'min_rez1': round(sorted_new_days_stock_dict[0][1], 1),
                                      'min_rez2': round(sorted_new_days_stock_dict[1][1], 1),
                                      'min_rez3': round(sorted_new_days_stock_dict[2][1], 1),
                                      'variant_sliv_92': row['variant_sliv_92'],
                                      'variant_sliv_95': row['variant_sliv_95'],
                                      'variant_sliv_50': row['variant_sliv_50']
                                      }
            table_azs_trucks_4_list.append(temp_azs_trucks_4_dict)

        db.engine.execute(TempAzsTrucks4.__table__.insert(), table_azs_trucks_4_list)
        _set_task_progress(100)
        logs = UserLogs(user_id=user_id,
                        action="preparation_ended",
                        timestamp=datetime.now())
        db.session.add(logs)
        db.session.commit()
    try:
        user = User.query.get(user_id)
        preparation_six()

    except:
        _set_task_progress(100)
        app.logger.error('Что-то пошло не так', exc_info=sys.exc_info())
