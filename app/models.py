import json
from datetime import datetime, timedelta
from time import time

import base64
import jwt
import os
import redis
import rq
from flask import current_app, url_for
from flask_login import UserMixin
from hashlib import md5
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login
from app.search import add_to_index, remove_from_index, query_index


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = query.paginate(page, per_page, False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page,
                                **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None
            }
        }
        return data


followers = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)


class User(UserMixin, PaginatedAPIMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(60))
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    messages_sent = db.relationship('Message',
                                    foreign_keys='Message.sender_id',
                                    backref='author', lazy='dynamic')
    messages_received = db.relationship('Message',
                                        foreign_keys='Message.recipient_id',
                                        backref='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship('Notification', backref='user',
                                    lazy='dynamic')
    tasks = db.relationship('Task', backref='user', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'],
            algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def new_messages(self):
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return Message.query.filter_by(recipient=self).filter(
            Message.timestamp > last_read_time).count()

    def add_notification(self, name, data):
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def launch_task(self, name, description, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue('app.tasks.' + name, self.id,
                                                *args, **kwargs)
        task = Task(id=rq_job.get_id(), name=name, description=description,
                    user=self)
        db.session.add(task)
        return task

    def get_tasks_in_progress(self):
        return Task.query.filter_by(user=self, complete=False).all()

    def get_task_in_progress(self, name):
        return Task.query.filter_by(name=name, user=self,
                                    complete=False).first()

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.isoformat() + 'Z',
            'about_me': self.about_me,
            'follower_count': self.followers.count(),
            'followed_count': self.followed.count(),
            '_links': {
                'self': url_for('api.get_user', id=self.id),
                'followers': url_for('api.get_followers', id=self.id),
                'followed': url_for('api.get_followed', id=self.id),
                'avatar': self.avatar(128)
            }
        }
        if include_email:
            data['email'] = self.email
        return data

    def from_dict(self, data, new_user=False):
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def get_token(self, expires_in=3600):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return '<Message {}>'.format(self.body)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.Float, index=True, default=time)
    payload_json = db.Column(db.Text)

    def get_data(self):
        return json.loads(str(self.payload_json))


class Task(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    complete = db.Column(db.Boolean, default=False)

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100


class AzsList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True)
    address = db.Column(db.String(140))
    phone = db.Column(db.String(140))
    email = db.Column(db.String(120))
    active = db.Column(db.Boolean)


class AzsSystems(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(40), unique=True)


class CfgDbConnection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'), unique=True)
    system_type = db.Column(db.Integer, db.ForeignKey('azs_systems.id'))
    ip_address = db.Column(db.String(240))
    port = db.Column(db.Integer)
    username = db.Column(db.String(120))
    password = db.Column(db.String(120))
    database = db.Column(db.String(120))


