from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, FloatField
from wtforms.validators import ValidationError, DataRequired, Length

from app.models import User


class EditProfileForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    first_name = StringField('Имя')
    last_name = StringField('Фамилия')
    about_me = TextAreaField('Обо мне',
                             validators=[Length(min=0, max=140)])
    submit = SubmitField('Сохранить')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('Пожалуйста введите другое имя пользователя')


class PostForm(FlaskForm):
    post = TextAreaField('Скажите что-нибудь', validators=[DataRequired()])
    submit = SubmitField('Отправить')


class SearchForm(FlaskForm):
    q = StringField('Search', validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)


class MessageForm(FlaskForm):
    message = TextAreaField('Сообщение', validators=[
        DataRequired(), Length(min=1, max=140)])
    submit = SubmitField('Отправить')


class ManualInputForm(FlaskForm):
    residue = FloatField('Остаток топлива', validators=[DataRequired()])
    realisation = FloatField('Максимальная реализация по резервуару', validators=[DataRequired()])
    hour_realisation = FloatField('Примерная реализация в час')
    sumbit = SubmitField('Сохранить')
