from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, PasswordField, IntegerField, FloatField, \
    BooleanField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
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
    tank = IntegerField(_l('Номер резервуара'), validators=[DataRequired()])
    fuel_type = IntegerField(_l('Тип топлива'), validators=[DataRequired()])
    nominal_capacity = FloatField(_l('Номинальная емкость'), validators=[DataRequired()])
    real_capacity = FloatField(_l('Реальная емкость'), validators=[DataRequired()])
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
    ip_address = StringField(_l('IP-адрес'), validators=[DataRequired()])
    port = IntegerField(_l('Порт'))
    database = StringField(_l('База данных'))
    username = StringField(_l('Имя пользователя БД'), validators=[DataRequired()])
    password = StringField(_l('Пароль БД'), validators=[DataRequired()])
    system = SelectField(_l('Система управления'), validators=[DataRequired()], choices=[], coerce=int)
    submit = SubmitField('Добавить')


class EditCfgForm(FlaskForm):
    azs_id = SelectField(_l('Номер АЗС'), validators=[DataRequired()], choices=[], coerce=int)
    ip_address = StringField(_l('IP-адрес'), validators=[DataRequired()])
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
    nominal_capacity = FloatField(_l('Номинальная емкость'), validators=[DataRequired()])
    real_capacity = FloatField(_l('Реальная емкость'), validators=[DataRequired()])
    # corrected_capacity = IntegerField(_l('Скорректированная емкость'), validators=[DataRequired()])
    drain_time = IntegerField(_l('Время слива'), validators=[DataRequired()])
    after_drain_time = IntegerField(_l('Время после слива'), validators=[DataRequired()])
    mixing = BooleanField(_l('Смешение'))
    active = BooleanField(_l('Активен'))
    ams = BooleanField(_l('АИС'))
    submit = SubmitField('Обновить')
