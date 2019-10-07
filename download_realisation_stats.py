# фоновая загрузка данных о реализации за 1 сутки
import sys
from app import create_app, db
from app.models import CfgDbConnection, FuelRealisation, AzsList, Tanks, RealisationStats
import psycopg2
from datetime import datetime
import fdb
date = datetime.today()
app = create_app()
app.app_context().push()


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
                                sql_1_days = "SELECT id_shop, product, sum(volume) as volume FROM pj_td " \
                                             " WHERE id_shop = " \
                                             + str(i.number) + \
                                             " and begtime between current_TIMESTAMP - interval '1 day'" \
                                             " and current_TIMESTAMP and (err=0 or err=2)" \
                                             " GROUP BY id_shop, product"
                                cursor.execute(sql_1_days)
                                query = cursor.fetchall()
                                collected_data = {'azs_id': 0,
                                                  'fuel_type': 0,
                                                  'date': 0,
                                                  'realisation': 0}
                                for row in query:
                                    collected_data['realisation'] = row[2]
                                    collected_data['azs_id'] = i.id
                                    collected_data['fuel_type'] = row[1]
                                    collected_data['date'] = date
                                    app.logger.info(collected_data)
                                    add = RealisationStats(azs_id=collected_data['azs_id'],
                                                           fuel_type=collected_data['fuel_type'],
                                                           realisation=collected_data['realisation'],
                                                           date=collected_data['date'])
                                    db.session.add(add)
                                    db.session.commit()
                            finally:
                                if (connection):
                                    cursor.close()
                                    connection.close()
                        except(Exception, psycopg2.Error) as error:
                            print("Ошибка во время получения данных", error)
                            pass
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
                                sql_1_days = "select gas, sum(litres) volume from filling " \
                                             "where endstamp between current_TIMESTAMP - interval '1 day' " \
                                             "and current_TIMESTAMP " \
                                             "group by gas"
                                cursor.execute(sql_1_days)
                                query_1 = cursor.fetchall()
                                collected_data = {'azs_id': 0,

                                                  'fuel_type': 0,
                                                  'date': 0,
                                                  'realisation': 0}

                                print("SQL запрос книжных остатков на АЗС №" + str(
                                    i.number) + " выполнен")

                                for row in query_1:
                                    collected_data['realisation'] = row[1]
                                    collected_data['azs_id'] = i.id
                                    collected_data['fuel_type'] = row[0]
                                    collected_data['date'] = date
                                    app.logger.info(collected_data)
                                    add = RealisationStats(azs_id=collected_data['azs_id'],
                                                           fuel_type=collected_data['fuel_type'],
                                                           realisation=collected_data['realisation'],
                                                           date=collected_data['date'])
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

                            sql_1_days = "select fuel_id, sum(factvolume) as volume from gsmarchive " \
                                         "where datetime >= current_date-1 group by 1,fuel_id"
                            cursor.execute(sql_1_days)
                            query_1 = cursor.fetchall()
                            collected_data = {'azs_id': 0,
                                              'fuel_type': 0,
                                              'date': 0,
                                              'realisation': 0}
                            for row in query_1:
                                product_code = 0
                                if row[1] is 1:
                                    product_code = 95
                                elif row[1] is 2:
                                    product_code = 92
                                elif row[1] is 3:
                                    product_code = 50
                                elif row[1] is 4:
                                    product_code = 51
                                collected_data['realisation'] = row[1]
                                collected_data['azs_id'] = i.id
                                collected_data['fuel_type'] = product_code
                                collected_data['date'] = date
                                app.logger.info(collected_data)
                                add = RealisationStats(azs_id=collected_data['azs_id'],

                                                       fuel_type=collected_data['fuel_type'],
                                                       realisation=collected_data['realisation'],
                                                       date=collected_data['date'])
                                db.session.add(add)
                                db.session.commit()
                        except Exception as error:
                            pass
                            print("Ошибка во время получения данных", error)
    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


download_realisation_info()