class Tanks(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'), index=True)  # айди АЗС из таблицы azs_list
    tank_number = db.Column(db.Integer)  # номер резервуара
    fuel_type = db.Column(db.Integer)  # вид топлива
    nominal_capacity = db.Column(db.Float)  # емкость резервуара по паспорту
    real_capacity = db.Column(db.Float)  # реальная емкость резервуара
    corrected_capacity = db.Column(db.Float)  # корректированная емкость резервуара
    dead_capacity = db.Column(db.Float)  # мертвый остаток
    drain_time = db.Column(db.Integer)  # время слива
    after_drain_time = db.Column(db.Integer)  # время после слива
    mixing = db.Column(db.Boolean)  # разрешено ли смешение топлива (для дизеля)
    active = db.Column(db.Boolean)  # завозить топливо или нет
    ams = db.Column(db.Boolean)  # есть ли автоматическая система измерения
    deactive = db.Column(db.Boolean)  # выключение резервуара из интерфейса

    __table_args__ = (db.UniqueConstraint('azs_id', 'tank_number'),)


# остатки в резервуарах
class FuelResidue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'), index=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))
    product_code = db.Column(db.Integer)  # код топлива
    percent = db.Column(db.Integer)  # процент заполненности резервуара
    fuel_level = db.Column(db.Float)  # уровень топлива в резервуаре
    fuel_volume = db.Column(db.Float)  # количество топлива в литрах
    free_volume = db.Column(db.Float)  # Свободный объем резервуара в литрах
    fuel_volume_percents = db.Column(db.Float)
    fuel_temperature = db.Column(db.Float)  #
    datetime = db.Column(db.DateTime)  # время замера в системе АЗС
    download_time = db.Column(db.DateTime)  # время в которое данные загружены в базу
    auto = db.Column(db.Boolean)  # данные загружены с видерута или по книжным остаткам?


# реализация топлива на азс
class FuelRealisation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'), index=True)
    shop_id = db.Column(db.Integer, index=True)  # ПЕРЕИМЕНОВАТЬ В azs_id после релиза и связать с AzsList
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), index=True)
    product_code = db.Column(db.Integer)  # код топлива
    average_1_days = db.Column(db.Float)  # среднее значение реализации за сутки
    average_3_days = db.Column(db.Float)  # среднее значение реализации за 3 сутон
    average_7_days = db.Column(db.Float)  # среднее значение реализации за 7 суток
    average_10_days = db.Column(db.Float)  # среднее значение реализации за 10 суток
    average_week_ago = db.Column(db.Float)  # среднее значение реализации за сутки неделю назад
    fuel_realisation_1_days = db.Column(db.Float)  # реализация за 1 сутки
    fuel_realisation_3_days = db.Column(db.Float)  # реализация за 3 суток
    fuel_realisation_7_days = db.Column(db.Float)  # реализация за 7 суток
    fuel_realisation_10_days = db.Column(db.Float)  # реализация за 10 суток
    fuel_realisation_hour = db.Column(db.Float)  # реадизация за последний час
    fuel_realisation_max = db.Column(db.Float)  # максимальная реализация за все периоды
    day_stock_10 = db.Column(db.Float)  # запас суток (10 дней)
    day_stock_7 = db.Column(db.Float)  # запас суток (7 дней)
    day_stock_3 = db.Column(db.Float)  # запас суток (3 дней)
    day_stock_1 = db.Column(db.Float)  # запас суток (1 дн)
    day_stock_week_ago = db.Column(db.Float)  # неделю назад
    days_stock_min = db.Column(db.Float)  # минимальный запас суток из всех диапазонов
    download_time = db.Column(db.DateTime)  # время в которое данные загружены в базу
    fuel_realisation_week_ago = db.Column(db.Float)  # реализация за такой же день неделю назад
    average_for_azs = db.Column(db.Float)  # средний запас суток среди резервуаров


class Trucks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(30))  # номер машины
    trailer_reg_number = db.Column(db.String(40))  # номер прицепа
    seals = db.Column(db.Integer)  # пломбы
    weight = db.Column(db.Integer)  # вес бензовоза сухой
    weight_limit = db.Column(db.Integer)  # ограничение массы
    driver = db.Column(db.String(120))  # ФИО водителя
    day_start = db.Column(db.Time)
    day_end = db.Column(db.Time)
    manual_tanks = db.Column(db.String(120), db.ForeignKey('truck_tanks.id'))
    manual_fuel_tanks = db.Column(db.Integer)
    active = db.Column(db.Boolean)  # активен?


class TruckTanks(db.Model):  # резервуары бензовоза
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer)  # порядковый номер резервуара
    diesel = db.Column(db.Boolean)  # при наличии весов только дизель, если True
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    capacity = db.Column(db.Integer)  # вместимость резервуара


class PriorityList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_stock_from = db.Column(db.Float)  # запас суток от
    day_stock_to = db.Column(db.Float)  # запас суток до
    priority = db.Column(db.Integer)  # приоритет
    sort_method = db.Column(db.Integer)  # метод сортировки


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # к какой азс привязано по id
    distance = db.Column(db.Integer)  # расстояние до азс от нефтебазы
    time_to_before_lunch = db.Column(db.Integer)  # время до АЗС от нефтебазы до обеда (минуты)
    time_from_before_lunch = db.Column(db.Integer)  # время от АЗС до нефтебазы до обеда (минуты)
    time_to = db.Column(db.Integer)  # время до АЗС от нефтебазы (минуты)
    time_from = db.Column(db.Integer)  # время от АЗС до нефтебазы (минуты)
    weigher = db.Column(db.String(20))  # весы


