from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, send_file
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from guess_language import guess_language
from app import db
from app.main.forms import EditProfileForm, PostForm, SearchForm, MessageForm, ManualInputForm
from app.models import User, Post, Message, Notification, FuelResidue, AzsList, Tanks, FuelRealisation, Priority, \
    PriorityList, ManualInfo, Trucks, TruckTanks, TruckFalse, Trip, TempAzsTrucks, TempAzsTrucks2, WorkType
from app.translate import translate
from app.main import bp
import pandas as pd
from StyleFrame import StyleFrame, Styler, utils


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
    priority = Priority.query.order_by('priority').all()
    azs_list = list()
    for i in priority:
        azs_dict = {}
        if i.day_stock <= 2:
            azs = AzsList.query.filter_by(id=i.azs_id).first_or_404()
            tank = Tanks.query.filter_by(id=i.tank_id).first_or_404()
            azs_dict = {'number': azs.number,
                        'tank': tank.tank_number,
                        'day_stock': i.day_stock}
            azs_list.append(azs_dict)
    return render_template('index.html', title='Главная', azs_list=azs_list, index=True)


@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title=_('Explore'),
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


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


@bp.route('/download_tanks_info')
@login_required
def download_tanks_info():
    if current_user.get_task_in_progress('download_tanks_info'):
        flash(_('Выгрузка данных уже выполняется!'))
    else:
        current_user.launch_task('download_tanks_info', _('Выгружаю данные по остаткам топлива в резервуарах...'))
        db.session.commit()
    return redirect(url_for('main.online'))


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


@bp.route('/export_to_xlsx/<datetime>')
@login_required
def export_to_xlsx(datetime):
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


@bp.route('/online', methods=['POST', 'GET'])
@login_required
def online():
    azs_list = AzsList.query.order_by('number').all()
    online = FuelResidue.query.outerjoin(AzsList).outerjoin(Tanks).order_by(AzsList.number).all()
    tanks_list = Tanks.    query.all()
    return render_template('online.html', title='Online остатки', online_active=True,
                           online=online, azs_list=azs_list, tanks_list=tanks_list, datetime=datetime.now().strftime("%Y-%m-%d-%H-%M"))


@bp.route('/page/azs/id<id>', methods=['POST', 'GET'])
@login_required
def page_azs(id):
    azs_list = AzsList.query.filter_by(id=id).first()
    tanks_list = Tanks.query.filter_by(azs_id=id).all()
    online = FuelResidue.query.outerjoin(Tanks).order_by(Tanks.tank_number).all()
    return render_template('page_azs.html', title='АЗС № ' + str(azs_list.number), page_azs_active=True,
                           online=online, azs_list=azs_list, tanks_list=tanks_list)


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
                           realisation=realisation, azs_list=azs_list, tanks_list=tanks_list)


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


@bp.route('/start', methods=['POST', 'GET'])
@login_required
def start():
    def check():
        errors = 0
        azs_list = AzsList.query.all()
        for azs in azs_list:
            if azs.active:
                tanks_list = Tanks.query.filter_by(azs_id=azs.id).all()
                for tank in tanks_list:
                    if tank.active:
                        residue = FuelResidue.query.filter_by(tank_id=tank.id).first()
                        realisation = FuelRealisation.query.filter_by(tank_id=tank.id).first()
                        if residue.fuel_volume is None or residue.fuel_volume is 0:
                            print('   Резервуар №' + str(tank.tank_number) + ' не содержит данных об остатках! ')
                            errors = errors + 1
                        if realisation.fuel_realisation_1_days is None or realisation.fuel_realisation_1_days is 0:
                            print('   Резервуар №' + str(tank.tank_number) + ' не содержит данных о реализации! ')
                            errors = errors + 1
                        priority_list = PriorityList.query.all()
                        for priority in priority_list:
                            if priority.day_stock_from <= realisation.days_stock_min <= priority.day_stock_to:
                                this_priority = PriorityList.query.filter_by(priority=priority.priority).first_or_404()
                                if not this_priority.id:
                                    errors = errors + 1
                                    print('   Резервуар №' + str(tank.tank_number) +
                                          ' не попадает в диапазон приоритетов!!!')
        return errors

    def temp_tank(tank, fuel, azs):
        temp_truck_azs = dict()
        temp_truck_azs['azs_id'] = azs
        temp_truck_azs['capacity'] = tank.capacity
        temp_truck_azs['truck_id'] = tank.truck_id
        temp_truck_azs['truck_tank_id'] = tank.id
        temp_truck_azs['fuel_type'] = fuel
        return temp_truck_azs

    def preparation():
        truck_list = Trucks.query.filter_by(active=True).all()
        azs_list = AzsList.query.filter_by(active=True).all()
        print('started')
        temp_tanks_list = list()
        temp_tanks_list.clear()
        count_variant = 1
        for azs in azs_list:
            for truck in truck_list:
                truck_tanks_list = TruckTanks.query.filter_by(truck_id=truck.id).all()
                truck_tanks_count = TruckTanks.query.filter_by(truck_id=truck.id).count()
                print(truck.id, truck_tanks_count)
                for tank in truck_tanks_list:
                    if truck_tanks_count == 1:
                        for a in range(1, 4):
                            if a is 1:
                                temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                            elif a is 2:
                                temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                            elif a is 3:
                                temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                            count_variant = count_variant + 1
                    elif truck_tanks_count == 2:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                if a is 1:
                                    temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                elif a is 2:
                                    temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                elif a is 3:
                                    temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                if b is 1:
                                    temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                elif b is 2:
                                    temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                elif b is 3:
                                    temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                count_variant = count_variant + 1
                    elif truck_tanks_count == 3:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    if a is 1:
                                        temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                    elif a is 2:
                                        temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                    elif a is 3:
                                        temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                    if b is 1:
                                        temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                    elif b is 2:
                                        temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                    elif b is 3:
                                        temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                    if c is 1:
                                        temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                    elif c is 2:
                                        temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                    elif c is 3:
                                        temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                    count_variant = count_variant + 1

                    elif truck_tanks_count == 4:
                        for a in range(1, 4):
                            for b in range(1, 4):
                                for c in range(1, 4):
                                    for d in range(1, 4):
                                        if a is 1:
                                            temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                        elif a is 2:
                                            temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                        elif a is 3:
                                            temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                        if b is 1:
                                            temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                        elif b is 2:
                                            temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                        elif b is 3:
                                            temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                        if c is 1:
                                            temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                        elif c is 2:
                                            temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                        elif c is 3:
                                            temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                        if d is 1:
                                            temp_tanks_list.append(temp_tank(tank, '92', azs.id))
                                        elif d is 2:
                                            temp_tanks_list.append(temp_tank(tank, '95', azs.id))
                                        elif d is 3:
                                            temp_tanks_list.append(temp_tank(tank, '50', azs.id))
                                        count_variant = count_variant + 1

        for i in temp_tanks_list:
            sql = TempAzsTrucks(azs_id=i['azs_id'], truck_id=i['truck_id'], truck_tank_id=i['truck_tank_id'],
                                fuel_type=i['fuel_type'], capacity=i['capacity'])
            db.session.add(sql)
            db.session.commit()
    if check() > 0:
        return redirect(url_for('main.manual_input'))
    else:
        preparation()
        return redirect(url_for('main.index'))
