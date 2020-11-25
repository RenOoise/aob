# фоновая загрузка данных о реализации за 1 сутки
import sys
from datetime import datetime
import psycopg2

from app import create_app, db
from app.models import CfgDbConnection, AzsList, RealisationStats

date = datetime.today()
app = create_app()
app.app_context().push()


def download_realisation_info():
    azs = AzsList.query.filter_by(active=True).order_by("number").all()  # получаем список активных АЗС
    try:
        for i in azs:  # перебираем список азс
            test = CfgDbConnection.query.filter_by(azs_id=i.id).first()
            if test is not None:  # если тестирование соединения успешно
                
                if test.system_type == 2:
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
                                             "where endstamp between current_TIMESTAMP - interval '30 day' " \
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
                                    print('realisation: ', row[1], 'azs_id: ', i.id, 'fuel_type: ', row[0])

                            finally:
                                if (connection):
                                    cursor.close()
                                    connection.close()
                                    print("Соединение закрыто")
                        except(Exception, psycopg2.Error) as error:
                            print("Ошибка во время получения данных", error)
                            pass
                
    except:
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())


download_realisation_info()
