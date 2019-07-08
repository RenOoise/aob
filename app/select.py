import psycopg2
from app import create_app, db
from app.models import FuelResidue, CfgDbConnection, FuelRealisation

app = create_app()
app.app_context().push()

try:
    connection = psycopg2.connect(user="db_report",
                                  password="db_report",
                                  host="172.19.8.20",
                                  port="5432",
                                  database="ubuk")
    cursor = connection.cursor()
    sql = ("SELECT tanknum, prodcod, lvl, volume, t FROM pj_tanks WHERE optime > now() - interval '10 days';")
    cursor.execute(sql)
    query = cursor.fetchall()
    for row in query:
        print(row[0], row[1], row[2],row[3], row[4])
        with app.app_context():
            FuelRealisation(tank_id=row[0], product_code=row[1], fuel_level=[2], fuel_volume=[3], fuel_temperature=[4])
            db.session.add(sql)
            db.session.commit()
except(Exception, psycopg2.Error) as error:
    print("Error while fetching data", error)

finally:
    if(connection):
        cursor.close()
        connection.close()
        print("Connection is closed")