class Priority(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), unique=True)
    day_stock = db.Column(db.Float)  # запас суток
    priority = db.Column(db.Integer, unique=True)  # номер в очереди
    table_priority = db.Column(db.Integer, db.ForeignKey('priority_list.id'))
    average_for_azs = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)


class ManualInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), unique=True)
    fuel_realisation_max = db.Column(db.Float)  # максимальная реализация за все периоды
    fuel_volume = db.Column(db.Float)  # количество топлива в литрах
    timestamp = db.Column(db.DateTime)  # время ввода данных


class TruckFalse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # к какой азс привязан по id
    reason = db.Column(db.String(120))
    timestamp = db.Column(db.DateTime)


class WorkType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(600))  # режим работы приложения
    fuel_type = db.Column(db.String(10))  # вид топлива
    days_stock_limit = db.Column(db.String(10))
    active = db.Column(db.Boolean)  # активен или нет


class TempAzsTrucks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, index=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    truck_tank_id = db.Column(db.Integer, db.ForeignKey('truck_tanks.id'))
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    fuel_type = db.Column(db.Integer)
    capacity = db.Column(db.Integer)
    cells_92 = db.Column(db.Integer)
    cells_95 = db.Column(db.Integer)
    cells_50 = db.Column(db.Integer)


class TempAzsTrucks2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant = db.Column(db.Integer, index=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant_sliv = db.Column(db.Integer)
    fuel_type = db.Column(db.Integer)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))  # айдишник резервуара с этим типом топлива (Tanks)
    str_sliv = db.Column(db.String(120))
    sum_sliv = db.Column(db.Integer)  # сумма количества топлива по ячейкам бензовоза с одним видом топлива
    truck_tank_id_string = db.Column(db.String(60))
    is_it_fit = db.Column(db.Boolean)  # входит ли топливо в резервуары?
    is_it_fit_later = db.Column(db.Boolean)  # войдет ли позже?
    is_it_fit_on_second_trip = db.Column(db.Boolean)  # войдет ли при втором рейсе?
    new_fuel_volume = db.Column(db.Float)  # новый объем
    new_days_stock = db.Column(db.Float)  # новый запас суток
    second_new_fuel_volume = db.Column(db.Float)  # новый объем для второго рейса
    second_new_days_stock = db.Column(db.Float)  # новый запас суток для второго рейса
    is_it_able_to_enter = db.Column(db.Boolean)  # сможет ли заехать бензовоз
    is_variant_good = db.Column(db.Boolean)  # подходит ли этот вариант?
    is_variant_sliv_good = db.Column(db.Boolean)  # подходит ли этот вариант слива?
    is_variant_weigher_good = db.Column(db.Boolean)  # подходит ли вариант налива, если на пути есть весы


class TempAzsTrucks2SecondTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant = db.Column(db.Integer, index=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant_sliv = db.Column(db.Integer)
    fuel_type = db.Column(db.Integer)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))  # айдишник резервуара с этим типом топлива (Tanks)
    str_sliv = db.Column(db.String(120))
    sum_sliv = db.Column(db.Integer)  # сумма количества топлива по ячейкам бензовоза с одним видом топлива
    truck_tank_id_string = db.Column(db.String(60))
    is_it_fit = db.Column(db.Boolean)  # входит ли топливо в резервуары?
    is_it_fit_on_second_trip = db.Column(db.Boolean)  # войдет ли при втором рейсе?
    second_new_fuel_volume = db.Column(db.Float)  # новый объем для второго рейса
    second_new_days_stock = db.Column(db.Float)  # новый запас суток для второго рейса
    is_it_able_to_enter = db.Column(db.Boolean)  # сможет ли заехать бензовоз
    is_variant_good = db.Column(db.Boolean)  # подходит ли этот вариант?
    is_variant_sliv_good = db.Column(db.Boolean)  # подходит ли этот вариант слива?
    is_variant_weigher_good = db.Column(db.Boolean)  # подходит ли вариант налива, если на пути есть весы
    is_trip_end_time_good = db.Column(db.Boolean)  # успеет ли бензовоз вернуться до конца рабочего дня


