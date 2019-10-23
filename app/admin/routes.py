from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm
from app.admin.forms import AddUserForm, AddTankForm, AddAzsForm, AddCfgForm, EditCfgForm, EditTankForm, EditAzsForm, \
    AddTruckForm, AddTruckTankForm, EditTruckForm, EditPriorityListForm, AddTripForm, WorkTypeForm, TruckFalseForm
from app.models import User, AzsList, Tanks, CfgDbConnection, AzsSystems, Trucks, TruckTanks, Trip, Priority, \
    PriorityList, FuelRealisation, FuelResidue, WorkType, TruckFalse
from app.admin import bp
import jsonify
from sqlalchemy import desc


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
    azs_list = AzsList.query.order_by("number").all()
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
    return render_template('settings/editor.html', title='Редактирование профиля', edit_profile=True,
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
    return render_template('admin/adder.html', title='Добавление пользователя',
                           form=form)


@bp.route('/admin/addtank', methods=['GET', 'POST'])
@login_required
def addtank():
    categories = [(c.id, c.number) for c in AzsList.query.order_by("number").all()]
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
                         corrected_capacity=(form.real_capacity.data/100)*95, drain_time=form.drain_time.data,
                         after_drain_time=form.after_drain_time.data, mixing=form.mixing.data, active=form.active.data,
                         ams=form.ams.data, dead_capacity=form.dead_capacity.data)
            db.session.add(tank)
            db.session.commit()
            flash('Резервуар добавлен')
            return redirect(url_for('admin.tanks'))
    return render_template('admin/adder.html', title='Добавление резервуара',
                           form=form)


@bp.route('/admin/tanks', methods=['POST', 'GET'])
@login_required
def tanks():
    azs_list = AzsList.query.order_by("number").all()
    tank_list = Tanks.query.outerjoin(AzsList).order_by(AzsList.number, "tank_number").all()
    return render_template('admin/tanks.html', title='Список резервуаров', tanks=True, settings_active=True,
                           tank_list=tank_list, azs_list=azs_list)


@bp.route('/admin/config_list', methods=['POST', 'GET'])
@login_required
def config_lst():
    config_list = CfgDbConnection.query.outerjoin(AzsList).order_by(AzsList.number).all()
    azs_list = AzsList.query.all()
    return render_template('admin/config_list.html', title='Список конфигов', db_configs=True, settings_active=True,
                           config_list=config_list, azs_list=azs_list)


@bp.route('/admin/addazs', methods=['GET', 'POST'])
@login_required
def add_azs():
    form = AddAzsForm()
    if form.validate_on_submit():
        azs = AzsList(number=form.number.data, active=form.active.data, address=form.address.data,
                      phone=form.phone.data, email=form.email.data)
        db.session.add(azs)
        db.session.commit()
        flash('АЗС добавлена')
        return redirect(url_for('admin.azslist'))
    return render_template('admin/adder.html', title='Добавление АЗС', form=form)


