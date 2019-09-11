import datetime

from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, send_file
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from datetime import date
import threading  # многопоточность

import random
from app import db
from app.main.forms import EditProfileForm, PostForm, SearchForm, MessageForm, ManualInputForm
from app.models import User, Post, Message, Notification, FuelResidue, AzsList, Tanks, FuelRealisation, Priority, \
    PriorityList, ManualInfo, Trucks, TruckTanks, TruckFalse, Trip, TempAzsTrucks, TempAzsTrucks2, WorkType, Errors
from app.models import Close1Tank1, Close1Tank2, Close1Tank3, Close1Tank4, Close1Tank5, Close2Tank1, Close2Tank2, \
    Close2Tank3, Close2Tank4, Close2Tank5, Close3Tank1, Close3Tank2, Close3Tank3, Close3Tank4, Close3Tank5, Close4Tank1, \
    Close4Tank2, Close4Tank3, Close4Tank4, Close4Tank5, Test, TripForToday
import time
import redis
from app.translate import translate
from app.main import bp
import pandas as pd
from StyleFrame import StyleFrame, Styler, utils
from datetime import datetime, timedelta
from sqlalchemy import desc
r = redis.StrictRedis(host='localhost', port=6379, db=0)


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    def check():
        errors = 0
        azs_list = AzsList.query.all()
        error_tank_list = list()
        errors_list = list()
        for azs in azs_list:
            if azs.active:
                tanks_list = Tanks.query.filter_by(azs_id=azs.id, active=True).all()
                for tank in tanks_list:
                    if tank.active:
                        residue = FuelResidue.query.filter_by(tank_id=tank.id).first()
                        realisation = FuelRealisation.query.filter_by(tank_id=tank.id).first()
                        if residue.fuel_volume is None or residue.fuel_volume <= 0 \
                                or residue.download_time < datetime.now()-timedelta(seconds=600):
                            if residue.download_time < datetime.now()-timedelta(seconds=600):
                                error_text = "АЗС №" + str(azs.number) + ", резервуар №" + str(tank.tank_number) + \
                                             " - возможно данные об остатках устерели"
                            else:
                                error_text = "АЗС №" + str (azs.number) + ", резервуар №" + str(tank.tank_number) + \
                                             " - нет данных об остатках"
                            sql = Errors(timestamp=datetime.now(), error_text=error_text, azs_id=azs.id,
                                         tank_id=tank.id, active=True, error_type="residue_error")
                            db.session.add(sql)
                            db.session.commit()
                            errors = errors + 1
                            error_tank_list.append(tank.id)

                            errors_list.append(error_text)

                        if realisation.fuel_realisation_1_days is None or realisation.fuel_realisation_1_days <= 0 \
                                or realisation.download_time < datetime.now()-timedelta(seconds=600):
                            if realisation.download_time < datetime.now() - timedelta(seconds=600):
                                error_text = "АЗС №" + str(azs.number) + ", резервуар №" + str(tank.tank_number) + \
                                             " - возможно данные о реализации устерели"
                            else:
                                error_text = "АЗС №" + str(azs.number) + ", резервуар №" + str(tank.tank_number) + \
                                             " - нет данных о реализации"
                            sql = Errors(timestamp=datetime.now(), error_text=error_text, azs_id=azs.id,
                                         tank_id=tank.id, active=True, error_type="time_error")
                            db.session.add(sql)
                            db.session.commit()
                            errors = errors + 1
                            error_tank_list.append(tank.id)
                            errors_list.append(error_text)
                        priority_list = PriorityList.query.all()
                        for priority in priority_list:
                            if priority.day_stock_from <= realisation.days_stock_min <= priority.day_stock_to:
                                this_priority = PriorityList.query.filter_by(priority=priority.priority).first_or_404()
                                if not this_priority.id:
                                    print('Резервуар №' + str(tank.tank_number) +
                                          ' не попадает в диапазон приоритетов!!!')
        return errors, errors_list

    priority = Priority.query.order_by('priority').all()
    trip_for_today = TripForToday.query.order_by("trip_number").all()
    azs_list = list()
    error_list = list()
    for i in priority:
        azs_dict = {}
        if i.day_stock <= 2:
            azs = AzsList.query.filter_by(id=i.azs_id).first_or_404()
            tank = Tanks.query.filter_by(id=i.tank_id).first_or_404()
            azs_dict = {'number': azs.number,
                        'azs_id': i.azs_id,
                        'tank': tank.tank_number,
                        'day_stock': i.day_stock}
            azs_list.append(azs_dict)
    errors_num, errors = check()
    for error in errors:
        error_list.append(error)
    return render_template('index.html', title='Главная', azs_list=azs_list, error_list=error_list, index=True,
                           trip_for_today=trip_for_today)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.user', username=user.username,
                       page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username,
                       page=posts.prev_num) if posts.has_prev else None
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_popup.html', user=user)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title=_('Edit Profile'),
                           form=form)


@bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(_('User %(username)s not found.', username=username))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash(_('You cannot follow yourself!'))
        return redirect(url_for('main.user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash(_('You are following %(username)s!', username=username))
    return redirect(url_for('main.user', username=username))


@bp.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(_('User %(username)s not found.', username=username))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash(_('You cannot unfollow yourself!'))
        return redirect(url_for('main.user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash(_('You are not following %(username)s.', username=username))
    return redirect(url_for('main.user', username=username))


@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    return jsonify({'text': translate(request.form['text'],
                                      request.form['source_language'],
                                      request.form['dest_language'])})


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title=_('Search'), posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username=recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user,
                      body=form.message.data)
        db.session.add(msg)
        user.add_notification('unread_message_count', user.new_messages())
        db.session.commit()
        flash(_('Your message has been sent.'))
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title=_('Send Message'),
                           form=form, recipient=recipient)


@bp.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.messages', page=messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) \
        if messages.has_prev else None
    return render_template('messages.html', messages=messages.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_task_in_progress('export_posts'):
        flash(_('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])


@bp.route('/residue_xlsx/остатки_<datetime>')
@login_required
def residue_xlsx(datetime):
    timenow = datetime

    online = FuelResidue.query.outerjoin(AzsList).outerjoin(Tanks).order_by(AzsList.number).all()
    online_list = list()
    for data in online:
        azs_number = AzsList.query.filter_by(id=data.azs_id).first()
        tank_number = Tanks.query.filter_by(id=data.tank_id).first()
        if data.auto:
            auto = "Автоматически"
        else:
            auto = "По книжным остаткам"
        online_dict = {
            '№': 'АЗС № ' + str(azs_number.number),
            'Резервуар №': tank_number.tank_number,
            'Вид топлива': data.product_code,
            'Процент (%)': data.percent,
            'Текущий остаток (л)': data.fuel_volume,
            'Свободная емкость (до 95%) (л)': round(tank_number.corrected_capacity - data.fuel_volume, 1),
            'Время замера АИСом': data.datetime,
            'Время получения данных': data.download_time,
            'Тип формирования': auto
        }
        online_list.append(online_dict)
    df = pd.DataFrame(online_list)
    excel_writer = StyleFrame.ExcelWriter(r'/home/administrator/aob-test/files/онлайн-остатки_'+str(timenow)+'.xlsx')
    sf = StyleFrame(df)

    sf.apply_style_by_indexes(indexes_to_style=sf[sf['Текущий остаток (л)'] == 0],
                              cols_to_style=['Время получения данных',
                                             'Тип формирования', 'Время замера АИСом',
                                             'Свободная емкость (до 95%) (л)',
                                             'Резервуар №',
                                             '№',
                                             'Вид топлива',
                                             'Текущий остаток (л)',
                                             'Процент (%)'], styler_obj=Styler(bg_color='F5455F'))

    sf.apply_style_by_indexes(indexes_to_style=sf[sf['Тип формирования'] == 'По книжным остаткам'],
                              cols_to_style=['Время получения данных',
                                             'Тип формирования',
                                             'Время замера АИСом',
                                             'Свободная емкость (до 95%) (л)',
                                             'Резервуар №',
                                             '№',
                                             'Вид топлива',
                                             'Текущий остаток (л)',
                                             'Процент (%)'], styler_obj=Styler(bg_color='BFEDFF'))

    sf.apply_style_by_indexes(indexes_to_style=sf[sf['Тип формирования'] == 'По книжным остаткам'],
                              cols_to_style=['Время получения данных',
                                             'Время замера АИСом'],
                              styler_obj=Styler(number_format=utils.number_formats.date_time, bg_color='BFEDFF'))

    sf.apply_style_by_indexes(indexes_to_style=sf[sf['Текущий остаток (л)'] == 0],
                              cols_to_style=['Время получения данных',
                                             'Время замера АИСом'],
                              styler_obj=Styler(number_format=utils.number_formats.date_time, bg_color='F5455F'))

    sf.to_excel(excel_writer=excel_writer, row_to_add_filters=0,
                columns_and_rows_to_freeze='A1', best_fit=['Время получения данных',
                                                           'Тип формирования', 'Время замера АИСом',
                                                           'Свободная емкость (до 95%) (л)',
                                                           'Резервуар №',
                                                           '№',
                                                           'Вид топлива',
                                                           'Процент (%)',
                                                           'Текущий остаток (л)',
                                                           'Процент (%)'
                                                           ])

    # df.to_excel(r'/home/administrator/aob-test/files/онлайн-остатки_'+str(timenow)+'.xlsx')
    excel_writer.save()
    path = '/home/administrator/aob-test/files/онлайн-остатки_'+str(timenow)+'.xlsx'
    return send_file(path)


@bp.route('/realisation_xlsx/реализация_<datetime>')
@login_required
def realisation_xlsx(datetime):
    timenow = datetime

    realisation = FuelRealisation.query.outerjoin(AzsList).outerjoin(Tanks).order_by(AzsList.number).all()
    realisation_list = list()
    for data in realisation:
        azs_number = AzsList.query.filter_by(id=data.azs_id).first()
        tank_number = Tanks.query.filter_by(id=data.tank_id).first()
        realisation_dict = {
            '№': 'АЗС № ' + str(azs_number.number),
            'Резервуар №': tank_number.tank_number,
            'Вид топлива': data.product_code,
            'Сред. за 10 дней(л)': data.average_10_days,
            'Сред. за 7 дней(л)': data.average_7_days,
            'Сред. за 3 дня(л)': data.average_3_days,
            'Реализация за 1 день(л)': data.fuel_realisation_1_days,
            'Реализация за 1 день(л) неделю назад': data.fuel_realisation_week_ago,
            'Реализация за 1 час': data.fuel_realisation_hour,
            'Мин. запас суток':  data.days_stock_min,
            'Время выгрузки': data.download_time
        }
        realisation_list.append(realisation_dict)
    df = pd.DataFrame(realisation_list)
    excel_writer = StyleFrame.ExcelWriter(r'/home/administrator/aob-test/files/реализация_'+str(timenow)+'.xlsx')
    sf = StyleFrame(df)
    sf.to_excel(excel_writer=excel_writer, row_to_add_filters=0,
                columns_and_rows_to_freeze='A1', best_fit=['№',
                                                           'Резервуар №',
                                                           'Вид топлива',
                                                           'Сред. за 10 дней(л)',
                                                           'Сред. за 7 дней(л)',
                                                           'Сред. за 3 дня(л)',
                                                           'Реализация за 1 день(л)',
                                                           'Реализация за 1 день(л) неделю назад',
                                                           'Реализация за 1 час',
                                                           'Мин. запас суток',
                                                           'Время выгрузки'
                                                           ])
    excel_writer.save()
    path = '/home/administrator/aob-test/files/реализация_'+str(timenow)+'.xlsx'
    return send_file(path)


@bp.route('/online', methods=['POST', 'GET'])
@login_required
def online():
    azs_list = AzsList.query.order_by('number').all()
    online = FuelResidue.query.outerjoin(AzsList).outerjoin(Tanks).order_by(AzsList.number).all()
    tanks_list = Tanks.    query.all()
    return render_template('online.html', title='Online остатки', online_active=True,
                           online=online, azs_list=azs_list, tanks_list=tanks_list,
                           datetime=datetime.now().strftime("%Y-%m-%d-%H-%M"))


@bp.route('/page/azs/id<id>', methods=['POST', 'GET'])
@login_required
def page_azs(id):
    azs_list = AzsList.query.filter_by(id=id).first()
    tanks_list = Tanks.query.filter_by(azs_id=id).all()
    online = FuelResidue.query.outerjoin(Tanks).order_by(Tanks.tank_number).all()
    realisation = FuelRealisation.query.all()
    return render_template('page_azs.html', title='АЗС № ' + str(azs_list.number), page_azs_active=True,
                           online=online, realisation=realisation, azs_list=azs_list, tanks_list=tanks_list,
                           azs_list_active=True)


@bp.route('/download_realisation_info')
@login_required
def download_realisation_info():
    if current_user.get_task_in_progress('download_realisation_info'):
        flash(_('Выгрузка данных уже выполняется!'))
    else:
        current_user.launch_task('download_realisation_info', _('Выгружаю данные по реализации...'))
        db.session.commit()
    return redirect(url_for('main.realisation'))


@bp.route('/realisation', methods=['POST', 'GET'])
@login_required
def realisation():
    azs_list = AzsList.query.all()
    realisation = FuelRealisation.query.order_by(FuelRealisation.shop_id).all()
    tanks_list = Tanks.query.all()
    return render_template('realisation.html', title='Реализация топлива', realisation_active=True,
                           realisation=realisation, azs_list=azs_list, tanks_list=tanks_list,
                           datetime=datetime.now().strftime("%Y-%m-%d-%H-%M"))


@bp.route('/priority', methods=['GET', 'POST'])
@login_required
def priority():
    azs_list = AzsList.query.all()
    tanks_list = Tanks.query.all()
    priority = Priority.query.order_by("priority").all()
    priority_list = PriorityList.query.all()
    return render_template('priority.html', title='Список АЗС по приоритету', priority_active=True,
                           azs_list=azs_list, priority=priority, tanks_list=tanks_list, priority_list=priority_list)


@bp.route('/manual/id<id>', methods=['GET', 'POST'])
@login_required
def manual_input(id):
    tank = Tanks.query.filter_by(id=id).first_or_404()
    azs = AzsList.query.filter_by(id=tank.azs_id).first_or_404()
    form = ManualInputForm()
    if form.validate_on_submit():
        input = ManualInfo(fuel_volume=form.residue.data, fuel_realisation_max=form.realisation.data, tank_id=id,
                           timestamp=datetime.now())

        db.session.add(input)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('manual.html', title='Ручной ввод данных',
                           manual_input=True,
                           form=form,
                           azs_number=str(azs.number),
                           tank_number=str(tank.tank_number))


@bp.route('/azs', methods=['POST', 'GET'])
@login_required
def azs_redirect():
    azs = AzsList.query.first_or_404()
    return redirect(url_for('main.azs', id=azs.id))


@bp.route('/page/azs/', methods=['POST', 'GET'])
@login_required
def azs():
    azs_list = AzsList.query.order_by("number").all()
    return render_template('azs_list.html', azs_list=azs_list, title="Список АЗС", azs_list_active=True)


@bp.route('/start', methods=['POST', 'GET'])
@login_required
def start():
    def check():
        errors = 0
        azs_list = AzsList.query.all()
        error_tank_list = list()
        for azs in azs_list:
            if azs.active:
                tanks_list = Tanks.query.filter_by(azs_id=azs.id, active=True).all()
                for tank in tanks_list:
                    if tank.active:
                        residue = FuelResidue.query.filter_by(tank_id=tank.id).first()
                        realisation = FuelRealisation.query.filter_by(tank_id=tank.id).first()
                        if residue.fuel_volume is None or residue.fuel_volume <= 0:
                            print('   Резервуар №' + str(tank.tank_number) + ' не содержит данных об остатках! ')
                            '''error_text = "Ошибка при подключении к базе данных АЗС №" + str(i.number)
                            sql = Errors(timestamp=datetime.now(), error_text=error_text, azs_id=i.id, active=True,
                                         error_type="connection_error")
                            db.session.add(sql)
                            db.session.commit()'''
                            errors = errors + 1
                            error_tank_list.append(tank.id)
                        if realisation.fuel_realisation_1_days is None or realisation.fuel_realisation_1_days <= 0:
                            print('   Резервуар №' + str(tank.tank_number) + ' не содержит данных о реализации! ')
                            errors = errors + 1
                            error_tank_list.append(tank.id)
                        priority_list = PriorityList.query.all()
                        for priority in priority_list:
                            if priority.day_stock_from <= realisation.days_stock_min <= priority.day_stock_to:
                                this_priority = PriorityList.query.filter_by(priority=priority.priority).first_or_404()
                                if not this_priority.id:
                                    print('Резервуар №' + str(tank.tank_number) +
                                          ' не попадает в диапазон приоритетов!!!')
        return errors, error_tank_list

    def preparation():
        print("Подготовка начата")
        db.session.query(TempAzsTrucks).delete()
        db.session.commit()
        azs_list = AzsList.query.filter_by(active=True).all()
        truck_list = Trucks.query.filter_by(active=True).all()
        variant_counter = 1
        for azs in azs_list:
            for truck in truck_list:
                fuel_types = list()
                truck_tanks = TruckTanks.query.filter_by(truck_id=truck.id).all()
                truck_tanks_count = TruckTanks.query.filter_by(truck_id=truck.id).count()
                if truck_tanks_count == 1:
                    for a in range(1, 4):
                        fuel_types = [a]
                        for index, type in enumerate(fuel_types):
                            if type is 1:
                                fuel_types[index] = 92
                            elif type is 2:
                                fuel_types[index] = 95
                            elif type is 3:
                                fuel_types[index] = 50

                            tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                   number=index + 1).first()

                            sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id, truck_tank_id=tanks_row.id,
                                                truck_id=truck.id, fuel_type=fuel_types[index],
                                                capacity=tanks_row.capacity)
                            db.session.add(sql)

                        variant_counter = variant_counter + 1
                if truck_tanks_count == 2:
                    for a in range(1, 4):
                        for b in range(1, 4):
                            fuel_types = [a, b]
                            for index, type in enumerate(fuel_types):
                                if type is 1:
                                    fuel_types[index] = 92
                                elif type is 2:
                                    fuel_types[index] = 95
                                elif type is 3:
                                    fuel_types[index] = 50

                                tanks_row = TruckTanks.query.filter_by(truck_id=truck.id, number=index + 1).first()
                                sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                    truck_tank_id=tanks_row.id,
                                                    truck_id=truck.id, fuel_type=fuel_types[index],
                                                    capacity=tanks_row.capacity)
                                db.session.add(sql)


                            variant_counter = variant_counter + 1

                if truck_tanks_count == 3:
                    for a in range(1, 4):
                        for b in range(1, 4):
                            for c in range(1, 4):
                                fuel_types = [a, b, c]
                                for index, type in enumerate(fuel_types):
                                    if type is 1:
                                        fuel_types[index] = 92
                                    elif type is 2:
                                        fuel_types[index] = 95
                                    elif type is 3:
                                        fuel_types[index] = 50

                                    tanks_row = TruckTanks.query.filter_by(truck_id=truck.id, number=index + 1).first()

                                    sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                        truck_tank_id=tanks_row.id,
                                                        truck_id=truck.id, fuel_type=fuel_types[index],
                                                        capacity=tanks_row.capacity)
                                    db.session.add(sql)

                                variant_counter = variant_counter + 1

                if truck_tanks_count == 4:
                    for a in range(1, 4):
                        for b in range(1, 4):
                            for c in range(1, 4):
                                for d in range(1, 4):
                                    fuel_types = [a, b, c, d]
                                    for index, type in enumerate(fuel_types):
                                        if type is 1:
                                            fuel_types[index] = 92
                                        elif type is 2:
                                            fuel_types[index] = 95
                                        elif type is 3:
                                            fuel_types[index] = 50

                                        tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                               number=index + 1).first()

                                        sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                            truck_tank_id=tanks_row.id,
                                                            truck_id=truck.id, fuel_type=fuel_types[index],
                                                            capacity=tanks_row.capacity)
                                        db.session.add(sql)

                                    variant_counter = variant_counter + 1
                    if truck_tanks_count == 5:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    for d in range(1, 4):
                                        for e in range(1, 4):
                                            fuel_types = [a, b, c, d, e]
                                            for index, type in enumerate(fuel_types):
                                                if type is 1:
                                                    fuel_types[index] = 92
                                                elif type is 2:
                                                    fuel_types[index] = 95
                                                elif type is 3:
                                                    fuel_types[index] = 50

                                                tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                                       number=index + 1).first()

                                                sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                                    truck_tank_id=tanks_row.id,
                                                                    truck_id=truck.id, fuel_type=fuel_types[index],
                                                                    capacity=tanks_row.capacity)
                                                db.session.add(sql)

                                            variant_counter = variant_counter + 1
                    if truck_tanks_count == 6:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    for d in range(1, 4):
                                        for e in range(1, 4):
                                            for f in range(1, 4):
                                                fuel_types = [a, b, c, d, e, f]
                                            for index, type in enumerate(fuel_types):
                                                if type is 1:
                                                    fuel_types[index] = 92
                                                elif type is 2:
                                                    fuel_types[index] = 95
                                                elif type is 3:
                                                    fuel_types[index] = 50

                                                tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                                       number=index + 1).first()

                                                sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                                    truck_tank_id=tanks_row.id,
                                                                    truck_id=truck.id, fuel_type=fuel_types[index],
                                                                    capacity=tanks_row.capacity)
                                                db.session.add(sql)

                                            variant_counter = variant_counter + 1
                    if truck_tanks_count == 7:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    for d in range(1, 4):
                                        for e in range(1, 4):
                                            for f in range(1, 4):
                                                for g in range(1, 4):
                                                    fuel_types = [a, b, c, d, e, f, g]
                                            for index, type in enumerate(fuel_types):
                                                if type is 1:
                                                    fuel_types[index] = 92
                                                elif type is 2:
                                                    fuel_types[index] = 95
                                                elif type is 3:
                                                    fuel_types[index] = 50

                                                tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                                       number=index + 1).first()

                                                sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                                    truck_tank_id=tanks_row.id,
                                                                    truck_id=truck.id, fuel_type=fuel_types[index],
                                                                    capacity=tanks_row.capacity)
                                                db.session.add(sql)

                                            variant_counter = variant_counter + 1
                    if truck_tanks_count == 8:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    for d in range(1, 4):
                                        for e in range(1, 4):
                                            for f in range(1, 4):
                                                for g in range(1, 4):
                                                    for h in range(1, 4):
                                                        fuel_types = [a, b, c, d, e, f, g, h]
                                            for index, type in enumerate(fuel_types):
                                                if type is 1:
                                                    fuel_types[index] = 92
                                                elif type is 2:
                                                    fuel_types[index] = 95
                                                elif type is 3:
                                                    fuel_types[index] = 50

                                                tanks_row = TruckTanks.query.filter_by(truck_id=truck.id,
                                                                                       number=index + 1).first()

                                                sql = TempAzsTrucks(variant_id=variant_counter, azs_id=azs.id,
                                                                    truck_tank_id=tanks_row.id,
                                                                    truck_id=truck.id, fuel_type=fuel_types[index],
                                                                    capacity=tanks_row.capacity)
                                                db.session.add(sql)

                                            variant_counter = variant_counter + 1
        db.session.commit()
        print("Подготовка закончена")

    def preparation_two():
        db.session.query(TempAzsTrucks2).delete()
        db.session.commit()
        print("Подготовка 2 начата")

        preparation_one = TempAzsTrucks.query.all()
        # Получаем количество вариантов заполнения бензовоза (благодаря таблице TempAzsTrucks полю - variant_id)
        preparation_one_last = TempAzsTrucks.query.order_by(desc(TempAzsTrucks.variant_id)).first_or_404()

        variant_counter_sliv = 1  # вариант слива для таблицы TempAzsTrucks2
        # Перебираем варианты налива бензовозов
        for variant in range(1, preparation_one_last.variant_id):
            # preparation_one_last.variant_id
            azs = TempAzsTrucks.query.filter_by(variant_id=variant).first_or_404()
            table_temp_azs_trucks = TempAzsTrucks.query.filter_by(variant_id=variant).all()
            # Узнаем сколько отсеков у бензовоза с каждым видом топлива
            tanks_counter_92 = TempAzsTrucks.query.filter_by(variant_id=variant, fuel_type=92).count()
            tanks_counter_95 = TempAzsTrucks.query.filter_by(variant_id=variant, fuel_type=95).count()
            tanks_counter_50 = TempAzsTrucks.query.filter_by(variant_id=variant, fuel_type=50).count()
            # Получаем id АЗС
            azs_id = azs.azs_id
            # Считаем количество резервуаров АЗС по каждому виду топлива
            table_tanks = Tanks.query.filter_by(azs_id=azs_id).all()
            count_92 = 0
            count_95 = 0
            count_50 = 0
            tanks_list_92 = list()
            tanks_list_95 = list()
            tanks_list_50 = list()
            for tank in table_tanks:
                if tank.fuel_type is 92:
                    tanks_list_92.append(tank.id)
                    count_92 = count_92 + 1
                elif tank.fuel_type is 95:
                    tanks_list_95.append(tank.id)
                    count_95 = count_95 + 1
                elif tank.fuel_type is 50:
                    tanks_list_50.append(tank.id)
                    count_50 = count_50 + 1

            truck_cell_capacity = list()
            cells_list_92 = list()
            cells_list_95 = list()
            cells_list_50 = list()

            cells_capacity_92 = list()
            cells_capacity_95 = list()
            cells_capacity_50 = list()
            for row in table_temp_azs_trucks:
                if row.fuel_type == 92:
                    cells_list_92.append(row.truck_tank_id)
                    cells_capacity_92.append(row.capacity)
                if row.fuel_type == 95:
                    cells_list_95.append(row.truck_tank_id)
                    cells_capacity_95.append(row.capacity)
                if row.fuel_type == 50:
                    cells_list_50.append(row.truck_tank_id)
                    cells_capacity_50.append(row.capacity)

            '''sum_92 = 0
            sum_95 = 0
            sum_50 = 0
            for row in table_temp_azs_trucks:
                if row.fuel_type is 92:
                    sum_92 = sum_92 + row.capacity
                if row.fuel_type is 95:
                    sum_92 = sum_95 + row.capacity
                if row.fuel_type is 50:
                    sum_92 = sum_50 + row.capacity'''
            table_sliv_variant_92 = None
            table_sliv_variant_50 = None
            table_sliv_variant_95 = None

            # Блаодаря тому, что мы знаем количество резервуаров АЗС и количество отсеков бензовоза с этим видом топлива
            # получаем нужную константную таблицу с вариантами слива бензовоза

            if count_92 == 1 and tanks_counter_92 == 1:
                table_sliv_variant_92 = Close1Tank1.query.all()

            if count_92 == 1 and tanks_counter_92 == 2:
                table_sliv_variant_92 = Close1Tank2.query.all()

            if count_92 == 1 and tanks_counter_92 == 3:
                table_sliv_variant_92 = Close1Tank3.query.all()

            if count_92 == 1 and tanks_counter_92 == 4:
                table_sliv_variant_92 = Close1Tank4.query.all()

            if count_92 == 2 and tanks_counter_92 == 1:
                table_sliv_variant_92 = Close2Tank1.query.all()

            if count_92 == 2 and tanks_counter_92 == 2:
                table_sliv_variant_92 = Close2Tank2.query.all()

            if count_92 == 2 and tanks_counter_92 == 3:
                table_sliv_variant_92 = Close2Tank3.query.all()

            if count_92 == 2 and tanks_counter_92 == 4:
                table_sliv_variant_92 = Close2Tank4.query.all()

            '''---------------------------------------------'''
            if count_95 == 1 and tanks_counter_95 == 1:
                table_sliv_variant_95 = Close1Tank1.query.all()

            if count_95 == 1 and tanks_counter_95 == 2:
                table_sliv_variant_95 = Close1Tank2.query.all()

            if count_95 == 1 and tanks_counter_95 == 3:
                table_sliv_variant_95 = Close1Tank3.query.all()

            if count_95 == 1 and tanks_counter_95 == 4:
                table_sliv_variant_95 = Close1Tank4.query.all()

            if count_95 == 2 and tanks_counter_95 == 1:
                table_sliv_variant_95 = Close2Tank1.query.all()

            if count_95 == 2 and tanks_counter_95 == 2:
                table_sliv_variant_95 = Close2Tank2.query.all()

            if count_95 == 2 and tanks_counter_95 == 3:
                table_sliv_variant_95 = Close2Tank3.query.all()

            if count_95 == 2 and tanks_counter_95 == 4:
                table_sliv_variant_95 = Close2Tank4.query.all()

            '''---------------------------------------------'''

            if count_50 == 1 and tanks_counter_50 == 1:
                table_sliv_variant_50 = Close1Tank1.query.all()

            if count_50 == 1 and tanks_counter_50 == 2:
                table_sliv_variant_50 = Close1Tank2.query.all()

            if count_50 == 1 and tanks_counter_50 == 3:
                table_sliv_variant_50 = Close1Tank3.query.all()

            if count_50 == 1 and tanks_counter_50 == 4:
                table_sliv_variant_50 = Close1Tank4.query.all()

            if count_50 == 2 and tanks_counter_50 == 1:
                table_sliv_variant_50 = Close2Tank1.query.all()

            if count_50 == 2 and tanks_counter_50 == 2:
                table_sliv_variant_50 = Close2Tank2.query.all()

            if count_50 == 2 and tanks_counter_50 == 3:
                table_sliv_variant_50 = Close2Tank3.query.all()

            if count_50 == 2 and tanks_counter_50 == 4:
                table_sliv_variant_50 = Close2Tank4.query.all()

            if table_sliv_variant_92 is not None:
                if count_92 == 1:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_92[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_92 == 2:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_92[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_92[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_92 == 3:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_92[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_92[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_92[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_92 == 4:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_92[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_92[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_92[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_92[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank4,
                                                 tank_id=tanks_list_92[3],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1

            ''' -------------------------------- '''
            ''' --- Для 95 вида топлива '''

            if table_sliv_variant_95 is not None:
                if count_95 == 1:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_95[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 2:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_95[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_95[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 3:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=92,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_95[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_95[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_92[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_95[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 4:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_95[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_95[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_95[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_95[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_95[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=95,
                                                 str_sliv=variant_sliv.tank4,
                                                 tank_id=tanks_list_95[3],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1

            ''' -------------------------------- '''
            ''' --- Для 50 вида топлива '''

            if table_sliv_variant_50 is not None:
                if count_50 == 1:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_50[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 2:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_50[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_50[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 3:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_50[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_50[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_50[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 4:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank1,
                                                 tank_id=tanks_list_50[0],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank2,
                                                 tank_id=tanks_list_50[1],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank3,
                                                 tank_id=tanks_list_50[2],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + cells_capacity_50[int(number) - 1]
                                str_sliv_cells_list.append(str(cells_list_50[int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            sql = TempAzsTrucks2(variant=variant,
                                                 azs_id=azs_id,
                                                 truck_id=azs.truck_id,
                                                 variant_sliv=variant_counter_sliv,
                                                 fuel_type=50,
                                                 str_sliv=variant_sliv.tank4,
                                                 tank_id=tanks_list_50[3],
                                                 truck_tank_id_string=str_sliv_cells,
                                                 sum_sliv=sum_sliv)
                            db.session.add(sql)

                        variant_counter_sliv = variant_counter_sliv + 1
            db.session.commit()
        print("Подготовка 2 закончена")

    def is_it_fit():
        residue = FuelResidue.query.all()
        for re in residue:
            temp_azs_trucks_2 = TempAzsTrucks2.query.filter_by(tank_id=re.tank_id).all()
            print(re.azs_id)
            trip = Trip.query.filter_by(azs_id=re.azs_id).first()
            print(trip.time_to)

            for row in temp_azs_trucks_2:
                realisation = FuelRealisation.query.filter_by(tank_id=re.tank_id).first()
                sliv = re.free_volume - row.sum_sliv
                if sliv < 0:
                    row.is_it_fit = False
                    realis = realisation.fuel_realisation_hour / 6
                    time_to_float = trip.time_to.hour
                    realis_time = realis * time_to_float
                    sliv_after_trip = re.free_volume - realis_time - row.sum_sliv
                    if sliv_after_trip < 0:
                        row.is_it_fit_later = False
                    else:
                        row.is_it_fit_later = True
                else:
                    row.is_it_fit = True
                    realis = realisation.fuel_realisation_hour / 6
                    time_to_float = trip.time_to.hour
                    realis_time = realis * time_to_float
                    sliv_after_trip = re.free_volume - realis_time - row.sum_sliv
                    if sliv_after_trip < 0:
                        row.is_it_fit_later = False
                    else:
                        row.is_it_fit_later = True
                row.new_fuel_volume = re.fuel_volume + row.sum_sliv

            db.session.commit()

    def preparation_three():
        # Перебираем варианты налива бензовозов
        preparation_two_last = TempAzsTrucks2.query.order_by(desc(TempAzsTrucks2.variant)).first_or_404()

        for variant in range(960, 3000):
            is_it_92 = 0
            is_it_95 = 0
            is_it_50 = 0
            is_it_92_sliv = 0
            is_it_95_sliv = 0
            is_it_50_sliv = 0
            temp_azs_trucks = TempAzsTrucks.query.filter_by(variant_id=variant).all()

            for row in temp_azs_trucks:
                if row.fuel_type == 92:
                    is_it_92 = True

                if row.fuel_type == 95:
                    is_it_95 = True

                if row.fuel_type == 50:
                    is_it_50 = True

            if is_it_92:
                temp_variant_sliv_first = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=92).order_by("variant_sliv").first()
                temp_variant_sliv_last = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=92).order_by(desc("variant_sliv")).first()
                temp_variant_sliv = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=92).all()
                trigger = 1
                for row in range(temp_variant_sliv_first.variant_sliv, temp_variant_sliv_last.variant_sliv+1):
                    i = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=92, variant_sliv=row).all()
                    for row in i:
                        if row.is_it_fit_later == 0:
                            trigger = 0
                if trigger == 1:
                    is_it_92_sliv = 1

            if is_it_95:
                temp_variant_sliv_first = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=95).order_by(
                    "variant_sliv").first()
                temp_variant_sliv_last = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=95).order_by(
                    desc("variant_sliv")).first()
                temp_variant_sliv = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=95).all()
                trigger = 1
                for row in range(temp_variant_sliv_first.variant_sliv, temp_variant_sliv_last.variant_sliv+1):
                    i = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=95, variant_sliv=row).all()
                    for row in i:
                        if row.is_it_fit_later == 0:
                            trigger = 0
                if trigger == 1:
                    is_it_95_sliv = 1

            if is_it_50:
                temp_variant_sliv_first = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=50).order_by("variant_sliv").first()
                temp_variant_sliv_last = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=50).order_by(desc("variant_sliv")).first()
                temp_variant_sliv = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=50).all()
                trigger = 1
                for row in range(temp_variant_sliv_first.variant_sliv, temp_variant_sliv_last.variant_sliv+1):
                    i = TempAzsTrucks2.query.filter_by(variant=variant, fuel_type=50, variant_sliv=row).all()
                    for row in i:
                        if row.is_it_fit_later == 0:
                            trigger = 0
                if trigger == 1:
                    is_it_50_sliv = 1
            if (is_it_92+is_it_95+is_it_50) == (is_it_92_sliv+is_it_95_sliv+is_it_50_sliv):
                print(variant)
                print("Заебися")
                print(is_it_92, is_it_95, is_it_50, is_it_92_sliv, is_it_95_sliv, is_it_50_sliv)

            else:
                x =1

    def create_today_trip():
        print("Формирование задания на сегодня")

        db.session.query(TripForToday).delete()
        db.session.commit()
        priority = Priority.query.order_by("priority").all()
        trucks = Trucks.query.all()
        truck_tanks = TruckTanks.query.all()
        temp_azs_trucks_2 = TempAzsTrucks2.query.all()
        fuel_list = list()
        trucks_list = list()
        trucks_number_list = list()
        fuel_list = [92, 95, 50]
        trucks_count = Trucks.query.filter_by(active=True).count()
        trucks = Trucks.query.filter_by(active=True).all()
        for truck in trucks:
            trucks_list.append(truck.id)
            trucks_number_list.append(truck.reg_number)
        number_of_priorities = Priority.query.order_by("id").limit(trucks_count*2).all()
        number_of_azs = list()
        for azs in number_of_priorities:
            azs_number = AzsList.query.filter_by(id=azs.azs_id).first()
            number_of_azs.append(azs_number.number)

        counter = 0
        for element in range(0, trucks_count):
            this_truck_tanks = TruckTanks.query.filter_by(truck_id=trucks_list[element]).all()
            fuel_types = list()
            fuel_types.clear()
            for cell in this_truck_tanks:
                fuel_type = random.choice(fuel_list)
                fuel_types.append(fuel_type)
            sql = TripForToday(azs_number=number_of_azs[counter],
                               truck_number=trucks_number_list[element],
                               truck_id=trucks_list[element],
                               zapolnenie=str(fuel_types).strip('[]'),
                               timestamp=datetime.now(),
                               trip_number=1)
            db.session.add(sql)
            counter = counter + 1

        for element in range(trucks_count, trucks_count*2):
            this_truck_tanks = TruckTanks.query.filter_by(truck_id=trucks_list[element-trucks_count]).all()
            fuel_types = list()
            fuel_types.clear()
            for cell in this_truck_tanks:
                fuel_type = random.choice(fuel_list)
                fuel_types.append(fuel_type)
            sql = TripForToday(azs_number=number_of_azs[counter],
                               truck_number=trucks_number_list[element-trucks_count],
                               truck_id=trucks_list[element-trucks_count],
                               zapolnenie=str(fuel_types).strip('[]'),
                               timestamp=datetime.now(),
                               trip_number=2)
            db.session.add(sql)
            counter = counter + 1
        db.session.commit()

    error, tanks = check()
    if error > 10:
        print("Number of error: " + str(error) + ", wrong tanks " + " ".join(str(x) for x in tanks))
        return redirect(url_for('main.index'))
    else:
        # preparation()

        # preparation_two()
        is_it_fit()
        # preparation_three()
        today_trip = TripForToday.query.first()
        db_date = today_trip.timestamp
        if today_trip and db_date.date() == date.today():
            flash('Расстановка бензовозов на сегодня уже сформирована!')
            return redirect(url_for('main.index'))
        else:
            flash('Расстановка выполнена')
            create_today_trip()

        return redirect(url_for('main.index'))
