from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm
from app.admin.forms import AddUserForm, AddTankForm
from app.models import User, AzsList, Tanks
from app.admin import bp
"import jsonify"


@bp.route('/admin', methods=['POST', 'GET'])
@login_required
def settings():

    return render_template('admin/settings.html', title='Настройки', settings=True, settings_active=True)


@bp.route('/admin/users', methods=['POST', 'GET'])
@login_required
def users():
    users_list = User.query.all()
    return render_template('admin/users.html', title='Пользователи', users=True, settings_active=True,
                           users_list=users_list)


@bp.route('/admin/azslist', methods=['POST', 'GET'])
@login_required
def azslist():
    azs_list = AzsList.query.all()
    return render_template('admin/azslist.html', title='Список АЗС', azslist=True, settings_active=True,
                           azs_list=azs_list)


@bp.route('/admin/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.nickname = form.nickname.data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Ваш профиль обновлен!')
        return redirect(url_for('main.user', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.nickname.data = current_user.nickname
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.about_me.data = current_user.about_me
    return render_template('settings/edit_profile.html', title='Редактирование профиля', edit_profile=True,
                           settings_active=True, form=form)


@bp.route('/admin/adduser', methods=['GET', 'POST'])
@login_required
def adduser():
    form = AddUserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Пользователь добавлен')
        return redirect(url_for('admin.adduser'))
    return render_template('admin/register.html', title='Добавление пользователя',
                           form=form)


@bp.route('/admin/addtank', methods=['GET', 'POST'])
@login_required
def addtank():
    categories = [(c.id, c.number) for c in AzsList.query.all()]
    form = AddTankForm(request.form)
    form.azs_id.choices = categories
    if form.validate_on_submit():
        tank = Tanks(azs_id=form.azs_id.data, tank_number=form.tank.data, fuel_type=form.fuel_type.data,
                     nominal_capacity=form.nominal_capacity.data, real_capacity=form.real_capacity.data,
                     corrected_capacity=form.corrected_capacity.data, drain_time=form.drain_time.data,
                     after_drain_time=form.after_drain_time.data, mixing=form.mixing.data, active=form.active.data)
        db.session.add(tank)
        db.session.commit()
        flash('Резервуар добавлен')
        return redirect(url_for('admin.tanks'))
    return render_template('admin/addtank.html', title='Добавление резервуара',
                           form=form)


@bp.route('/admin/<number>')
@login_required
def pick_line(number):
    azs_list = AzsList.query.filter_by(number=number).all()
    azsArray = []
    for azs in azs_list:
        azsObj = {}
        azsObj['id'] = azs.id
        azsObj['number'] = azs.name
        azsArray.append([azsObj])

    return 0
    '''jsonify({'azs': azsArray})'''


@bp.route('/admin/tanks', methods=['POST', 'GET'])
@login_required
def tanks():
    tank_list = Tanks.query.all()
    return render_template('admin/tanks.html', title='Список резервуаров', tanks=True, settings_active=True,
                           tank_list=tank_list)
