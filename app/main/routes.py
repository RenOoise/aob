from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, send_file, Response
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from app import db
from app.main.forms import EditProfileForm, PostForm, SearchForm, MessageForm, ManualInputForm
from app.models import User, Post, Message, Notification, FuelResidue, AzsList, Tanks, FuelRealisation, Priority, \
    PriorityList, ManualInfo, Trucks, TruckTanks, TruckFalse, Trip, TempAzsTrucks, TempAzsTrucks2, WorkType, Errors, \
    Trips, Result, TrucksForAzs
from app.models import Close1Tank1, Close1Tank2, Close1Tank3, Close1Tank4, Close1Tank5, Close2Tank1, Close2Tank2, \
    Close2Tank3, Close2Tank4, Close2Tank5, Close3Tank1, Close3Tank2, Close3Tank3, Close3Tank4, Close3Tank5, Close4Tank1, \
    Close4Tank2, Close4Tank3, Close4Tank4, Close4Tank5, Test, TripForToday, TruckFalse,RealisationStats, TempAzsTrucks3, \
    TempAzsTrucks4
from app.translate import translate
from app.main import bp
import pandas as pd
from StyleFrame import StyleFrame, Styler, utils
from datetime import datetime, timedelta, date
import pygal
from pygal.style import Style, BlueStyle
import time
import random
import json
from sqlalchemy import desc


@bp.route('/stats', methods=['GET', 'POST'])
@login_required
def stats():

    # Graphs
    labels = []
    fuel_92 = list()
    fuel_95 = list()
    fuel_50 = list()
    previous_month = datetime.today() - timedelta(days=30)
    select_last_month = RealisationStats.query.filter(RealisationStats.date <= datetime.today(), previous_month < RealisationStats.date).filter_by(azs_id=1).all()
    for row in select_last_month:
        if row.fuel_type == 92:
            fuel_92.append(row.realisation)
            labels.append(datetime.strftime(row.date, "%d/%m"))
        elif row.fuel_type == 95:
            fuel_95.append(row.realisation)
        elif row.fuel_type == 50:
            fuel_50.append(row.realisation)

    graph = pygal.StackedLine(fill=True, style=BlueStyle, height=500)
    graph.title = 'Реализация топлива в течение месяца'
    graph.x_labels = labels
    graph.add('АИ-92', fuel_92)
    graph.add('АИ-95', fuel_95)
    graph.add('Дт', fuel_50)
    graph_data = graph.render_data_uri()

    return render_template('stats.html', title='Статистика по реализации за месяц', stats=True, graph_data=graph_data)


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
                        if residue is not None:
                            if residue.fuel_volume is None or residue.fuel_volume <= 0 \
                                    or residue.download_time < datetime.now()-timedelta(seconds=600):
                                if residue.download_time < datetime.now()-timedelta(seconds=600):
                                    error_text = "АЗС №" + str(azs.number) + ", резервуар №" + str(tank.tank_number) + \
                                                 " - возможно данные об остатках устарели"
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
                                             " - возможно данные о реализации устарели"
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


@bp.route('/online.json', methods=['POST', 'GET'])
@login_required
def online_json():
    rows = list()
    online = FuelResidue.query.outerjoin(AzsList).outerjoin(Tanks).order_by(AzsList.number).all()
    for i in online:
        tank = Tanks.query.filter_by(id=i.tank_id).first()
        if tank.deactive !=True:
            azs_number = AzsList.query.filter_by(id=i.azs_id).first()
            if len(str(azs_number.number)) == 1:
                azs_number = str(0) + str(azs_number.number)
            else:
                azs_number = str(azs_number.number)
            tank_number = Tanks.query.filter_by(id=i.tank_id).first()
            if i.auto == True:
                auto = "Автоматически"
            else:
                auto = "По книжным остаткам"
            row = {'azs_number': "АЗС №" + azs_number,
                   'url': url_for('main.page_azs', id=i.azs_id),
                   'tank_number': tank_number.tank_number,
                   'product_code': i.product_code,
                   'percent': str(i.percent) + str("%"),
                   'fuel_volume': i.fuel_volume,
                   'free_volume': i.free_volume,
                   'datetime': i.datetime.strftime("(%H:%M) %d.%m.%Y"),
                   'download_time': i.download_time.strftime("(%H:%M) %d.%m.%Y"),
                   'auto': auto
                   }

            rows.append(row)
    return Response(json.dumps(rows), mimetype='application/json')


@bp.route('/page/azs/id<id>', methods=['POST', 'GET'])
@login_required
def page_azs(id):
    azs_list = AzsList.query.filter_by(id=id).first()
    tanks_list = Tanks.query.filter_by(azs_id=id, active=True).all()
    online = FuelResidue.query.outerjoin(Tanks).order_by(Tanks.tank_number).all()
    realisation = FuelRealisation.query.all()
    check_if_exist = FuelResidue.query.filter_by(azs_id=id).first()

    # Graphs
    labels = []
    fuel_92 = list()
    fuel_95 = list()
    fuel_50 = list()
    previous_month = datetime.today() - timedelta(days=30)
    select_last_month = RealisationStats.query.filter(RealisationStats.date <= datetime.today(), previous_month < RealisationStats.date).filter_by(azs_id=id).all()
    for row in select_last_month:

        tank_id = row.tank_id
        sum_92 = 0
        sum_95 = 0
        sum_50 = 0
        if row.fuel_type == 92:
            if row.tank_id is tank_id:
                sum_92 = sum_92 + row.realisation
            fuel_92.append(row.realisation)
            labels.append(datetime.strftime(row.date, "%d/%m"))
        elif row.fuel_type == 95:
            fuel_95.append(row.realisation)
        elif row.fuel_type == 50:
            fuel_50.append(row.realisation)

    graph = pygal.StackedLine(fill=True, style=BlueStyle, height=500)
    graph.title = 'Реализация топлива в течение месяца'
    graph.x_labels = labels
    graph.add('АИ-92', fuel_92)
    graph.add('АИ-95', fuel_95)
    graph.add('Дт', fuel_50)
    graph_data = graph.render_data_uri()
    return render_template('page_azs.html', title='АЗС № ' + str(azs_list.number), page_azs_active=True,
                           online=online, realisation=realisation, azs_list=azs_list, tanks_list=tanks_list,
                           azs_list_active=True, check_if_exist=check_if_exist, graph_data=graph_data)


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


