# фоновая загрузка данных
import sys
from app import create_app, db
from app.models import FuelResidue, CfgDbConnection, FuelRealisation, AzsList, Tanks, Priority, PriorityList
import psycopg2
from datetime import datetime
import fdb
from time import sleep
app = create_app()
app.app_context().push()


def download_tanks_info():
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    try:
        for i in azs:  # перебираем список азс
            QueryFromDb(i.id).download_tanks_info()
    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def download_realisation_info():
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    azs_count = AzsList.query.filter_by(active=True).count()  # получаем количество активных АЗС
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
                            print("SQL запрос книжных остатков на АЗС №" + str(
                                azs_config.ip_address) + " выполнен")
                            for row in query_10:

                                tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[2]).first()
                                add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()

                                if add:
                                    add.fuel_realisation_10_days = row[3]
                                    add.fuel_realisation_3_days = query_3[0][3]
                                    add.fuel_realisation_7_days = query_7[0][3]
                                    add.fuel_realisation_1_days = query_1[0][3]
                                    add.shop_id = i.number
                                    add.azs_id = i.id
                                    add.tank_id = tankid.id
                                    add.product_code = row[1]
                                    add.download_time = datetime.now()
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(row[0]) + " не найдены", error)
                                else:
                                    add = FuelRealisation(shop_id=i.number, azs_id=i.id,
                                                          tank_id=tankid.id,
                                                          product_code=row[1],
                                                          fuel_realisation_10_days=row[3],
                                                          fuel_realisation_1_days=query_1[0][3],
                                                          fuel_realisation_3_days=query_3[0][3],
                                                          fuel_realisation_7_days=query_7[0][3],
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
                                         "where endstamp between current_TIMESTAMP - interval '0 day' " \
                                         "and current_TIMESTAMP " \
                                         "group by tank, gas order by tank"
                            cursor.execute(sql_1_days)
                            query_1 = cursor.fetchall()
                            print(query_10)
                            print("SQL запрос книжных остатков на АЗС №" + str(
                                azs_config.ip_address) + " выполнен")
                            for row in query_10:
                                tankid = Tanks.query.filter_by(azs_id=i.id, tank_number=row[0]).first()
                                add = FuelRealisation.query.filter_by(shop_id=i.number, tank_id=tankid.id).first()

                                if add:
                                    add.fuel_realisation_10_days = row[2]
                                    add.shop_id = i.number
                                    add.azs_id = i.id
                                    add.tank_id = tankid.id
                                    add.product_code = row[1]
                                    add.download_time = datetime.now()
                                    db.session.add(add)
                                    try:
                                        db.session.commit()
                                    except Exception as error:
                                        print("Данные по АЗС № " + str(azs.number) + " не найдены", error)
                                else:
                                    add = FuelRealisation(shop_id=i.number, azs_id=i.id,
                                                          tank_id=tankid.id,
                                                          product_code=row[1],
                                                          fuel_realisation_10_days=row[2],
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
                                    add = FuelRealisation(shop_id=i.number, tank_id=tankid.id, azs_id=i.id,
                                                          product_code=product_code, fuel_realisation_10_days=row[2],
                                                          download_time=datetime.now())
                                    db.session.add(add)
                                    db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)


    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


def calculate_days_stock(azs_id):
    azs_number = AzsList.query.filter_by(id=azs_id).first_or_404()
    realisation = FuelRealisation.query.filter_by(shop_id=azs_number.number).all()
    residue = FuelResidue.query.filter_by(azs_id=azs_id).all()


def realisation(azs_id):
    azs_number = AzsList.query.filter_by(id=azs_id).first_or_404()
    realisation = FuelRealisation.query.filter_by(shop_id=azs_number.number).all()
    residue = FuelResidue.query.filter_by(azs_id=azs_id).all()

    for fuel in residue:
        for data in realisation:
            if fuel.tank_id is data.tank_id:
                add = FuelRealisation.query.filter_by(tank_id=data.tank_id).first_or_404()
                days_stock_10 = fuel.fuel_volume / (data.fuel_realisation_10_days / 10)
                days_stock_10 = round(days_stock_10, 2)
                add.day_stock_10 = days_stock_10
                db.session.add(add)
                db.session.commit()
                print('АЗС ' + str(azs_number.number) + ' ' + str(days_stock_10))


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
                                        print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                else:
                                    add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=row[2],
                                                      fuel_level=row[3], fuel_volume=row[4],
                                                      fuel_temperature=row[5], datetime=row[6],
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
                                if add:
                                    add.fuel_level = row[3]
                                    add.fuel_volume = query[0][4] - realisation[0][3]
                                    add.fuel_temperature = row[5]
                                    add.datetime = row[6]
                                    add.azs_id = self.id
                                    add.tank_id = tankid.id
                                    add.product_code = row[2]
                                    add.download_time = datetime.now()
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
        elif self.system_type == 2:
            # дергаем конфиги для подключения к БД на АЗС
            azs_config = CfgDbConnection.query.filter_by(system_type=2, azs_id=self.id).first()
            # если есть конфиг для данной азс
            if azs_config:
                try:
                    connection = QueryFromDb(self.id).connection()

                    cursor = connection.cursor()
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
                                        print("Данные по АЗС № " + str(self.number) + " не найдены", error)
                                else:
                                    add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id,
                                                      product_code=id.fuel_type, fuel_level=row[6],
                                                      fuel_volume=row[7], fuel_temperature=row[10],
                                                      datetime=row[8], download_time=datetime.now(), auto=True)
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
                                            # add.fuel_level = row[3]
                                            add.fuel_volume = resid
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
                                            add = FuelResidue(azs_id=self.id, tank_id=tankid.id,
                                                              product_code=tankid.fuel_type,
                                                              fuel_volume=row[1] - realis[2],
                                                              datetime=shiftdate[0],
                                                              download_time=datetime.now(), auto=False)
                                        db.session.add(add)
                                        db.session.commit()

                except (Exception, psycopg2.Error) as error:
                    print( error)


                finally:
                    if (connection):
                        cursor.close()
                        connection.close()
                        print("Соединение закрыто")

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
                                    add = FuelResidue(azs_id=azsid.id, tank_id=tankid.id, product_code=product_code,
                                                      fuel_level=0, fuel_volume=row[3],
                                                      fuel_temperature=0, datetime=row[2],
                                                      download_time=datetime.now(), auto=True)
                                    db.session.add(add)
                                    db.session.commit()
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


def azs_priority():
    priority = Priority.query.all()
    for i in priority:
        db.session.delete(i)
        db.session.commit()
    priority_list = PriorityList.query.all()
    realisation = FuelRealisation.query.order_by("day_stock_10").all()
    realisation_count = FuelRealisation.query.order_by("day_stock_10").count()

    counter = 1
    for pr in realisation:
        tank = Tanks.query.filter_by(id=pr.tank_id).first_or_404()
        azs = AzsList.query.filter_by(id=pr.azs_id).first_or_404()
        if tank.active:
            if counter <= realisation_count:
                priority_sorted = Priority(azs_id=pr.azs_id, day_stock=pr.day_stock_10, tank_id=pr.tank_id,
                                           priority=counter)
                db.session.add(priority_sorted)
                db.session.commit()
                counter += 1
        else:
            print("Резервуар №" + str(tank.tank_number) + " на АЗС №" + str(azs.number) + " отключен")


azs_priority()
download_tanks_info()
download_realisation_info()
azs_priority()
test = AzsList.query.order_by("number").all()

for i in test:
    azs_id = i.id
    realisation(azs_id)
sleep(2)


