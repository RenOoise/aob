from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.reports import bp
from app.models import FuelResidue, AzsList, Tanks
import psycopg2
from sqlalchemy import desc, func


@bp.route('/reports/index', methods=['GET', 'POST'])
@login_required
def index():
    # Получаем данные о реализации за сутки определенного дня
    connection = psycopg2.connect(user="sl",
                                  password="sl",
                                  host="192.168.150.191",
                                  database="oilix-head-server",
                                  connect_timeout=10)

    def realisation():
        table = list()
        try:
            cursor = connection.cursor()
            print("Подключаюсь к базе oilix-head-server")
            try:
                sql = "select gas, sum(litres) volume from filling " \
                      "where endstamp BETWEEN '2020-11-27 00:00:00'::timestamp " \
                      "AND '2020-11-28 00:00:00'::timestamp " \
                      "group by gas order by gas;"
                cursor.execute(sql)
                print('Получаю данные о реализации за сутки')
                query = cursor.fetchall()

                for row in query:
                    collected_data = {'product_code': row[0],
                                      'fuel_realisation': row[1]
                                      }
                    table.append(collected_data)

            finally:
                if (connection):
                    cursor.close()
                    connection.close()
                    print("Соединение с базой закрыто")
        except(Exception, psycopg2.Error) as error:
            print("Ошибка во время получения данных", error)
            pass
        return table

    # получаем инфу об остатках и свободном месте в резервуарах всех АЗС
    def tanks_info():
        test = 0
        table = list()
        residue = FuelResidue.query.all()
        #residue = FuelResidue.query.with_entities(FuelResidue.product_code, func.sum(FuelResidue.free_volume), func.sum(FuelResidue.fuel_volume)).group_by(FuelResidue.product_code).all()
        for i in residue:
            test = test + int(i.fuel_volume)
            

    tanks_info()
    return render_template('reports/index.html', title="Отчеты", reports_active=True)
