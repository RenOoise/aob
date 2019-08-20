# фоновая загрузка данных
import sys
from app import create_app, db
from app.models import FuelResidue, CfgDbConnection, FuelRealisation, AzsList, Tanks, Priority, PriorityList, Trip
import psycopg2
from datetime import datetime
import fdb
from time import sleep
import pandas as pd
from datetime import date, time, timedelta


app = create_app()
app.app_context().push()


def add_data(collected_data):
    add = FuelRealisation(shop_id=collected_data['shop_id'],
                          azs_id=collected_data['azs_id'],
                          tank_id=collected_data['tank_id'],
                          product_code=collected_data['product_code'],
                          fuel_realisation_10_days=collected_data['fuel_realisation_10_days'],
                          fuel_realisation_1_days=collected_data['fuel_realisation_1_days'],
                          fuel_realisation_3_days=collected_data['fuel_realisation_3_days'],
                          fuel_realisation_7_days=collected_data['fuel_realisation_7_days'],
                          fuel_realisation_week_ago=collected_data['fuel_realisation_week_ago'],
                          download_time=collected_data['download_time'],
                          average_10_days=collected_data['average_10_days'],
                          average_7_days=collected_data['average_7_days'],
                          average_3_days=collected_data['average_3_days'])
    return add


def update_data(add, collected_data):
    add = add
    add.fuel_realisation_10_days = collected_data['fuel_realisation_10_days']
    add.fuel_realisation_7_days = collected_data['fuel_realisation_7_days']
    add.fuel_realisation_3_days = collected_data['fuel_realisation_3_days']
    add.fuel_realisation_1_days = collected_data['fuel_realisation_1_days']
    add.fuel_realisation_week_ago = collected_data['fuel_realisation_week_ago']
    add.fuel_realisation_hour = collected_data['fuel_realisation_hour']
    add.average_3_days = collected_data['average_3_days']
    add.average_7_days = collected_data['average_7_days']
    add.average_10_days = collected_data['average_10_days']
    add.shop_id = collected_data['shop_id']
    add.azs_id = collected_data['azs_id']
    add.tank_id = collected_data['tank_id']
    add.product_code = collected_data['product_code']
    add.download_time = collected_data['download_time']
    return add