class TempAzsTrucks3(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant = db.Column(db.Integer, index=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant_sliv = db.Column(db.Integer)
    fuel_type = db.Column(db.Integer)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))  # айдишник резервуара с этим типом топлива (Tanks)
    sum_sliv = db.Column(db.Integer)  # сумма количества топлива по ячейкам бензовоза с одним видом топлива
    truck_tank_id_string = db.Column(db.String(60))
    new_fuel_volume = db.Column(db.Float)  # новый объем
    new_days_stock = db.Column(db.Float)  # новый запас суток


class TempAzsTrucks4(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant = db.Column(db.Integer)
    sum_92 = db.Column(db.Integer)
    sum_95 = db.Column(db.Integer)
    sum_50 = db.Column(db.Integer)
    min_rez1 = db.Column(db.Float)
    min_rez2 = db.Column(db.Float)
    min_rez3 = db.Column(db.Float)
    variant_sliv_92 = db.Column(db.Integer)
    variant_sliv_95 = db.Column(db.Integer)
    variant_sliv_50 = db.Column(db.Integer)


class TempAzsTrucks3SecondTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant = db.Column(db.Integer, index=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant_sliv = db.Column(db.Integer)
    fuel_type = db.Column(db.Integer)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))  # айдишник резервуара с этим типом топлива (Tanks)
    sum_sliv = db.Column(db.Integer)  # сумма количества топлива по ячейкам бензовоза с одним видом топлива
    truck_tank_id_string = db.Column(db.String(60))
    new_fuel_volume = db.Column(db.Float)  # новый объем
    new_days_stock = db.Column(db.Float)  # новый запас суток


class TempAzsTrucks4SecondTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))  # к какому бензовозу привязан по id
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    variant = db.Column(db.Integer)
    sum_92 = db.Column(db.Integer)
    sum_95 = db.Column(db.Integer)
    sum_50 = db.Column(db.Integer)
    min_rez1 = db.Column(db.Float)
    min_rez2 = db.Column(db.Float)
    min_rez3 = db.Column(db.Float)
    variant_sliv_92 = db.Column(db.Integer)
    variant_sliv_95 = db.Column(db.Integer)
    variant_sliv_50 = db.Column(db.Integer)


class Errors(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))
    error_type = db.Column(db.String(60))
    error_text = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime)
    active = db.Column(db.Boolean)


class UserLogs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(160))
    timestamp = db.Column(db.DateTime)


