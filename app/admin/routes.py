from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm
from app.admin.forms import AddUserForm, AddTankForm, AddAzsForm, AddCfgForm, EditCfgForm, EditTankForm
from app.models import User, AzsList, Tanks, CfgDbConnection, AzsSystems
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
        tanks = Tanks.query.filter_by(azs_id=form.azs_id.data, tank_number=form.tank.data).first()
        if tanks:
            flash('Резервуар № ' + str(form.tank.data) + ' для АЗС ' + str(form.tank.data) + ' уже существует')
            return redirect(url_for('admin.tanks'))
        else:

            tank = Tanks(azs_id=form.azs_id.data, tank_number=form.tank.data, fuel_type=form.fuel_type.data,
                         nominal_capacity=form.nominal_capacity.data, real_capacity=form.real_capacity.data,
                         corrected_capacity=form.real_capacity.data/100*95, drain_time=form.drain_time.data,
                         after_drain_time=form.after_drain_time.data, mixing=form.mixing.data, active=form.active.data,
                         ams=form.ams.data)
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
    azs_list = AzsList.query.all()
    tank_list = Tanks.query.all()
    return render_template('admin/tanks.html', title='Список резервуаров', tanks=True, settings_active=True,
                           tank_list=tank_list, azs_list=azs_list)


@bp.route('/admin/config_list', methods=['POST', 'GET'])
@login_required
def config_lst():
    config_list = CfgDbConnection.query.all()
    azs_list = AzsList.query.all()
    return render_template('admin/config_list.html', title='Список конфигов', db_configs=True, settings_active=True,
                           config_list=config_list, azs_list=azs_list)


@bp.route('/admin/addazs', methods=['GET', 'POST'])
@login_required
def add_azs():
    form = AddAzsForm()
    if form.validate_on_submit():
        azs = AzsList(number=form.number.data, active=form.active.data, adress=form.address.data, phone=form.phone.data)
        db.session.add(azs)
        db.session.commit()
        flash('АЗС добавлена')
        return redirect(url_for('admin.azslist'))
    return render_template('admin/addazs.html', title='Добавление АЗС', form=form)


@bp.route('/admin/add_db_config', methods=['GET', 'POST'])
@login_required
def add_cfg():
    categories = [(c.id, c.number) for c in AzsList.query.all()]
    systems = [(s.id, s.type) for s in AzsSystems.query.all()]
    form = AddCfgForm(request.form)
    form.azs_id.choices = categories
    form.system.choices = systems

    if form.validate_on_submit():
        cfg = CfgDbConnection(azs_id=form.azs_id.data, system_type=form.system.data,
                              ip_address=form.ip_address.data, port=form.port.data,
                              database=form.database.data, username=form.username.data,
                              password=form.password.data)
        db.session.add(cfg)
        db.session.commit()
        flash('Конфиг добавлен')
        return redirect(url_for('admin.config_lst'))
    return render_template('admin/add_db_config.html', title='Добавление параметров подключения к базе', form=form)


@bp.route('/admin/<azs_id>/edit', methods=['POST', 'GET'])
@login_required
def edit_db_config(azs_id):
    categories = [(c.id, c.number) for c in AzsList.query.all()]
    systems = [(s.id, s.type) for s in AzsSystems.query.all()]
    form = EditCfgForm(request.form)
    form.azs_id.choices = categories
    form.system.choices = systems
    config = CfgDbConnection.query.filter_by(azs_id=azs_id).first()

    if form.validate_on_submit():
        config.azs_id = form.azs_id.data
        config.ip_address = form.ip_address.data
        config.port = form.port.data
        config.database = form.database.data
        config.username = form.username.data
        config.password = form.password.data
        config.system_type = form.system.data
        db.session.commit()
        flash('Конфиг обновлен!')
        return redirect(url_for('admin.config_lst'))
    elif request.method == 'GET':
        form.azs_id.data = config.azs_id
        form.ip_address.data = config.ip_address
        form.port.data = config.port
        form.database.data = config.database
        form.username.data = config.username
        form.password.data = config.password
        form.system.data = config.system_type
    return render_template('admin/edit_db_config.html', title='Редактирование конфига', edit_db_config=True, form=form,
                           settings_active=True)


@bp.route('/admin/tanks/<tank_id>/edit', methods=['POST', 'GET'])
@login_required
def edit_tank(tank_id):
    categories = [(c.id, c.number) for c in AzsList.query.all()]
    form = EditTankForm(request.form)
    form.azs_id.choices = categories
    tank = Tanks.query.filter_by(id=tank_id).first()

    if form.validate_on_submit():
        tank.azs_id = form.azs_id.data
        tank.tank_number = form.tank.data
        tank.fuel_type = form.fuel_type.data
        tank.nominal_capacity = form.nominal_capacity.data
        tank.real_capacity = form.real_capacity.data
        tank.drain_time = form.drain_time.data
        tank.after_drain_time = form.after_drain_time.data
        tank.ams = form.ams.data
        tank.mixing = form.mixing.data
        tank.active = form.active.data
        db.session.commit()
        flash('Данные резервуара обновлены!')
        return redirect(url_for('admin.tanks'))
    elif request.method == 'GET':
        form.azs_id.data = tank.azs_id
        form.tank.data = tank.tank_number
        form.fuel_type.data = tank.fuel_type
        form.nominal_capacity.data = tank.nominal_capacity
        form.real_capacity.data = tank.real_capacity
        form.drain_time.data = tank.drain_time
        form.after_drain_time.data = tank.after_drain_time
        form.ams.data = tank.ams
        form.mixing.data = tank.mixing
        form.active.data = tank.active
    return render_template('admin/edit_tank.html', title='Редактирование резервуара', edit_db_config=True, form=form,
                           settings_active=True)