def download_tanks_info():
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    try:
        for i in azs:  # перебираем список азс
            QueryFromDb(i.id).download_tanks_info()
    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def download_realisation_info():
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    try:
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
                            print("Подключение к базе " + str(azs_config.database) + " на сервере " +
                                  str(azs_config.ip_address) + " успешно")
                            try:
                                sql_10_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                              " WHERE id_shop = " \
                                              + str(i.number) + \
                                              " and begtime between current_TIMESTAMP - interval '10 day'" \
                                              " and current_TIMESTAMP and (err=0 or err=2)" \
                                              " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_10_days)
                                query_10 = cursor.fetchall()

                                sql_7_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                             " WHERE id_shop = " \
                                             + str(i.number) + \
                                             " and begtime between current_TIMESTAMP - interval '7 day'" \
                                             " and current_TIMESTAMP and (err=0 or err=2)" \
                                             " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_7_days)
                                query_7 = cursor.fetchall()

                                sql_3_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                             " WHERE id_shop = " \
                                             + str(i.number) + \
                                             " and begtime between current_TIMESTAMP - interval '3 day'" \
                                             " and current_TIMESTAMP and (err=0 or err=2)" \
                                             " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_3_days)
                                query_3 = cursor.fetchall()

                                sql_1_days = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                             " WHERE id_shop = " \
                                             + str(i.number) + \
                                             " and begtime between current_TIMESTAMP - interval '1 day'" \
                                             " and current_TIMESTAMP and (err=0 or err=2)" \
                                             " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_1_days)
                                query_1 = cursor.fetchall()

                                sql_week_ago = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                               " WHERE id_shop = " \
                                               + str(i.number) + \
                                               " and begtime between current_TIMESTAMP - interval '8 day'" \
                                               " and current_TIMESTAMP - interval '7 day' and (err=0 or err=2)" \
                                               " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_week_ago)
                                query_week_ago = cursor.fetchall()

                                sql_hour = "SELECT id_shop, product, tank, sum(volume) as volume FROM pj_td " \
                                           " WHERE id_shop = " \
                                           + str(i.number) + \
                                           " and begtime between current_TIMESTAMP - interval '6 hour'" \
                                           " and current_TIMESTAMP and (err=0 or err=2)" \
                                           " GROUP BY id_shop, product, tank ORDER BY tank"
                                cursor.execute(sql_hour)
                                query_hour = cursor.fetchall()
                                collected_data = {'shop_id': 0,
                                                  'azs_id': 0,
                                                  'tank_id': 0,
                                                  'product_code': 0,
                                                  'download_time': 0,
                                                  'fuel_realisation_1_days': 0,
                                                  'fuel_realisation_3_days': 0,
                                                  'fuel_realisation_7_days': 0,
                                                  'fuel_realisation_10_days': 0,
                                                  'fuel_realisation_week_ago': 0,
                                                  'fuel_realisation_hour': 0,
                                                  'average_10_days': 0,
                                                  'average_7_days': 0,
                                                  'average_3_days': 0,
                                                  'average_1_days': 0,
                                                  'average_week_ago': 0}

                                print("SQL запрос книжных остатков на АЗС №" + str(azs_config.ip_address) + " выполнен")

                                for row in query_10:
                                    print('collect rows')
                                    tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[2]).first()
                                    add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()

                                    for fr_1_d in query_1:
                                        if fr_1_d[2] is row[2]:
                                            collected_data['fuel_realisation_1_days'] = fr_1_d[3]

                                    for fr_3_d in query_3:
                                        if fr_3_d[2] is row[2]:
                                            collected_data['fuel_realisation_3_days'] = fr_3_d[3]
                                            collected_data['average_3_days'] = collected_data['fuel_realisation_3_days'] / 3
                                    for fr_7_d in query_7:
                                        if fr_7_d[2] is row[2]:
                                            collected_data['fuel_realisation_7_days'] = fr_7_d[3]
                                            collected_data['average_7_days'] = collected_data['fuel_realisation_7_days'] / 7
                                    for fr_10_d in query_10:
                                        if fr_10_d[2] is row[2]:
                                            collected_data['fuel_realisation_10_days'] = fr_10_d[3]
                                            collected_data['average_10_days'] = collected_data['fuel_realisation_10_days'] / 10
                                    for fr_week_ago in query_week_ago:
                                        if fr_week_ago[2] is row[2]:
                                            if fr_week_ago[2] <= 0 or fr_week_ago[2] is False:
                                                collected_data['fuel_realisation_week_ago'] = 2
                                            else:
                                                collected_data['fuel_realisation_week_ago'] = fr_week_ago[3]
                                    for fr_hour in query_hour:
                                        if fr_hour[2] is row[2]:

                                            collected_data['fuel_realisation_hour'] = fr_hour[3]

                                    collected_data['shop_id'] = i.number
                                    collected_data['azs_id'] = i.id
                                    collected_data['tank_id'] = tankid.id
                                    collected_data['product_code'] = row[1]
                                    collected_data['download_time'] = datetime.now()
                                    app.logger.info(collected_data)

                                    if add:
                                        add = update_data(add, collected_data)
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                    else:
                                        add = add_data(collected_data)
                                        db.session.add(add)
                                        db.session.commit()
                            finally:
                                if (connection):
                                    cursor.close()
                                    connection.close()

                        except(Exception, psycopg2.Error) as error:
                            print("Ошибка во время получения данных", error)
                            pass
                            print("Соединение закрыто")

                elif test.system_type == 2:
                    azs_config = CfgDbConnection.query.filter_by(system_type=2, azs_id=i.id).first()
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
                            try:
                                sql_10_days = "select tank, gas, sum(litres) volume from filling " \
                                              "where endstamp between current_TIMESTAMP - interval '10 day' " \
                                              "and current_TIMESTAMP " \
                                              "group by tank, gas order by tank"
                                cursor.execute(sql_10_days)
                                query_10 = cursor.fetchall()

                                sql_7_days = "select tank, gas, sum(litres) volume from filling " \
                                             "where endstamp between current_TIMESTAMP - interval '7 day' " \
                                             "and current_TIMESTAMP " \
                                             "group by tank, gas order by tank"
                                cursor.execute(sql_7_days)
                                query_7 = cursor.fetchall()

                                sql_3_days = "select tank, gas, sum(litres) volume from filling " \
                                             "where endstamp between current_TIMESTAMP - interval '3day' " \
                                             "and current_TIMESTAMP " \
                                             "group by tank, gas order by tank"
                                cursor.execute(sql_3_days)
                                query_3 = cursor.fetchall()

                                sql_1_days = "select tank, gas, sum(litres) volume from filling " \
                                             "where endstamp between current_TIMESTAMP - interval '1 day' " \
                                             "and current_TIMESTAMP " \
                                             "group by tank, gas order by tank"
                                cursor.execute(sql_1_days)
                                query_1 = cursor.fetchall()

                                sql_week_ago = "select tank, gas, sum(litres) volume from filling " \
                                               "where endstamp between current_TIMESTAMP - interval '8 day' " \
                                               "and current_TIMESTAMP - interval '7 day' " \
                                               "group by tank, gas order by tank"

                                cursor.execute(sql_week_ago)
                                query_week_ago = cursor.fetchall()

                                sql_hour = "select tank, gas, sum(litres) volume from filling " \
                                           "where endstamp between current_TIMESTAMP - interval '6 hour' " \
                                           "and current_TIMESTAMP " \
                                           "group by tank, gas order by tank"
                                cursor.execute(sql_hour)
                                query_hour = cursor.fetchall()

                                collected_data = {'shop_id': 0,
                                                  'azs_id': 0,
                                                  'tank_id': 0,
                                                  'product_code': 0,
                                                  'download_time': 0,
                                                  'fuel_realisation_1_days': 0,
                                                  'fuel_realisation_3_days': 0,
                                                  'fuel_realisation_7_days': 0,
                                                  'fuel_realisation_10_days': 0,
                                                  'fuel_realisation_week_ago': 0,
                                                  'fuel_realisation_hour': 0,
                                                  'average_10_days': 0,
                                                  'average_7_days': 0,
                                                  'average_3_days': 0,
                                                  'average_1_days': 0,
                                                  'average_week_ago': 0}

                                print("SQL запрос книжных остатков на АЗС №" + str(
                                    azs_config.ip_address) + " выполнен")

                                for row in query_10:
                                    tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[0], active=True).first()
                                    add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()
                                    for fr_1_d in query_1:
                                        if fr_1_d[0] is row[0]:
                                            collected_data['fuel_realisation_1_days'] = fr_1_d[2]

                                    for fr_3_d in query_3:
                                        if fr_3_d[0] is row[0]:
                                            collected_data['fuel_realisation_3_days'] = fr_3_d[2]
                                            collected_data['average_3_days'] = collected_data['fuel_realisation_3_days'] / 3

                                    for fr_7_d in query_7:
                                        if fr_7_d[0] is row[0]:
                                            collected_data['fuel_realisation_7_days'] = fr_7_d[2]
                                            collected_data['average_7_days'] = collected_data['fuel_realisation_7_days'] / 7
                                    for fr_10_d in query_10:
                                        if fr_10_d[0] is row[0]:
                                            collected_data['fuel_realisation_10_days'] = fr_10_d[2]
                                            collected_data['average_10_days'] = collected_data['fuel_realisation_10_days'] / 10

                                    for fr_week_ago in query_week_ago:
                                        if fr_week_ago[0] is row[0]:
                                            collected_data['fuel_realisation_week_ago'] = fr_week_ago[2]

                                    for fr_hour in query_hour:
                                        if fr_hour[0] is row[0]:
                                            collected_data['fuel_realisation_hour'] = fr_hour[2] / 2

                                    collected_data['shop_id'] = i.number
                                    collected_data['azs_id'] = i.id
                                    collected_data['tank_id'] = tankid.id
                                    collected_data['product_code'] = row[1]
                                    collected_data['download_time'] = datetime.now()
                                    app.logger.info(collected_data)

                                    if add:
                                        add = update_data(add, collected_data)
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                    else:
                                        add = add_data(collected_data)
                                        db.session.add(add)
                                        db.session.commit()
                            finally:
                                if (connection):
                                    cursor.close()
                                    connection.close()
                                    print("Соединение закрыто")

                        except(Exception, psycopg2.Error) as error:
                            print("Ошибка во время получения данных", error)
                            pass

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
                            query_10 = cursor.fetchall()
                            sql_7_days = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                         "where datetime >= current_date-7 group by 1,fuel_id, tank"
                            cursor.execute(sql_7_days)
                            query_7 = cursor.fetchall()
                            sql_3_days = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                         "where datetime >= current_date-3 group by 1,fuel_id, tank"
                            cursor.execute(sql_3_days)
                            query_3 = cursor.fetchall()
                            sql_1_days = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                         "where datetime >= current_date-1 group by 1,fuel_id, tank"
                            cursor.execute(sql_1_days)
                            query_1 = cursor.fetchall()
                            sql_week_ago = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                           "where datetime >= current_date-1 group by 1,fuel_id, tank"
                            cursor.execute(sql_week_ago)
                            query_week_ago = cursor.fetchall()
                            sql_addmin = "DECLARE EXTERNAL FUNCTION ADDMINUTE TIMESTAMP, INTEGER " \
                                         "RETURNS TIMESTAMP " \
                                         "ENTRY_POINT 'addMinute' MODULE_NAME 'fbudf';"
                            cursor.execute(sql_addmin)

                            sql_hour = "select fuel_id, tank, sum(factvolume) as volume from gsmarchive " \
                                       "where datetime > ADDMINUTE(CURRENT_TIMESTAMP, -360) group by 1,fuel_id, tank"
                            cursor.execute(sql_hour)
                            query_hour = cursor.fetchall()

                            collected_data = {'shop_id': 0,
                                              'azs_id': 0,
                                              'tank_id': 0,
                                              'product_code': 0,
                                              'download_time': 0,
                                              'fuel_realisation_1_days': 0,
                                              'fuel_realisation_3_days': 0,
                                              'fuel_realisation_7_days': 0,
                                              'fuel_realisation_10_days': 0,
                                              'fuel_realisation_week_ago': 0,
                                              'fuel_realisation_hour': 0,
                                              'average_10_days': 0,
                                              'average_7_days': 0,
                                              'average_3_days': 0,
                                              'average_1_days': 0,
                                              'average_week_ago': 0}

                            for row in query_10:
                                tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[0]).first()
                                add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()

                                product_code = 0
                                if row[1] is 1:
                                    product_code = 95
                                elif row[1] is 2:
                                    product_code = 92
                                elif row[1] is 3:
                                    product_code = 50
                                elif row[1] is 4:
                                    product_code = 51

                                for fr_1_d in query_1:
                                    if fr_1_d[1] is row[1]:
                                        collected_data['fuel_realisation_1_days'] = fr_1_d[2]
                                        collected_data['average_10_days'] = collected_data[
                                                                                'fuel_realisation_10_days'] / 10
                                for fr_3_d in query_3:
                                    if fr_3_d[1] is row[1]:
                                        collected_data['fuel_realisation_3_days'] = fr_3_d[2]
                                        collected_data['average_3_days'] = collected_data['fuel_realisation_3_days'] / 3
                                for fr_7_d in query_7:
                                    if fr_7_d[1] is row[1]:
                                        collected_data['fuel_realisation_7_days'] = fr_7_d[2]
                                        collected_data['average_7_days'] = collected_data['fuel_realisation_7_days'] / 7
                                for fr_10_d in query_10:
                                    if fr_10_d[1] is row[1]:
                                        collected_data['fuel_realisation_10_days'] = fr_10_d[2]
                                        collected_data['average_10_days'] = collected_data['fuel_realisation_10_days'] / 10
                                for fr_week_ago in query_week_ago:
                                    if fr_week_ago[1] is row[1]:
                                        collected_data['fuel_realisation_week_ago'] = fr_week_ago[2]
                                for fr_hour in query_hour:
                                    if fr_hour[1] is row[1]:
                                        collected_data['fuel_realisation_hour'] = fr_hour[2]

                                collected_data['shop_id'] = i.number
                                collected_data['azs_id'] = i.id
                                collected_data['tank_id'] = tankid.id
                                collected_data['product_code'] = product_code
                                collected_data['download_time'] = datetime.now()
                                app.logger.info(collected_data)

                                if add:
                                    add = update_data(add, collected_data)
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                else:
                                    add = add_data(collected_data)
                                    db.session.add(add)
                                    db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)

    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def day_stock(azs_id):
    azs_number = AzsList.query.filter_by(id=azs_id).first_or_404()
    realisation = FuelRealisation.query.filter_by(shop_id=azs_number.number).all()
    residue = FuelResidue.query.filter_by(azs_id=azs_id).all()

    for fuel in residue:
        for data in realisation:
            if fuel.tank_id is data.tank_id:
                add = FuelRealisation.query.filter_by(tank_id=data.tank_id).first_or_404()

                # считаем среднюю реализацию за сутки
                try:
                    average_day_stock_10 = data.fuel_realisation_10_days / 10
                    average_day_stock_7 = data.fuel_realisation_7_days / 7
                    average_day_stock_3 = data.fuel_realisation_3_days / 3
                    average_day_stock_1 = data.fuel_realisation_1_days / 1
                    average_day_stock_week_ago = data.fuel_realisation_week_ago / 1

                    # считаем запас суток по усредненной реалезации
                    days_stock_10 = round(fuel.fuel_volume / average_day_stock_10, 1)
                    days_stock_7 = round(fuel.fuel_volume / average_day_stock_7, 1)
                    days_stock_3 = round(fuel.fuel_volume / average_day_stock_3, 1)
                    days_stock_1 = round(fuel.fuel_volume / average_day_stock_1, 1)
                    days_stock_week_ago = round(fuel.fuel_volume / average_day_stock_week_ago)
                    days_stock_min = min([days_stock_10, days_stock_7, days_stock_3, days_stock_1, days_stock_week_ago])
                    add.day_stock_10 = days_stock_10
                    add.day_stock_7 = days_stock_7
                    add.day_stock_3 = days_stock_3
                    add.day_stock_1 = days_stock_1
                    add.days_stock_week_ago = days_stock_week_ago
                    add.days_stock_min = days_stock_min
                    db.session.add(add)
                    db.session.commit()
                except Exception as e:
                    print(e)
                    pass