class Close1Tank1(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close1Tank2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close1Tank3(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close1Tank4(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close1Tank5(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close2Tank1(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close2Tank2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close2Tank3(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close2Tank4(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close2Tank5(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close3Tank1(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close3Tank2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close3Tank3(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close3Tank4(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close3Tank5(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close4Tank1(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close4Tank2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close4Tank3(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close4Tank4(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Close4Tank5(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))
    sliv_id = db.Column(db.Integer)


class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tank1 = db.Column(db.String(120))
    tank2 = db.Column(db.String(120))
    tank3 = db.Column(db.String(120))
    tank4 = db.Column(db.String(120))


class RealisationStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))  # айдишник азс из таблицы azs_list
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))
    realisation = db.Column(db.Float)
    fuel_type = db.Column(db.Integer)
    fuel_type_name = db.Column(db.String(40))
    date = db.Column(db.DateTime)


class Trips(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_number = db.Column(db.Integer)  # порядковый номер рейса
    date = db.Column(db.DateTime)
    day = db.Column(db.Date)
    work_type_id = db.Column(db.Integer, db.ForeignKey('work_type.id'))
    variant_number = db.Column(db.Integer)  # номер предложеного варианта расстановки
    calculate_id = db.Column(db.Integer)
    incorrect = db.Column(db.Boolean)  # на случай создания новой расстановки, отмечаем старую неактивной
    file_name = db.Column(db.String(600))  # xlsx файл для распечатки


#  результат расстановки бензовозов
class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))
    variant = db.Column(db.Integer)  # вариант налива бензовоза
    variant_sliv_92 = db.Column(db.Integer)  # вариант слива бензовоза для 92 топлива
    variant_sliv_95 = db.Column(db.Integer)  # вариант слива бензовоза для 95 топлива
    variant_sliv_50 = db.Column(db.Integer)  # вариант слива бензовоза для 50 топлива
    min_rez1 = db.Column(db.Float)  # новый минимальный запас суток среди всех резервуаров азс
    min_rez2 = db.Column(db.Float)
    min_rez3 = db.Column(db.Float)
    volume_92 = db.Column(db.Integer)  # сколько 92 топлива будет слито
    volume_95 = db.Column(db.Integer)  # сколько 95 топлива будет слито
    volume_50 = db.Column(db.Integer)  # сколько 50 топлива будет слито
    time_to_return = db.Column(db.Integer)  # сколько времени бензовоз был в пути
    calculate_id = db.Column(db.Integer)  # порядковый номер расстановки
    trip_number = db.Column(db.Integer)  # порядковый номер рейса
    trip_end_time = db.Column(db.Time)  # время возвращения на нефтебазу


class TrucksForAzs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))
    number_of_trucks = db.Column(db.Integer)
    calculate_id = db.Column(db.Integer)
    trip_number = db.Column(db.Integer)


class VariantNalivaForTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant_from_table = db.Column(db.Integer)  # айди варианта налива из таблицы azs_trucks (на всякий случай)
    calculate_id = db.Column(db.Integer)
    truck_tank_id = db.Column(db.Integer, db.ForeignKey('truck_tanks.id'))
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))
    fuel_type = db.Column(db.Integer)
    capacity = db.Column(db.Integer)
    trip_number = db.Column(db.Integer)


class VariantSlivaForTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant_from_table = db.Column(db.Integer)  # айди варианта слива из таблицы azs_trucks (на всякий случай)
    calculate_id = db.Column(db.Integer)
    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'))
    truck_tank_id = db.Column(db.String(60))
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))
    fuel_type = db.Column(db.Integer)
    capacity = db.Column(db.Integer)
    trip_number = db.Column(db.Integer)


class TruckTanksVariations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variant_good = db.Column(db.Integer)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))
    truck_tank_id = db.Column(db.Integer, db.ForeignKey('truck_tanks.id'))
    diesel = db.Column(db.Boolean)


class GlobalSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40))
    trip_number = db.Column(db.Integer)  # к какому рейсу относится настройка
    description = db.Column(db.String(600))
    algorithm_id = db.Column(db.Integer, db.ForeignKey('global_settings_params.id'))


class GlobalSettingsParams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_id = db.Column(db.Integer, db.ForeignKey('global_settings.id'))
    value = db.Column(db.Integer)
    description = db.Column(db.String(120))
    active = db.Column(db.Boolean)


#  результат расстановки бензовозов
class TripResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azs_number = db.Column(db.String(20))
    truck_reg_number = db.Column(db.String(20))
    fuel_types = db.Column(db.String(120))
    fuel_capacities = db.Column(db.String(120))
    sliv_tanks = db.Column(db.String(120))
    disp_name = db.Column(db.String(120))
    driver_name = db.Column(db.String(120))
    date = db.Column(db.String(120))

    azs_id = db.Column(db.Integer, db.ForeignKey('azs_list.id'))
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'))
    variant = db.Column(db.Integer)  # вариант налива бензовоза
    variant_sliv_92 = db.Column(db.Integer)  # вариант слива бензовоза для 92 топлива
    variant_sliv_95 = db.Column(db.Integer)  # вариант слива бензовоза для 95 топлива
    variant_sliv_50 = db.Column(db.Integer)  # вариант слива бензовоза для 50 топлива
    min_rez1 = db.Column(db.Float)  # новый минимальный запас суток среди всех резервуаров азс
    min_rez2 = db.Column(db.Float)
    min_rez3 = db.Column(db.Float)
    volume_92 = db.Column(db.Integer)  # сколько 92 топлива будет слито
    volume_95 = db.Column(db.Integer)  # сколько 95 топлива будет слито
    volume_50 = db.Column(db.Integer)  # сколько 50 топлива будет слито
    time_to_return = db.Column(db.Integer)  # сколько времени бензовоз был в пути
    calculate_id = db.Column(db.Integer)  # порядковый номер расстановки
    trip_number = db.Column(db.Integer)  # порядковый номер рейса
    trip_end_time = db.Column(db.Time)  # время возвращения на нефтебазу


class FuelReports(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fuel_type = db.Column(db.Integer)
    fuel_volume = db.Column(db.Float)
    free_volume = db.Column(db.Float)
    fuel_realisation = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)
