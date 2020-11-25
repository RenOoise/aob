from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from werkzeug.urls import url_parse
from app import db
from app.reports import bp
from app.models import User


@bp.route('/reports/index', methods=['GET', 'POST'])
@login_required
def index():
    print("Разработка отчета")
    return render_template('reports/index.html', title="Отчеты", reports_active=True)