@bp.route('/admin/add_db_config', methods=['GET', 'POST'])
@login_required
def add_cfg():
    categories = [(c.id, c.number) for c in AzsList.query.order_by("number").all()]
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
    return render_template('admin/adder.html', title='Добавление параметров подключения к базе', form=form)


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
    return render_template('admin/editor.html', title='Редактирование конфига', edit_db_config=True, form=form,
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
        tank.dead_capacity = form.dead_capacity.data
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
        form.dead_capacity.data = tank.dead_capacity
        form.drain_time.data = tank.drain_time
        form.after_drain_time.data = tank.after_drain_time
        form.ams.data = tank.ams
        form.mixing.data = tank.mixing
        form.active.data = tank.active
    return render_template('admin/editor.html', title='Редактирование резервуара', edit_db_config=True, form=form,
                           settings_active=True)


@bp.route('/admin/azs/<azs_id>/edit', methods=['POST', 'GET'])
@login_required
def edit_azs(azs_id):
    azs_list = AzsList.query.filter_by(id=azs_id).first()
    form = EditAzsForm()
    if form.validate_on_submit():
        azs_list.number = form.number.data
        azs_list.phone = form.phone.data
        azs_list.address = form.address.data
        azs_list.email = form.email.data
        azs_list.active = form.active.data
        db.session.commit()
        flash('Конфиг обновлен!')
        return redirect(url_for('admin.azslist'))
    elif request.method == 'GET':
        form.number.data = azs_list.number
        form.phone.data = azs_list.phone
        form.address.data = azs_list.address
        form.email.data = azs_list.email
        form.active.data = azs_list.active
    return render_template('admin/editor.html', title='Редактирование параметров АЗС № ' + str(azs_list.number),
                           edit_azs=True, form=form, settings_active=True)


@bp.route('/admin/truck/add', methods=['POST', 'GET'])
@login_required
def add_truck():
    form = AddTruckForm()

    if form.validate_on_submit():
        trucks = Trucks(reg_number=form.reg_number.data, trailer_reg_number=form.trailer_reg_number.data,
                        seals=form.seals.data, weight=form.weight.data, driver=form.driver.data,
                        active=form.active.data, weight_limit=form.weight_limit.data)
        db.session.add(trucks)
        db.session.commit()
        flash('ТС добавлено в базу')
        return redirect(url_for('admin.trucks_list'))
    return render_template('admin/adder.html', title='Добавление бензовоза', add_truck=True, settings_active=True,
                           form=form)


@bp.route('/admin/trucks_list', methods=['POST', 'GET'])
@login_required
def trucks_list():
    trucks_list = Trucks.query.order_by("reg_number").all()
    return render_template('admin/trucks_list.html', title='Список ТС', add_truck=True,
                           settings_active=True, trucks_list=trucks_list)


@bp.route('/admin/truck_tanks_list', methods=['POST', 'GET'])
@login_required
def truck_tanks_list():
    truck_tanks_list = TruckTanks.query.order_by("truck_id").all()
    return render_template('admin/truck_tanks_list.html', title='Список резервуаров ТС', truck_tanks=True,
                           settings_active=True, truck_tanks_list=truck_tanks_list)


@bp.route('/admin/truck_tanks/add/id<id>', methods=['POST', 'GET'])
@login_required
def truck_tanks_add(id):
    form = AddTruckTankForm()

    if form.validate_on_submit():
        truck_tank = TruckTanks(number=form.number.data, truck_id=id, capacity=form.capacity.data)
        db.session.add(truck_tank)
        db.session.commit()
        flash('Резервуар бензовоза добавлен в базу')
        return redirect(url_for('admin.truck', id=id))

    return render_template('admin/add_truck_tank.html', title='Добавление резервуара ТС', truck_tanks=True,
                           settings_active=True, truck_tanks_list=truck_tanks_list, form=form)


@bp.route('/admin/truck/edit/id<id>', methods=['POST', 'GET'])
@login_required
def truck_edit(id):
    form = EditTruckForm()
    truck = Trucks.query.filter_by(id=id).first_or_404()

    if form.validate_on_submit():
        truck.reg_number = form.reg_number.data
        truck.trailer_reg_number = form.trailer_reg_number.data
        truck.seals = form.seals.data
        truck.weight = form.weight.data
        truck.driver = form.driver.data
        truck.active = form.active.data
        truck.day_start = form.start_time
        truck.day_end = form.end_time
        truck.weight_limit = form.weight_limit.data
        db.session.commit()
        flash('ТС отредактированно')
        return redirect(url_for('admin.truck', id=id))

    elif request.method == 'GET':
        form.reg_number.data = truck.reg_number
        form.trailer_reg_number.data = truck.trailer_reg_number
        form.seals.data = truck.seals
        form.weight.data = truck.weight
        form.driver.data = truck.driver
        form.start_time = truck.day_start
        form.end_time = truck.day_end
        form.active.data = truck.active
        form.weight_limit.data = truck.weight_limit

    return render_template('admin/editor.html', title='Редактирование бензовоза '+str(truck.reg_number),
                           truck_edit=True, settings_active=True, truck=truck, form=form)


@bp.route('/admin/truck/id<id>', methods=['POST', 'GET'])
@login_required
def truck(id):
    truck = Trucks.query.filter_by(id=id).first_or_404()
    truck_tanks_list = TruckTanks.query.filter_by(truck_id=id).all()
    truck_tanks_count = TruckTanks.query.filter_by(truck_id=id).count()
    return render_template('admin/truck.html', title='Бензовоз ' + truck.reg_number, truck_active=True,
                           settings_active=True, truck_tanks_list=truck_tanks_list, truck=truck,
                           truck_tanks_count=truck_tanks_count)


@bp.route('/admin/priority/add/', methods=['POST', 'GET'])
@login_required
def add_priority():
    form = EditPriorityListForm()
    if form.validate_on_submit():
        priority_list = PriorityList(day_stock_from=form.day_stock_from.data, day_stock_to=form.day_stock_to.data,
                                     priority=form.priority.data, sort_method=form.sort_method.data)
        db.session.add(priority_list)
        db.session.commit()
        flash('Приоритет добавлен')
        return redirect(url_for('admin.priority'))
    return render_template('admin/adder.html', title='Добавление приоритетов', add_priority=True,
                           settings_active=True, form=form)


@bp.route('/admin/priority', methods=['POST', 'GET'])
@login_required
def priority():
    priority_list = PriorityList.query.order_by("priority").all()
    form = PriorityList()
    return render_template('admin/priority_list.html', title='Список приоритетов', priority=True,
                           settings_active=True, priority_list=priority_list, form=form)


@bp.route('/admin/priority/edit/id<id>', methods=['POST', 'GET'])
@login_required
def edit_priority(id):
    form = EditPriorityListForm()
    priority_list = PriorityList.query.filter_by(id=id).first_or_404()

    if form.validate_on_submit():
        priority_list.day_stock_from = form.day_stock_from.data
        priority_list.day_stock_to = form.day_stock_to.data
        priority_list.priority = form.priority.data
        priority_list.sort_method = form.sort_method.data
        db.session.commit()
        flash('Приоритет отредактирован')
        return redirect(url_for('admin.priority'))

    elif request.method == 'GET':
        form.day_stock_from.data = priority_list.day_stock_from
        form.day_stock_to.data = priority_list.day_stock_to
        form.priority.data = priority_list.priority
        form.sort_method.data = priority_list.sort_method
    return render_template('admin/editor.html', title='Редактирование приоритета', priority_edit=True,
                           settings_active=True, priority_list=priority_list, form=form)


@bp.route('/admin/priority/delete/id<id>', methods=['POST', 'GET'])
@login_required
def delete_priority(id):
    priority = PriorityList.query.filter_by(id=id).first_or_404()
    db.session.delete(priority)
    db.session.commit()
    flash('Приоритет удален')
    return redirect(url_for('admin.priority'))


@bp.route('/admin/truck/delete/id<id>', methods=['POST', 'GET'])
@login_required
def truck_delete(id):
    sql = Trucks.query.filter_by(id=id).first_or_404()
    tanks = TruckTanks.query.filter_by(truck_id=id).all()
    if tanks:
        for i in tanks:
            db.session.delete(i)
            db.session.commit()
        db.session.delete(sql)
        db.session.commit()
        flash('Бензовоз удален')
    else:
        db.session.delete(sql)
        db.session.commit()
        flash('Бензовоз и резервуары удалены')
    return redirect(url_for('admin.trucks_list'))


@bp.route('/admin/trip/add', methods=['POST', 'GET'])
@login_required
def add_trip():
    form = AddTripForm()
    categories = [(c.id, c.number) for c in AzsList.query.order_by("number").all()]
    form.azs_id.choices = categories
    if form.validate_on_submit():

        trip = Trip(distance=form.distance.data,
                    time_from_before_lunch=form.time_from_before_lunch.data,
                    time_to_before_lunch=form.time_to_before_lunch.data,
                    time_from=form.time_from.data,
                    time_to=form.time_to.data,
                    azs_id=form.azs_id.data,
                    weigher=form.weigher.data)

        db.session.add(trip)
        db.session.commit()
        flash('Конфигурация добавлена в базу')
        return redirect(url_for('admin.trip_list'))
    return render_template('admin/adder.html', title='Добавление пути и времени', add_trip=True, settings_active=True,
                           form=form)


@bp.route('/admin/trip', methods=['POST', 'GET'])
@login_required
def trip_list():
    azs_list = AzsList.query.order_by('number').all()
    trip_list = Trip.query.all()
    return render_template('admin/trip_list.html', title='Расстояние и время до объектов', trip=True,
                           settings_active=True, azs_list=azs_list, trip_list=trip_list)


@bp.route('/admin/trip/edit/<id>', methods=['POST', 'GET'])
@login_required
def edit_trip(id):
    form = AddTripForm()
    categories = [(c.id, c.number) for c in AzsList.query.order_by("number").all()]
    form.azs_id.choices = categories
    trip_list = Trip.query.filter_by(id=id).first_or_404()
    if form.validate_on_submit():
        trip_list.azs_id = form.azs_id.data
        trip_list.distance = form.distance.data
        trip_list.time_to_before_lunch = form.time_to_before_lunch.data
        trip_list.time_from_before_lunch = form.time_from_before_lunch.data
        trip_list.time_to = form.time_to.data
        trip_list.time_from = form.time_from.data
        trip_list.weigher = form.weigher.data
        db.session.commit()
        flash('Данные изменены')
        return redirect(url_for('admin.trip_list'))

    elif request.method == 'GET':
        form.azs_id.data = trip_list.azs_id
        form.distance.data = trip_list.distance
        form.time_to_before_lunch.data = trip_list.time_to_before_lunch
        form.time_from_before_lunch.data = trip_list.time_from_before_lunch
        form.time_to.data = trip_list.time_to
        form.time_from.data = trip_list.time_from
        form.weigher.data = trip_list.weigher
    return render_template('admin/editor.html', title='Изменение пути и времени', edit_trip=True,
                           settings_active=True,
                           form=form)


@bp.route('/admin/work_type', methods=['POST', 'GET'])
@login_required
def work_type():
    form = WorkTypeForm()
    work_type_table = WorkType.query.all()
    categories = [(c.id, c.type) for c in WorkType.query.order_by("id").all()]
    form.type.choices = categories
    active = WorkType.query.filter_by(active=True).first()

    if form.validate_on_submit():
        for i in work_type_table:
            i.active = 0
        id = form.type.data
        type = WorkType.query.filter_by(id=id).first()
        type.active = True
        db.session.commit()
    else:
        form.type.data = active.id

    return render_template('admin/work_type.html', form=form)


@bp.route('/admin/trucks_false', methods=['POST', 'GET'])
@login_required
def trucks_false():
    trucks_false = TruckFalse.query.order_by("azs_id").all()
    trucks = list()
    for truck in trucks_false:
        reg = Trucks.query.filter_by(id=truck.truck_id).first()
        azs = AzsList.query.filter_by(id=truck.azs_id).first()
        truck = {
            'id': truck.id,
            'azs_number': azs.number,
            'truck_number': reg.reg_number,
            'reason': truck.reason
        }
        trucks.append(truck)
    return render_template('/admin/trucks_false.html', trucks=trucks)


@bp.route('/admin/trucks_false/add', methods=['POST', 'GET'])
@login_required
def trucks_false_add():
    false = TruckFalse.query.order_by("timestamp").all()

    categories = [(c.id, c.number) for c in AzsList.query.order_by("number").all()]
    trucks = [(s.id, s.reg_number) for s in Trucks.query.all()]
    form = TruckFalseForm(request.form)
    form.azs.choices = categories
    form.truck.choices = trucks
    if form.validate_on_submit():
        trucks_list = TruckFalse(azs_id=form.azs.data, truck_id=form.truck.data, reason=form.reason.data)
        db.session.add(trucks_list)
        db.session.commit()
        flash('Данные добавлены')
        return redirect(url_for('admin.trucks_false'))
    return render_template('/admin/adder.html', title="Добавление исключения для бензовоза", trucks=trucks, form=form)


@bp.route('/admin/trucks_false/delete/id<id>', methods=['POST', 'GET'])
@login_required
def trucks_false_delete(id):
    row = TruckFalse.query.filter_by(id=id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash('Данные удалены')
    return redirect(url_for('admin.trucks_false'))
