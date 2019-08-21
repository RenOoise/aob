from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, PasswordField, IntegerField, FloatField, \
    BooleanField, FieldList
from wtforms_components import TimeField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, IPAddress
from flask_babel import _, lazy_gettext as _l
from app.models import User


class AddUserForm(FlaskForm):
    username = StringField(_l('Имя пользователя'), validators=[DataRequired()])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Пароль'), validators=[DataRequired()])
    password2 = PasswordField(
        _l('Повторите пароль'), validators=[DataRequired(),
                                           EqualTo('password')])
    role = SelectField('Роль', choices=[('admin', 'Администратор'), ('dispatcher', 'Диспетчер'),
                                        ('director', 'Директор'), ('manager', 'Менеджер')])
    submit = SubmitField(_l('Создать'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_('Пожалуйста введите другое имя.'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError(_('Пожалуйста введите другой почтовый адрес.'))


class AddTankForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    tank = SelectField(_l('Номер резервуара'), choices=[('1', 1), ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6),
                                                        ('7', 7), ('8', 8), ('9', 9), ('10', 10)],
                        validators=[DataRequired()])
    fuel_type = SelectField(_l('Тип топлива'), choices=[('95', 95), ('92', 92), ('50', 50), ('51', 51)],
                            validators=[DataRequired()])
    nominal_capacity = FloatField(_l('Номинальный объем (л)'), validators=[DataRequired()])
    real_capacity = FloatField(_l('Действующий объем (л)'), validators=[DataRequired()])
    dead_capacity = FloatField('Мервый остаток (л)')
    # corrected_capacity = IntegerField(_l('Скорректированная емкость'), validators=[DataRequired()])
    drain_time = IntegerField(_l('Время слива'), validators=[DataRequired()])
    after_drain_time = IntegerField(_l('Время после слива'), validators=[DataRequired()])
    mixing = BooleanField(_l('Смешение'))
    active = BooleanField(_l('Активен'))
    ams = BooleanField(_l('АИС'))
    submit = SubmitField('Добавить')


class AddAzsForm(FlaskForm):
    number = IntegerField(_l('Номер АЗС'), validators=[DataRequired()])
    address = StringField(_l('Адрес'), validators=[DataRequired()])
    phone = StringField(_l('Телефон'), validators=[DataRequired()])
    email = StringField(_l('Email'), Email())
    active = BooleanField(_l('Активна?'), validators=[DataRequired()])
    submit = SubmitField('Добавить')


class EditAzsForm(FlaskForm):
    number = IntegerField(_l('Номер АЗС'), validators=[DataRequired()])
    address = StringField(_l('Адрес'), validators=[DataRequired()])
    phone = StringField(_l('Телефон'), validators=[DataRequired()])
    email = StringField(_l('Email'), validators=[Email("Неправильный E-mail адрес")])
    active = BooleanField('Активна?')
    submit = SubmitField('Обновить')


class AddCfgForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    ip_address = StringField(_l('IP-адрес'), validators=[DataRequired(), IPAddress(ipv4=True, ipv6=False,
                                                                                   message="Это точно IP-адрес?")])
    port = IntegerField(_l('Порт'))
    database = StringField(_l('База данных'))
    username = StringField(_l('Имя пользователя БД'), validators=[DataRequired()])
    password = StringField(_l('Пароль БД'), validators=[DataRequired()])
    system = SelectField(_l('Система управления'), validators=[DataRequired()], choices=[], coerce=int)
    submit = SubmitField('Добавить')


class EditCfgForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    ip_address = StringField(_l('IP-адрес'), validators=[DataRequired(), IPAddress(ipv4=True, ipv6=False,
                                                                                   message="Это точно IP-адрес?")])
    port = IntegerField(_l('Порт'))
    database = StringField(_l('База данных'))
    username = StringField(_l('Имя пользователя БД'), validators=[DataRequired()])
    password = StringField(_l('Пароль БД'), validators=[DataRequired()])
    system = SelectField(_l('Система управления'), validators=[DataRequired()], choices=[], coerce=int)
    submit = SubmitField('Обновить')


class EditTankForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    tank = IntegerField(_l('Номер резервуара'), validators=[DataRequired()])
    fuel_type = IntegerField(_l('Тип топлива'), validators=[DataRequired()])
    nominal_capacity = FloatField(_l('Номинальный объем (л)'), validators=[DataRequired()])
    real_capacity = FloatField(_l('Действующий объем (л)'), validators=[DataRequired()])
    dead_capacity = FloatField('Мервый остаток (л)')
    # corrected_capacity = IntegerField(_l('Скорректированная емкость'), validators=[DataRequired()])
    drain_time = IntegerField(_l('Время слива'), validators=[DataRequired()])
    after_drain_time = IntegerField(_l('Время после слива'), validators=[DataRequired()])
    mixing = BooleanField(_l('Смешение'))
    active = BooleanField(_l('Активен'))
    ams = BooleanField(_l('АИС'))
    submit = SubmitField('Обновить')


class AddTruckForm(FlaskForm):
    reg_number = StringField(_l('Регистрационный номер'), validators=[DataRequired()])
    trailer_reg_number = StringField(_l('Регистрационный номер прицепа'), validators=[DataRequired()])
    seals = IntegerField(_l('Пломбы'), validators=[DataRequired()])
    weight = IntegerField(_l('Сухая масса'))
    weight_limit = IntegerField('Максимальная масса', validators=[DataRequired()])
    driver = StringField(_l('ФИО водителя'))
    active = BooleanField('Активен?')
    submit = SubmitField('Добавить')


class AddTruckTankForm(FlaskForm):
    number = IntegerField(_l('Порядковый номер'), validators=[DataRequired()])
    capacity = IntegerField(_l('Емкость (л.)'), validators=[DataRequired()])
    submit = SubmitField('Добавить')


class EditTruckForm(FlaskForm):
    reg_number = StringField(_l('Регистрационный номер'), validators=[DataRequired()])
    trailer_reg_number = StringField(_l('Регистрационный номер прицепа'), validators=[DataRequired()])
    seals = IntegerField(_l('Пломбы (шт.)'), validators=[DataRequired()])
    weight = IntegerField(_l('Сухая масса'))
    weight_limit = IntegerField('Максимальная масса', validators=[DataRequired()])
    driver = StringField(_l('ФИО водителя'))
    active = BooleanField('Активен?')
    submit = SubmitField('Сохранить')


class EditPriorityListForm(FlaskForm):
    day_stock_from = FloatField('Запас суток От')
    day_stock_to = FloatField('Запас суток До', validators=[DataRequired()])  # запас суток до
    priority = IntegerField('Уровень приоритета', validators=[DataRequired()])  # приоритет
    sort_method = SelectField('Метод сортировки', choices=[('1', 'Приоритет дальние'), ('2', 'Приоритет ближние'),
                                                           ('3', 'Приоритет долгие'), ('4', 'Приоритет быстрые')],
                              validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class AddTripForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    distance = IntegerField('Расстояние от нефтебазы до АЗС')
    time_to_before_lunch = TimeField('Время до АЗС (до обеда)')
    time_from_before_lunch = TimeField('Время от АЗС (до обеда)')
    time_to = TimeField('Время до АЗС (после обеда)')
    time_from = TimeField('Время от АЗС (после обеда)')
    weigher = SelectField('Весы', choices=[('1', 'Да'), ('0', 'Нет')])
    submit = SubmitField('Сохранить')