class QueryFromDb(object):
    def __init__(self, id):
        conn_cfg = CfgDbConnection.query.filter_by(azs_id=id).first()
        azs = AzsList.query.filter_by(id=id).first_or_404()
        self.id = id
        self.ip_address = conn_cfg.ip_address
        self.username = conn_cfg.username
        self.password = conn_cfg.password
        self.database = conn_cfg.database
        self.system_type = conn_cfg.system_type
        self.number = azs.number

    def download_tanks_info(self):
        if self.system_type == 1:  # если БукТС
            if self.id:  # если есть конфиг
                try:
                    connection = QueryFromDb(self.id).connection()
                    cursor = connection.cursor()
                    try:
                        tanks = Tanks.query.filter_by(azs_id=self.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(self.database) + " на сервере " +
                              str(self.ip_address) + " успешно")
                        for id in tanks:  # перебераем резервуары
                            if id.active and id.ams:  # если активен и есть система автоматического измерения,
                                # то строим запрос к базе
                                sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                       "FROM pj_tanks WHERE tanknum = "
                                       + str(id.tank_number) +
                                       " ORDER BY optime DESC LIMIT 1;")
                                cursor.execute(sql)
                                print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС №" + str(
                                    self.number) + " выполнен")
                                query = cursor.fetchall()
                                for row in query:
                                    azsid = AzsList.query.filter_by(number=row[0]).first()
                                    tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=row[1]).first()
                                    add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()

                                    percent = (100*(float(row[4])/tankid.corrected_capacity))

                                    if add:
                                        add.fuel_level = row[3]
                                        add.fuel_volume = row[4]
                                        add.fuel_temperature = row[5]
                                        add.datetime = row[6]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.product_code = row[2]
                                        add.download_time = datetime.now()
                                        add.percent = percent
                                        add.auto = True
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                    else:
                                        add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                          fuel_level=row[3], fuel_volume=row[4],
                                                          fuel_temperature=row[5], datetime=row[6], percent=percent,
                                                          download_time=datetime.now(), auto=True)
                                        db.session.add(add)
                                        db.session.commit()
                            elif id.active and id.ams is False:
                                # если резервуар активен, но системы измерения нет, то получаем остаток
                                sql = ("SELECT id_shop, tanknum, prodcod, lvl, volume, t, optime "
                                       "FROM pj_tanks WHERE tanknum = "
                                       + str(id.tank_number) +
                                       " ORDER BY optime DESC LIMIT 1;")
                                cursor.execute(sql)
                                print("SQL запрос Книжных остатков по резервуару " + str(id.tank_number) + " на АЗС №" + str(
                                    self.number) + " выполнен")
                                query = cursor.fetchall()

                                # и делаем выборку по реализации с начала смены
                                realisation = (
                                        "SELECT pj_td.id_shop, pj_td.product, pj_td.tank, sum(pj_td.volume) as volume "
                                        "FROM pj_td, sj_tranz WHERE pj_td.id_shop=" + str(self.number) + " and pj_td.tank="
                                        + str(id.tank_number) +
                                        "and pj_td.begtime between current_TIMESTAMP - interval '1 day' "
                                        "and current_TIMESTAMP and (pj_td.err=0 or pj_td.err=2) "
                                        "and sj_tranz.id_shop=pj_td.id_shop "
                                        "and pj_td.trannum=sj_tranz.trannum "
                                        "and sj_tranz.shift=(select max(num) from sj_shifts where id_shop=" + str(
                                    self.number) +
                                        "and begtime between current_TIMESTAMP - interval '2 day' "
                                        "and current_TIMESTAMP ) GROUP BY pj_td.id_shop, pj_td.product, pj_td.tank")

                                cursor.execute(realisation)
                                realisation = cursor.fetchall()

                                for row in query:

                                    tankid = Tanks.query.filter_by(azs_id=self.id, tank_number=row[1]).first()
                                    add = FuelResidue.query.filter_by(azs_id=self.id, tank_id=tankid.id).first()
                                    percent = (100 * (float(query[0][4] - realisation[0][3]) / tankid.corrected_capacity))
                                    if add:
                                        add.fuel_level = row[3]
                                        add.fuel_volume = query[0][4] - realisation[0][3]
                                        add.fuel_temperature = row[5]
                                        add.datetime = row[6]
                                        add.azs_id = self.id
                                        add.tank_id = tankid.id
                                        add.product_code = row[2]
                                        add.download_time = datetime.now()
                                        add.percent = percent
                                        add.auto = False
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                    else:
                                        add = FuelResidue(azs_id=self.id, tank_id=tankid.id, product_code=row[2],
                                                          fuel_level=row[3], fuel_volume=query[0][4] - realisation[0][3],
                                                          fuel_temperature=row[5], datetime=row[6],
                                                          download_time=datetime.now(), percent=percent, auto=False)
                                        db.session.add(add)
                                        db.session.commit()
                    finally:
                        if (connection):
                            cursor.close()
                            connection.close()
                            print("Соединение закрыто")

                except(Exception, psycopg2.Error) as error:
                    print("Ошибка во время получения данных", error)
                    pass

        # если система oilix
        elif self.system_type == 2:
            # дергаем конфиги для подключения к БД на АЗС
            azs_config = CfgDbConnection.query.filter_by(system_type=2, azs_id=self.id).first()
            # если есть конфиг для данной азс
            if azs_config:
                try:
                    connection = QueryFromDb(self.id).connection()
                    cursor = connection.cursor()
                    try:
                        tanks = Tanks.query.filter_by(azs_id=self.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(azs_config.database) + " на сервере " + str(
                            azs_config.ip_address) + " успешно")
                        for id in tanks:  # перебераем резервуары
                            if id.active and id.ams:
                                # если активен и есть система автоматического измерения, то строим запрос к базе

                                sql = ("SELECT id, calculatedvolume, comment, density, incomeactive, "
                                       "insideincomefillinglitres, level, lmsvolume, stamp, tank, temperature, volume, "
                                       "water "
                                       "FROM tanklmsinfo WHERE tank="
                                       + str(id.tank_number) +
                                       " ORDER BY stamp desc limit 1")

                                cursor.execute(sql)
                                print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(
                                    self.number) + " выполнен")
                                query = cursor.fetchall()

                                for row in query:
                                    azsid = AzsList.query.filter_by(number=self.number).first()
                                    tankid = Tanks.query.filter_by(azs_id=azsid.id, tank_number=id.tank_number).first()
                                    add = FuelResidue.query.filter_by(azs_id=azsid.id, tank_id=tankid.id).first()
                                    percent = (100 * (float(row[3]) / tankid.corrected_capacity))
                                    if add:
                                        add.fuel_level = row[6]
                                        add.fuel_volume = row[7]
                                        add.fuel_temperature = row[10]
                                        add.datetime = row[8]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.product_code = id.fuel_type
                                        add.percent = percent
                                        add.download_time = datetime.now()
                                        add.auto = True
                                        db.session.add(add)
                                        try:
                                            db.session.commit()
                                        except Exception as error:
                                            print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                    else:
                                        add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id,
                                                          product_code=id.fuel_type, fuel_level=row[6],
                                                          fuel_volume=row[7], fuel_temperature=row[10],
                                                          datetime=row[8], download_time=datetime.now(),
                                                          percent=percent, auto=True)
                                        db.session.add(add)
                                        db.session.commit()

                            elif id.active and id.ams is False:
                                # если резервуар активен, но системы измерения нет, то получаем остаток
                                sql = ("select code, startvolume"
                                       " from TankShiftInfo "
                                       "where shiftinfo_id "
                                       "in (select id from shiftinfo "
                                       "order by shiftdate DESC limit 1) order by code;")
                                cursor.execute(sql)
                                residue = cursor.fetchall()

                                finished = ("select shiftdate from shiftinfo order by shiftdate DESC limit 1")
                                cursor.execute(finished)
                                shiftdate = cursor.fetchall()

                                print("SQL запрос по резервуару " + str(id.tank_number) + " на АЗС " + str(
                                    self.number) + " выполнен")
                                print(residue)

                                # и делаем выборку по реализации с начала смены
                                realisation = ("select tank, gas, sum(litres) volume from filling fl "
                                               "join payment pm on fl.payment_id = pm.id "
                                               "join bninfo bi on pm.bnmode = bi.code "
                                               "where fl.shiftinfo_id "
                                               "in (select id from shiftinfo order by number desc limit 1) "
                                               "and not bi.tosign group by tank, gas order by tank")

                                cursor.execute(realisation)
                                realisation = cursor.fetchall()

                                for row in residue:
                                    tankid = Tanks.query.filter_by(azs_id=self.id, tank_number=row[0]).first()
                                    add = FuelResidue.query.filter_by(azs_id=self.id, tank_id=tankid.id).first()
                                    for realis in realisation:
                                        if add:
                                            if row[0] is tankid.tank_number:
                                                resid = row[1] - realis[2]
                                                percent = (100 * (float(resid) / tankid.corrected_capacity))
                                                # add.fuel_level = row[3]
                                                add.fuel_volume = resid
                                                add.percent = percent
                                                # add.fuel_temperature = row[5]
                                                add.datetime = shiftdate[0]
                                                add.azs_id = self.id
                                                add.tank_id = tankid.id
                                                add.product_code = tankid.fuel_type
                                                add.download_time = datetime.now()
                                                add.auto = False
                                                db.session.add(add)
                                                try:
                                                    db.session.commit()
                                                except Exception as error:
                                                    print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                        else:
                                            if row[0] is tankid.tank_number:
                                                resid = row[1] - realis[2]
                                                percent = (100 * (float(resid) / tankid.corrected_capacity))
                                                add = FuelResidue(azs_id=self.id, tank_id=tankid.id,
                                                                  product_code=tankid.fuel_type,
                                                                  fuel_volume=row[1] - realis[2],
                                                                  datetime=shiftdate[0],
                                                                  download_time=datetime.now(), percent=percent,
                                                                  auto=False)
                                            db.session.add(add)
                                            db.session.commit()
                    finally:
                        if (connection):
                            cursor.close()
                            connection.close()
                            print("Соединение закрыто")

                except (Exception, psycopg2.Error) as error:
                    print("Ошибка подключения к серверу" + error)
                    pass
        # если система serviopump
        elif self.system_type == 3:
            print("SERVIOPUMP!")
            if self.id:  # если есть конфиг
                try:
                    connection = fdb.connect(
                        dsn=self.ip_address + ':' + self.database,
                        user=self.username,
                        password=self.password)

                    cursor = connection.cursor()
                    try:
                        tanks = Tanks.query.filter_by(azs_id=self.id, active=True).all()  # получаем список резервуаров
                        print("Подключение к базе " + str(self.database) + " на сервере " + str(
                            self.ip_address) + " успешно")
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
                                    self.number) + " выполнен")
                                query = cursor.fetchall()
                                for row in query:
                                    azsid = AzsList.query.filter_by(number=self.number).first()
                                    tankid = Tanks.query.filter_by(azs_id=self.id, tank_number=id.tank_number).first()
                                    add = FuelResidue.query.filter_by(azs_id=self.id, tank_id=tankid.id).first()
                                    if add:
                                        add.fuel_volume = row[3]
                                        percent = (100 * (float(row[3]) / tankid.corrected_capacity))
                                        print(percent)
                                        add.datetime = row[2]
                                        add.shop_id = azsid.id
                                        add.tank_id = tankid.id
                                        add.percent = percent
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
                                            print("Данные по АЗС № " + str(self.number) + " не найдены", error)
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
                                        percent = (100 * (float(row[3]) / tankid.corrected_capacity))
                                        add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=product_code,
                                                          fuel_level=0, fuel_volume=row[3],
                                                          fuel_temperature=0, datetime=row[2],
                                                          download_time=datetime.now(), percent=percent, auto=True)
                                        db.session.add(add)
                                        db.session.commit()
                    finally:
                        if (connection):
                            cursor.close()
                            connection.close()
                            print("Соединение закрыто")

                except Exception as error:
                    pass
                    print("Ошибка во время получения данных", error)

    def download_realisation_info(self):
        print("realis")

    def connection(self):
        connection = psycopg2.connect(user=self.username,
                                      password=self.password,
                                      host=self.ip_address,
                                      database=self.database,
                                      connect_timeout=10)
        return connection