@bp.route('/realisation.json', methods=['POST', 'GET'])
@login_required
def realisation_json():
    rows = list()
    realisation = FuelRealisation.query.order_by(FuelRealisation.shop_id).all()
    for i in realisation:
        tank = Tanks.query.filter_by(id=i.tank_id).first()
        if tank.deactive !=True:
            azs_number = AzsList.query.filter_by(id=i.azs_id).first()
            if len(str(azs_number.number)) == 1:
                azs_number = str(0) + str(azs_number.number)
            else:
                azs_number = str(azs_number.number)
            tank_number = Tanks.query.filter_by(id=i.tank_id).first()
            row = {'azs_number': "АЗС №" + azs_number,
                   'tank_number': tank_number.tank_number,
                   'product_code': i.product_code,
                   'fuel_realisation_10_days': i.fuel_realisation_10_days,
                   'fuel_realisation_7_days': i.fuel_realisation_7_days,
                   'fuel_realisation_3_days': i.fuel_realisation_3_days,
                   'fuel_realisation_1_days': i.fuel_realisation_1_days,
                   'fuel_realisation_week_ago': i.fuel_realisation_week_ago,
                   'fuel_realisation_hour': i.days_stock_min,
                   'days_stock_min': i.fuel_realisation_hour,
                   'download_time': i.download_time.strftime("(%H:%M) %d.%m.%Y")
                   }

            rows.append(row)
    return Response(json.dumps(rows), mimetype='application/json')


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
                        if residue is not None:
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
        # функция создает таблицу всех возможных комбинаций налива топлива в бензовозы
        # для каждой азс и каждого бензовоза

        # очистка таблицы TempAzsTrucks в БД
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks`")
        # формируем массивы данных из БД
        azs_list = AzsList.query.filter_by(active=True).all()  # получаем список АКТИВНЫХ АЗС
        truck_list = Trucks.query.filter_by(active=True).all()  # получаем список АКТИВНЫХ бензовозов
        azs_tanks = Tanks.query.filter_by(active=True).all()  # получаем список АКТИЫНЫХ резервуаров всех АЗС
        truck_cells_list = TruckTanks.query.all()  # получаем список всех отсеков бензовозов
        # счетчик номера варианта налива
        variant_counter = 1
        # создаем список для записи в таблицу TempAzsTrucks
        temp_azs_truck_list = list()
        # создаем словарь для добавления в список temp_azs_trucks_list
        temp_azs_truck_dict = dict()
        for azs in azs_list:  # перебераем активные АЗС
            # создаем переменные для определения есть эти виды топлива на АЗС или нет
            is_92 = 0
            is_95 = 0
            is_50 = 0
            # перебираем таблицу из памяти со всеми АКТИЫНЫМИ резервуарами АЗС
            for row in azs_tanks:
                # проверяем есть ли у этой АЗС (которую перебираем в цикле) резервуары с 92 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 92):
                    is_92 = 1  # если есть, то помечаем соответствующий вид топлива
                # проверяем есть ли у этой АЗС резервуары с 95 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 95):
                    is_95 = 1  # если есть, то помечаем соответствующий вид топлива
                # проверяем есть ли у этой АЗС резервуары с 50 топливом
                if (row.azs_id == azs.id) and (row.fuel_type == 50):
                    is_50 = 1  # если есть, то помечаем соответствующий вид топлива

                # для ускорения проверяем, если все три вида топлив есть,
                # то можно цикл остановить, так как больше точно ничего не найдем
                if (is_92 == 1 and is_95 == 1 and is_50 == 1) and row.azs_id == azs.id:
                    break
            # В зависимости от найденных видов топлива на АЗС, формируем список
            azs_types = list()
            if (is_92 == 1) and (is_95 == 1) and (is_50 == 1):
                azs_types = [92, 95, 50]
            if (is_92 == 1) and (is_95 == 1) and (is_50 == 0):
                azs_types = [92, 95]
            if (is_92 == 1) and (is_95 == 0) and (is_50 == 1):
                azs_types = [92, 50]
            if (is_92 == 0) and (is_95 == 1) and (is_50 == 1):
                azs_types = [95, 50]
            if (is_92 == 1) and (is_95 == 0) and (is_50 == 0):
                azs_types = [92]
            if (is_92 == 0) and (is_95 == 1) and (is_50 == 0):
                azs_types = [95]
            if (is_92 == 0) and (is_95 == 0) and (is_50 == 1):
                azs_types = [50]

            # считаем количество отсеков в каждом из активных бензовозов
            # для этого:
            # перебираем список всех АКТИВНЫХ бензовозов
            for truck in truck_list:
                # создаем список для хранения видов топлива для заполнения данного бензовоза
                fuel_types = list()
                cell_counter = 0  # при смене бензовоза обнуляем счетчик отсеков
                for cell in truck_cells_list:  # перебираем все отсеки всех бензовозов
                    if cell.truck_id == truck.id:  # выбираем все отсеки у конкретного бензовоза
                        cell_counter = cell_counter + 1  # увеличиваем счетчик отсеков бензовоза
                # если у бензовоза ОДИН отсек
                if cell_counter == 1:
                    # тогда делаем 1 вложенный цикл, который перебирает все возможные виды топлива данной АЗС
                    for a in azs_types:
                        # добавляем в список один из всех возможных видов топлива данного бензовоза
                        fuel_types = [a]
                        # считаем количество отсеков с каждым видом топлива в данном варианте налива
                        cells_count_92 = 0
                        cells_count_95 = 0
                        cells_count_50 = 0
                        for i in fuel_types:
                            if i == 92:
                                cells_count_92 = cells_count_92 + 1
                            if i == 95:
                                cells_count_95 = cells_count_95 + 1
                            if i == 50:
                                cells_count_50 = cells_count_50 + 1

                        # перебираем все возможные виды топлива для данного бензовоза, с получением порядкового номера
                        # отсека и его емкости
                        for index, type in enumerate(fuel_types):
                            # перебираем список всего отсеков данного бензовоза
                            for cell in truck_cells_list:
                                # если нашли id нашего бензовоза и порядковый номер отсека совпадает с порядковым
                                # номером из списка fuel_types
                                if cell.truck_id == truck.id and cell.number == index + 1:
                                    # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                    temp_azs_truck_dict = {'variant_id': variant_counter,
                                                           'azs_id': azs.id,
                                                           'truck_tank_id': cell.id,
                                                           'truck_id': truck.id,
                                                           'fuel_type': fuel_types[index],
                                                           'capacity': cell.capacity,
                                                           'cells_92': cells_count_92,
                                                           'cells_95': cells_count_95,
                                                           'cells_50': cells_count_50}
                                    # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                    temp_azs_truck_list.append(temp_azs_truck_dict)
                                    # останавливаем итерацию цикла, так как искать больше нет смысла
                                    break
                        variant_counter = variant_counter + 1

                # если у бензовоза ДВА отсека
                if cell_counter == 2:
                    # тогда делаем 2 вложенных цикла которые переберают все возможные виды топлива данной азс
                    for a in azs_types:
                        for b in azs_types:
                            # добавляем в список два из всех возможных видов топлива данного бензовоза
                            fuel_types = [a, b]
                            # считаем количество отсеков с каждым видом топлива в данном варианте налива
                            cells_count_92 = 0
                            cells_count_95 = 0
                            cells_count_50 = 0
                            for i in fuel_types:
                                if i == 92:
                                    cells_count_92 = cells_count_92 + 1
                                if i == 95:
                                    cells_count_95 = cells_count_95 + 1
                                if i == 50:
                                    cells_count_50 = cells_count_50 + 1

                            # перебираем все возможные виды топлива для данного бензовоза,
                            # с получением порядкового номера отсека и его емкости
                            for index, type in enumerate(fuel_types):
                                # перебираем список всего отсеков данного бензовоза
                                for cell in truck_cells_list:
                                    # если нашли id нашего бензовоза и порядковый номер отсека совпадает с порядковым
                                    # номером из списка fuel_types
                                    if cell.truck_id == truck.id and cell.number == index + 1:
                                        # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                        temp_azs_truck_dict = {'variant_id': variant_counter,
                                                               'azs_id': azs.id,
                                                               'truck_tank_id': cell.id,
                                                               'truck_id': truck.id,
                                                               'fuel_type': fuel_types[index],
                                                               'capacity': cell.capacity,
                                                               'cells_92': cells_count_92,
                                                               'cells_95': cells_count_95,
                                                               'cells_50': cells_count_50}
                                        # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                        temp_azs_truck_list.append(temp_azs_truck_dict)
                                        # останавливаем итерацию цикла, так как искать больше нет смысла
                                        break
                # по аналогии для ТРЕХ отсеков бензовоза
                if cell_counter == 3:
                    for a in azs_types:
                        for b in azs_types:
                            for c in azs_types:
                                fuel_types = [a, b, c]
                                # считаем количество отсеков с каждым видом топлива в данном варианте налива
                                cells_count_92 = 0
                                cells_count_95 = 0
                                cells_count_50 = 0
                                for i in fuel_types:
                                    if i == 92:
                                        cells_count_92 = cells_count_92 + 1
                                    if i == 95:
                                        cells_count_95 = cells_count_95 + 1
                                    if i == 50:
                                        cells_count_50 = cells_count_50 + 1

                                # перебираем все возможные виды топлива для данного бензовоза,
                                # с получением порядкового номера отсека и его емкости
                                for index, type in enumerate(fuel_types):
                                    for cell in truck_cells_list:
                                        if cell.truck_id == truck.id and cell.number == index + 1:
                                            # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                            temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                   'azs_id': azs.id,
                                                                   'truck_tank_id': cell.id,
                                                                   'truck_id': truck.id,
                                                                   'fuel_type': fuel_types[index],
                                                                   'capacity': cell.capacity,
                                                                   'cells_92': cells_count_92,
                                                                   'cells_95': cells_count_95,
                                                                   'cells_50': cells_count_50}
                                            # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                            temp_azs_truck_list.append(temp_azs_truck_dict)
                                            # останавливаем итерацию цикла, так как искать больше нет смысла
                                            break
                                variant_counter = variant_counter + 1
                # по аналогии для ЧЕТЫРЕХ отсеков бензовоза
                if cell_counter == 4:
                    for a in azs_types:
                        for b in azs_types:
                            for c in azs_types:
                                for d in azs_types:
                                    fuel_types = [a, b, c, d]
                                    cells_count_92 = 0
                                    cells_count_95 = 0
                                    cells_count_50 = 0
                                    for i in fuel_types:
                                        if i == 92:
                                            cells_count_92 = cells_count_92 + 1
                                        if i == 95:
                                            cells_count_95 = cells_count_95 + 1
                                        if i == 50:
                                            cells_count_50 = cells_count_50 + 1
                                    for index, type in enumerate(fuel_types):
                                        for cell in truck_cells_list:
                                            if cell.truck_id == truck.id and cell.number == index + 1:
                                                # то формируем словарь с данными для записи в таблицу TempAzsTrucks в БД
                                                temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                       'azs_id': azs.id,
                                                                       'truck_tank_id': cell.id,
                                                                       'truck_id': truck.id,
                                                                       'fuel_type': fuel_types[index],
                                                                       'capacity': cell.capacity,
                                                                       'cells_92': cells_count_92,
                                                                       'cells_95': cells_count_95,
                                                                       'cells_50': cells_count_50}
                                                # добавляем словарь в список temp_azs_truck_list, созданный ранее
                                                temp_azs_truck_list.append(temp_azs_truck_dict)
                                                # останавливаем итерацию цикла, так как искать больше нет смысла
                                                break
                                    variant_counter = variant_counter + 1
                    # по аналогии для ПЯТИ отсеков бензовоза
                    if cell_counter == 5:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            fuel_types = [a, b, c, d, e]
                                            # считаем количество отсеков с каждым видом топлива в данном варианте налива
                                            cells_count_92 = 0
                                            cells_count_95 = 0
                                            cells_count_50 = 0
                                            for i in fuel_types:
                                                if i == 92:
                                                    cells_count_92 = cells_count_92 + 1
                                                if i == 95:
                                                    cells_count_95 = cells_count_95 + 1
                                                if i == 50:
                                                    cells_count_50 = cells_count_50 + 1

                                            for index, type in enumerate(fuel_types):
                                                for cell in truck_cells_list:
                                                    if cell.truck_id == truck.id and cell.number == index + 1:
                                                        # то формируем словарь с данными для записи в таблицу
                                                        # TempAzsTrucks в БД
                                                        temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                               'azs_id': azs.id,
                                                                               'truck_tank_id': cell.id,
                                                                               'truck_id': truck.id,
                                                                               'fuel_type': fuel_types[index],
                                                                               'capacity': cell.capacity,
                                                                               'cells_92': cells_count_92,
                                                                               'cells_95': cells_count_95,
                                                                               'cells_50': cells_count_50}
                                                        # добавляем словарь в список temp_azs_truck_list,
                                                        # созданный ранее
                                                        temp_azs_truck_list.append(temp_azs_truck_dict)
                                                        # останавливаем итерацию цикла, так как искать больше нет смысла
                                                        break

                                            variant_counter = variant_counter + 1
                    # по аналогии для ШЕСТИ отсеков бензовоза
                    if cell_counter == 6:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                fuel_types = [a, b, c, d, e, f]
                                                # считаем количество отсеков с каждым видом топлива
                                                # в данном варианте налива
                                                cells_count_92 = 0
                                                cells_count_95 = 0
                                                cells_count_50 = 0
                                                for i in fuel_types:
                                                    if i == 92:
                                                        cells_count_92 = cells_count_92 + 1
                                                    if i == 95:
                                                        cells_count_95 = cells_count_95 + 1
                                                    if i == 50:
                                                        cells_count_50 = cells_count_50 + 1

                                                for index, type in enumerate(fuel_types):
                                                    for cell in truck_cells_list:
                                                        if cell.truck_id == truck.id and cell.number == index + 1:
                                                            # то формируем словарь с данными для записи в таблицу
                                                            # TempAzsTrucks в БД
                                                            temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                   'azs_id': azs.id,
                                                                                   'truck_tank_id': cell.id,
                                                                                   'truck_id': truck.id,
                                                                                   'fuel_type': fuel_types[index],
                                                                                   'capacity': cell.capacity,
                                                                                   'cells_92': cells_count_92,
                                                                                   'cells_95': cells_count_95,
                                                                                   'cells_50': cells_count_50}
                                                            # добавляем словарь в список temp_azs_truck_list,
                                                            # созданный ранее
                                                            temp_azs_truck_list.append(temp_azs_truck_dict)
                                                            # останавливаем итерацию цикла,
                                                            # так как искать больше нет смысла
                                                            break

                                            variant_counter = variant_counter + 1
                    # по аналогии для СЕМИ отсеков бензовоза
                    if cell_counter == 7:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                for g in azs_types:
                                                    fuel_types = [a, b, c, d, e, f, g]

                                                    # считаем количество отсеков с каждым видом топлива
                                                    # в данном варианте налива
                                                    cells_count_92 = 0
                                                    cells_count_95 = 0
                                                    cells_count_50 = 0
                                                    for i in fuel_types:
                                                        if i == 92:
                                                            cells_count_92 = cells_count_92 + 1
                                                        if i == 95:
                                                            cells_count_95 = cells_count_95 + 1
                                                        if i == 50:
                                                            cells_count_50 = cells_count_50 + 1

                                                    for index, type in enumerate(fuel_types):
                                                        for cell in truck_cells_list:
                                                            if cell.truck_id == truck.id and cell.number == index + 1:
                                                                # то формируем словарь с данными для записи в таблицу
                                                                # TempAzsTrucks в БД
                                                                temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                       'azs_id': azs.id,
                                                                                       'truck_tank_id': cell.id,
                                                                                       'truck_id': truck.id,
                                                                                       'fuel_type': fuel_types[index],
                                                                                       'capacity': cell.capacity,
                                                                                       'cells_92': cells_count_92,
                                                                                       'cells_95': cells_count_95,
                                                                                       'cells_50': cells_count_50}
                                                                # добавляем словарь в список temp_azs_truck_list,
                                                                # созданный ранее
                                                                temp_azs_truck_list.append(temp_azs_truck_dict)
                                                                # останавливаем итерацию цикла, так как искать больше нет смысла
                                                                break

                                            variant_counter = variant_counter + 1
                    # по аналогии для ВОСЬМИ отсеков бензовоза
                    if cell_counter == 8:
                        for a in azs_types:
                            for b in azs_types:
                                for c in azs_types:
                                    for d in azs_types:
                                        for e in azs_types:
                                            for f in azs_types:
                                                for g in azs_types:
                                                    for h in azs_types:
                                                        fuel_types = [a, b, c, d, e, f, g, h]

                                                        # считаем количество отсеков с каждым видом топлива
                                                        # в данном варианте налива
                                                        cells_count_92 = 0
                                                        cells_count_95 = 0
                                                        cells_count_50 = 0
                                                        for i in fuel_types:
                                                            if i == 92:
                                                                cells_count_92 = cells_count_92 + 1
                                                            if i == 95:
                                                                cells_count_95 = cells_count_95 + 1
                                                            if i == 50:
                                                                cells_count_50 = cells_count_50 + 1

                                                        for index, type in enumerate(fuel_types):
                                                            for cell in truck_cells_list:
                                                                if cell.truck_id == truck.id and cell.number == index + 1:
                                                                    # то формируем словарь с данными для записи в таблицу
                                                                    # TempAzsTrucks в БД
                                                                    temp_azs_truck_dict = {'variant_id': variant_counter,
                                                                                           'azs_id': azs.id,
                                                                                           'truck_tank_id': cell.id,
                                                                                           'truck_id': truck.id,
                                                                                           'fuel_type': fuel_types[index],
                                                                                           'capacity': cell.capacity,
                                                                                           'cells_92': cells_count_92,
                                                                                           'cells_95': cells_count_95,
                                                                                           'cells_50': cells_count_50}
                                                                    # добавляем словарь в список temp_azs_truck_list,
                                                                    # созданный ранее
                                                                    temp_azs_truck_list.append(temp_azs_truck_dict)
                                                                    # останавливаем итерацию цикла,
                                                                    # так как искать больше нет смысла
                                                                    break

                                            variant_counter = variant_counter + 1
        # После выполнения функции записываем все полученные данные в таблицу TempAzsTrucks в базе данных
        return temp_azs_truck_list

    Close1_Tank1 = Close1Tank1.query.all()
    Close1_Tank2 = Close1Tank2.query.all()
    Close1_Tank3 = Close1Tank3.query.all()
    Close1_Tank4 = Close1Tank4.query.all()
    Close2_Tank1 = Close2Tank1.query.all()
    Close2_Tank2 = Close2Tank2.query.all()
    Close2_Tank3 = Close2Tank3.query.all()
    Close2_Tank4 = Close2Tank4.query.all()
    Close3_Tank1 = Close3Tank1.query.all()
    Close3_Tank2 = Close3Tank2.query.all()
    Close3_Tank3 = Close3Tank3.query.all()
    Close3_Tank4 = Close3Tank4.query.all()

    def select_close_tank_table(count, tanks_counter):
        if count == 1 and tanks_counter == 1:
            table_sliv_variant = Close1_Tank1
            return table_sliv_variant
        if count == 1 and tanks_counter == 2:
            table_sliv_variant = Close1_Tank2
            return table_sliv_variant
        if count == 1 and tanks_counter == 3:
            table_sliv_variant = Close1_Tank3
            return table_sliv_variant
        if count == 1 and tanks_counter == 4:
            table_sliv_variant = Close1_Tank4
            return table_sliv_variant

        if count == 2 and tanks_counter == 1:
            table_sliv_variant = Close2_Tank1
            return table_sliv_variant
        if count == 2 and tanks_counter == 2:
            table_sliv_variant = Close2_Tank2
            return table_sliv_variant
        if count == 2 and tanks_counter == 3:
            table_sliv_variant = Close2_Tank3
            return table_sliv_variant
        if count == 2 and tanks_counter == 4:
            table_sliv_variant = Close2_Tank4
            return table_sliv_variant

        if count == 3 and tanks_counter == 1:
            table_sliv_variant = Close3_Tank1
            return table_sliv_variant
        if count == 3 and tanks_counter == 2:
            table_sliv_variant = Close3_Tank2
            return table_sliv_variant
        if count == 3 and tanks_counter == 3:
            table_sliv_variant = Close3_Tank3
            return table_sliv_variant
        if count == 3 and tanks_counter == 4:
            table_sliv_variant = Close3_Tank4
            return table_sliv_variant

    # функция формирует все возмоные варианты слива топлива на АЗС
    def preparation_two():

        # очищаем таблицу
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks2`")
        # создаем массив для хранения сформированных итоговых данных
        # для последующей записи в таблицу TempAzsTrucks2 в БД
        temp_azs_trucks_2_list = list()
        temp_azs_trucks_2_dict = dict()
        # помещаем таблицу всех вариантов налива бензовозов TempAzsTrucks в переменную
        temp_azs_trucks = preparation()
        # помещаем таблицу всех АКТИВНЫХ АЗС в переменную
        table_azs_list = AzsList.query.filter_by(active=True).all()
        # помещаем таблицу все АКТИВНЫЕ резервуары АЗС в переменную
        table_tanks = Tanks.query.filter_by(active=True).all()

        # Получаем количество вариантов заполнения бензовоза (благодаря таблице TempAzsTrucks полю - variant_id)
        # счетчик варианта слива для таблицы TempAzsTrucks2
        variant_counter_sliv = 1
        # Для каждой АКТИВНОЙ АЗС считаем количество АКТИЫНЫХ резервуаров по каждому из видов топлива
        tanks_count = dict()
        # перебираем таблицу со списком АКТИВНЫХ АЗС

        for i in table_azs_list:

            # счетчик для хранения количества АКТИВНЫХ резервуаров данной азс
            tank_count_92 = 0
            tank_count_95 = 0
            tank_count_50 = 0
            # список с айдишниками АКТИВНЫХ резервуаров данной АЗС
            tanks_list_92 = list()
            tanks_list_95 = list()
            tanks_list_50 = list()
            # перебираем список АКТИВНЫХ резервуаров данной АЗС
            for tank in table_tanks:
                if i.id == tank.azs_id:
                    if tank.fuel_type == 92:
                        tank_count_92 = tank_count_92 + 1
                        tanks_list_92.append(tank.id)
                    if tank.fuel_type == 95:
                        tank_count_95 = tank_count_95 + 1
                        tanks_list_95.append(tank.id)
                    if tank.fuel_type == 50:
                        tank_count_50 = tank_count_50 + 1
                        tanks_list_50.append(tank.id)
                    tanks_count[i.id] = {
                        'tank_count_92': tank_count_92,
                        'tank_count_95': tank_count_95,
                        'tank_count_50': tank_count_50,
                        'tanks_list_92': tanks_list_92,
                        'tanks_list_95': tanks_list_95,
                        'tanks_list_50': tanks_list_50}
        # создаем словарь с обобщенными даннными для каждого варианта налива (основным ключем в словаре
        # является variant_id)
        slovar = dict()

        # создаем словарь с заполнеными ключами "variant_id, truck_id, cells_92, cells_95 и cells_50".
        # Остальные ячейки обнуляем
        for i in temp_azs_trucks:
            slovar[i['variant_id']] = {'azs_id': i['azs_id'],
                                       'cells_list_92': [],
                                       'cells_list_95': [],
                                       'cells_list_50': [],
                                       'capacity_92': 0,
                                       'capacity_95': 0,
                                       'capacity_50': 0,
                                       'cells_92': i['cells_92'],
                                       'cells_95': i['cells_95'],
                                       'cells_50': i['cells_50'],
                                       'truck_id': i['truck_id'],
                                       'cells_capacity_list_92': [],
                                       'cells_capacity_list_95': [],
                                       'cells_capacity_list_50': []
                                       }
        # перебираем таблицу TempAzsTrucks с вариантами налива и дополняем словарь
        for i in temp_azs_trucks:
            # обращаемся к ячейкам словаря по ключу variant_id
            temp_variant = i['variant_id']
            # если в текущей строке в таблице TempAzsTrucks вид топлива - 92,
            # то заполняем словарь согласно таблице для этого вида топлива
            if i['fuel_type'] == 92:
                # создаем пустой список для хранения айдишников отвеков бензовоза
                cells_list_92 = list()
                # создаем пустой список для хранения емкостей отсеков бензовоза
                cells_capacity_list_92 = list()
                # добавляем емкость отсека из текущей строки в список
                cells_capacity_list_92.append(i['capacity'])
                # добавляем айдишник отсека из текущей строки в список
                cells_list_92.append(i['truck_tank_id'])
                # обновляем данные в словаре
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'] + i['capacity'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'] + cells_list_92,
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'],
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'],
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'] + cells_capacity_list_92,
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'],
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50']
                                        }
            # выполняем действия для 95 вида топлива по аналогии с 92 видом топлива
            if i['fuel_type'] == 95:
                cells_list_95 = list()
                cells_capacity_list_95 = list()
                cells_capacity_list_95.append(i['capacity'])
                cells_list_95.append(i['truck_tank_id'])
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'] + i['capacity'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'],
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'] + cells_list_95,
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'],
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'],
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'] + cells_capacity_list_95,
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50']
                                        }

            # выполняем действия для дизеля вида топлива по аналогии с 92 и 95 видами топлива
            if i['fuel_type'] == 50:
                cells_list_50 = list()
                cells_capacity_list_50 = list()
                cells_capacity_list_50.append(i['capacity'])
                cells_list_50.append(i['truck_tank_id'])
                slovar[temp_variant] = {'azs_id': i['azs_id'],
                                        'capacity_92': slovar[temp_variant]['capacity_92'],
                                        'capacity_95': slovar[temp_variant]['capacity_95'],
                                        'capacity_50': slovar[temp_variant]['capacity_50'] + i['capacity'],
                                        'cells_list_92': slovar[temp_variant]['cells_list_92'],
                                        'cells_list_95': slovar[temp_variant]['cells_list_95'],
                                        'cells_list_50': slovar[temp_variant]['cells_list_50'] + cells_list_50,
                                        'cells_92': slovar[temp_variant]['cells_92'],
                                        'cells_95': slovar[temp_variant]['cells_95'],
                                        'cells_50': slovar[temp_variant]['cells_50'],
                                        'truck_id': slovar[temp_variant]['truck_id'],
                                        'cells_capacity_list_92': slovar[temp_variant]['cells_capacity_list_92'],
                                        'cells_capacity_list_95': slovar[temp_variant]['cells_capacity_list_95'],
                                        'cells_capacity_list_50': slovar[temp_variant]['cells_capacity_list_50'] + cells_capacity_list_50
                                        }

        # перебираем варианты налива от первого до последнего
        for variant in range(1, temp_azs_trucks[-1]['variant_id']):
            # получаем айдишник текущей АЗС
            azs_id = slovar[variant]['azs_id']
            # Получаем количество резервуаров АЗС по каждому виду топлива
            count_92 = tanks_count[azs_id]['tank_count_92']
            count_95 = tanks_count[azs_id]['tank_count_95']
            count_50 = tanks_count[azs_id]['tank_count_50']
            # создаем переменные для хранения таблиц необходимых для перебора всех возможных вариантов слива
            table_sliv_variant_92 = None
            table_sliv_variant_50 = None
            table_sliv_variant_95 = None

            # Благодаря тому, что мы знаем количество резервуаров АЗС и количество отсеков бензовоза с этим видом
            # топлива получаем нужную константную таблицу с вариантами слива бензовоза
            # для 92 вида топлива
            if count_92 == 1 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 1 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 2 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 1:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 2:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 3:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            if count_92 == 3 and slovar[variant]['cells_92'] == 4:
                table_sliv_variant_92 = select_close_tank_table(count_92, slovar[variant]['cells_92'])

            # для 95 вида топлива
            if count_95 == 1 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 1 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 2 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 1:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 2:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 3:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            if count_95 == 3 and slovar[variant]['cells_95'] == 4:
                table_sliv_variant_95 = select_close_tank_table(count_95, slovar[variant]['cells_95'])

            # # для 50 вида топлива
            if count_50 == 1 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 1 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 2 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 1:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 2:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 3:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])

            if count_50 == 3 and slovar[variant]['cells_50'] == 4:
                table_sliv_variant_50 = select_close_tank_table(count_50, slovar[variant]['cells_50'])
            # если у данной АЗС есть 92 топливо, то перебираем таблицу, возвращенную функцией select_close_tank_table
            if table_sliv_variant_92 is not None:
                # если резервуар с таким видом топлива один, то
                if count_92 == 1:
                    # перебираем таблицу
                    for variant_sliv in table_sliv_variant_92:
                        # если первая ячейка таблицы не пуста или не равна NULL, то
                        if variant_sliv.tank1 is not None:
                            # обнуляем счетчик суммарного слива
                            sum_sliv = 0
                            # создаем список, в котором будем хранить айди отсеков бензовоза в виде строковых параметров
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            # перебираем варианты слива, записанные в виде строки, разделенные знаком "+"
                            # из таблицы table_sliv_variant_92
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                # по индексу получаем емкость каждого отсека, суммируем емкости
                                # и получаем суммарный слив
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                # по индексу получаем айди отсеков бензовоза, и формирвем из них строку,
                                # где айди разделены знаком "+"
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            # формируем целую строку
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            # заполняем словарь полученными даннми
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            # добавляем полученынй словарь в списокдля последующей записи в базу
                            # в таблицу TempAzsTrucks2
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        # увеличиваем счетчик варианта слива на единицу
                        variant_counter_sliv = variant_counter_sliv + 1
                # для двух резервуаров выполняем те же действия как с одним
                if count_92 == 2:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()

                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()

                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1
                # для трех резервуаров, по аналогии с одним
                if count_92 == 3:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1
                # по аналогии с 4 резервуарами
                if count_92 == 4:
                    for variant_sliv in table_sliv_variant_92:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_92'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_92'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 92,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_92'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)

                        variant_counter_sliv = variant_counter_sliv + 1

            # --- Для 95 вида топлива выполняем по аналогии с 92 видом топлива
            if table_sliv_variant_95 is not None:
                if count_95 == 1:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 2:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 3:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_95 == 4:
                    for variant_sliv in table_sliv_variant_95:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_95'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_95'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 95,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_95'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
            # --- Для 50 вида топлива выполняем по аналогии с 92 и 95 видом топлива
            if table_sliv_variant_50 is not None:
                if count_50 == 1:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 2:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 3:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""

                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
                if count_50 == 4:
                    for variant_sliv in table_sliv_variant_50:
                        if variant_sliv.tank1 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank1.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank1,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][0],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank2 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank2.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank2,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][1],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank3 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank3.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id' : azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank3,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][2],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        if variant_sliv.tank4 is not None:
                            sum_sliv = 0
                            str_sliv_cells_list = list()
                            str_sliv_cells = ""
                            for index, number in enumerate(variant_sliv.tank4.split('+')):
                                sum_sliv = sum_sliv + slovar[variant]['cells_capacity_list_50'][int(number) - 1]
                                str_sliv_cells_list.append(str(slovar[variant]['cells_list_50'][int(number) - 1]))
                            str_sliv_cells = '+'.join(str_sliv_cells_list)
                            temp_azs_trucks_2_dict = {'variant': variant,
                                                      'azs_id': azs_id,
                                                      'truck_id': slovar[variant]['truck_id'],
                                                      'variant_sliv': variant_counter_sliv,
                                                      'fuel_type': 50,
                                                      'str_sliv': variant_sliv.tank4,
                                                      'tank_id': tanks_count[azs_id]['tanks_list_50'][3],
                                                      'truck_tank_id_string': str_sliv_cells,
                                                      'sum_sliv': sum_sliv
                                                      }
                            temp_azs_trucks_2_list.append(temp_azs_trucks_2_dict)
                        variant_counter_sliv = variant_counter_sliv + 1
        db.engine.execute(TempAzsTrucks.__table__.insert(), temp_azs_trucks)
        return temp_azs_trucks_2_list

    ''' 
    # функция определяет может ли вариант слива в данный момент слиться на АЗС,
    # сможет ли вариант слива слиться после времени бензовоза в пути
    # определяет новый запас суток
    # определяет остатки топлива после слива
    # определяет, может ли бензовой зайти на АЗС
    # может ли этот варинат налива пройти по дороге с весами
    '''
    def is_it_fit():
        temp_azs_trucks_2_list = preparation_two()
        # получаем остатки из базы
        residue = FuelResidue.query.all()
        # получаем реализацию из базы
        realisation = FuelRealisation.query.all()
        # получаем информацию о времени до азс
        trip = Trip.query.all()
        # получаем информанию об азс, на которые не могут заехать определенные бензовозы
        trucks_false = TruckFalse.query.all()
        # создаем пустой словарь для хранеия в нем данных о реализации и остатков
        realisation_n_residue = dict()
        # создаем пустой словарь для хранеия в нем данных времени пути до АЗС
        azs_trip_access = dict()
        azs_trip_time = dict()
        # заполняем словарь с данными об остатках топлива
        for i in residue:
            realisation_n_residue[i.tank_id] = {'azs_id': i.azs_id,  # id_АЗС
                                                'fuel_volume': i.fuel_volume,  # остаток топлива в резервуаре
                                                'free_volume': i.free_volume,  # свободная емкость в резервуаре
                                                # реализация в резервуаре (нулевая, так как заполняем ее потом)
                                                'fuel_realisation': 0,
                                                # максимальная реализация топлива в резервуаре (среди всех периодов)
                                                'fuel_realisation_max': 0
                                                }
        # заполняем словарь данными о реализации топлива
        for i in realisation:
            realisation_n_residue[i.tank_id] = {'azs_id': i.azs_id,  # id_АЗС
                                                # Оставляем прошлое значение остатка топлива в резервуаре
                                                'fuel_volume': realisation_n_residue[i.tank_id]['fuel_volume'],
                                                # свободная емкость в резервуаре
                                                'free_volume': realisation_n_residue[i.tank_id]['free_volume'],
                                                # Добавляем в словарь реализацию из этого резервуара
                                                # (среднюю в час за шестичасовой период)
                                                'fuel_realisation': i.fuel_realisation_hour / 6,
                                                # максимальная реализация топлива в резервуаре (среди всех периодов)
                                                'fuel_realisation_max': i.fuel_realisation_max
                                                }

        # формируем словарь для хранения данных о растоянии до АЗС и времени пути
        for i in trip:
            azs_trip_time[i.azs_id] = {'time_to_before_lunch': i.time_to_before_lunch,
                                       'time_to': i.time_to,
                                       'weigher': i.weigher}
        # формируем словарь для хранения данных о бензовозах и азс на которые они не могут заезжать
        for i in trucks_false:
            azs_trip_access[str(i.azs_id)+'-'+str(i.truck_id)] = {'access': False}

        is_it_fit_list = list()
        for i in temp_azs_trucks_2_list:
            # проверяем, сольется ли бензовоз в данный момент
            # из свободной емкости резервуара вычитаем сумму слива бензовоза
            sliv = realisation_n_residue[i['tank_id']]['free_volume'] - i['sum_sliv']
            # переводим время из вида db.time() в strptime() и переводим результат в секунды
            time_to_string = azs_trip_time[i['azs_id']]['time_to_before_lunch']
            x = time.strptime(str(time_to_string), '%H:%M:%S')
            time_to_seconds = timedelta(hours=x.tm_hour, minutes=x.tm_min,
                                        seconds=x.tm_sec).total_seconds()
            # считаем примерное количество топлива, которое будет реализовано за время в пути бензовоза
            realis_time = realisation_n_residue[i["tank_id"]]['fuel_realisation'] * ((time_to_seconds / 60) / 60)
            # проверяем сольется ли бензовоз, с учетом реализации за время его пути к АЗС
            # из свободной емкости резервуара вычитаем сумму слива бензовоза, и прибавляем количество топлива,
            # которое реализуется у данного резервуара за время пути бензовоза к ней
            sliv_later = realisation_n_residue[i['tank_id']]['free_volume'] - i['sum_sliv'] + realis_time

            # если бензовоз не сливается в данный момент (то есть переменная sliv - меньше нуля)
            if sliv < 0:
                # записываем в базу, что бензовоз в данный момент слиться не сможет
                i['is_it_fit'] = False
                # новый запас суток и новые остатки не считаем
                i['new_fuel_volume'] = 0
                i['new_days_stock'] = 0
            # если бензовоз сможет слиться натекущий момент (то есть переменная sliv - больше нуля)
            else:
                # записываем в базу, что бензовоз в данный момент сольется
                i['is_it_fit'] = True
                # расчитываем количество отстатков в резервуаре после слива
                i['new_fuel_volume'] = realisation_n_residue[i['tank_id']]['free_volume'] + i['sum_sliv']
                # расчитываем новый запас суток
                i['new_days_stock'] = i['new_fuel_volume'] / realisation_n_residue[i['tank_id']]['fuel_realisation_max']
            # если бензовоз не сливается после времени затраченного на дорогу (то есть переменная sliv_later
            # - меньше нуля)
            if sliv_later < 0:
                # записываем в базу, что бензовоз слиться не сможет
                i['is_it_fit_later'] = False
                # новый запас суток и новые остатки не считаем
                i['new_fuel_volume'] = 0
                i['new_days_stock'] = 0
            else:
                # записываем в базу, что бензовоз сольется спустя время затраченное на дорогу
                i['is_it_fit_later'] = True
                # расчитываем количество отстатков в резервуаре после слива
                i['new_fuel_volume'] = realisation_n_residue[i['tank_id']]['free_volume'] + i['sum_sliv']
                # расчитываем новый запас суток
                i['new_days_stock'] = i['new_fuel_volume'] / realisation_n_residue[i['tank_id']]['fuel_realisation_max']
            # проверяем, сможет ли бензовоз заехать на АЗС (нет ли для него никаких ограничений)
            # т.е. проверяем наличие ключа в словаре azs_trip_access, в котором содержатся ограничения для бензовозов
            # ключ АЗС-АйдиБензовоза
            if str(i['azs_id']) + '-' + str(i['truck_id']) in azs_trip_access:
                # если ограничения есть, то ставим False
                i['is_it_able_to_enter'] = False
            else:
                # если ограничений нет, то ставим True
                i['is_it_able_to_enter'] = True
            # добавляем словарь в список для записи в базу данных, в таблицу TempAzsTrucks2
            is_it_fit_list.append(i)
        # создаем словарь для хранения переменных с информацией о том, влезет ли определенный вид топлива
        # в резервуар на АЗС (3 переменные по всем видам топлива)
        fuel_types_dict = dict()
        # создаем список  для хранеия обновленной таблицы TempAzsTrucks2
        is_variant_sliv_good_list = list()
        # заполняем переменные словаря fuel_types_dict единицами
        # ключем в словаре является связка variant:variant_sliv
        for i in is_it_fit_list:
            fuel_types_dict[str(i['variant'])+':'+str(i['variant_sliv'])] = {'is_it_fit_92': 1,
                                                                             'is_it_fit_95': 1,
                                                                             'is_it_fit_50': 1}
        # заново перебираем таблицу TempAzsTrucks2(которая хранится в виде списка словарей)
        for i in is_it_fit_list:
            # в переменную key заносим ключ итого словаря (связка variant:variant_sliv)
            key = str(i['variant']) + ':' + str(i['variant_sliv'])
            # если находим вид топлива которое не сливается, то помечаем его нулем
            if i['fuel_type'] == 92 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': 0,
                                        'is_it_fit_95': fuel_types_dict[key]['is_it_fit_95'],
                                        'is_it_fit_50': fuel_types_dict[key]['is_it_fit_50']}
            if i['fuel_type'] == 95 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': fuel_types_dict[key]['is_it_fit_92'],
                                        'is_it_fit_95': 0,
                                        'is_it_fit_50': fuel_types_dict[key]['is_it_fit_50']}
            if i['fuel_type'] == 50 and i['is_it_fit_later'] == 0:
                fuel_types_dict[key] = {'is_it_fit_92': fuel_types_dict[key]['is_it_fit_92'],
                                        'is_it_fit_95': fuel_types_dict[key]['is_it_fit_95'],
                                        'is_it_fit_50': 0}
        # снова беребираем список словарей с данными из таблицы TempAzsTrucks2
        for i in is_it_fit_list:
            # в переменную key заносим ключ итого словаря (связка variant:variant_sliv)
            key = str(i['variant']) + ':' + str(i['variant_sliv'])
            # если все три вида топлива (или все виды топлива которые мы везем на азс) сливаются, то помечаем столбец
            # в котором хранится информация о том, сливается ли данный вариант (is_variant_sliv_good) единицей
            if fuel_types_dict[key]['is_it_fit_92'] == 1 and fuel_types_dict[key]['is_it_fit_95'] == 1 and fuel_types_dict[key]['is_it_fit_50'] == 1:
                i['is_variant_sliv_good'] = 1
                # добавляем обновленный словарь в список
                is_variant_sliv_good_list.append(i)
            # если не все топливо из данного варианта слива сливается, то ставим в ячейке ноль (False)
            else:
                i['is_variant_sliv_good'] = 0
                # добавляем обновленный словарь в список
                is_variant_sliv_good_list.append(i)
        # создаем словарь для хранения обновленных данных (по факту - в словаре появится ячейка is_variant_good)
        is_variant_good_list = dict()
        # перебираем список словарей с данными из таблицы TempAzsTrucks2 (из предыдущего цикла)
        for i in is_variant_sliv_good_list:
            # в созданные ранее словарь добавляем ячейки с нулями
            is_variant_good_list[str(i['variant'])] = {'is_it_92': 0,
                                                       'is_it_95': 0,
                                                       'is_it_50': 0}
        # снова перебираем список словарей
        for i in is_variant_sliv_good_list:
            # если находим определенный вид топлива, и вариант слива относящийся к этой строке таблицы отмечен True,
            # то помечаем го цифрой 2
            # а если нет, то единицей
            if i['fuel_type'] == 92 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': 2,
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 92 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': 1,
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 95 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': 2,
                                                           'is_it_50':  is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 95 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': 1,
                                                           'is_it_50': is_variant_good_list[str(i['variant'])]['is_it_50']}
            if i['fuel_type'] == 50 and i['is_variant_sliv_good'] == 1:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50': 2}
            if i['fuel_type'] == 50 and i['is_variant_sliv_good'] == 0:
                is_variant_good_list[str(i['variant'])] = {'is_it_92': is_variant_good_list[str(i['variant'])]['is_it_92'],
                                                           'is_it_95': is_variant_good_list[str(i['variant'])]['is_it_95'],
                                                           'is_it_50': 1}
        # создаем финальный список для данной функции, который будет записан в таблицу TempAzsTrucks2 в БД
        final_list = list()
        # перебираем список словарей
        for i in is_variant_sliv_good_list:
            # если все виды топлива данного варианта сливаются, то ячейку is_variant_good в таблице записываем True,
            # если же нет, то в ячейку is_variant_good пишем False
            if is_variant_good_list[str(i['variant'])]['is_it_92'] != 1 \
                    and is_variant_good_list[str(i['variant'])]['is_it_95'] != 1 \
                    and is_variant_good_list[str(i['variant'])]['is_it_50'] != 1:
                i['is_variant_good'] = True
                # добавляем получившийся словарь в список
                final_list.append(i)
            else:
                i['is_variant_good'] = False
                # добавляем получившийся словарь в список
                final_list.append(i)

        # записываем данные из списка в базу
        db.engine.execute(TempAzsTrucks2.__table__.insert(), final_list)
        return final_list

    ''' функция отсеивает все варианты из таблицы TempAzsTrucks2 и дает им оценку'''
    def preparation_four():
        final_list = is_it_fit()
        # очищаем таблицу
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks3`")
        db.engine.execute("TRUNCATE TABLE `temp_azs_trucks4`")
        temp_azs_trucks3_list = list()
        fuel_realisation = FuelRealisation.query.all()
        days_stock_dict = dict()

        # перебираем список из предыдущей функции
        for i in final_list:
            # если вариант сливается, бензовоз может заехать на АЗС и бензовоз сливается полностью
            if i['is_it_fit_later'] == True and i['is_it_able_to_enter'] == True and i['is_variant_good'] == True \
                    and i['is_variant_sliv_good'] == True:
                # добавляем словарь в список
                temp_azs_trucks3_list.append(i)
        new_days_stock_dict = dict()
        temp_azs_trucks4_dict = dict()

        for i in temp_azs_trucks3_list:
            temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': [],
                                                        'variant_sliv_95': [],
                                                        'variant_sliv_50': [],
                                                        'volume_92': [],
                                                        'volume_95': [],
                                                        'volume_50': [],
                                                        'azs_id': i['azs_id'],
                                                        'truck_id': i['truck_id']
                                                        }
        for i in temp_azs_trucks3_list:
            variant_sliv_92 = list()
            variant_sliv_95 = list()
            variant_sliv_50 = list()
            volume_92 = list()
            volume_95 = list()
            volume_50 = list()

            if i['fuel_type'] == 92:
                variant_sliv_92.append(i['variant_sliv'])
                volume_92.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_92'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_92'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_92'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'] + variant_sliv_92,
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'],
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'],
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'] + volume_92,
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'],
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'],
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])]['azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])]['truck_id']
                                                                }
            if i['fuel_type'] == 95:
                variant_sliv_95.append(i['variant_sliv'])
                volume_95.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_95'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_95'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_95'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'],
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'] + variant_sliv_95,
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'],
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'],
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'] + volume_95,
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'],
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'truck_id']

                                                                }
            if i['fuel_type'] == 50:
                variant_sliv_50.append(i['variant_sliv'])
                volume_50.append(i['sum_sliv'])
                if i['variant_sliv'] in temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50']:
                    index = temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'].index(i['variant_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_50'].insert(index, temp_azs_trucks4_dict[str(i['variant'])]['volume_50'][index] + i['sum_sliv'])
                    temp_azs_trucks4_dict[str(i['variant'])]['volume_50'].pop(index+1)
                else:
                    temp_azs_trucks4_dict[str(i['variant'])] = {'variant_sliv_92': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_92'],
                                                                'variant_sliv_95': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_95'],
                                                                'variant_sliv_50': temp_azs_trucks4_dict[str(i['variant'])]['variant_sliv_50'] + variant_sliv_50,
                                                                'volume_92': temp_azs_trucks4_dict[str(i['variant'])]['volume_92'],
                                                                'volume_95': temp_azs_trucks4_dict[str(i['variant'])]['volume_95'],
                                                                'volume_50': temp_azs_trucks4_dict[str(i['variant'])]['volume_50'] + volume_50,
                                                                'azs_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'azs_id'],
                                                                'truck_id': temp_azs_trucks4_dict[str(i['variant'])][
                                                                    'truck_id']
                                                                }
        print('Перебираем Таблицу')
        for i in temp_azs_trucks4_dict:
            if i == str(7740):
                for x in temp_azs_trucks4_dict[i]:
                    print(temp_azs_trucks4_dict[str(i)][x])

        print("Перебор закончен")
        azs_trucks_4_list_final = list()
        azs_trucks_4_dict_final = {'variant': 0,
                                   'sum_92': 0,
                                   'sum_95': 0,
                                   'sum_50': 0,
                                   'min_rez1': 0,
                                   'min_rez2': 0,
                                   'min_rez3': 0,
                                   'variant_sliv_50': 0,
                                   'variant_sliv_92': 0,
                                   'variant_sliv_95': 0,
                                   'azs_id': 0,
                                   'truck_id': 0
                                   }

        for i in temp_azs_trucks4_dict:
            variant_sliv_92 = temp_azs_trucks4_dict[i]['variant_sliv_92']
            variant_sliv_95 = temp_azs_trucks4_dict[i]['variant_sliv_95']
            variant_sliv_50 = temp_azs_trucks4_dict[i]['variant_sliv_50']
            volume_92 = temp_azs_trucks4_dict[i]['volume_92']
            volume_95 = temp_azs_trucks4_dict[i]['volume_95']
            volume_50 = temp_azs_trucks4_dict[i]['volume_50']
            if len(variant_sliv_92) != 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) != 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_b, b in enumerate(variant_sliv_95):
                        for index_c, c in enumerate(variant_sliv_50):
                            azs_trucks_4_dict_final = {'variant': i,
                                                       'sum_92': volume_92[index_a],
                                                       'sum_95': volume_95[index_b],
                                                       'sum_50': volume_50[index_c],
                                                       'min_rez1': 0,
                                                       'min_rez2': 0,
                                                       'min_rez3': 0,
                                                       'variant_sliv_50': c,
                                                       'variant_sliv_92': a,
                                                       'variant_sliv_95': b,
                                                       'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                       'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                       }
                            azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

            if len(variant_sliv_92) != 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) == 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_b, b in enumerate(variant_sliv_95):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': volume_92[index_a],
                                                   'sum_95': volume_95[index_b],
                                                   'sum_50': 0,
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': 0,
                                                   'variant_sliv_92': a,
                                                   'variant_sliv_95': b,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

            if len(variant_sliv_92) != 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) != 0:
                for index_a, a in enumerate(variant_sliv_92):
                    for index_c, c in enumerate(variant_sliv_50):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': volume_92[index_a],
                                                   'sum_95': 0,
                                                   'sum_50': volume_50[index_c],
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': c,
                                                   'variant_sliv_92': a,
                                                   'variant_sliv_95': 0,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) != 0:
                for index_b, b in enumerate(variant_sliv_95):
                    for index_c, c in enumerate(variant_sliv_50):
                        azs_trucks_4_dict_final = {'variant': i,
                                                   'sum_92': 0,
                                                   'sum_95': volume_95[index_b],
                                                   'sum_50': volume_50[index_c],
                                                   'min_rez1': 0,
                                                   'min_rez2': 0,
                                                   'min_rez3': 0,
                                                   'variant_sliv_50': c,
                                                   'variant_sliv_92': 0,
                                                   'variant_sliv_95': b,
                                                   'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                                   'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                                   }
                        azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) != 0:
                for index_c, c in enumerate(variant_sliv_50):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': 0,
                                               'sum_95': 0,
                                               'sum_50': volume_50[index_c],
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': c,
                                               'variant_sliv_92': 0,
                                               'variant_sliv_95': 0,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) == 0 and len(variant_sliv_95) != 0 and len(variant_sliv_50) == 0:
                for index_b, b in enumerate(variant_sliv_95):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': 0,
                                               'sum_95': volume_95[index_b],
                                               'sum_50': 0,
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': 0,
                                               'variant_sliv_92': 0,
                                               'variant_sliv_95': b,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)
            if len(variant_sliv_92) != 0 and len(variant_sliv_95) == 0 and len(variant_sliv_50) == 0:
                for index_a, a in enumerate(variant_sliv_92):
                    azs_trucks_4_dict_final = {'variant': i,
                                               'sum_92': volume_92[index_a],
                                               'sum_95': 0,
                                               'sum_50': 0,
                                               'min_rez1': 0,
                                               'min_rez2': 0,
                                               'min_rez3': 0,
                                               'variant_sliv_50': 0,
                                               'variant_sliv_92': a,
                                               'variant_sliv_95': 0,
                                               'azs_id': temp_azs_trucks4_dict[i]['azs_id'],
                                               'truck_id': temp_azs_trucks4_dict[i]['truck_id']
                                               }
                    azs_trucks_4_list_final.append(azs_trucks_4_dict_final)

        db.engine.execute(TempAzsTrucks3.__table__.insert(), temp_azs_trucks3_list)
        return azs_trucks_4_list_final, temp_azs_trucks3_list

    # определение худшего запаса суток среди всех резервуаров АЗС
    def preparation_six():
        # берем таблицу 4
        table_azs_trucks_4, table_azs_trucks_3 = preparation_four()
        table_azs_trucks_4_list = list()
        fuel_realisation = FuelRealisation.query.all()
        days_stock_old_dict = dict()
        for i in fuel_realisation:
            days_stock_old_dict[i.azs_id] = {'days_stock': [],
                                             'tank_id': []}

        for i in fuel_realisation:
            days_stock_min_old_list = [i.days_stock_min]
            tank_ids_list = [i.tank_id]
            days_stock_old_dict[i.azs_id] = {'days_stock': days_stock_old_dict[i.azs_id]['days_stock'] + days_stock_min_old_list,
                                             'tank_id': days_stock_old_dict[i.azs_id]['tank_id'] + tank_ids_list}
        variants_dict = dict()
        for i in table_azs_trucks_3:
            variants_dict[(i['variant'], i['variant_sliv'])] = {'days_stock': [],
                                                                'tank_id': []}
        for i in table_azs_trucks_3:
            days_stock_min_new_list = [i['new_days_stock']]
            tank_ids_list = [i['tank_id']]
            variants_dict[(i['variant'], i['variant_sliv'])] = {'days_stock': variants_dict[(i['variant'], i['variant_sliv'])]['days_stock'] + days_stock_min_new_list,
                                                                'tank_id': variants_dict[(i['variant'], i['variant_sliv'])]['tank_id'] + tank_ids_list
                                                                }
        for row in table_azs_trucks_4:

            variant = row['variant']
            variants_list = list()
            if row['variant_sliv_92']:
                variants_list.append(row['variant_sliv_92'])
            if row['variant_sliv_95']:
                variants_list.append(row['variant_sliv_95'])
            if row['variant_sliv_50']:
                variants_list.append(row['variant_sliv_50'])
            new_days_stock_dict = dict()
            tank_list = days_stock_old_dict[row['azs_id']]['tank_id']
            stock_list = days_stock_old_dict[row['azs_id']]['days_stock']
            for index, tank in enumerate(tank_list):
                new_days_stock_dict[tank] = stock_list[index]
            for variant_sliv in variants_list:
                tank_list_new = variants_dict[(int(row['variant']), variant_sliv)]['tank_id']
                stock_list_new = variants_dict[(int(row['variant']), variant_sliv)]['days_stock']
                for index, tank in enumerate(tank_list_new):
                    new_days_stock_dict[tank] = stock_list_new[index]

            sorted_new_days_stock_dict = sorted(new_days_stock_dict.items(), key=lambda x: x[1])
            temp_azs_trucks_4_dict = {'truck_id': row['truck_id'],
                                      'azs_id': row['azs_id'],
                                      'variant': row['variant'],
                                      'sum_92': row['sum_92'],
                                      'sum_95': row['sum_95'],
                                      'sum_50': row['sum_50'],
                                      'min_rez1': round(sorted_new_days_stock_dict[0][1], 1),
                                      'min_rez2': round(sorted_new_days_stock_dict[1][1], 1),
                                      'min_rez3': round(sorted_new_days_stock_dict[2][1], 1),
                                      'variant_sliv_92': row['variant_sliv_92'],
                                      'variant_sliv_95': row['variant_sliv_95'],
                                      'variant_sliv_50': row['variant_sliv_50']
                                      }
            table_azs_trucks_4_list.append(temp_azs_trucks_4_dict)

        db.engine.execute(TempAzsTrucks4.__table__.insert(), table_azs_trucks_4_list)

    def create_trip():
        work_type = WorkType.query.filter_by(active=True).first_or_404()
        if work_type.id == 2 or work_type.id == 3:
            fuel_type = work_type.fuel_type
            min_days_stock_global = work_type.days_stock_limit
        else:
            fuel_type = 0

        table_azs_trucks_4 = TempAzsTrucks4.query.all()
        priority = Priority.query.all()
        trucks_for_azs_dict = dict()
        azs_trucks_best_days_stock = dict()
        azs_trucks_max_92 = dict()
        azs_trucks_max_95 = dict()
        azs_trucks_max_50 = dict()
        azs_trucks_min_92 = dict()
        azs_trucks_min_95 = dict()
        azs_trucks_min_50 = dict()
        for i in table_azs_trucks_4:
            # словарь для хранения информации о том, какие бензовозы могут отправиться на данную АЗС
            trucks_for_azs_dict[i.azs_id] = {'azs_trucks': [0]}
            # Словарь для первого режима работы
            # Информация о лучщем заполнении для пары АЗС:БЕНЗОВОЗ
            azs_trucks_best_days_stock[str(i.azs_id)+':'+str(i.truck_id)] = {'min_rez1': -1,
                                                                             'min_rez2': -1,
                                                                             'min_rez3': -1,
                                                                             'variant': 0,
                                                                             'variant_sliv_92': 0,
                                                                             'variant_sliv_95': 0,
                                                                             'variant_sliv_50': 0}
            # Словари для второго режима работы (вывоз максимального количества определенного топлива)
            azs_trucks_max_92[str(i.azs_id)+':'+str(i.truck_id)] = {'max_volume_92': -1,
                                                                    'max_volume_95': -1,
                                                                    'max_volume_50': -1,
                                                                    'min_rez1': -1,
                                                                    'variant': 0,
                                                                    'variant_sliv_92': 0,
                                                                    'variant_sliv_95': 0,
                                                                    'variant_sliv_50': 0
                                                                    }

            azs_trucks_max_95[str(i.azs_id)+':'+str(i.truck_id)] = {'max_volume_92': -1,
                                                                    'max_volume_95': -1,
                                                                    'max_volume_50': -1,
                                                                    'min_rez1': -1,
                                                                    'variant': 0,
                                                                    'variant_sliv_92': 0,
                                                                    'variant_sliv_95': 0,
                                                                    'variant_sliv_50': 0
                                                                    }

            azs_trucks_max_50[str(i.azs_id)+':'+str(i.truck_id)] = {'max_volume_50': -1,
                                                                    'min_rez1': -1,
                                                                    'variant': 0,
                                                                    'variant_sliv_92': 0,
                                                                    'variant_sliv_95': 0,
                                                                    'variant_sliv_50': 0
                                                                    }
            # Словари для третьего режима работы (вывоз минимального количества топлива определенного вида)
            azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_92': -1,
                                                                        'min_rez1': -1,
                                                                        'min_rez2': -1,
                                                                        'min_rez3': -1,
                                                                        'variant': 0,
                                                                        'variant_sliv_92': 0,
                                                                        'variant_sliv_95': 0,
                                                                        'variant_sliv_50': 0
                                                                        }

            azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_95': -1,
                                                                        'min_rez1': -1,
                                                                        'min_rez2': -1,
                                                                        'min_rez3': -1,
                                                                        'variant': 0,
                                                                        'variant_sliv_92': 0,
                                                                        'variant_sliv_95': 0,
                                                                        'variant_sliv_50': 0
                                                                        }

            azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_50': -1,
                                                                        'min_rez1': -1,
                                                                        'min_rez2': -1,
                                                                        'min_rez3': -1,
                                                                        'variant': 0,
                                                                        'variant_sliv_92': 0,
                                                                        'variant_sliv_95': 0,
                                                                        'variant_sliv_50': 0
                                                                        }
        # Перебираем таблицу table_azs_truck_4 для заполнения словарей для всех трех режимов работы
        for i in table_azs_trucks_4:
            # заполняем словарь для хранения информации о том, какие бензовозы могут отправиться на данную АЗС
            trucks_list = list()
            trucks_list.append(i.truck_id)
            if i.truck_id not in trucks_for_azs_dict[i.azs_id]['azs_trucks']:
                trucks_for_azs_dict[i.azs_id] = {'azs_trucks': trucks_for_azs_dict[i.azs_id]['azs_trucks'] + trucks_list
                                                 }

            # Заполняем словари информацией о лучщем заполнении для пары АЗС:БЕНЗОВОЗ (для первого режима работы)
            min_rez1 = azs_trucks_best_days_stock[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
            min_rez2 = azs_trucks_best_days_stock[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez2']
            min_rez3 = azs_trucks_best_days_stock[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez3']

            if i.min_rez1 > min_rez1 \
                    or (i.min_rez1 == min_rez1 and i.min_rez2 > min_rez2) \
                    or (i.min_rez1 == min_rez1 and i.min_rez2 == min_rez2 and i.min_rez3 > min_rez3):

                azs_trucks_best_days_stock[str(i.azs_id)+':'+str(i.truck_id)] = {'min_rez1': i.min_rez1,
                                                                                 'min_rez2': i.min_rez2,
                                                                                 'min_rez3': i.min_rez3,
                                                                                 'variant': i.variant,
                                                                                 'variant_sliv_92': i.variant_sliv_92,
                                                                                 'variant_sliv_95': i.variant_sliv_95,
                                                                                 'variant_sliv_50': i.variant_sliv_50}

        if work_type.id == 2:
            if min_days_stock_global == -1:
                for i in table_azs_trucks_4:
                    # Заполняем словари для второго режима работы(вывоз максимального количества топлива определенного вида)
                    min_rez1_92 = azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_95 = azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_50 = azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']

                    max_volume_92 = azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_92']
                    max_volume_95 = azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_95']
                    max_volume_50 = azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_50']

                    if i.min_rez1 > min_rez1_92 or (i.min_rez1 == min_rez1_92 and i.sum_92 > max_volume_92):
                        azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_92': i.sum_92,
                                                                                    'max_volume_95': i.sum_95,
                                                                                    'max_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                    if i.min_rez1 > min_rez1_95 or (i.min_rez1 == min_rez1_95 and i.sum_95 > max_volume_95):
                        azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_95': i.sum_95,
                                                                                    'max_volume_92': i.sum_92,
                                                                                    'max_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                    if i.min_rez1 > min_rez1_50 or (i.min_rez1 == min_rez1_50 and i.sum_50 > max_volume_50):
                        azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
            else:
                for i in table_azs_trucks_4:
                    max_volume_92 = azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_92']
                    max_volume_95 = azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_95']
                    max_volume_50 = azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_50']

                    if i.min_rez1 >= min_days_stock_global and i.sum_92 > max_volume_92:
                        azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_92': i.sum_92,
                                                                                    'max_volume_95': i.sum_95,
                                                                                    'max_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }

                    if (i.min_rez1 >= min_days_stock_global and i.sum_95 > max_volume_95):
                        azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_95': i.sum_95,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }

                    if (i.min_rez1 >= min_days_stock_global and i.sum_50 > max_volume_50):
                        azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                for i in table_azs_trucks_4:
                    min_rez1_92 = azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_95 = azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_50 = azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']

                    max_volume_92 = azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_92']
                    max_volume_95 = azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_95']
                    max_volume_50 = azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['max_volume_50']

                    if azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_92 or (i.min_rez1 == min_rez1_92 and i.sum_92 > max_volume_92):
                            azs_trucks_max_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_92': i.sum_92,
                                                                                        'max_volume_95': i.sum_95,
                                                                                        'max_volume_50': i.sum_50,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
                    if azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_95 or (i.min_rez1 == min_rez1_95 and i.sum_95 > max_volume_95):
                            azs_trucks_max_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_95': i.sum_95,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
                    if azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_50 or (i.min_rez1 == min_rez1_50 and i.sum_50 > max_volume_50):
                            azs_trucks_max_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'max_volume_50': i.sum_50,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
        elif work_type.id == 3:
            if min_days_stock_global == -1:
                for i in table_azs_trucks_4:
                    # Заполняем словари для второго режима работы(вывоз максимального количества топлива определенного вида)
                    min_rez1_92 = azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_95 = azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_50 = azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']

                    min_volume_92 = azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_92']
                    min_volume_95 = azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_95']
                    min_volume_50 = azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_50']

                    if i.min_rez1 > min_rez1_92 or (i.min_rez1 == min_rez1_92 and i.sum_92 < min_volume_92):
                        azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_92': i.sum_92,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                    if i.min_rez1 > min_rez1_95 or (i.min_rez1 == min_rez1_95 and i.sum_95 < min_volume_95):
                        azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_95': i.sum_95,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                    if i.min_rez1 > min_rez1_50 or (i.min_rez1 == min_rez1_50 and i.sum_50 < min_volume_50):
                        azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
            else:
                for i in table_azs_trucks_4:
                    min_volume_92 = azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_92']
                    min_volume_95 = azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_95']
                    min_volume_50 = azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_50']

                    if (i.min_rez1 >= min_days_stock_global and i.sum_92 < min_volume_92):
                        azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_92': i.sum_92,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }

                    if (i.min_rez1 >= min_days_stock_global and i.sum_95 < min_volume_95):
                        azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_95': i.sum_95,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }

                    if (i.min_rez1 >= min_days_stock_global and i.sum_50 < min_volume_50):
                        azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_50': i.sum_50,
                                                                                    'min_rez1': i.min_rez1,
                                                                                    'variant': i.variant,
                                                                                    'variant_sliv_92': i.variant_sliv_92,
                                                                                    'variant_sliv_95': i.variant_sliv_95,
                                                                                    'variant_sliv_50': i.variant_sliv_50
                                                                                    }
                for i in table_azs_trucks_4:
                    min_rez1_92 = azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_95 = azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']
                    min_rez1_50 = azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1']

                    min_volume_92 = azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_92']
                    min_volume_95 = azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_95']
                    min_volume_50 = azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_volume_50']
                    if azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_92 or (i.min_rez1 == min_rez1_92 and i.sum_92 < min_volume_92):
                            azs_trucks_min_92[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_92': i.sum_92,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
                    if azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_95 or (i.min_rez1 == min_rez1_95 and i.sum_95 < min_volume_95):
                            azs_trucks_min_95[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_95': i.sum_95,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
                    if azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)]['min_rez1'] == -1:
                        if i.min_rez1 > min_rez1_50 or (i.min_rez1 == min_rez1_50 and i.sum_50 < min_volume_50):
                            azs_trucks_min_50[str(i.azs_id) + ':' + str(i.truck_id)] = {'min_volume_50': i.sum_50,
                                                                                        'min_rez1': i.min_rez1,
                                                                                        'variant': i.variant,
                                                                                        'variant_sliv_92': i.variant_sliv_92,
                                                                                        'variant_sliv_95': i.variant_sliv_95,
                                                                                        'variant_sliv_50': i.variant_sliv_50
                                                                                        }
        # Заполняем словари для третьего режима работы (вывоз минимального количества топлива определенного вида)

        # АЛГОРИТМ №1 - СЛУЧАНАЯ РАССТАНОВКА С ОГРОМНЫМ КОЛИЧЕСТВОМ ВАРИАНТОВ
        active_trucks = Trucks.query.filter_by(active=True).count()  # получаем количество активных бензовозов
        active_azs = Priority.query.order_by("priority").all()  # получаем список активных АЗС из таблицы Priority
        # с сортировкой по важности (чем меньше число (стобец priority), тем важнее отправить бензовоз на эту АЗС
        choices_dict_work_type_1 = dict()  # храним итоговые варианты расстановки с оценкой каждого для 1 режима работы
        choices_dict_work_type_2 = dict()  # храним итоговые варианты расстановки с оценкой каждого для 2 режима работы
        azs_queue_dict = dict()  # создаем словарь для хранения id АЗС в порядке важности отправки бензовоза на АЗС
        # (нужна для последующего анализа итоговых расстановок)

        for i in priority:  # заполняем словарь
            azs_queue_dict[i.azs_id] = {'queue': i.priority}

        # таймаут для принудительной остановки расстановки бензовозов через
        # указанное количество времени (сейчас минута)
        timeout = time.time() + 20 * 1

        # количество успешных расстановок
        number_of_success_loops = 0
        # вводим переменную на случай, если расстановка бензовозов не удастся.
        # Изначально переменной присвоена 1, что означает неудачную расстановку.
        alarm = 1

        # Главный цикл расстановки бензовозов (количество попыток от 0 до 10 млн)
        for choice in range(0, 100000000):
            # создаем словарь для хранения связки АЗС - бензовозы
            # (словарь для хранения итогового списка азс-бензовоз для каждого варианта расстановки)
            choice_azs_truck_dict = dict()

            # создаем список уже использованных бензовозов для исключения повтора
            # при текущем цикле расстановки
            used_trucks = list()

            # счетчик, равный количеству активных бензовозов
            # (т.е. сколько бензовозов требуется расставить)
            checker = active_trucks
            good = 1  # переменная-триггер, по которой определяем, что расстановка удалась (или нет!)
            for i in active_azs:  # перебираем все активные АЗС
                if i.azs_id in trucks_for_azs_dict:  # если есть хотябы один бензовоз, который можно отправить на АЗС
                    azs_trucks = trucks_for_azs_dict[i.azs_id]['azs_trucks']  # получаем список всех бензовозов,
                    # которые можно отправить на эту АЗС (включая 0 - т.е. АЗС на которую не будет отправлен бензовоз)
                    truck_id = random.choice(azs_trucks)  # функцией RANDOM из списка azs_trucks
                    # выбираем бензовоз для этой АЗС
                    if truck_id in used_trucks and truck_id != 0: # если данный безовоз уже был в данном варианте
                        # расстановки и он не равен 0, то считаем вариант не удачным, и досрочно прерыываем цикл
                        good = 0
                        break
                    # если все хорошо, то
                    else:
                        # добавляем этот бензовоз к списку использованных
                        # в данном варианте бензовозов
                        used_trucks.append(truck_id)

                        # добавляем параметр azs_id-truck_id
                        # в словарь с расстановкой
                        choice_azs_truck_dict[i.azs_id] = {'truck_id': truck_id}
                        # если безовоз не нулевой, то уменьшаем количество бензовозов которые
                        if truck_id != 0:
                            # требуется расставить на 1
                            checker = checker-1
                            # если все бензовозы расставлены (счетчик равен 0)
                    if checker == 0:
                        # то помечаем вариант хорошим и досрочно завершаем цикл
                        good = 1
                        break

            # если все бензовозы расставлены
            if good == 1:
                # то расстановка безовозов удалась (переменная = 0)
                alarm = 0
                # увеличиваем количество успешных расстановок на 1
                number_of_success_loops = number_of_success_loops + 1

                '''**************************************************************************************************'''

                # Оцениваем вариант расстановки на предмет не отправки бензовоза на критичные АЗС

                # переменная для хранения оценки текущей расстановки бензовозов (т.е. чем большее количество
                points = 0
                # критичных АЗС пропущено, тем меньше оценка (расстановка хуже)
                for i in choice_azs_truck_dict:  #
                    if choice_azs_truck_dict[i]['truck_id'] != 0:
                        points = points + (1 / (azs_queue_dict[i]['queue']))*1000
                # округляем оценку до целого числа
                points = int(points)

                '''**************************************************************************************************'''

                # checker = active_trucks  # счетчик, равный количеству активных бензовозов
                # минимальный запас суток среди всех АЗС
                min_days_stock1_work_type_1 = 1234
                # перебираем список расстановки
                for i in choice_azs_truck_dict:
                    if choice_azs_truck_dict[i]['truck_id'] != 0 \
                            and (azs_trucks_best_days_stock[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1'] < min_days_stock1_work_type_1):
                        if min_days_stock1_work_type_1 != 1234:
                            min_days_stock2_work_type_1 = min_days_stock1_work_type_1
                        min_days_stock1_work_type_1 = azs_trucks_best_days_stock[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                    else:
                        min_days_stock1_work_type_1 = 0
                        min_days_stock2_work_type_1 = 0
                    # checker = checker - 1
                    # if checker == 0:
                    # break


                '''**************************************************************************************************'''
                # собираем все оцененные варианты расстановки в словарь
                choices_dict_work_type_1[number_of_success_loops] = {'variants': choice_azs_truck_dict,
                                                                     'points': points,
                                                                     'days_stock_min1': min_days_stock1_work_type_1,
                                                                     'days_stock_min2': min_days_stock2_work_type_1
                                                                     }

                '''**************************************************************************************************'''

                # оценка количества вывозимого топлива при текущей расстановке
                min_days_stock1_work_type_2 = 1000
                sum_max_volume_92 = 0
                sum_max_volume_95 = 0
                sum_max_volume_50 = 0

                for i in choice_azs_truck_dict:
                    if choice_azs_truck_dict[i]['truck_id'] != 0:
                        key = str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])
                        # для 92 топлива
                        if fuel_type == 92:
                            sum_max_volume_92 = sum_max_volume_92 + azs_trucks_max_92[key]['max_volume_92']
                            sum_max_volume_95 = sum_max_volume_95 + azs_trucks_max_92[key]['max_volume_95']
                            sum_max_volume_50 = sum_max_volume_50 + azs_trucks_max_92[key]['max_volume_50']

                            if (azs_trucks_max_92[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']) \
                                    < min_days_stock1_work_type_2:
                                min_days_stock1_work_type_2 = azs_trucks_max_92[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                        # для 95 топлива
                        elif fuel_type == 95:
                            sum_max_volume_92 = sum_max_volume_92 + azs_trucks_max_95[key]['max_volume_92']
                            sum_max_volume_95 = sum_max_volume_95 + azs_trucks_max_95[key]['max_volume_95']
                            sum_max_volume_50 = sum_max_volume_50 + azs_trucks_max_95[key]['max_volume_50']

                            if (azs_trucks_max_95[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                                    < min_days_stock1_work_type_2):
                                min_days_stock1_work_type_2 = azs_trucks_max_95[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                        # для 50 топлива
                        elif fuel_type == 50:
                            sum_max_volume_92 = sum_max_volume_92 + azs_trucks_max_50[key]['max_volume_92']
                            sum_max_volume_95 = sum_max_volume_95 + azs_trucks_max_50[key]['max_volume_95']
                            sum_max_volume_50 = sum_max_volume_50 + azs_trucks_max_50[key]['max_volume_50']

                            if (azs_trucks_max_50[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                                    < min_days_stock1_work_type_2):
                                min_days_stock1_work_type_2 = azs_trucks_max_50[str(i) + ':' + str(choice_azs_truck_dict[i]['truck_id'])]['min_rez1']
                    else:
                        min_days_stock1_work_type_2 = 0

                '''**************************************************************************************************'''

                # собираем все оцененные варианты расстановки в словарь для второго режима работы

                choices_dict_work_type_2[number_of_success_loops] = {'variants': choice_azs_truck_dict,
                                                                     'points': points,
                                                                     'days_stock_min1': min_days_stock1_work_type_2,
                                                                     'max_volume_92': sum_max_volume_92,
                                                                     'max_volume_95': sum_max_volume_95,
                                                                     'max_volume_50': sum_max_volume_50,
                                                                     }
            # если время выполнения превышает значение переменной timeout объявленной выше
            if time.time() > timeout:
                # то цикл принудительно прерывается
                break

        if alarm == 1:
            print('Расстановка не удалась')
        else:
            print('Расстановка успешно завершена')
            print(number_of_success_loops)

            # сортируем полученные результаты по трем параметрам
            # На выходе получим отсортированный список ключей словаря choices_dict
            if work_type.id == 1:
                sort_choices_dict = sorted(choices_dict_work_type_1,
                                           key=lambda k: (choices_dict_work_type_1[k]['points'],
                                                          choices_dict_work_type_1[k]['days_stock_min1'],
                                                          choices_dict_work_type_1[k]['days_stock_min2']))
            elif work_type.id == 2:
                if fuel_type == 92:
                    sort_choices_dict = sorted(choices_dict_work_type_2,
                                               key=lambda k: (choices_dict_work_type_2[k]['points'],
                                                              choices_dict_work_type_2[k]['max_volume_92'],
                                                              choices_dict_work_type_2[k]['days_stock_min1']
                                                              ))
                elif fuel_type == 95:
                    sort_choices_dict = sorted(choices_dict_work_type_2,
                                               key=lambda k: (choices_dict_work_type_2[k]['points'],
                                                              choices_dict_work_type_2[k]['max_volume_95'],
                                                              choices_dict_work_type_2[k]['days_stock_min1']
                                                              ))
                elif fuel_type == 50:
                    sort_choices_dict = sorted(choices_dict_work_type_2,
                                               key=lambda k: (choices_dict_work_type_2[k]['points'],
                                                              choices_dict_work_type_2[k]['max_volume_50'],
                                                              choices_dict_work_type_2[k]['days_stock_min1']
                                                              ))

            elif work_type.id == 3:
                print('Режим работы № 3')
            else:
                alarm = 1
            if work_type.id == 1:
                # создаем список, в котором будем хранить лучшие варианты расстановки
                best_choices = list()
                # берем айди предыдущего варианта расстановки
                trips_last = Trips.query.order_by(desc("calculate_id")).first()

                if not trips_last:
                    previous_variant_id = 0
                else:
                    previous_variant_id = trips_last.calculate_id

                # перебираем отсортированные от худшего к лучшему варианты расстановки
                for i in sort_choices_dict:
                    # каждый вариант добавляем в список
                    best_choices.append(i)
                    # сокращаем список до 1
                    best_choices = sort_choices_dict[-1:]
                # перебираем список из 10 лучших вариантов
                for i in best_choices:
                    trips = Trips(trip_number=1, date=datetime.today(), work_type_id=work_type.id,
                                  calculate_id=previous_variant_id + 1)
                    db.session.add(trips)
                    print(i, choices_dict_work_type_1[i]['points'], choices_dict_work_type_1[i]['days_stock_min1'],
                          choices_dict_work_type_1[i]['days_stock_min2'])

                    for z in trucks_for_azs_dict:
                        trucks_for_azs = TrucksForAzs(azs_id=z,
                                                      number_of_trucks=len(trucks_for_azs_dict[z]['azs_trucks']) - 1,
                                                      calculate_id=previous_variant_id + 1)

                        db.session.add(trucks_for_azs)

                    for x in choices_dict_work_type_1[i]['variants']:
                        if choices_dict_work_type_1[i]['variants'][x]['truck_id'] != 0:
                            variant_sliv_92 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['variant_sliv_92']
                            variant = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['variant']
                            truck_id = choices_dict_work_type_1[i]['variants'][x]['truck_id']
                            azs_id = x
                            variant_sliv_95 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['variant_sliv_95']
                            variant_sliv_50 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['variant_sliv_50']
                            min_rez1 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['min_rez1']
                            min_rez2 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['min_rez2']
                            min_rez3 = azs_trucks_best_days_stock[str(x) + ':' + str(choices_dict_work_type_1[i]['variants'][x]['truck_id'])]['min_rez3']
                            query_variant = TempAzsTrucks4.query.filter_by(azs_id=azs_id, truck_id=truck_id, variant=variant, variant_sliv_92=variant_sliv_92).first()
                            calculate_id = previous_variant_id + 1
                            result = Result(azs_id=azs_id, truck_id=truck_id,
                                            variant=variant,
                                            variant_sliv_92=variant_sliv_92,
                                            variant_sliv_95=variant_sliv_95,
                                            variant_sliv_50=variant_sliv_50,
                                            min_rez1=min_rez1,
                                            min_rez2=min_rez2,
                                            min_rez3=min_rez3,
                                            volume_92=query_variant.sum_92,
                                            volume_95=query_variant.sum_95,
                                            volume_50=query_variant.sum_50,
                                            calculate_id=calculate_id)
                            db.session.add(result)

                            print("АЗС:", azs_id,
                                  "Бензовоз:", truck_id,
                                  "Вариант налива:", variant,
                                  "Вариант слива 92:", variant_sliv_92,
                                  "Вариант слива 95:", variant_sliv_95,
                                  "Вариант слива 50:", variant_sliv_50)

                db.session.commit()

            elif work_type.id == 2:
                # создаем список, в котором будем хранить лучшие варианты расстановки
                best_choices = list()
                # перебираем отсортированные от худшего к лучшему варианты расстановки
                for i in sort_choices_dict:
                    # каждый вариант добавляем в список
                    best_choices.append(i)
                    # сокращаем список до 1
                    best_choices = sort_choices_dict[-1:]

                # берем айди предыдущего варианта расстановки
                trips_last = Trips.query.order_by(desc("calculate_id")).first()
                previous_variant_id = trips_last.calculate_id
                if not trips_last:
                    previous_variant_id = 0
                else:
                    previous_variant_id = trips_last.calculate_id
                results = Result.query.all()
                # перебираем список из 10 лучших вариантов
                for i in best_choices:
                    trips = Trips(trip_number=1, date=datetime.today(), work_type_id=work_type.id,
                                  calculate_id=previous_variant_id + 1)
                    '''print(i, 'points', choices_dict_work_type_2[i]['points'], 'days_stock1',
                                 choices_dict_work_type_2[i]['days_stock_min1'],
                                'max_volume_92', choices_dict_work_type_2[i]['max_volume_92'],
                                'max_volume_95', choices_dict_work_type_2[i]['max_volume_95'],
                                'max_volume_50', choices_dict_work_type_2[i]['max_volume_50'],)'''
                    for x in choices_dict_work_type_2[i]['variants']:
                        if choices_dict_work_type_1[i]['variants'][x]['truck_id'] != 0:
                            if fuel_type == 92:
                                key = str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])
                                print("АЗС:", x, "бензовоз:",
                                      choices_dict_work_type_2[i]['variants'][x]['truck_id'],
                                      'variants:', azs_trucks_max_92[key ]['variant'],
                                      'sliv_92:', azs_trucks_max_92[key]['variant_sliv_92'],
                                      'sliv_95:', azs_trucks_max_92[key]['variant_sliv_95'],
                                      'sliv_50:', azs_trucks_max_92[key]['variant_sliv_50'],
                                      'max_volume_92:', azs_trucks_max_92[key]['max_volume_92'],
                                      'max_volume_95:', azs_trucks_max_92[key]['max_volume_95'],
                                      'max_volume_50:', azs_trucks_max_92[key]['max_volume_50'],
                                      )
                            elif fuel_type == 95:
                                print("АЗС:", x, "бензовоз:",
                                      choices_dict_work_type_2[i]['variants'][x]['truck_id'],
                                      'variants:', azs_trucks_max_95[str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant'],
                                      'sliv_92:', azs_trucks_max_95[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_92'],
                                      'sliv_95:', azs_trucks_max_95[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_95'],
                                      'sliv_50:', azs_trucks_max_95[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_50'])
                            elif fuel_type == 50:
                                print("АЗС:", x, "бензовоз:",
                                      choices_dict_work_type_2[i]['variants'][x]['truck_id'],
                                      'variants:', azs_trucks_max_50[str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant'],
                                      'sliv_92:', azs_trucks_max_50[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_92'],
                                      'sliv_95:', azs_trucks_max_50[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_95'],
                                      'sliv_50:', azs_trucks_max_50[
                                          str(x) + ':' + str(choices_dict_work_type_2[i]['variants'][x]['truck_id'])]['variant_sliv_50'])
            '''
            for i in best_choice:
                print(i, best_choice[i]['truck_id'], "==", trucks_for_azs_dict[i]['azs_trucks'])
            '''

    error, tanks = check()
    if error > 10:
        print("Number of error: " + str(error) + ", wrong tanks " + " ".join(str(x) for x in tanks))
        return redirect(url_for('main.index'))
    else:
        start_time = time.time()
        # preparation_six()
        # time.sleep(10)
        create_trip()
        flash('Время выполнения %s' % (time.time() - start_time))
        return redirect(url_for('main.trip_creation'))


@bp.route('/start_trip', methods=['POST', 'GET'])
@login_required
def start_trip():
    if current_user.get_task_in_progress('prepare_tables'):
        flash(_('Пересчет таблиц уже выполняется данных уже выполняется!'))
    else:
        current_user.launch_task('prepare_tables', _('Начат пересчет подготовительных таблиц...'))
        db.session.commit()
    return redirect(url_for('main.index'))


@bp.route('/trip_creation', methods=['POST', 'GET'])
@login_required
def trip_creation():
    datetime = date.today()
    print(datetime)
    trips = Trips.query.order_by(desc("calculate_id")).first()
    if trips.date.strftime("%d.%m.%Y") == datetime.today().strftime("%d.%m.%Y"):
        trips = True
    else:
        trips = False
    return render_template('trip_creation.html', title='Отправка бензовозов', trip_creation=True, trips=trips)


@bp.route('/trips.json', methods=['POST', 'GET'])
@login_required
def trips_json():
    rows = list()
    priority = Priority.query.all()
    trips = Trips.query.order_by(desc("calculate_id")).first()
    for i in priority:
        azs = AzsList.query.filter_by(id=i.azs_id).first()
        result = Result.query.filter_by(calculate_id=trips.calculate_id, azs_id=i.azs_id).first()
        trucks_for_azs = TrucksForAzs.query.filter_by(azs_id=i.azs_id, calculate_id=trips.calculate_id).first()
        if result:
            trucks = Trucks.query.filter_by(id=result.truck_id).first()
            reg_number = trucks.reg_number
            new_day_stock = result.min_rez1
        else:
            reg_number = "-"
            new_day_stock = "-"
        if trucks_for_azs:
            number_of_trucks = trucks_for_azs.number_of_trucks
        else:
            number_of_trucks = "0"
        if number_of_trucks == "0":
            reg_number = "Нет вариантов"
        row = {'priority': i.priority,
               'azs_number': "АЗС № " + str(azs.number),
               'day_stock': i.day_stock,
               'first_trip': reg_number,
               'second_trip': "-",
               'new_day_stock': new_day_stock,
               'number_of_trucks': number_of_trucks,
               'datetime': trips.date.strftime("%d.%m.%Y"),
               }
        rows.append(row)
    return Response(json.dumps(rows), mimetype='application/json')
