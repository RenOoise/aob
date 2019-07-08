from datetime import datetime
from datetime import date as dt
import calendar
from flask import render_template, flash, redirect, url_for, request, g
from flask_login import current_user, login_required
from flask_babel import get_locale
from app import db
from app.main.forms import EditProfileForm
from app.models import User, FuelResidue, CfgDbConnection
from app.main import bp
import postgresql


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():

    return render_template('index.html', title='Главная', index=True)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Ваши изменения успешно сохранены')
        return redirect(url_for('main.user', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Редактирование профиля', profile=True,
                           form=form)


@bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("Пользователь %s не существует." % username)
        return redirect(url_for('main.index'))
    if user == current_user:
        flash('Вы не можете подписаться на свои обновления!')
        return redirect(url_for('main.user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('Вы подписались на пользователя %s !' % username)
    return redirect(url_for('main.user', username=username))


@bp.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Пользователь %s не существует.', username)
        return redirect(url_for('main.index'))
    if user == current_user:
        flash('Вы не можете отписаться от своих обновлений!')
        return redirect(url_for('main.user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('Вы отписались от пользователя %s.' % username)
    return redirect(url_for('main.user', username=username))


@bp.route('/settings', methods=['POST', 'GET'])
@login_required
def settings():

    return render_template('settings.html', title='Настройки', settings=True, sql=sql)


@bp.route('/user/<username>')
@login_required
def user(username):

    user = User.query.filter_by(username=username).first_or_404()

    return render_template('user.html', user=user, profile=True, title=username)