def sum_time(first, second):
    sum = timedelta()
    timeList = [str(first), str(second)]
    for time in timeList:
        (h, m, s) = time.split(':')
        d = timedelta(hours=int(h), minutes=int(m), seconds=int(s))
        sum += d
    return sum


def priority_sort(sorted_list):
    counterX = 0

    priority_list = PriorityList.query.order_by('priority').all()

    final_list = list()

    for pl in priority_list:
        temp_list = list()
        counterX = counterX + 1
        for tbl_pr in sorted_list:
            if tbl_pr['table_priority'] == pl.id:
                trip = Trip.query.filter_by(azs_id=int(tbl_pr['azs_id'])).first_or_404()
                tbl_pr['distance'] = trip.distance
                tbl_pr['time_before'] = sum_time(trip.time_to_before_lunch, trip.time_from_before_lunch)
                tbl_pr['time_after'] = sum_time(trip.time_to, trip.time_from)
                temp_list.append(tbl_pr)
        try:
            if temp_list:
                if pl.sort_method == "1":
                    df = pd.DataFrame(temp_list)
                    test = df.sort_values('distance', ascending=False).to_dict('r')
                    for i in test:
                        final_list.append(i)

                elif pl.sort_method == "2":
                    df = pd.DataFrame(temp_list)
                    test = df.sort_values('distance').to_dict('r')
                    for i in test:
                        final_list.append(i)

                elif pl.sort_method == "3":
                    df = pd.DataFrame(temp_list)
                    test = df.sort_values('time_before', ascending=False).to_dict('r')
                    for i in test:
                        final_list.append(i)

                elif pl.sort_method == "4":
                    df = pd.DataFrame(temp_list)
                    test = df.sort_values('time_before').to_dict('r')
                    for i in test:
                        final_list.append(i)

        except Exception as e:
            print(e)
            pass
    for i in final_list:
        print(i)
    return final_list


