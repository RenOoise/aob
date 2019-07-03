from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, FloatField, SelectField, DateField
from wtforms.validators import ValidationError, DataRequired, Length
from app.models import User
from datetime import date


class EditProfileForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    about_me = TextAreaField('Обо мне',
                             validators=[Length(min=0, max=140)])
    submit = SubmitField('Применить')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('Пожалуйста, введите другое имя.')


class PostForm(FlaskForm):
    post = TextAreaField('Скажите чо-нить', validators=[DataRequired()])
    submit = SubmitField('Отправить')