def azs_priority():
    azs_list = AzsList.query.order_by("number").filter_by(active=True).all()
    priority = Priority.query.all()
    for i in priority:
        db.session.delete(i)
        db.session.commit()
    realisation_count = FuelRealisation.query.order_by("days_stock_min").count()
    counter_list = 0
    unsorted_list = []
    for azs in azs_list:
        realisation = FuelRealisation.query.filter_by(azs_id=azs.id).all()
        min_tank = []
        average_azs_stock = 0
        for tank in realisation:
            tank_id = Tanks.query.filter_by(id=tank.tank_id).first()
            if tank_id.active:
                if not pd.isnull(tank.days_stock_min) or tank.days_stock_min is not None:
                    counter_list = counter_list + 1
                    azs_tanks = {'number': azs.number,
                                 'azs_id': tank.azs_id,
                                 'tank_id': tank.tank_id,
                                 'day_stock': tank.days_stock_min,
                                 'priority': 0,
                                 'day_stock_average_by_tank': average_azs_stock,
                                 'table_priority': 0}
                    min_tank.append(azs_tanks)
                else:
                    counter_list = counter_list + 1
                    azs_tanks = {'number': azs.number,
                                 'azs_id': tank.azs_id,
                                 'tank_id': tank.tank_id,
                                 'day_stock': 0,
                                 'priority': 0,
                                 'day_stock_average_by_tank': average_azs_stock,
                                 'table_priority': 0}
                    min_tank.append(azs_tanks)
        df = pd.DataFrame(min_tank)
        test_list = df.sort_values('day_stock').to_dict('r')
        unsorted_list.append(test_list[0])
    df = pd.DataFrame(unsorted_list)
    sorted_list = df.sort_values('day_stock').to_dict('r')
    # print(sorted_list)
    priority_list = PriorityList.query.all()
    counter = 1
    for pr in sorted_list:
        tank = Tanks.query.filter_by(id=pr['tank_id']).first()
        for tp in priority_list:
            if tp.day_stock_from <= pr['day_stock'] <= tp.day_stock_to:
                priority_id = PriorityList.query.filter_by(priority=tp.priority).first_or_404()
                pr['table_priority'] = priority_id.id
        if tank.active is not None or tank.active is True:
            if counter <= realisation_count:
                priority_sorted = Priority(azs_id=int(pr['azs_id']), day_stock=float(pr['day_stock']),
                                           tank_id=int(pr['tank_id']),
                                           priority=counter, table_priority=int(pr['table_priority']),
                                           average_for_azs=float(pr['day_stock_average_by_tank']),
                                           timestamp=datetime.now())
                db.session.add(priority_sorted)
                db.session.commit()
                counter += 1
        else:
            print('Резервуар не активен!')
    final = priority_sort(sorted_list)
    priority = Priority.query.all()

    for i in priority:
        db.session.delete(i)
        db.session.commit()
    counter = 1
    for priority in final:

        if counter <= realisation_count:

            priority_sorted = Priority(azs_id=priority['azs_id'], day_stock=priority['day_stock'], tank_id=priority['tank_id'],
                                       priority=counter, table_priority=priority['table_priority'], timestamp=datetime.now())
            try:
                db.session.add(priority_sorted)
                db.session.commit()
            except Exception as error:
                print(error)
                pass

        counter += 1


download_tanks_info()
download_realisation_info()
test = AzsList.query.order_by("number").all()
for i in test:
    azs_id = i.id
    day_stock(azs_id)
sleep(2)
azs_priority()
